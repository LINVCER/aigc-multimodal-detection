"""
知识库：knowledge/*.md 按二级标题切块，内存 BM25 检索。

块格式（每个 .md）::

    # 文件标题
    tags: 检测原理, 校准          ← 文件级标签，可省
    ## 块标题
    正文 200-500 字……

几万字规模不值得上向量库；运营改 markdown 后调 reload() 或重启即生效。
"""
from __future__ import annotations

import glob
import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field

from .config import CONFIG

log = logging.getLogger("assistant.knowledge")

try:
    import jieba  # type: ignore
    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")
_STOP = set("的了是在和与或及等着过也都就而但把被让给对于为以及并且吗呢啊吧呀么什么怎么如何可以能不会有没")


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    if _HAS_JIEBA:
        toks = [t.strip() for t in jieba.lcut(text) if t.strip()]
    else:
        toks = _TOKEN_RE.findall(text)
    out = []
    for t in toks:
        if t in _STOP or len(t) == 0:
            continue
        out.append(t)
        # 中文词再拆字，提高短查询召回
        if len(t) >= 2 and all("一" <= c <= "鿿" for c in t):
            out.extend(list(t))
    return out


@dataclass
class Chunk:
    doc: str
    title: str
    text: str
    tags: list[str] = field(default_factory=list)
    tokens: Counter = field(default_factory=Counter)

    @property
    def ref(self) -> str:
        return f"{self.doc} › {self.title}"


class KnowledgeBase:
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self.chunks: list[Chunk] = []
        self._df: Counter = Counter()
        self._avgdl = 1.0
        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        chunks: list[Chunk] = []
        for path in sorted(glob.glob(os.path.join(self.directory, "*.md"))):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read()
            except OSError as e:
                log.warning("读取知识文件失败 %s: %s", path, e)
                continue
            chunks.extend(self._split(os.path.splitext(os.path.basename(path))[0], raw))
        self.chunks = chunks
        self._df = Counter()
        for c in chunks:
            c.tokens = Counter(_tokenize(c.title + " " + " ".join(c.tags) + " " + c.text))
            self._df.update(set(c.tokens))
        total = sum(sum(c.tokens.values()) for c in chunks)
        self._avgdl = (total / len(chunks)) if chunks else 1.0
        log.info("知识库加载：%d 文件 %d 块", len(set(c.doc for c in chunks)), len(chunks))

    @staticmethod
    def _split(doc: str, raw: str) -> list[Chunk]:
        tags: list[str] = []
        m = re.search(r"^tags:\s*(.+)$", raw, flags=re.M)
        if m:
            tags = [t.strip() for t in re.split(r"[,，、]", m.group(1)) if t.strip()]
        parts = re.split(r"^##\s+", raw, flags=re.M)
        out: list[Chunk] = []
        for part in parts[1:]:
            lines = part.strip().splitlines()
            if not lines:
                continue
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            if len(body) < 20:
                continue
            out.append(Chunk(doc=doc, title=title, text=body, tags=tags))
        return out

    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int | None = None, k1: float = 1.5, b: float = 0.75) -> list[tuple[Chunk, float]]:
        top_k = top_k or CONFIG.knowledge_top_k
        if not self.chunks or not query.strip():
            return []
        q = _tokenize(query)
        n = len(self.chunks)
        scored: list[tuple[Chunk, float]] = []
        for c in self.chunks:
            dl = sum(c.tokens.values()) or 1
            s = 0.0
            for term in set(q):
                tf = c.tokens.get(term, 0)
                if tf == 0:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                s += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self._avgdl))
            # 标题命中加权：问「红线」就该优先命中标题含「红线」的块
            if any(t in c.title.lower() for t in q if len(t) >= 2):
                s *= 1.3
            if s > 0:
                scored.append((c, s))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def format_context(self, hits: list[tuple[Chunk, float]], max_chars: int = 1800) -> str:
        parts, used = [], 0
        for c, _ in hits:
            block = f"【{c.ref}】\n{c.text}"
            if used + len(block) > max_chars:
                block = block[: max(0, max_chars - used)]
            if not block:
                break
            parts.append(block)
            used += len(block)
        return "\n\n".join(parts)


_KB: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase(CONFIG.knowledge_dir)
    return _KB
