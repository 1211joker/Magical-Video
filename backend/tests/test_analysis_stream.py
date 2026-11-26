import asyncio
import os
import signal
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from starlette.requests import ClientDisconnect

from routers.analyze import AnalysisStreamResponse, _with_heartbeat
from services.ytdlp_service import parse_video_info


class AnalysisStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_progress_keeps_the_stream_alive(self):
        ready = asyncio.Event()

        async def events():
            yield "data: started\n\n"
            await ready.wait()
            yield "data: finished\n\n"

        with patch("routers.analyze.SSE_HEARTBEAT_SECONDS", 0.01):
            stream = _with_heartbeat(events())
            try:
                self.assertEqual(await stream.__anext__(), "data: started\n\n")
                self.assertEqual(await stream.__anext__(), ": keep-alive\n\n")
                ready.set()
                self.assertEqual(await stream.__anext__(), "data: finished\n\n")
                with self.assertRaises(StopAsyncIteration):
                    await stream.__anext__()
            finally:
                await stream.aclose()

    async def test_disconnect_while_sending_a_heartbeat_cancels_pending_work(self):
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def events():
            try:
                started.set()
                await asyncio.Future()
                yield "data: finished\n\n"
            finally:
                stopped.set()

        async def send(message):
            if message["type"] == "http.response.body":
                self.assertEqual(message["body"], b": keep-alive\n\n")
                raise OSError("connection closed")

        with patch("routers.analyze.SSE_HEARTBEAT_SECONDS", 0.01):
            response = AnalysisStreamResponse(_with_heartbeat(events()))
            with self.assertRaises(ClientDisconnect):
                await response({"type": "http", "asgi": {"spec_version": "2.4"}}, AsyncMock(), send)
        self.assertTrue(started.is_set())
        self.assertTrue(stopped.is_set())


class MetadataProcessTests(unittest.IsolatedAsyncioTestCase):
    async def check_process_cleanup(self, *, cancelled):
        started = asyncio.Event()
        drained = asyncio.Event()
        cookie_file = None

        async def spawn(*command, **kwargs):
            nonlocal cookie_file
            cookie_file = Path(command[command.index("--cookies") + 1])
            self.assertEqual(kwargs["start_new_session"], os.name == "posix")
            return process

        async def communicate():
            if not started.is_set():
                started.set()
                await asyncio.Future()
            self.assertTrue(cookie_file.is_file())
            drained.set()
            return b"", b""

        process = SimpleNamespace(pid=1234, communicate=communicate, kill=Mock())
        with patch("services.ytdlp_service.asyncio.create_subprocess_exec", side_effect=spawn), \
             patch("services.ytdlp_service.os.killpg", create=True) as kill_group, \
             patch("services.ytdlp_service.YTDLP_TIMEOUT", 1 if cancelled else 0.02):
            task = asyncio.create_task(parse_video_info("https://www.bilibili.com/video/BVexample", "test-cookie"))
            await asyncio.wait_for(started.wait(), timeout=1)
            if cancelled:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            else:
                with self.assertRaisesRegex(RuntimeError, "解析超时"):
                    await task
        if os.name == "posix":
            kill_group.assert_called_once_with(process.pid, signal.SIGKILL)
        else:
            process.kill.assert_called_once()
        self.assertTrue(drained.is_set())
        self.assertFalse(cookie_file.exists())

    async def test_cancellation_reaps_the_process_before_removing_cookies(self):
        await self.check_process_cleanup(cancelled=True)

    async def test_timeout_reaps_the_process_before_removing_cookies(self):
        await self.check_process_cleanup(cancelled=False)
