"""embeddings —— 向量化与相似检索。

第 18 批：让 VectorStore 真正走 sqlite-vec 主路径（vec0 虚拟表 +
vec_distance_cosine），不再误用 numpy 在 Python 侧算 cosine。

提供：
    - TextEmbedder：可插拔后端的文本嵌入（qwen3 / openai / hash）
    - VectorStore：sqlite-vec vec0 虚拟表存向量；
                   similarity = 1 - vec_distance_cosine() in SQL；
                   vec0 加载失败时回退到 BLOB + numpy 算 cosine
    - EntityEmbedder：高层封装 add_entity / similar_to

"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_DIM = 1024   # Qwen3-Embedding-0.6B hidden_size


def _default_db_path() -> Optional[str]:
    """共用：拿 settings.VEC_DB_PATH，无配置则 None。"""
    try:
        from config import settings
        return settings.VEC_DB_PATH or None
    except Exception:
        return None


def _try_load_vec0(conn: sqlite3.Connection) -> bool:
    """尝试加载 sqlite-vec vec0 扩展。返回 True 表示成功。

    优先用官方 sqlite_vec.loadable_path() 拿到绝对路径，
    避免 dlopen 在 Mac / Linux 上找不到 'vec0' 默认位置。
    """
    try:
        import sqlite_vec
        # sqlite_vec.load() 不会自动 enable_load_extension；必须显式开
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return True
    except Exception as e:
        logger.debug("sqlite-vec 加载失败，回退到 numpy: %s", e)
        return False


class TextEmbedder:
    """文本嵌入器（可插拔 backend）。

    后端：
        - "qwen3"（默认）：Qwen3-Embedding（modelscope 本地缓存，1024 维）
        - "openai"         ：langchain_openai.OpenAIEmbeddings
        - "hash"           ：sklearn HashingVectorizer（离线兜底）
    """

    def __init__(self, backend: Optional[str] = None, dim: int = _DEFAULT_DIM,
                 model_name: Optional[str] = None, device: Optional[str] = None):
        from config import settings
        if backend is None:
            backend = settings.EMBEDDING_PROVIDER
        if model_name is None and backend in ("qwen3", "openai"):
            model_name = settings.EMBEDDING_MODEL
        if device is None:
            device = settings.EMBEDDING_DEVICE

        self._backend = backend
        self._dim = dim
        self._model_name = model_name
        self._device = device
        self._hf_model = None
        self._hf_tokenizer = None
        self._hf_device = None
        self._openai_model = None

        # ── qwen3 后端（主力）──
        if backend == "qwen3":
            try:
                import os
                if settings.MODELSCOPE_CACHE:
                    os.environ["MODELSCOPE_CACHE"] = settings.MODELSCOPE_CACHE
                elif "MODELSCOPE_CACHE" not in os.environ:
                    pass
                from modelscope import AutoTokenizer as MsAutoTokenizer
                from modelscope import AutoModel as MsAutoModel
                import torch
                self._hf_tokenizer = MsAutoTokenizer.from_pretrained(
                    model_name, trust_remote_code=True)
                self._hf_model = MsAutoModel.from_pretrained(
                    model_name, trust_remote_code=True)
                self._hf_model.eval()
                self._hf_device = (torch.device("cuda")
                                   if device == "cuda" and torch.cuda.is_available()
                                   else torch.device("cpu"))
                self._hf_model = self._hf_model.to(self._hf_device)
                self._dim = getattr(self._hf_model.config, "hidden_size", 1024)
                self._max_length = settings.EMBEDDING_MAX_LENGTH
            except Exception as e:
                logger.warning("qwen3 加载失败，自动回退 hash 后端: %s", e)
                backend = "hash"
                self._backend = backend

        # ── openai 后端 ──
        if backend == "openai":
            try:
                from langchain_openai import OpenAIEmbeddings
                self._openai_model = OpenAIEmbeddings(
                    model=model_name,
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL or None,
                )
            except Exception as e:
                logger.warning("openai 加载失败，自动回退 hash: %s", e)
                backend = "hash"
                self._backend = backend

        # ── hash 后端（兜底）──
        if backend == "hash":
            from sklearn.feature_extraction.text import HashingVectorizer
            self._hash_vec = HashingVectorizer(
                n_features=dim, alternate_sign=False, norm="l2")
            self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def backend(self) -> str:
        return self._backend

    def embed(self, texts: list[str] | str) -> np.ndarray:
        """把文本嵌入为向量矩阵 (N, dim)。"""
        if isinstance(texts, str):
            texts = [texts]

        if self._backend == "qwen3":
            import torch
            with torch.no_grad():
                enc = self._hf_tokenizer(
                    texts, padding=True, truncation=True,
                    max_length=self._max_length,
                    return_tensors="pt").to(self._hf_device)
                out = self._hf_model(**enc)
                # last-token pooling（Qwen 推荐做 instruction-style embedding）
                last = out.last_hidden_state[:, -1, :]
                # L2 归一化（cosine 距离的等价形式）
                last = torch.nn.functional.normalize(last, p=2, dim=-1)
                return last.cpu().numpy()
        if self._backend == "openai" and self._openai_model:
            return np.asarray(self._openai_model.embed_documents(texts),
                             dtype=np.float32)
        if self._backend == "hash":
            X = self._hash_vec.transform(texts)        # sparse
            X = X.toarray().astype(np.float32)
            n = np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
            return X / n
        raise RuntimeError(f"unknown backend: {self._backend}")


class VectorStore:
    """sqlite-vec vec0 向量存储（item_id → vector，k-NN 检索）。

    检索路径（item_at_search）真正走 SQL：
        SELECT item_id, vec_distance_cosine(embedding, ?) AS d
        FROM vec_items ORDER BY d ASC LIMIT k
    把距离转回相似度（1 - distance），按相似度降序返回。

    向量序列化：vec0 自动接受 JSON / 二进制 packed float32 数组；
    这里用 JSON 字符串 [] 形式（最简单、跨版本最稳；Qwen3 dim=1024 完全 OK）。

    vec0 加载失败时（极少数环境）：回退到 BLOB 存向量 + numpy 算 cosine。
    """

    def __init__(self, db_path: Optional[str] = None, dim: int = _DEFAULT_DIM):
        if db_path is None:
            db_path = _default_db_path()
        self._db_path = db_path
        self._dim = dim
        self._use_vec0 = False     # 启动后探测决定走 vec0 还是 fallback
        if self._db_path:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        """拿 SQLite 连接：

        第 18 批：vec0 加载是 per-connection 状态（Python sqlite3 默认），
        必须每次 _conn 重新 enable_load_extension + load_extension，否则
        第二次调用 connection 会找不到 vec0 函数。
        """
        c = sqlite3.connect(self._db_path or ":memory:")
        c.row_factory = sqlite3.Row
        if self._use_vec0:
            try:
                c.enable_load_extension(True)
                import sqlite_vec
                sqlite_vec.load(c)
            except Exception as e:
                logger.debug("vec0 per-conn 加载失败: %s", e)
        return c

    def _init(self) -> None:
        """建表：根据 vec0 是否可用选虚拟表或 fallback BLOB 表。"""
        if not self._db_path:
            return  # 纯内存
        # 探测 vec0
        c = self._conn()
        try:
            self._use_vec0 = _try_load_vec0(c)
        finally:
            c.close()
        if self._use_vec0:
            with self._conn() as c:
                c.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_items "
                    f"USING vec0(item_id text primary key, "
                    f"embedding float[{self._dim}])"
                )
            logger.info("VectorStore: sqlite-vec 加载成功（vec0 主路径）")
        else:
            with self._conn() as c:
                c.execute("CREATE TABLE IF NOT EXISTS vec_items ("
                          "item_id TEXT PRIMARY KEY, dim INTEGER, embedding BLOB)")
            logger.info("VectorStore: vec0 不可用，回退到 BLOB+numpy 路径")

    def add(self, item_id: str, vector: np.ndarray) -> None:
        v = np.asarray(vector, dtype=np.float32).flatten()
        if v.size != self._dim:
            # 自动矫正
            if v.size < self._dim:
                v = np.pad(v, (0, self._dim - v.size))
            else:
                v = v[:self._dim]
        with self._conn() as c:
            if self._use_vec0:
                c.execute(
                    "INSERT OR REPLACE INTO vec_items (item_id, embedding) "
                    "VALUES (?, ?)",
                    (item_id, _pack_vec0(v)))
            else:
                c.execute("INSERT OR REPLACE INTO vec_items (item_id, dim, embedding) "
                          "VALUES (?, ?, ?)",
                          (item_id, len(v), v.tobytes()))
            c.commit()

    def search(self, query: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """返回 [(item_id, similarity), ...]，按相似度降序。

        vec0 主路径：SELECT ... ORDER BY vec_distance_cosine ASC LIMIT k
        回退路径：Python numpy 算 cosine similarity 后排序
        """
        q = np.asarray(query, dtype=np.float32).flatten()
        if q.size != self._dim:
            if q.size < self._dim:
                q = np.pad(q, (0, self._dim - q.size))
            else:
                q = q[:self._dim]
        if not self._db_path:
            return []
        with self._conn() as c:
            if self._use_vec0:
                rows = c.execute(
                    "SELECT item_id, vec_distance_cosine(embedding, ?) AS d "
                    "FROM vec_items ORDER BY d ASC LIMIT ?",
                    (_pack_vec0(q), k)).fetchall()
                # cosine distance ∈ [0, 2]，similarity = 1 - distance
                return [(r["item_id"], float(1.0 - r["d"])) for r in rows]
            # fallback numpy
            rows = c.execute("SELECT item_id, dim, embedding FROM vec_items").fetchall()
            if not rows:
                return []
            ids, vecs = [], []
            for r in rows:
                ids.append(r["item_id"])
                blob = r["embedding"]
                if blob and len(blob) // 4 == r["dim"]:
                    vecs.append(np.frombuffer(blob, dtype=np.float32))
                else:
                    vecs.append(np.zeros(r["dim"], dtype=np.float32))
            M = np.stack(vecs)
            qn = np.linalg.norm(q) + 1e-12
            Mn = np.linalg.norm(M, axis=1) + 1e-12
            sims = (M @ q) / (Mn * qn)
            order = np.argsort(-sims)[:k]
            return [(ids[i], float(sims[i])) for i in order]

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM vec_items")
            c.commit()

    def count(self) -> int:
        if not self._db_path:
            return 0
        with self._conn() as c:
            return c.execute("SELECT count(*) FROM vec_items").fetchone()[0]


def _pack_vec0(vec: np.ndarray) -> str:
    """vec0 接受 JSON / packed binary float32 字符串。

    Qwen3 dim=1024 用 JSON 字符串最简单（不依赖 numpy.tolist 重载），size ≈ 8 KB / 行。
    生产 10 万行 × 8 KB ≈ 800 MB —— 改用 packed binary 也能一行直 drop。
    """
    return "[" + ",".join(f"{x:.6f}" for x in vec.tolist()) + "]"


class EntityEmbedder:
    """实体嵌入 + 检索高层封装（embedder + vector_store）。

    backend 默认走 settings.EMBEDDING_PROVIDER。
    """

    def __init__(self, embedder: Optional[TextEmbedder] = None,
                 store: Optional[VectorStore] = None,
                 db_path: Optional[str] = None,
                 backend: Optional[str] = None):
        if embedder is None:
            from config import settings
            backend = backend or settings.EMBEDDING_PROVIDER
            embedder = TextEmbedder(backend=backend)
        self.embedder = embedder
        if store is None:
            if db_path is None:
                db_path = _default_db_path()
            self.store = VectorStore(db_path=db_path, dim=self.embedder.dim)
        else:
            self.store = store

    def add_entity(self, entity_id: str, mention: str,
                   entity_type: str = "") -> None:
        text = f"{entity_type}:{mention}" if entity_type else mention
        v = self.embedder.embed([text])[0]
        self.store.add(entity_id, v)

    def similar_to(self, entity_id: str, k: int = 5) -> list[dict]:
        """返回与该 entity 最相似的 k 个 [{item_id, score}, ...]。

        第 18 批：直接复用 `store.search(query_item)` 路径：
        query 已在 store 内取出后，搜索全表取 top k+1，再过滤自身。
        """
        # 取出自身向量（一条 SQL）
        with self.store._conn() as c:
            row = c.execute(
                "SELECT embedding FROM vec_items WHERE item_id=?",
                (entity_id,)).fetchone()
        if not row or not row["embedding"]:
            return []
        # row["embedding"] 在 vec0 是 blob / json str，回退路径是 BLOB
        v = np.asarray(
            _unpack_row_embedding(row["embedding"], self.store.dim),
            dtype=np.float32)
        hits = self.store.search(v, k=k + 1)
        return [{"item_id": i, "score": s} for i, s in hits if i != entity_id][:k]


def _unpack_row_embedding(raw: object, dim: int) -> list[float]:
    """回退路径时 `_conn()` 返回的 embedding 是 BLOB；"""
    """vec0 路径这里返回 JSON 字符串，但 similar_to 不走 vec0 主路径（取自身向量）"""
    """为了保证 similar_to 也能在 vec0 路径上工作，统一反序列化。"""
    if isinstance(raw, str):
        import json as _json
        arr = _json.loads(raw)
        return [float(x) for x in arr][:dim]
    if isinstance(raw, (bytes, bytearray, memoryview)):
        v = np.frombuffer(raw, dtype=np.float32)
        return v[:dim].tolist()
    raise TypeError(f"unsupported embedding row type: {type(raw)}")
