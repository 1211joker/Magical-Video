"""设置管理员账号，并在后端停止期间导入、备份和恢复资料。"""

import argparse
from contextlib import closing, contextmanager
from pathlib import Path
from shutil import copyfile
import sqlite3
from tempfile import TemporaryDirectory
import time

from storage.accounts import ACCOUNT_SUPPORTED_VERSIONS, AccountsDatabase
from storage.data_home import data_directory, exclusive_data, user_study_directory
from storage.study_db import StudyDatabase

LIBRARY_TABLES = {"videos", "sources", "courses", "wiki_pages", "conversations", "turns", "jobs", "search_docs"}
ACCOUNT_TABLES = {"accounts", "sessions", "auth_limits", "ai_usage"}


def _read(path, *, immutable=False):
    query = "?mode=ro&immutable=1" if immutable else "?mode=ro"
    return sqlite3.connect(path.resolve().as_uri() + query, uri=True)


@contextmanager
def _read_backup(path, workspace):
    path = path.resolve()
    sidecars = [path.with_name(path.name + suffix) for suffix in ("-wal", "-journal")]
    sidecars = [file for file in sidecars if file.is_file()]
    if not sidecars:
        with closing(_read(path, immutable=True)) as connection:
            yield connection
        return

    # 在可写副本上回放日志，避免跳过尚未合并到主库的记录。
    with TemporaryDirectory(dir=workspace, prefix=".sqlite-copy-") as temporary:
        staged = Path(temporary)
        copyfile(path, staged / path.name)
        for file in sidecars:
            copyfile(file, staged / file.name)
        with closing(sqlite3.connect(staged / path.name)) as connection:
            yield connection


def _check(connection, required, versions=(1,)):
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if connection.execute("PRAGMA user_version").fetchone()[0] not in versions or not required <= names:
        raise ValueError("数据库版本或结构不受支持")
    if (connection.execute("PRAGMA quick_check").fetchone() != ("ok",)
            or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
        raise ValueError("数据库完整性检查失败")


def _snapshot(source, target, tables, *, versions=(1,), source_is_backup=False):
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    reader = _read_backup(source, target.parent) if source_is_backup else closing(_read(source))
    with reader as original, closing(sqlite3.connect(target)) as copy:
        _check(original, tables, versions)
        original.backup(copy)
        # 保存可独立读取的快照，读回时无需创建 WAL 辅助文件。
        copy.execute("PRAGMA journal_mode=DELETE")
        _check(copy, tables, versions)
    target.chmod(0o600)


@contextmanager
def _new_directory(target):
    if target.exists():
        raise ValueError("目标目录已存在，请指定新目录")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent, prefix=".snapshot-") as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir(mode=0o700)
        yield staged
        if target.exists():
            raise ValueError("目标目录已存在，请指定新目录")
        staged.rename(target)


def import_library(directory, source, username):
    with exclusive_data(directory):
        accounts = AccountsDatabase(directory)
        if accounts.path.is_file():
            accounts.initialize()
        owner = accounts.id_for_username(username)
        if not owner:
            raise ValueError("请指定一个已注册的用户名")
        target = user_study_directory(directory, owner) / "library.sqlite3"
        if source.resolve() == target.resolve():
            raise ValueError("请选择旧资料库的备份文件")
        if target.exists():
            with closing(_read(target)) as existing:
                _check(existing, LIBRARY_TABLES)
                if existing.execute(
                    """SELECT 1 FROM videos UNION ALL SELECT 1 FROM courses UNION ALL SELECT 1 FROM jobs
                       UNION ALL SELECT 1 FROM conversations UNION ALL SELECT 1 FROM video_groups LIMIT 1"""
                ).fetchone():
                    raise ValueError("目标账号已有资料，请指定空账号")
        with TemporaryDirectory(dir=directory, prefix=".import-") as temporary:
            staged = Path(temporary) / "library.sqlite3"
            _snapshot(source, staged, LIBRARY_TABLES, source_is_backup=True)
            database = StudyDatabase(staged)
            database.initialize()
            with database.transaction(write=True) as connection:
                connection.execute(
                    """UPDATE jobs SET state='cancelled', phase='cancelled', checkpoint=NULL, code=NULL,
                       detail='导入前尚未完成的任务已停止', updated_at=?
                       WHERE state IN ('queued', 'running', 'needs_input', 'needs_retry')""",
                    (time.time(),),
                )
            _snapshot(staged, target, LIBRARY_TABLES)


def _copy_account_data(source, target, *, source_is_backup=False):
    accounts = AccountsDatabase(target)
    _snapshot(
        AccountsDatabase(source).path, accounts.path, ACCOUNT_TABLES,
        versions=ACCOUNT_SUPPORTED_VERSIONS, source_is_backup=source_is_backup,
    )
    for owner in accounts.ids():
        library = user_study_directory(source, owner) / "library.sqlite3"
        if library.is_file():
            _snapshot(
                library, user_study_directory(target, owner) / library.name,
                LIBRARY_TABLES, source_is_backup=source_is_backup,
            )


def backup(directory, target):
    if target.is_relative_to(directory):
        raise ValueError("请在资料卷之外指定备份目录")
    with exclusive_data(directory), _new_directory(target) as staged:
        _copy_account_data(directory, staged)


def restore(source, target):
    with _new_directory(target) as staged:
        _copy_account_data(source, staged, source_is_backup=True)
        accounts = AccountsDatabase(staged)
        accounts.initialize()
        with accounts.transaction(write=True) as connection:
            # 恢复快照后，所有设备重新登录。
            connection.execute("DELETE FROM sessions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=data_directory())
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import-library")
    importer.add_argument("source", type=Path)
    importer.add_argument("--username", required=True)
    admin = commands.add_parser("promote-admin", help="将已注册的账号设为管理员")
    admin.add_argument("--username", required=True)
    snapshot = commands.add_parser("backup")
    snapshot.add_argument("target", type=Path)
    recovery = commands.add_parser("restore")
    recovery.add_argument("source", type=Path)
    args = parser.parse_args()
    data = args.data_dir.expanduser().resolve()
    try:
        if args.command == "import-library":
            import_library(data, args.source, args.username)
        elif args.command == "promote-admin":
            if not AccountsDatabase(data).promote_admin(args.username):
                raise ValueError("请指定一个已注册的用户名")
        elif args.command == "backup":
            backup(data, args.target.expanduser().resolve())
        else:
            restore(args.source, data)
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")
    print("操作完成")


if __name__ == "__main__":
    main()
