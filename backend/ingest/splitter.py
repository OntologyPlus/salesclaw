"""文本切分 —— 「基类 + 按策略注册 + 每步自带溯源」

本模块不调 LLM，纯规则切分，可离线运行与测试。切分出的每段都携带
SourceReference，供上游 ingest 管线挂 provenance。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from provenance.schemas import SourceReference


@dataclass
class Chunk:
    chunk_id: str
    index: int
    text: str
    source: SourceReference
    metadata: dict = field(default_factory=dict)


class TextSplitter:
    """按空行/标题切分为语义块；长块再按句边界二次切分。"""

    _TITLE_RE = re.compile(r"^\s*(#{1,6}\s+.+|第[一二三四五六七八九十\d]+[章节节条]\s*.+)\s*$")
    _SENT_RE = re.compile(r"[。！？!?\n]")

    def __init__(self, max_chunk_chars: int = 800):
        self.max_chunk_chars = max_chunk_chars

    def split(self, text: str, source: SourceReference) -> list[Chunk]:
        raw_blocks = self._split_blocks(text)
        chunks: list[Chunk] = []
        idx = 0
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue
            for piece in self._enforce_size(block):
                chunks.append(
                    Chunk(chunk_id=f"chunk:{idx}", index=idx, text=piece, source=source)
                )
                idx += 1
        return chunks

    # ── 内部 ──
    def _split_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        buf: list[str] = []
        for line in text.splitlines():
            if self._TITLE_RE.match(line) and buf:
                blocks.append("\n".join(buf))
                buf = []
            buf.append(line)
        if buf:
            blocks.append("\n".join(buf))
        # 若没有任何分块（纯文本无空行），整体作为一块
        return blocks or [text]

    def _enforce_size(self, block: str) -> list[str]:
        if len(block) <= self.max_chunk_chars:
            return [block]
        pieces: list[str] = []
        cur = ""
        for sent in self._SENT_RE.split(block):
            sent = sent.strip()
            if not sent:
                continue
            if cur and len(cur) + len(sent) > self.max_chunk_chars:
                pieces.append(cur)
                cur = sent
            else:
                cur = (cur + " " + sent).strip()
        if cur:
            pieces.append(cur)
        return pieces or [block]
