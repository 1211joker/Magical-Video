import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from services.download_service import DownloadJobNotFound, DownloadJobs
from services.ytdlp_service import PreparedVideo


class DownloadResumeTests(unittest.TestCase):
    def test_same_file_address_accepts_multiple_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.write_bytes(b"abcdefgh")
            with patch("services.download_service.prepare_download", return_value=PreparedVideo(path)) as prepare:
                with TestClient(app) as client:
                    created = client.post("/api/download/jobs", json={"url": "https://youtu.be/example"})
                    self.assertEqual(created.status_code, 202)
                    job_url = "/api/download/jobs/" + created.json()["job_id"]
                    status = client.get(job_url)
                    self.assertEqual(status.json()["status"], "ready")
                    file_url = status.json()["download_url"]
                    first = client.get(file_url, headers={"Range": "bytes=0-3"})
                    resumed = client.get(file_url, headers={"Range": "bytes=4-"})
                    self.assertEqual((first.status_code, first.content), (206, b"abcd"))
                    self.assertEqual((resumed.status_code, resumed.content), (206, b"efgh"))
                    self.assertEqual(resumed.headers["content-range"], "bytes 4-7/8")
                    self.assertTrue(path.is_file())
                self.assertEqual(prepare.await_count, 1)
            self.assertFalse(path.exists())


class DownloadLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_expiry_counts_from_last_active_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.touch()
            jobs = DownloadJobs(retention_seconds=0.02)
            with patch("services.download_service.prepare_download", return_value=PreparedVideo(path)):
                job_id = jobs.start("https://youtu.be/example", "best", None)
                await asyncio.sleep(0)
                _, finish_first = jobs.acquire(job_id)
                _, finish_second = jobs.acquire(job_id)
                finish_first()
                await asyncio.sleep(0.04)
                self.assertTrue(path.is_file())
                self.assertIsNotNone(jobs.result(job_id))
                finish_second()
                with self.assertRaises(DownloadJobNotFound):
                    await asyncio.sleep(0.04)
                    jobs.result(job_id)
                await jobs.close()
            self.assertFalse(path.exists())

    async def test_discard_rejects_new_transfers_and_waits_to_remove_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.touch()
            jobs = DownloadJobs()
            with patch("services.download_service.prepare_download", return_value=PreparedVideo(path)):
                job_id = jobs.start("https://youtu.be/example", "best", None)
                await asyncio.sleep(0)
                _, finish = jobs.acquire(job_id)
                await asyncio.wait_for(jobs.discard(job_id), timeout=1)
                with self.assertRaises(DownloadJobNotFound):
                    jobs.acquire(job_id)
                self.assertTrue(path.is_file())
                finish()
                await asyncio.wait_for(jobs.close(), timeout=1)
            self.assertFalse(path.exists())
