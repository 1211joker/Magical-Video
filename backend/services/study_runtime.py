"""单机上的账号资料库和共享任务调度。"""

import asyncio
from functools import partial
import logging
import os
import sqlite3

from services.ai_client import using_account_ai
from services.study import StudyService
from services.study_embeddings import LocalEmbeddings, index_batch, model_directory
from storage.data_home import user_study_directory

logger = logging.getLogger(__name__)


class StudyRuntime:
    def __init__(self, directory, accounts):
        self.directory = directory
        self.accounts = accounts
        self.encoder = LocalEmbeddings(model_directory(directory), enabled=os.getenv("STUDY_SEMANTIC", "1") != "0")
        self.services = {}
        self.ready = {}
        self.changed = asyncio.Event()
        self.workers = []

    def _schedule(self, owner):
        self.ready.setdefault(owner, None)
        self.changed.set()

    def for_user(self, owner):
        if owner not in self.services:
            service = StudyService(user_study_directory(self.directory, owner), self.encoder,
                                   partial(self._schedule, owner))
            service.start()
            self.services[owner] = service
            self._schedule(owner)
        return self.services[owner]

    def start(self):
        for owner in self.accounts.database.ids():
            if (user_study_directory(self.directory, owner) / "library.sqlite3").is_file():
                try:
                    self.for_user(owner)
                except (OSError, RuntimeError, sqlite3.Error):
                    logger.error("一个账号的资料库无法恢复，请检查数据库")
        self.workers = [asyncio.create_task(self._work()), asyncio.create_task(self._maintain())]

    async def close(self):
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.services.clear()
        self.ready.clear()

    async def _work(self):
        while True:
            if not self.ready:
                self.changed.clear()
                await self.changed.wait()
            owner = next(iter(self.ready))
            self.ready.pop(owner)
            try:
                with using_account_ai(owner, self.accounts.model_request):
                    worked = await self.services[owner].jobs.run_next()
                if worked:
                    self.ready.pop(owner, None)
                    self._schedule(owner)
            except sqlite3.Error:
                logger.error("一个账号的调度数据库不可用，将继续处理其他账号")
            await asyncio.sleep(0)

    async def _maintain(self):
        while True:
            searchable = self.encoder.enabled and await asyncio.to_thread(self.encoder.load)
            indexed = False
            for service in tuple(self.services.values()):
                service.jobs.prune()
                if searchable:
                    try:
                        indexed = await index_batch(service.database, self.encoder) or indexed
                    except sqlite3.Error:
                        logger.error("一个账号的资料索引暂时无法更新")
            await asyncio.sleep(0 if indexed else 2)
