"""SQLite 连接、迁移和事务。"""

from contextlib import contextmanager, nullcontext
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from models.study import normalized_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    duration INTEGER NOT NULL,
    private INTEGER NOT NULL,
    source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
    updated_at REAL NOT NULL,
    UNIQUE(platform, external_id)
);
CREATE TABLE IF NOT EXISTS video_groups (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS video_preferences (
    video_id TEXT PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
    custom_title TEXT,
    group_id TEXT REFERENCES video_groups(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS video_deletions (
    identity_digest TEXT PRIMARY KEY,
    deleted_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    digest TEXT NOT NULL,
    segments TEXT NOT NULL,
    analysis TEXT NOT NULL,
    UNIQUE(video_id, digest)
);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    text TEXT NOT NULL,
    UNIQUE(source_id, position)
);
CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS membership (
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY(course_id, video_id)
);
CREATE TABLE IF NOT EXISTS wiki_pages (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    aliases TEXT NOT NULL,
    edited INTEGER NOT NULL DEFAULT 0,
    UNIQUE(course_id, normalized_title)
);
CREATE TABLE IF NOT EXISTS wiki_claims (
    id TEXT PRIMARY KEY,
    page_id TEXT NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    explanation TEXT NOT NULL,
    quote TEXT NOT NULL,
    UNIQUE(page_id, chunk_id, quote)
);
CREATE TABLE IF NOT EXISTS wiki_links (
    page_id TEXT NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    related_id TEXT NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    provenance TEXT NOT NULL,
    PRIMARY KEY(page_id, related_id, provenance),
    CHECK(page_id <> related_id)
);
CREATE TABLE IF NOT EXISTS wiki_publications (
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    PRIMARY KEY(course_id, video_id)
);
CREATE TABLE IF NOT EXISTS wiki_link_declines (
    page_id TEXT NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    related_id TEXT NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    PRIMARY KEY(page_id, related_id)
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    scope_id TEXT,
    scope_label TEXT NOT NULL,
    title TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    citations TEXT NOT NULL,
    recalled TEXT NOT NULL,
    invalidated INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turn_sources (
    turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    PRIMARY KEY(turn_id, source_id)
);
CREATE TABLE IF NOT EXISTS turn_dependencies (
    turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    prior_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    PRIMARY KEY(turn_id, prior_id)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    state TEXT NOT NULL,
    phase TEXT NOT NULL,
    label TEXT NOT NULL,
    payload TEXT NOT NULL,
    checkpoint TEXT,
    result TEXT,
    detail TEXT,
    code TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS search_docs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    entity TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB,
    UNIQUE(kind, entity)
);
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    text, content='search_docs', content_rowid='id', tokenize='trigram'
);
CREATE TRIGGER IF NOT EXISTS search_insert AFTER INSERT ON search_docs BEGIN
    INSERT INTO search_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS search_delete AFTER DELETE ON search_docs BEGIN
    INSERT INTO search_fts(search_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS search_update AFTER UPDATE OF text ON search_docs BEGIN
    INSERT INTO search_fts(search_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO search_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunk_search_cleanup AFTER DELETE ON chunks BEGIN
    DELETE FROM search_docs WHERE kind = 'chunk' AND entity = old.id;
END;
CREATE TRIGGER IF NOT EXISTS video_search_cleanup AFTER DELETE ON videos BEGIN
    DELETE FROM search_docs WHERE kind = 'video' AND entity = old.id;
END;
CREATE TRIGGER IF NOT EXISTS wiki_search_cleanup AFTER DELETE ON wiki_pages BEGIN
    DELETE FROM search_docs WHERE kind = 'wiki' AND entity = old.id;
END;
CREATE TRIGGER IF NOT EXISTS turn_search_cleanup AFTER DELETE ON turns BEGIN
    DELETE FROM search_docs WHERE kind = 'history' AND entity = old.id;
END;
CREATE INDEX IF NOT EXISTS membership_video ON membership(video_id);
CREATE INDEX IF NOT EXISTS video_preferences_group ON video_preferences(group_id);
CREATE INDEX IF NOT EXISTS wiki_claims_chunk ON wiki_claims(chunk_id);
CREATE INDEX IF NOT EXISTS turns_conversation ON turns(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS turn_sources_source ON turn_sources(source_id);
CREATE INDEX IF NOT EXISTS turn_dependencies_prior ON turn_dependencies(prior_id);
CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state, kind, created_at);
"""


class StudyProblem(Exception):
    def __init__(self, detail: str, status: int = 400, code: str = "study_error"):
        super().__init__(detail)
        self.detail = detail
        self.status = status
        self.code = code


class StudyDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.write_lock = RLock()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.write_lock:
            connection = self.connect()
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > 1:
                    raise RuntimeError("本地资料库版本高于当前程序支持的版本")
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(f"BEGIN IMMEDIATE;\n{SCHEMA}\nPRAGMA user_version = 1;\nCOMMIT;")
            finally:
                connection.close()
            self.path.chmod(0o600)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def transaction(self, *, write=False):
        with self.write_lock if write else nullcontext():
            connection = self.connect()
            try:
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()


def new_id() -> str:
    return uuid4().hex


def pack(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def index_document(connection, kind: str, entity: str, text: str):
    connection.execute(
        """INSERT INTO search_docs(kind, entity, text) VALUES (?, ?, ?)
           ON CONFLICT(kind, entity) DO UPDATE SET text=excluded.text, embedding=NULL
           WHERE search_docs.text <> excluded.text""",
        (kind, entity, normalized_text(text)),
    )


def require_row(row, detail: str):
    if row is None:
        raise StudyProblem(detail, 404, "not_found")
    return row
