"""语义推理层 —— 第八批：rdflib OWL 推理
对外暴露：
    - OntologyReasoner：把 ontology.registry 建模为 RDF/OWL + 类型层可达性推理
    - 与 ontology.chain.infer_relation_chain 互补（类型层 vs 实例层）

"""
from .ont_reasoner import OntologyReasoner, _EX

__all__ = ["OntologyReasoner", "_EX"]
