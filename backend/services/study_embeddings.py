"""固定版本的本地多语种 E5 和可补建的语义索引。"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
from threading import Lock
from storage.data_home import data_directory

MODEL = "intfloat/multilingual-e5-small"
REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
MODEL_FILE = "onnx/model.onnx"
MODEL_FILES = [MODEL_FILE, "config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"]
DIMENSIONS = 384
logger = logging.getLogger(__name__)
_registration_lock = Lock()


def model_directory(data_dir):
    return Path(os.environ.get("STUDY_MODEL_DIR", data_dir / "e5-model")).expanduser().resolve()


def prepare_model(data_dir):
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=MODEL, revision=REVISION, allow_patterns=MODEL_FILES,
        local_dir=model_directory(data_dir), token=False,
    )


class LocalEmbeddings:
    def __init__(self, directory, *, enabled=True):
        self.directory = directory
        self._model = None
        self._lock = Lock()
        self.enabled = enabled
        self.state = "not_prepared" if enabled else "disabled"

    def load(self):
        if not self.enabled or self._model is not None:
            return self._model is not None
        if self.state == "unavailable" or not all((self.directory / file).is_file() for file in MODEL_FILES):
            return False
        try:
            from fastembed import TextEmbedding
            from fastembed.common.model_description import ModelSource, PoolingType

            with _registration_lock:
                if not any(item["model"] == MODEL for item in TextEmbedding.list_supported_models()):
                    TextEmbedding.add_custom_model(
                        model=MODEL, pooling=PoolingType.MEAN, normalization=True,
                        sources=ModelSource(hf=MODEL), dim=DIMENSIONS, model_file=MODEL_FILE,
                    )
            self._model = TextEmbedding(
                MODEL, threads=1, specific_model_path=str(self.directory), local_files_only=True,
                enable_cpu_mem_arena=False,
            )
        except Exception:
            self.state = "unavailable"
            logger.warning("本地语义模型不可用，资料库将使用全文检索")
            return False
        self.state = "ready"
        return True

    def vectors(self, texts, *, query=False):
        if self._model is None:
            return None
        prefix = "query: " if query else "passage: "
        try:
            with self._lock:
                return list(self._model.embed([prefix + text[:1800] for text in texts], batch_size=8))
        except Exception:
            self._model = None
            self.state = "unavailable"
            logger.warning("本地语义计算失败，资料库将使用全文检索")
            return None


async def index_batch(database, encoder):
    """小批量补索引，CPU 推理放在线程里，写入时确认原始文本版本。"""
    with database.transaction() as connection:
        pending = connection.execute(
            "SELECT id, text FROM search_docs WHERE embedding IS NULL ORDER BY id LIMIT 24"
        ).fetchall()
    if not pending:
        return False
    vectors = await asyncio.to_thread(encoder.vectors, [item["text"] for item in pending])
    if vectors is None:
        return False
    with database.transaction(write=True) as connection:
        connection.executemany(
            "UPDATE search_docs SET embedding=? WHERE id=? AND text=? AND embedding IS NULL",
            [(vector.astype("<f4").tobytes(), row["id"], row["text"]) for row, vector in zip(pending, vectors)],
        )
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="准备课程 Wiki 的本地 E5 模型")
    parser.add_argument("--prepare", required=True, action="store_true", help="下载固定版本的模型文件")
    parser.parse_args()
    print(prepare_model(data_directory()))
