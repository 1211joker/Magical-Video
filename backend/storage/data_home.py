"""本机持久卷的路径和单进程访问锁。"""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
import fcntl
import os

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / ".study-data"


def data_directory():
    return Path(os.environ.get("STUDY_DATA_DIR", DEFAULT_DATA_DIR)).expanduser().resolve()


def user_study_directory(directory, account_id):
    if UUID(account_id).hex != account_id:
        raise ValueError("无效的账号编号")
    return directory / "users" / account_id


@contextmanager
def exclusive_data(directory):
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (directory / ".active.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("资料卷正在使用。请先停止对应后端再操作。") from None
        yield
