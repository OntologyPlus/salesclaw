"""嵌入层 —— 第八批：实体/文本向量化与检索

当前生产配置：
    - TextEmbedder 后端：Qwen/Qwen3-Embedding-0.6B（modelscope SDK，
      last-token pooling + L2 normalize, dim=1024），fallback hash
    - VectorStore：SQLite 普通表（vec0 虚拟表已删除）+ Python numpy 算 cosine；
      路径走 settings.VEC_DB_PATH
    - EntityEmbedder：高层封装（add_entity / similar_to）

"""
from .embedder import TextEmbedder, VectorStore, EntityEmbedder

__all__ = ["TextEmbedder", "VectorStore", "EntityEmbedder"]
