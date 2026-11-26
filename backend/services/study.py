"""本地资料库的应用服务，协调学习资源和后台任务。"""

import asyncio
from contextlib import suppress
import os
import time
from uuid import NAMESPACE_URL, UUID, uuid5

from services import study_ai, study_search
from services.ai_client import AIServiceError, default_provider, select_provider
from services.analysis_service import analyze_subtitles
from services.panopto_service import PanoptoError
from services.study_embeddings import LocalEmbeddings, data_directory, index_loop, model_directory
from services.study_jobs import LocalStudyJobs
from services.study_sources import archive_identity, normalized_segments, subtitle_chunks, video_link
from services.video_service import open_video
from services.video_session import BilibiliSessionError
from services.youtube_network import YouTubeNetworkUnavailable
from storage import study_conversations as conversations
from storage import study_jobs as job_store
from storage import study_library as library
from storage import study_wiki as wiki
from storage.study_db import StudyDatabase, StudyProblem
from storage.study_jobs import StudyJob

WIKI_BATCH_SIZE = 16


class StudyService:
    def __init__(self, directory=None):
        directory = directory or data_directory()
        self.database = StudyDatabase(directory / "library.sqlite3")
        self.encoder = LocalEmbeddings(
            model_directory(directory), enabled=os.environ.get("STUDY_SEMANTIC", "1") != "0",
        )
        self.jobs = LocalStudyJobs(self.database, self._execute)
        self.indexer = None

    def start(self):
        self.database.initialize()
        self.jobs.start()
        if self.encoder.enabled:
            self.indexer = asyncio.create_task(index_loop(self.database, self.encoder))

    async def close(self):
        if self.indexer:
            self.indexer.cancel()
            with suppress(asyncio.CancelledError):
                await self.indexer
        await self.jobs.close()

    def status(self):
        with self.database.transaction() as connection:
            pending = connection.execute("SELECT count(*) FROM search_docs WHERE embedding IS NULL").fetchone()[0]
        return {"semantic": self.encoder.state, "pending_index": pending}

    def list_library(self):
        with self.database.transaction() as connection:
            return library.list_library(connection)

    def video(self, video_id):
        with self.database.transaction() as connection:
            return library.video_detail(connection, video_id)

    def update_video(self, video_id, group_id, title):
        with self.database.transaction(write=True) as connection:
            library.update_video(connection, video_id, group_id, title)

    def save_group(self, title, group_id=None):
        with self.database.transaction(write=True) as connection:
            return library.save_group(connection, title, group_id)

    def delete_group(self, group_id):
        with self.database.transaction(write=True) as connection:
            library.delete_group(connection, group_id)

    def create_course(self, title):
        with self.database.transaction(write=True) as connection:
            return library.create_course(connection, title)

    def rename_course(self, course_id, title):
        with self.database.transaction(write=True) as connection:
            library.course_row(connection, course_id)
            connection.execute("UPDATE courses SET title=? WHERE id=?", (title, course_id))

    async def course(self, course_id, *, include_suggestions=True):
        with self.database.transaction() as connection:
            course = dict(library.course_row(connection, course_id))
            members = library.course_members(connection, course_id)
            all_videos = library.list_library(connection)["videos"] if include_suggestions else []
            pages = wiki.list_pages(connection, course_id)
            for item in members:
                job = job_store.read_job(connection, self._wiki_job_id(course_id, item["id"], item["source_id"]))
                item["wiki_task"] = job.brief() if job else None
        if not all_videos:
            return {**course, "videos": members, "wiki_pages": pages, "suggestions": []}
        query = " ".join([course["title"], *(item["title"] for item in members[:4])])
        allowed = {item["id"]: item for item in all_videos}
        for item in members:
            allowed.pop(item["id"], None)
        vector = await self._query_vector(query) if allowed else None
        with self.database.transaction() as connection:
            ranked = study_search.rank(connection, "video", query, allowed, vector, limit=5)
        suggestions = [allowed[item.id] for item in ranked if item.lexical or item.similarity >= 0.82]
        return {**course, "videos": members, "wiki_pages": pages, "suggestions": suggestions}

    def add_video(self, course_id, video_id):
        with self.database.transaction(write=True) as connection:
            source_id = library.add_member(connection, course_id, video_id)
            job = self._queue_wiki(connection, course_id, video_id, source_id)
        self.jobs.changed.set()
        return job.brief()

    def reorder(self, course_id, video_ids):
        with self.database.transaction(write=True) as connection:
            library.reorder_course(connection, course_id, video_ids)

    def remove_video(self, course_id, video_id):
        with self.database.transaction(write=True) as connection:
            library.course_row(connection, course_id)
            library.video_row(connection, video_id)
            conversations.invalidate_turns(connection, conversations.video_turns(connection, video_id, course_id))
            wiki.remove_video_contributions(connection, course_id, video_id)
            connection.execute("DELETE FROM membership WHERE course_id=? AND video_id=?", (course_id, video_id))
            library.compact_course_order(connection, course_id)
            interrupted = self._drop_tasks(connection, "wiki", {"course_id": course_id, "video_id": video_id})
        for job_id in interrupted:
            self.jobs.interrupt(job_id)

    def delete_course(self, course_id):
        with self.database.transaction(write=True) as connection:
            library.course_row(connection, course_id)
            affected = conversations.dependent_turns(connection,
                """SELECT t.id FROM turns t JOIN conversations c ON c.id=t.conversation_id
                   WHERE c.scope='course' AND c.scope_id=?""", (course_id,),
            )
            conversations.invalidate_turns(connection, affected)
            interrupted = self._drop_tasks(connection, "wiki", {"course_id": course_id})
            connection.execute("DELETE FROM courses WHERE id=?", (course_id,))
        for job_id in interrupted:
            self.jobs.interrupt(job_id)

    def video_impact(self, video_id):
        with self.database.transaction() as connection:
            return self._impact(connection, video_id)

    def delete_video(self, video_id, clear_turns):
        with self.database.transaction(write=True) as connection:
            impact = self._impact(connection, video_id)
            video = connection.execute(
                "SELECT id, url, platform, external_id FROM videos WHERE id=?", (video_id,),
            ).fetchone()
            turns = conversations.video_turns(connection, video_id)
            conversations.invalidate_turns(connection, turns, clear=clear_turns)
            for course in impact["courses"]:
                wiki.remove_video_contributions(connection, course["id"], video_id)
            interrupted = self._drop_tasks(connection, "wiki", {"video_id": video_id})
            interrupted += job_store.delete_video_analyses(connection, video)
            library.delete_video(connection, video)
            for course in impact["courses"]:
                library.compact_course_order(connection, course["id"])
        for job_id in interrupted:
            self.jobs.interrupt(job_id)
        return impact

    def _impact(self, connection, video_id):
        library.video_row(connection, video_id)
        courses = [dict(row) for row in connection.execute(
            "SELECT c.id, c.title FROM membership m JOIN courses c ON c.id=m.course_id WHERE m.video_id=?",
            (video_id,),
        )]
        pages = [dict(row) for row in connection.execute(
            """SELECT DISTINCT p.id, p.title FROM wiki_claims w JOIN wiki_pages p ON p.id=w.page_id
               JOIN chunks ch ON ch.id=w.chunk_id JOIN sources s ON s.id=ch.source_id WHERE s.video_id=?""",
            (video_id,),
        )]
        return {"courses": courses, "pages": pages, "turn_count": len(conversations.video_turns(connection, video_id))}

    @staticmethod
    def _drop_tasks(connection, kind, filters):
        filters_sql = " AND ".join("json_extract(payload, ?)=?" for _ in filters)
        args = (kind, *(part for key, value in filters.items() for part in (f"$.{key}", value)))
        rows = connection.execute(f"SELECT id FROM jobs WHERE kind=? AND {filters_sql}", args).fetchall()
        connection.executemany("DELETE FROM jobs WHERE id=?", [(row[0],) for row in rows])
        return [row[0] for row in rows]

    def wiki_page(self, page_id):
        with self.database.transaction() as connection:
            return wiki.page_detail(connection, page_id)

    def edit_page(self, page_id, title, aliases):
        with self.database.transaction(write=True) as connection:
            wiki.update_page(connection, page_id, title, aliases)

    def merge_pages(self, page_id, target_id):
        with self.database.transaction(write=True) as connection:
            wiki.merge_pages(connection, page_id, target_id)

    def link_pages(self, page_id, target_id, accepted):
        with self.database.transaction(write=True) as connection:
            wiki.set_cross_course_link(connection, page_id, target_id, accepted)

    def create_conversation(self, scope, scope_id):
        with self.database.transaction(write=True) as connection:
            return conversations.create_conversation(connection, scope, scope_id)

    def list_conversations(self, scope, scope_id):
        with self.database.transaction() as connection:
            return conversations.list_conversations(connection, scope, scope_id)

    def conversation(self, conversation_id):
        with self.database.transaction() as connection:
            result = conversations.conversation_detail(connection, conversation_id)
        result["tasks"] = [
            {**job.brief(), "question": job.payload["question"]}
            for job in self.jobs.list(conversation_id) if job.state != "done"
        ]
        return result

    def delete_conversation(self, conversation_id):
        jobs = self.jobs.list(conversation_id)
        with self.database.transaction(write=True) as connection:
            conversations.delete_conversation(connection, conversation_id)
        for job in jobs:
            self.jobs.interrupt(job.id)

    def submit_analysis(self, body):
        try:
            platform, _, url = video_link(body.url)
        except ValueError as error:
            raise StudyProblem(str(error), 400, "video_link") from None
        credentials = {key: getattr(body, key) for key in ("cookies", "bilibili_session", "panopto_session")
                       if getattr(body, key, None)}
        private = bool(credentials) or platform == "panopto"
        if private and body.save and not body.private_consent:
            raise StudyProblem("请选择是否允许保存并处理此登录视频的字幕", 400, "private_consent")
        job = StudyJob(
            body.request_id, "analysis", (body.title or "").strip() or "视频分析",
            {"url": url, "platform": platform, "private": private,
             "provider": select_provider(body.provider).id,
             "requires_session": bool(credentials) and platform != "panopto"},
            persistent=body.save,
        )
        return self.jobs.submit(job, credentials)

    def submit_question(self, conversation_id, body):
        question = body.question.strip()
        if not question:
            raise StudyProblem("问题不能为空")
        with self.database.transaction() as connection:
            conversation = conversations.conversation_row(connection, conversation_id)
            conversations.scope_title(connection, conversation["scope"], conversation["scope_id"])
        return self.jobs.submit(StudyJob(
            body.request_id, "question", question[:72],
            {"conversation_id": conversation_id, "question": question, "recall": body.recall,
             "provider": select_provider(body.provider).id},
        ))

    def task(self, task_id):
        job = self.jobs.get(task_id)
        result = job.result
        if job.kind == "analysis" and job.state == "done" and job.persistent:
            with self.database.transaction() as connection:
                result = library.video_detail(connection, result["video_id"], result["source_id"])
        return {**job.brief(), "target": self._target(job), "result": result}

    def retry_task(self, task_id, body):
        job = self.jobs.get(task_id)
        if job.kind != "analysis":
            return self.jobs.retry(job)
        credentials = {key: getattr(body, key) for key in ("bilibili_session", "panopto_session") if getattr(body, key)}
        if credentials and job.persistent and not job.payload["private"] and not body.private_consent:
            raise StudyProblem("请确认允许保存及处理这个登录视频", 400, "private_consent")
        if credentials:
            job.payload["private"] = True
            if job.payload["platform"] != "panopto":
                job.payload["requires_session"] = True
        if job.checkpoint is None and self._requires_session(job) and not credentials:
            platform = job.payload["platform"]
            raise StudyProblem("请重新填写平台会话", 401, f"{platform}_login_required")
        return self.jobs.retry(job, credentials)

    @staticmethod
    def _requires_session(job):
        return job.payload.get("requires_session", job.payload["private"] and job.payload["platform"] != "panopto")

    @classmethod
    def _target(cls, job):
        target = {key: job.payload[key] for key in ("url", "platform", "private", "course_id", "video_id", "conversation_id")
                  if key in job.payload}
        if job.kind == "analysis":
            target["requires_session"] = cls._requires_session(job)
        return target

    @staticmethod
    def _wiki_job_id(course_id, video_id, source_id):
        return uuid5(NAMESPACE_URL, f"magical-video/wiki/{course_id}/{video_id}/{source_id}").hex

    @classmethod
    def _queue_wiki(cls, connection, course_id, video_id, source_id):
        job_id = cls._wiki_job_id(course_id, video_id, source_id)
        existing = job_store.read_job(connection, job_id)
        if existing and existing.state != "done" and existing.code != "source_changed":
            return existing
        published = connection.execute(
            "SELECT source_id FROM wiki_publications WHERE course_id=? AND video_id=?", (course_id, video_id),
        ).fetchone()
        if existing and published and published["source_id"] == source_id:
            return existing
        provider_id = library.source_provider(connection, source_id)
        default = default_provider() if not provider_id else None
        if default:
            provider_id = default.id
        if existing:
            existing.state = existing.phase = "queued"
            existing.checkpoint = existing.result = existing.detail = existing.code = None
            existing.payload["provider"] = provider_id
            existing.updated_at = time.time()
            job_store.update_job(connection, existing)
            return existing
        course = library.course_row(connection, course_id)
        video = library.video_row(connection, video_id)
        job = StudyJob(job_id, "wiki", f'{course["title"]} · {video["title"]}',
                       {"course_id": course_id, "video_id": video_id, "source_id": source_id, "provider": provider_id})
        job_store.insert_job(connection, job)
        return job

    async def _execute(self, job, credentials):
        try:
            if job.kind == "analysis":
                await self._analysis(job, credentials)
            elif job.kind == "wiki":
                await self._wiki(job)
            else:
                await self._question(job)
        except AIServiceError as error:
            if error.outcome_unknown:
                raise StudyProblem("AI 请求结果未知，请确认是否重试", 502, "retry_confirmation") from None
            raise StudyProblem(str(error), error.status_code, "ai_failed") from None

    def _start_ai(self, job):
        provider = select_provider(job.payload.get("provider"))
        job.payload["provider"] = provider.id
        self.jobs.progress(job, "ai")
        return provider

    async def _fetch_subtitles(self, job, credentials):
        if self._requires_session(job) and not credentials:
            raise StudyProblem("任务恢复后需要重新填写平台会话", 401, f'{job.payload["platform"]}_login_required')
        self.jobs.progress(job, "fetching")
        try:
            video = await open_video(job.payload["url"], **credentials)
            data = await video.subtitles()
        except (PanoptoError, BilibiliSessionError, YouTubeNetworkUnavailable) as error:
            if error.code.endswith(("_login_required", "_session_rejected")):
                job.payload["requires_session"] = True
            raise StudyProblem(str(error), 400, error.code) from None
        except RuntimeError as error:
            raise StudyProblem(str(error), 400, "video_fetch") from None
        finally:
            credentials.clear()
        if not data:
            raise StudyProblem("这条视频没有取得可用字幕", 422, "no_subtitles")
        segments = normalized_segments(data.segments)
        if not segments:
            raise StudyProblem("这条视频没有有效的时间戳字幕", 422, "no_subtitles")
        try:
            platform, external_id, url = archive_identity(job.payload["url"], video.info.webpage_url)
        except ValueError as error:
            raise StudyProblem(str(error), 400, "video_identity") from None
        job.label = video.info.title[:240]
        checkpoint = {
            "video": {"platform": platform, "external_id": external_id, "url": url,
                      "title": job.label, "duration": video.info.duration, "private": job.payload["private"]},
            "segments": segments,
        }
        self.jobs.progress(job, "subtitles_ready", checkpoint)

    async def _analysis(self, job, credentials):
        if job.checkpoint is None:
            await self._fetch_subtitles(job, credentials)
        video = job.checkpoint["video"]
        segments = job.checkpoint["segments"]
        if job.persistent:
            with self.database.transaction() as connection:
                deleted = library.deleted_after_submission(connection, video, job.created_at)
            if deleted:
                self.jobs.delete_analysis(job.id)
                return
        plain_text = " ".join(segment["text"] for segment in segments)
        provider = self._start_ai(job)
        try:
            analyzed = await analyze_subtitles(
                plain_text, video["title"], provider, retry_requests=False, session_id=UUID(job.id),
            )
        except AIServiceError:
            raise
        except RuntimeError as error:
            raise StudyProblem(str(error), 502, "analysis_failed") from None
        analysis = {**analyzed.model_dump(), "provider": provider.id}
        if not job.persistent:
            info = {key: video[key] for key in ("platform", "url", "title", "duration", "private")}
            self.jobs.complete(job, {**info, "analysis": analysis, "subtitle_segments": segments})
            return

        def archive(connection):
            video_id, source_id = library.archive_video(connection, video, segments, subtitle_chunks(segments), analysis)
            for course in connection.execute("SELECT course_id FROM membership WHERE video_id=?", (video_id,)).fetchall():
                self._queue_wiki(connection, course["course_id"], video_id, source_id)
            return {"video_id": video_id, "source_id": source_id}

        self.jobs.complete(job, commit=archive)
        self.jobs.changed.set()

    async def _wiki(self, job):
        course_id, video_id, source_id = (job.payload[key] for key in ("course_id", "video_id", "source_id"))
        with self.database.transaction() as connection:
            members = library.course_members(connection, course_id)
            video = next((row for row in members if row["id"] == video_id), None)
            if not video or video["source_id"] != source_id:
                raise StudyProblem("课程的字幕版本已经变化", 409, "source_changed")
            chunks = [dict(row) for row in connection.execute(
                "SELECT id, text FROM chunks WHERE source_id=? ORDER BY position", (source_id,),
            )]
            existing = wiki.list_pages(connection, course_id)[:120]
        checkpoint = job.checkpoint or {"offset": 0, "pages": []}
        offset = checkpoint["offset"]
        if offset < len(chunks):
            batch = chunks[offset:offset + WIKI_BATCH_SIZE]
            provider = self._start_ai(job)
            result = await study_ai.generate_wiki(batch, existing, provider=provider, session_id=UUID(job.id))
            checked = wiki.verified_pages(result.pages, {chunk["id"]: chunk for chunk in batch})
            checkpoint = {"offset": offset + len(batch), "pages": [*checkpoint["pages"], *checked]}
            if checkpoint["offset"] < len(chunks):
                self.jobs.progress(job, "draft_ready", checkpoint, requeue=True)
                return
            self.jobs.progress(job, "draft_ready", checkpoint)
        if not checkpoint["pages"]:
            job.checkpoint = None
            raise StudyProblem("本次没有生成可核对字幕出处的 Wiki 内容", 422, "wiki_no_evidence")

        def publish(connection):
            wiki.publish_video(connection, course_id, video_id, source_id, checkpoint["pages"])
            return {"course_id": course_id, "video_id": video_id}

        self.jobs.complete(job, commit=publish)

    async def _query_vector(self, query):
        vectors = await asyncio.to_thread(self.encoder.vectors, [query], query=True)
        return vectors[0] if vectors else None

    async def _question(self, job):
        conversation_id, question = job.payload["conversation_id"], job.payload["question"]
        self.jobs.progress(job, "retrieving")
        with self.database.transaction() as connection:
            current = dict(conversations.conversation_row(connection, conversation_id))
            conversations.scope_title(connection, current["scope"], current["scope_id"])
            recent = conversations.recent_turns(connection, conversation_id)
        query = study_search.follow_up_query(question, recent)
        evidence, recalled = [], []
        citations, displayed_recall = [], []
        if study_search.needs_topic(question, recent):
            answer = "你想接着哪条问答的第二点或哪一个概念？补充一点主题，我就能继续查找。"
        else:
            vector = await self._query_vector(query)
            with self.database.transaction() as connection:
                evidence, eligible = study_search.retrieve(
                    connection, current["scope"], current["scope_id"], query, vector, question=question,
                )
                if job.payload["recall"] and evidence:
                    recalled = study_search.recall_turns(connection, current, query, vector, eligible)
            answer = "当前范围没有找到足够的字幕依据。可以补充视频、讲次或关键词。"
            if evidence:
                provider = self._start_ai(job)
                result = await study_ai.generate_answer(
                    question, evidence, [self._short_turn(item) for item in recent],
                    [self._short_turn(item) for item in recalled], provider=provider, session_id=UUID(conversation_id),
                )
                allowed_citations = {item["id"] for item in evidence}
                allowed_recall = {item["id"] for item in recalled}
                citations = [item for item in dict.fromkeys(result.citations) if item in allowed_citations]
                if citations:
                    answer = result.answer.strip() or answer
                    displayed_recall = [item for item in dict.fromkeys(result.recalled_turns) if item in allowed_recall]

        def persist(connection):
            past = {item["id"] for item in [*recent, *recalled]}
            conversations.validate_dependencies(connection, past)
            self._validate_sources(connection, current, evidence)
            conversations.add_turn(
                connection, job.id, conversation_id, question, answer, citations, displayed_recall,
                {item["source_id"] for item in evidence}, past,
            )
            return {"turn_id": job.id, "conversation_id": conversation_id}

        self.jobs.complete(job, commit=persist)

    @staticmethod
    def _short_turn(turn):
        return {"id": turn["id"], "question": turn["question"][:1200], "answer": turn["answer"][:1800]}

    @staticmethod
    def _validate_sources(connection, current, evidence):
        current_ids = {item["id"] for item in library.active_chunks(connection, current["scope"], current["scope_id"])}
        if not {item["id"] for item in evidence} <= current_ids:
            raise StudyProblem("资料在回答期间已变化，请重新提交", 409, "source_changed")
