"""冲突检测 —— 第八批：本体/三元组矛盾检测

对外暴露：
    - ConflictDetector：detect(triples, ontology_links?) -> list[conflict]


"""
from .detector import ConflictDetector

__all__ = ["ConflictDetector"]
