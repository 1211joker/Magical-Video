"""持久问答、来源与记忆依赖。"""

import json
import time

from storage.study_db import StudyProblem, index_document, new_id, pack, require_row
from storage.study_library import citation_rows, course_row, video_row


def scope_title(connection, scope, scope_id):
    if scope == "course":
        return course_row(connection, scope_id)["title"]
    if scope == "video":
        return video_row(connection, scope_id)["title"]
    return "全部资料"


def create_conversation(connection, scope, scope_id):
    label = scope_title(connection, scope, scope_id)
    conversation_id = new_id()
    connection.execute(
        "INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, scope, scope_id, label, "新对话", time.time()),
    )
    return dict(conversation_row(connection, conversation_id))


def conversation_row(connection, conversation_id):
    return require_row(connection.execute(
        "SELECT * FROM conversations WHERE id=?", (conversation_id,),
    ).fetchone(), "对话已删除")


def list_conversations(connection, scope, scope_id):
    if scope is None:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC, id",
        )]
    scope_title(connection, scope, scope_id)
    return [dict(row) for row in connection.execute(
        "SELECT * FROM conversations WHERE scope=? AND scope_id IS ? ORDER BY updated_at DESC, id",
        (scope, scope_id),
    )]


def conversation_detail(connection, conversation_id):
    conversation = dict(conversation_row(connection, conversation_id))
    try:
        conversation["scope_title"] = scope_title(connection, conversation["scope"], conversation["scope_id"])
        conversation["archived"] = False
    except StudyProblem:
        conversation["scope_title"] = conversation["scope_label"]
        conversation["archived"] = True
    conversation["turns"] = []
    for row in connection.execute(
        "SELECT * FROM turns WHERE conversation_id=? ORDER BY created_at, id", (conversation_id,),
    ):
        turn = dict(row)
        turn["citations"] = [] if turn["invalidated"] else citation_rows(connection, json.loads(row["citations"]))
        turn["recalled"] = [] if turn["invalidated"] else [
            memory for term in json.loads(row["recalled"]) if (memory := available_turn(connection, term))
        ]
        conversation["turns"].append(turn)
    return conversation


def available_turn(connection, turn_id):
    row = connection.execute(
        """SELECT id, conversation_id, question, answer, created_at FROM turns
           WHERE id=? AND invalidated=0""", (turn_id,),
    ).fetchone()
    return dict(row) if row else None


def recent_turns(connection, conversation_id):
    rows = connection.execute(
        """SELECT id, question, answer FROM turns WHERE conversation_id=? AND invalidated=0
           ORDER BY created_at DESC, id DESC LIMIT 5""", (conversation_id,),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def add_turn(connection, turn_id, conversation_id, question, answer, citations, recalled, source_ids, prior_ids):
    conversation = conversation_row(connection, conversation_id)
    connection.execute(
        """INSERT INTO turns(id, conversation_id, question, answer, citations, recalled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (turn_id, conversation_id, question, answer, pack(citations), pack(recalled), time.time()),
    )
    connection.executemany(
        "INSERT INTO turn_sources VALUES (?, ?)", [(turn_id, source_id) for source_id in sorted(source_ids)],
    )
    connection.executemany(
        "INSERT INTO turn_dependencies VALUES (?, ?)", [(turn_id, prior_id) for prior_id in sorted(prior_ids)],
    )
    if citations:
        index_document(connection, "history", turn_id, f"{question} {answer[:2400]}")
    title = question[:54] if conversation["title"] == "新对话" else conversation["title"]
    connection.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=?", (title, time.time(), conversation_id))


def dependent_turns(connection, seed_sql, values):
    return [row[0] for row in connection.execute(
        f"""WITH RECURSIVE affected(id) AS (
               {seed_sql}
               UNION
               SELECT d.turn_id FROM turn_dependencies d JOIN affected a ON a.id=d.prior_id
            ) SELECT id FROM affected""", values,
    )]


def video_turns(connection, video_id, course_id=None):
    course_filter = ""
    values = (video_id,)
    if course_id:
        course_filter = """AND EXISTS(SELECT 1 FROM turns t JOIN conversations c ON c.id=t.conversation_id
                                      WHERE t.id=ts.turn_id AND c.scope='course' AND c.scope_id=?)"""
        values = (video_id, course_id)
    return dependent_turns(connection,
        f"""SELECT ts.turn_id FROM turn_sources ts JOIN sources s ON s.id=ts.source_id
            WHERE s.video_id=? {course_filter}""", values,
    )


def invalidate_turns(connection, turn_ids, *, clear=False):
    connection.executemany(
        "DELETE FROM search_docs WHERE kind='history' AND entity=?", [(turn_id,) for turn_id in turn_ids],
    )
    if clear:
        connection.executemany("DELETE FROM jobs WHERE id=? AND kind='question'", [(turn_id,) for turn_id in turn_ids])
        connection.executemany("DELETE FROM turns WHERE id=?", [(turn_id,) for turn_id in turn_ids])
        return
    connection.executemany("UPDATE turns SET invalidated=1 WHERE id=?", [(turn_id,) for turn_id in turn_ids])


def delete_conversation(connection, conversation_id):
    conversation_row(connection, conversation_id)
    turns = dependent_turns(connection, "SELECT id FROM turns WHERE conversation_id=?", (conversation_id,))
    invalidate_turns(connection, turns)
    connection.execute("DELETE FROM jobs WHERE kind='question' AND json_extract(payload, '$.conversation_id')=?",
                       (conversation_id,))
    connection.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))


def validate_dependencies(connection, prior_ids):
    if any(available_turn(connection, turn_id) is None for turn_id in prior_ids):
        raise StudyProblem("问答依据已变化，请重新提交", 409, "source_changed")
