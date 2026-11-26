"""可追溯的课程概念、来源贡献及双向链接。"""

from collections import defaultdict
import json

from models.study import normalized_text
from storage.study_db import StudyProblem, index_document, new_id, pack, require_row
from storage.study_library import citation_rows, course_row


def page_row(connection, page_id):
    return require_row(connection.execute(
        """SELECT p.*, c.title AS course_title FROM wiki_pages p
           JOIN courses c ON c.id=p.course_id WHERE p.id=?""", (page_id,),
    ).fetchone(), "概念页已移除")


def list_pages(connection, course_id):
    course_row(connection, course_id)
    return [_page_header(row) for row in connection.execute(
        "SELECT * FROM wiki_pages WHERE course_id=? ORDER BY normalized_title", (course_id,),
    )]


def _page_header(row):
    return {
        "id": row["id"], "title": row["title"], "course_id": row["course_id"],
        "aliases": json.loads(row["aliases"]),
    }


def page_detail(connection, page_id):
    page = page_row(connection, page_id)
    result = {**_page_header(page), "course_title": page["course_title"]}
    claims = [dict(row) for row in connection.execute(
        """SELECT w.id, w.explanation, w.quote, w.chunk_id FROM wiki_claims w
           JOIN chunks ch ON ch.id=w.chunk_id JOIN sources s ON s.id=ch.source_id
           JOIN membership m ON m.video_id=s.video_id AND m.course_id=?
           WHERE w.page_id=? ORDER BY m.position, ch.start_time, w.id""",
        (page["course_id"], page_id),
    )]
    citations = {row["id"]: row for row in citation_rows(connection, [item["chunk_id"] for item in claims])}
    result["claims"] = [{**item, "source": citations[item["chunk_id"]]} for item in claims]
    result["related"] = [dict(row) for row in connection.execute(
        """SELECT DISTINCT p.id, p.title, p.course_id, c.title AS course_title
           FROM wiki_links l JOIN wiki_pages p ON p.id=
           CASE WHEN l.page_id=? THEN l.related_id ELSE l.page_id END
           JOIN courses c ON c.id=p.course_id
           WHERE l.page_id=? OR l.related_id=? ORDER BY p.title""", (page_id, page_id, page_id),
    )]
    excluded = {row["id"] for row in result["related"]}
    excluded.update(row[0] for row in connection.execute(
        """SELECT CASE WHEN page_id=? THEN related_id ELSE page_id END FROM wiki_link_declines
           WHERE page_id=? OR related_id=?""", (page_id, page_id, page_id)
    ))
    terms = {normalized_text(name) for name in [result["title"], *result["aliases"]]}
    result["suggestions"] = []
    for row in connection.execute(
        """SELECT p.*, c.title AS course_title FROM wiki_pages p
           JOIN courses c ON c.id=p.course_id WHERE p.course_id<>? ORDER BY c.title, p.title""",
        (page["course_id"],),
    ):
        matching = terms.intersection({row["normalized_title"], *map(normalized_text, json.loads(row["aliases"]))})
        if matching and row["id"] not in excluded:
            result["suggestions"].append({**_page_header(row), "course_title": row["course_title"]})
        if len(result["suggestions"]) == 6:
            break
    return result


def _reindex(connection, page_id):
    row = page_row(connection, page_id)
    explanations = [item["explanation"] for item in connection.execute(
        "SELECT explanation FROM wiki_claims WHERE page_id=? ORDER BY id", (page_id,),
    )]
    index_document(connection, "wiki", page_id, " ".join([row["title"], *json.loads(row["aliases"]), *explanations]))


def _clear_video_contributions(connection, course_id, video_id):
    affected = {row[0] for row in connection.execute(
        """SELECT DISTINCT w.page_id FROM wiki_claims w JOIN wiki_pages p ON p.id=w.page_id
           JOIN chunks ch ON ch.id=w.chunk_id JOIN sources s ON s.id=ch.source_id
           WHERE p.course_id=? AND s.video_id=?""", (course_id, video_id),
    )}
    connection.execute(
        """DELETE FROM wiki_claims WHERE page_id IN (SELECT id FROM wiki_pages WHERE course_id=?)
           AND chunk_id IN (SELECT ch.id FROM chunks ch JOIN sources s ON s.id=ch.source_id WHERE s.video_id=?)""",
        (course_id, video_id),
    )
    connection.execute(
        """DELETE FROM wiki_links WHERE page_id IN (SELECT id FROM wiki_pages WHERE course_id=?)
           AND provenance IN (SELECT id FROM sources WHERE video_id=?)""", (course_id, video_id),
    )
    return affected


def _refresh_changed_pages(connection, page_ids):
    for page_id in page_ids:
        if connection.execute("SELECT 1 FROM wiki_claims WHERE page_id=? LIMIT 1", (page_id,)).fetchone():
            _reindex(connection, page_id)
        else:
            connection.execute("DELETE FROM wiki_pages WHERE id=?", (page_id,))


def remove_video_contributions(connection, course_id, video_id):
    _refresh_changed_pages(connection, _clear_video_contributions(connection, course_id, video_id))
    connection.execute(
        "DELETE FROM wiki_publications WHERE course_id=? AND video_id=?", (course_id, video_id),
    )


def verified_pages(drafts, chunks):
    """引文按提交给模型的字幕核验。时间和来源始终由数据库决定。"""
    result = []
    for draft in drafts:
        claims = []
        for claim in draft.claims:
            quote = " ".join(claim.quote.split())
            if len(quote) >= 6 and claim.chunk_id in chunks and quote in chunks[claim.chunk_id]["text"]:
                claims.append({**claim.model_dump(), "quote": quote})
        if claims:
            result.append({**draft.model_dump(exclude={"claims"}), "claims": claims})
    return result


def publish_video(connection, course_id, video_id, source_id, drafts):
    active = connection.execute(
        """SELECT v.source_id FROM videos v JOIN membership m ON m.video_id=v.id
           WHERE m.course_id=? AND m.video_id=?""", (course_id, video_id),
    ).fetchone()
    if not active or active["source_id"] != source_id:
        raise StudyProblem("课程资料已变化，请从课程页面重新更新 Wiki", 409, "source_changed")
    affected = _clear_video_contributions(connection, course_id, video_id)
    pages = {row["normalized_title"]: dict(row) for row in connection.execute(
        "SELECT * FROM wiki_pages WHERE course_id=?", (course_id,),
    )}
    aliases = defaultdict(set)
    for page in pages.values():
        for alias in json.loads(page["aliases"]):
            aliases[normalized_text(alias)].add(page["id"])
    by_id = {page["id"]: page for page in pages.values()}
    relations = []
    for draft in drafts:
        title_key = normalized_text(draft["title"])
        page = pages.get(title_key)
        alias_matches = aliases[title_key]
        if page is None and len(alias_matches) == 1:
            page = by_id[next(iter(alias_matches))]
        if page is None:
            page = {"id": new_id(), "title": draft["title"], "aliases": "[]", "edited": 0}
            connection.execute(
                "INSERT INTO wiki_pages VALUES (?, ?, ?, ?, ?, 0)",
                (page["id"], course_id, page["title"], title_key, "[]"),
            )
            pages[title_key] = page
            by_id[page["id"]] = page
        page_id = page["id"]
        if not page["edited"]:
            page["aliases"] = pack(_unique_aliases(page["title"], [*json.loads(page["aliases"]), *draft["aliases"]]))
            connection.execute("UPDATE wiki_pages SET aliases=? WHERE id=?", (page["aliases"], page_id))
            for alias in json.loads(page["aliases"]):
                aliases[normalized_text(alias)].add(page_id)
        for claim in draft["claims"]:
            connection.execute(
                "INSERT OR IGNORE INTO wiki_claims VALUES (?, ?, ?, ?, ?)",
                (new_id(), page_id, claim["chunk_id"], claim["explanation"], claim["quote"]),
            )
        affected.add(page_id)
        relations.extend((page_id, normalized_text(name)) for name in draft["related"])
    for page_id, key in relations:
        related = pages.get(key)
        if related and related["id"] != page_id:
            _link(connection, page_id, related["id"], source_id)
    _refresh_changed_pages(connection, affected)
    connection.execute(
        """INSERT INTO wiki_publications VALUES (?, ?, ?)
           ON CONFLICT(course_id, video_id) DO UPDATE SET source_id=excluded.source_id""",
        (course_id, video_id, source_id),
    )


def _unique_aliases(title, aliases):
    terms = {normalized_text(title)}
    result = []
    for alias in aliases:
        key = normalized_text(alias)
        if key and key not in terms:
            terms.add(key)
            result.append(alias)
    return result[:24]


def update_page(connection, page_id, title, aliases):
    page = page_row(connection, page_id)
    collision = connection.execute(
        "SELECT 1 FROM wiki_pages WHERE course_id=? AND normalized_title=? AND id<>?",
        (page["course_id"], normalized_text(title), page_id),
    ).fetchone()
    if collision:
        raise StudyProblem("课程已有同名概念，可以使用合并功能", 409, "duplicate_title")
    connection.execute(
        "UPDATE wiki_pages SET title=?, normalized_title=?, aliases=?, edited=1 WHERE id=?",
        (title, normalized_text(title), pack(_unique_aliases(title, aliases)), page_id),
    )
    _reindex(connection, page_id)


def merge_pages(connection, source_id, target_id):
    source = page_row(connection, source_id)
    target = page_row(connection, target_id)
    if source_id == target_id or source["course_id"] != target["course_id"]:
        raise StudyProblem("请选择同一课程里的另一张概念页")
    for row in connection.execute("SELECT * FROM wiki_claims WHERE page_id=?", (source_id,)).fetchall():
        connection.execute(
            "INSERT OR IGNORE INTO wiki_claims VALUES (?, ?, ?, ?, ?)",
            (new_id(), target_id, row["chunk_id"], row["explanation"], row["quote"]),
        )
    for row in connection.execute(
        "SELECT * FROM wiki_links WHERE page_id=? OR related_id=?", (source_id, source_id),
    ).fetchall():
        peer = row["related_id"] if row["page_id"] == source_id else row["page_id"]
        if peer != target_id:
            _link(connection, target_id, peer, row["provenance"])
    connection.execute("DELETE FROM wiki_pages WHERE id=?", (source_id,))
    aliases = [*json.loads(target["aliases"]), source["title"], *json.loads(source["aliases"])]
    update_page(connection, target_id, target["title"], aliases)


def _link(connection, page_id, target_id, provenance):
    connection.execute(
        "INSERT OR IGNORE INTO wiki_links VALUES (?, ?, ?)", (*sorted((page_id, target_id)), provenance),
    )


def set_cross_course_link(connection, page_id, target_id, accepted):
    page = page_row(connection, page_id)
    target = page_row(connection, target_id)
    if page["course_id"] == target["course_id"]:
        raise StudyProblem("此操作用于不同课程之间的链接")
    pair = sorted((page_id, target_id))
    if accepted:
        _link(connection, page_id, target_id, "manual")
        connection.execute("DELETE FROM wiki_link_declines WHERE page_id=? AND related_id=?", pair)
    else:
        connection.execute("DELETE FROM wiki_links WHERE page_id=? AND related_id=? AND provenance='manual'", pair)
        connection.execute("INSERT OR IGNORE INTO wiki_link_declines VALUES (?, ?)", pair)
