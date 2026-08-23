"""去重 —— 第八批：实体/三元组合并

对外暴露：
    - EntityDeduper：基于 mention TF-IDF 余弦相似度 + 编辑距离，合并重复实体
    - 合并策略：keep_first / most_complete

"""
from .deduper import EntityDeduper, _edit_distance

__all__ = ["EntityDeduper", "_edit_distance"]
