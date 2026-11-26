"""在限定范围内合并全文与向量排序，沿 Wiki 引用查找字幕。"""

from collections import defaultdict
from dataclasses import dataclass
import re

import numpy as np

from models.study import normalized_text
from storage import study_conversations as conversations
from storage import study_library as library

_WORDS = re.compile(r"[a-z0-9][a-z0-9_-]*|[\u3400-\u9fff]+")
_COMMON = {"the", "and", "are", "for", "from", "what", "with", "does", "how", "when", "this", "that"}
_FOLLOW_UP = re.compile(r"^(?:上次|之前|刚才|上一轮)?[，,\s]*(?:第[一二三四五六七八九十\d]+(?:点|条|个)|这(?:点|个|里)|它|继续|展开)")
_ORDINAL = re.compile(r"第([一二三四五六七八九十\d]+)(?:点|条|个)")
_NUMBERED = re.compile(r"^\s*(?:[-*]\s*)?(\d+)[.．、)）]\s*\S", re.MULTILINE)
_CHINESE_NUMBERS = {label: position for position, label in enumerate("一二三四五六七八九十", 1)}
_LESSON_NUMBER = re.compile(r"第\s*([一二三四五六七八九十]|\d{1,3})\s*(?:讲|节|集|课)"
                            r"|\b(?:lecture|chapter|lesson)\s+(\d{1,3})\b", re.IGNORECASE)


@dataclass(frozen=True)
class RankedHit:
    id: str
    lexical: bool
    similarity: float


def terms(text):
    result = []
    for word in _WORDS.findall(normalized_text(text)):
        if word[0].isascii():
            if len(word) >= 2 and word not in _COMMON:
                result.append(word)
        elif len(word) <= 4:
            result.append(word)
        else:
            result.extend(word[i:i + 3] for i in range(0, len(word) - 2, 2))
            result.append(word[-3:])
    return list(dict.fromkeys(result))[:36]


def _lexical(connection, kind, query, allowed, limit):
    long = [term for term in terms(query) if len(term) >= 3]
    result = []
    if long:
        match = " OR ".join(f'"{term}"' for term in long)
        rows = connection.execute(
            """SELECT d.entity FROM search_fts JOIN search_docs d ON d.id=search_fts.rowid
               WHERE search_fts MATCH ? AND d.kind=? ORDER BY bm25(search_fts), d.entity""",
            (match, kind),
        )
        for row in rows:
            if row["entity"] in allowed:
                result.append(row["entity"])
            if len(result) == limit:
                return result
    short = {term for term in terms(query) if len(term) == 2}
    if short:
        found = set(result)
        for row in connection.execute("SELECT entity, text FROM search_docs WHERE kind=? ORDER BY entity", (kind,)):
            if row["entity"] in allowed and row["entity"] not in found and any(term in row["text"] for term in short):
                result.append(row["entity"])
            if len(result) == limit:
                break
    return result


def rank(connection, kind, query, allowed, vector, *, limit=8, linked=()):
    if not allowed:
        return []
    lexical = _lexical(connection, kind, query, allowed, max(32, limit))
    dense = []
    similarities = {}
    if vector is not None:
        ids, embeddings = [], []
        for row in connection.execute(
            "SELECT entity, embedding FROM search_docs WHERE kind=? AND embedding IS NOT NULL", (kind,),
        ):
            if row["entity"] in allowed and len(row["embedding"]) == vector.size * 4:
                ids.append(row["entity"])
                embeddings.append(np.frombuffer(row["embedding"], dtype="<f4"))
        if embeddings:
            scores = np.stack(embeddings) @ vector
            ordered = sorted(zip(ids, map(float, scores)), key=lambda item: (-item[1], item[0]))[:max(32, limit)]
            similarities = dict(ordered)
            dense = list(similarities)
    scores = defaultdict(float)
    for ranking in (lexical, dense):
        for position, entity in enumerate(ranking, 1):
            scores[entity] += 1 / (32 + position)
    lexical_ids = set(lexical)
    for entity in set(linked).intersection(scores):
        scores[entity] += 0.006
    ranked = sorted(scores, key=lambda entity: (-scores[entity], -similarities.get(entity, 0), entity))
    return [RankedHit(entity, entity in lexical_ids, similarities.get(entity, 0)) for entity in ranked[:limit]]


def follow_up_query(question, recent):
    if not _FOLLOW_UP.search(question) or not recent:
        return question
    prior = recent[-1]
    match = _ORDINAL.search(question)
    if match:
        label = match[1]
        number = int(label) if label.isdigit() else _CHINESE_NUMBERS.get(label)
        points = list(_NUMBERED.finditer(prior["answer"]))
        for index, point in enumerate(points):
            if int(point[1]) == number:
                end = points[index + 1].start() if index + 1 < len(points) else len(prior["answer"])
                topic = prior["answer"][point.start():end].strip()
                return f'{topic[:350]} {prior["question"][:160]} {question}'
    return f'{prior["question"][:250]} {question}'


def needs_topic(question, recent):
    # 只有指代且没有可识别主题时，避免随意挑选另一段旧对话。
    match = _FOLLOW_UP.search(question)
    if not match or recent:
        return False
    remaining = re.sub(r"(能不能|能再|再|展开|详细|解释|讲讲|说说|讲一下|是什么|吗|一下|具体|呢)", "",
                       question[match.end():])
    return not _WORDS.search(remaining)


def retrieve(connection, scope, scope_id, query, vector, *, question=None, limit=8):
    available = {row["id"]: dict(row) for row in library.active_chunks(connection, scope, scope_id)}
    eligible_videos = {item["video_id"] for item in available.values()}
    requested = _requested_lessons(question or query) if scope == "course" else set()
    if requested:
        available = {key: item for key, item in available.items() if item["lesson_number"] in requested}
    if not available:
        return [], eligible_videos
    clauses = {"course": (" WHERE course_id=?", (scope_id,)),
               "library": ("", ()),
               "video": (""" WHERE EXISTS(SELECT 1 FROM wiki_claims w JOIN chunks ch ON ch.id=w.chunk_id
                                          JOIN sources s ON s.id=ch.source_id
                                          WHERE w.page_id=wiki_pages.id AND s.video_id=?)""", (scope_id,))}
    where, parameters = clauses[scope]
    allowed_pages = {row[0] for row in connection.execute(f"SELECT id FROM wiki_pages{where}", parameters)}
    wiki_hits = rank(connection, "wiki", query, allowed_pages, vector, limit=4)
    pages = {hit.id for hit in wiki_hits if hit.lexical or hit.similarity >= 0.78}
    seeds = set(pages)
    linked_chunks = set()
    for page_id in sorted(seeds):
        for neighbor in connection.execute(
            """SELECT DISTINCT CASE WHEN page_id=? THEN related_id ELSE page_id END AS peer
               FROM wiki_links WHERE page_id=? OR related_id=? ORDER BY peer LIMIT 4""",
            (page_id, page_id, page_id),
        ):
            if neighbor["peer"] in allowed_pages:
                pages.add(neighbor["peer"])
    for page_id in sorted(pages):
        linked_chunks.update(row[0] for row in connection.execute(
            "SELECT DISTINCT chunk_id FROM wiki_claims WHERE page_id=?", (page_id,),
        ))
    direct = rank(connection, "chunk", query, available.keys(), vector, limit=max(limit * 3, 24), linked=linked_chunks)
    ids = _lesson_candidates(connection, requested, available, query, vector, linked_chunks, limit)
    for hit in direct:
        if len(ids) >= limit:
            break
        chunk = available[hit.id]
        # 相邻字幕的重叠部分留一份即可，不占用多个候选位置。
        if any(_nearly_same(chunk, available[previous]) for previous in ids):
            continue
        ids.append(hit.id)
        if len(ids) == limit:
            break
    if len(ids) < limit:
        for chunk_id in sorted(linked_chunks & available.keys(), key=lambda key: (available[key]["video_id"],
                                                                                  available[key]["start_time"])):
            if chunk_id not in ids and not any(_nearly_same(available[chunk_id], available[previous]) for previous in ids):
                ids.append(chunk_id)
            if len(ids) == limit:
                break
    return [available[chunk_id] for chunk_id in ids], eligible_videos


def _requested_lessons(question):
    labels = [first or second for first, second in _LESSON_NUMBER.findall(normalized_text(question))]
    return {int(label) if label.isdigit() else _CHINESE_NUMBERS[label] for label in labels}


def _lesson_candidates(connection, requested, available, query, vector, linked, limit):
    if len(requested) < 2:
        return []
    ids = []
    quota = max(1, min(2, limit // len(requested)))
    for number in sorted(requested):
        allowed = {key for key, item in available.items() if item["lesson_number"] == number}
        selected = []
        for hit in rank(connection, "chunk", query, allowed, vector, limit=6, linked=linked):
            if not any(_nearly_same(available[hit.id], available[other]) for other in selected):
                selected.append(hit.id)
            if len(selected) == quota:
                break
        ids.extend(selected)
        if len(ids) >= limit:
            return ids[:limit]
    return ids


def _nearly_same(a, b):
    if a["source_id"] != b["source_id"]:
        return False
    overlap = min(a["end_time"], b["end_time"]) - max(a["start_time"], b["start_time"])
    shortest = min(a["end_time"] - a["start_time"], b["end_time"] - b["start_time"])
    return a["text"] == b["text"] or (shortest > 0 and overlap / shortest >= 0.72)


def recall_turns(connection, current, query, vector, allowed_videos):
    scope, scope_id = current["scope"], current["scope_id"]
    where, params = "", ()
    if scope == "course":
        where = """AND ((c.scope='course' AND c.scope_id=?) OR
                         (c.scope='video' AND c.scope_id IN (SELECT video_id FROM membership WHERE course_id=?)))"""
        params = (scope_id, scope_id)
    elif scope == "video":
        where, params = "AND c.scope='video' AND c.scope_id=?", (scope_id,)
    candidates = defaultdict(set)
    for row in connection.execute(
        f"""SELECT t.id, s.video_id FROM turns t JOIN conversations c ON c.id=t.conversation_id
            JOIN turn_sources ts ON ts.turn_id=t.id JOIN sources s ON s.id=ts.source_id
            WHERE t.invalidated=0 AND c.id<>? {where}""", (current["id"], *params),
    ):
        candidates[row["id"]].add(row["video_id"])
    allowed = {turn_id for turn_id, videos in candidates.items() if videos and videos <= allowed_videos}
    ranked = rank(connection, "history", query, allowed, vector, limit=6)
    hits = [hit.id for hit in ranked if hit.lexical or hit.similarity >= 0.82][:3]
    return [conversations.available_turn(connection, turn_id) for turn_id in hits]
