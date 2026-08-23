"""RAG 检索包 - 统一入口

对外暴露：
- EnhancedRAGRetriever / RAGRetriever：检索器类
- retrieve：模块级便捷函数（内部复用单例 RAGRetriever 实例）

业务实现见 `retriever.py`，本文件仅作包门面（facade）。
"""
from .retriever import EnhancedRAGRetriever, RAGRetriever

# 模块级单例：避免每次调用都重建 TfidfVectorizer（含 fit 缓存）
_retriever_instance = None


def retrieve(query: str, tenant_id, db, top_k: int = 5) -> list[dict]:
    """模块级检索便捷函数。

    供 `ai.tools.registry` 等调用方使用 `from ai.rag import retrieve`。
    复用进程内单例 RAGRetriever，保留 B6 的 fit 缓存。
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
    return _retriever_instance.retrieve(query, tenant_id, db, top_k=top_k)


__all__ = ["EnhancedRAGRetriever", "RAGRetriever", "retrieve"]
