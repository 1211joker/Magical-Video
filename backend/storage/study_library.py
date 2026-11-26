"""归档视频、字幕版本和课程成员的查询及写入。"""

from hashlib import sha256
import json
import time

from models.study import normalized_text
from storage.study_db import StudyProblem, index_document, new_id, pack, require_row

VIDEO_PREFERENCES = "LEFT JOIN video_preferences vp ON vp.video_id=v.id"
VIDEO_TITLE = "COALESCE(vp.custom_title, v.title)"
VIDEO_FIELDS = (
    f"v.id, {VIDEO_TITLE} AS title, v.url, v.platform, v.duration, v.private, v.source_id, v.updated_at, vp.group_id"
)


def index_video(connection, video_id, title, analysis):
    key_points = " ".join(item["point"] for item in analysis.get("key_points", [])[:8])
    index_document(connection, "video", video_id, f'{title} {analysis.get("overview", "")} {key_points}')


def archive_video(connection, video, segments, chunks, analysis):
    """复用同一字幕版本，并以一次事务切换当前版本。"""
    existing = connection.execute(
        f"""SELECT v.id, vp.custom_title FROM videos v {VIDEO_PREFERENCES}
            WHERE v.platform=? AND v.external_id=?""",
        (video["platform"], video["external_id"]),
    ).fetchone()
    video_id = existing["id"] if existing else new_id()
    connection.execute(
        """INSERT INTO videos(id, platform, external_id, url, title, duration, private, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET title=excluded.title, url=excluded.url,
               duration=excluded.duration, private=max(videos.private, excluded.private),
               updated_at=excluded.updated_at""",
        (video_id, video["platform"], video["external_id"], video["url"], video["title"],
         video["duration"], video["private"], time.time()),
    )
    serialized = pack(segments)
    digest = sha256(serialized.encode("utf-8")).hexdigest()
    source = connection.execute(
        "SELECT id FROM sources WHERE video_id=? AND digest=?", (video_id, digest),
    ).fetchone()
    source_id = source["id"] if source else new_id()
    if source:
        connection.execute("UPDATE sources SET analysis=? WHERE id=?", (pack(analysis), source_id))
    else:
        connection.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?)",
            (source_id, video_id, digest, serialized, pack(analysis)),
        )
        for position, chunk in enumerate(chunks):
            chunk_id = new_id()
            connection.execute(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                (chunk_id, source_id, position, chunk["start_time"], chunk["end_time"], chunk["text"]),
            )
            index_document(connection, "chunk", chunk_id, chunk["text"])
    connection.execute("UPDATE videos SET source_id=? WHERE id=?", (source_id, video_id))
    custom_title = existing["custom_title"] if existing else None
    index_video(connection, video_id, custom_title or video["title"], analysis)
    return video_id, source_id


def list_library(connection):
    videos = [dict(row) for row in connection.execute(
        f"SELECT {VIDEO_FIELDS} FROM videos v {VIDEO_PREFERENCES} ORDER BY v.updated_at DESC, v.id"
    )]
    courses = [dict(row) for row in connection.execute(
        """SELECT c.id, c.title, COUNT(m.video_id) AS video_count FROM courses c
           LEFT JOIN membership m ON m.course_id=c.id GROUP BY c.id ORDER BY c.created_at DESC, c.id"""
    )]
    groups = [dict(row) for row in connection.execute(
        """SELECT g.id, g.title, COUNT(p.video_id) AS video_count FROM video_groups g
           LEFT JOIN video_preferences p ON p.group_id=g.id
           GROUP BY g.id ORDER BY g.created_at, g.id"""
    )]
    memberships = {video["id"]: [] for video in videos}
    for row in connection.execute(
        "SELECT m.video_id, c.id, c.title FROM membership m JOIN courses c ON c.id=m.course_id ORDER BY c.title"
    ):
        memberships[row["video_id"]].append({"id": row["id"], "title": row["title"]})
    for video in videos:
        video["courses"] = memberships[video["id"]]
    return {"videos": videos, "courses": courses, "groups": groups}


def video_row(connection, video_id):
    return require_row(
        connection.execute(
            f"SELECT {VIDEO_FIELDS} FROM videos v {VIDEO_PREFERENCES} WHERE v.id=?", (video_id,),
        ).fetchone(),
        "视频已移出资料库",
    )


def video_detail(connection, video_id, source_id=None):
    video = dict(video_row(connection, video_id))
    video["source_id"] = source_id or video["source_id"]
    source = require_row(connection.execute(
        "SELECT segments, analysis FROM sources WHERE id=? AND video_id=?",
        (video["source_id"], video_id),
    ).fetchone(), "该字幕版本已删除")
    video["analysis"] = json.loads(source["analysis"])
    video["subtitle_segments"] = json.loads(source["segments"])
    return video


def source_provider(connection, source_id):
    source = connection.execute(
        "SELECT json_extract(analysis, '$.provider') AS provider FROM sources WHERE id=?", (source_id,),
    ).fetchone()
    return source["provider"] if source else None


def _identity_digest(video):
    return sha256(pack([video["platform"], video["external_id"]]).encode()).hexdigest()


def delete_video(connection, video):
    # 在拿到短链指向之前，后台任务无法按视频标识直接定位。
    connection.execute(
        """INSERT INTO video_deletions VALUES (?, ?)
           ON CONFLICT(identity_digest) DO UPDATE SET deleted_at=excluded.deleted_at""",
        (_identity_digest(video), time.time()),
    )
    connection.execute("DELETE FROM videos WHERE id=?", (video["id"],))


def deleted_after_submission(connection, video, submitted_at):
    return connection.execute(
        "SELECT 1 FROM video_deletions WHERE identity_digest=? AND deleted_at>=?",
        (_identity_digest(video), submitted_at),
    ).fetchone() is not None


def update_video(connection, video_id, group_id, title):
    video = video_row(connection, video_id)
    if group_id is not None:
        group_row(connection, group_id)
    connection.execute(
        """INSERT INTO video_preferences(video_id, custom_title, group_id) VALUES (?, ?, ?)
           ON CONFLICT(video_id) DO UPDATE SET
               custom_title=COALESCE(excluded.custom_title, video_preferences.custom_title),
               group_id=excluded.group_id""",
        (video_id, title, group_id),
    )
    if title is not None:
        source = connection.execute("SELECT analysis FROM sources WHERE id=?", (video["source_id"],)).fetchone()
        index_video(connection, video_id, title, json.loads(source["analysis"]) if source else {})


def group_row(connection, group_id):
    return require_row(
        connection.execute("SELECT id FROM video_groups WHERE id=?", (group_id,)).fetchone(),
        "分组已删除，请刷新后再试",
    )


def save_group(connection, title, group_id=None):
    normalized = normalized_text(title)
    existing = connection.execute("SELECT id FROM video_groups WHERE normalized_title=?", (normalized,)).fetchone()
    if existing and existing["id"] != group_id:
        raise StudyProblem("已有同名分组，请换一个名称", 409, "group_exists")
    if group_id is None:
        group_id = new_id()
        connection.execute(
            "INSERT INTO video_groups(id, title, normalized_title, created_at) VALUES (?, ?, ?, ?)",
            (group_id, title, normalized, time.time()),
        )
    else:
        group_row(connection, group_id)
        connection.execute(
            "UPDATE video_groups SET title=?, normalized_title=? WHERE id=?", (title, normalized, group_id),
        )
    return {"id": group_id, "title": title}


def delete_group(connection, group_id):
    group_row(connection, group_id)
    connection.execute("DELETE FROM video_groups WHERE id=?", (group_id,))


def course_row(connection, course_id):
    return require_row(
        connection.execute("SELECT id, title FROM courses WHERE id=?", (course_id,)).fetchone(),
        "课程已删除",
    )


def course_members(connection, course_id):
    course_row(connection, course_id)
    return [dict(row) for row in connection.execute(
        f"""SELECT {VIDEO_FIELDS}, p.source_id AS published_source FROM membership m
            JOIN videos v ON v.id=m.video_id {VIDEO_PREFERENCES} LEFT JOIN wiki_publications p
            ON p.course_id=m.course_id AND p.video_id=m.video_id
            WHERE m.course_id=? ORDER BY m.position, v.id""", (course_id,),
    )]


def create_course(connection, title):
    course_id = new_id()
    connection.execute("INSERT INTO courses VALUES (?, ?, ?)", (course_id, title, time.time()))
    return {"id": course_id, "title": title}


def add_member(connection, course_id, video_id):
    course_row(connection, course_id)
    video = video_row(connection, video_id)
    connection.execute(
        """INSERT OR IGNORE INTO membership(course_id, video_id, position)
           SELECT ?, ?, COALESCE(MAX(position)+1, 0) FROM membership WHERE course_id=?""",
        (course_id, video_id, course_id),
    )
    return video["source_id"]


def reorder_course(connection, course_id, video_ids):
    existing = {row["id"] for row in course_members(connection, course_id)}
    if len(video_ids) != len(existing) or set(video_ids) != existing:
        raise StudyProblem("课程的视频已变化，请刷新后再调整顺序", 409, "course_changed")
    _write_course_order(connection, course_id, video_ids)


def compact_course_order(connection, course_id):
    rows = connection.execute(
        "SELECT video_id FROM membership WHERE course_id=? ORDER BY position, video_id", (course_id,),
    )
    _write_course_order(connection, course_id, [row["video_id"] for row in rows])


def _write_course_order(connection, course_id, video_ids):
    connection.executemany(
        "UPDATE membership SET position=? WHERE course_id=? AND video_id=?",
        [(position, course_id, video_id) for position, video_id in enumerate(video_ids)],
    )


def active_chunks(connection, scope, scope_id):
    """在排序前限定候选来源，供问答和回忆共用。"""
    params = ()
    where = ""
    membership = ""
    position = "NULL"
    if scope == "video":
        video_row(connection, scope_id)
        where, params = "WHERE v.id=?", (scope_id,)
    elif scope == "course":
        course_row(connection, scope_id)
        membership = """JOIN (
            SELECT video_id, ROW_NUMBER() OVER (ORDER BY position, video_id) AS lesson_number
            FROM membership WHERE course_id=?
        ) m ON m.video_id=v.id"""
        position = "m.lesson_number"
        params = (scope_id,)
    return connection.execute(
        f"""SELECT ch.id, ch.source_id, ch.start_time, ch.end_time, ch.text,
                   v.id AS video_id, {VIDEO_TITLE} AS video_title, v.url, v.platform, {position} AS lesson_number
            FROM videos v {VIDEO_PREFERENCES} {membership} JOIN chunks ch ON ch.source_id=v.source_id {where}""", params,
    )


def citation_rows(connection, chunk_ids):
    rows = []
    for chunk_id in dict.fromkeys(chunk_ids):
        row = connection.execute(
            f"""SELECT ch.id, ch.source_id, ch.start_time, ch.end_time, ch.text,
                      v.id AS video_id, {VIDEO_TITLE} AS video_title, v.url, v.platform
               FROM chunks ch JOIN sources s ON s.id=ch.source_id
               JOIN videos v ON v.id=s.video_id {VIDEO_PREFERENCES} WHERE ch.id=?""", (chunk_id,),
        ).fetchone()
        if row:
            rows.append(dict(row))
    return rows
