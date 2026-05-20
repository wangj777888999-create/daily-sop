"""RAG Pipeline — BM25 + 向量混合检索，RRF 融合排名"""
import logging
from typing import List, Optional

from .models import SearchResult, RAGRequest, RAGResponse, DocType
from .indexer import BM25Index
from .vector_store import VectorStore, COLLECTION_NAMES
from .generator import generate_with_context
from .storage import get_doc

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF 平滑常数，标准值


def _rrf_score(rank: int) -> float:
    return 1.0 / (rank + RRF_K)


def _rrf_merge(
    bm25_results: List[dict],
    vector_results: List[dict],
    top_k: int = 5,
) -> List[dict]:
    """
    倒数排名融合：两路各自按排名打分，相加后取 top_k。
    chunk 唯一键为 chunk id（doc_id + chunk_index 拼接）。
    最终对同一文档的相邻 chunk 去重，保留分数更高的一个。
    """
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    def _chunk_key(r: dict) -> str:
        return f"{r.get('doc_id', '')}_{r.get('chunk_index', 0)}"

    # BM25 贡献
    for rank, r in enumerate(bm25_results):
        key = _chunk_key(r)
        scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
        if key not in meta:
            meta[key] = {**r, "bm25_rank": rank, "vector_rank": None}

    # 向量贡献
    for rank, r in enumerate(vector_results):
        key = _chunk_key(r)
        scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
        if key not in meta:
            meta[key] = {**r, "bm25_rank": None, "vector_rank": rank}
        else:
            meta[key]["vector_rank"] = rank

    # 合并排序（先取 top_k * 2 供去重后再裁剪）
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    candidates = []
    for key, score in ranked[:top_k * 2]:
        item = {**meta[key], "rrf_score": round(score, 6)}
        candidates.append(item)

    # 相邻 chunk 去重：同一文档内，连续 chunk_index 只保留分数最高的
    results: List[dict] = []
    kept: set[str] = set()   # "doc_id_chunkIdx" already kept
    for item in candidates:
        doc_id = item.get("doc_id", "")
        idx = int(item.get("chunk_index", 0))
        # 如果紧邻的 chunk（±1）已经保留，跳过当前
        adj_kept = (
            f"{doc_id}_{idx - 1}" in kept or
            f"{doc_id}_{idx + 1}" in kept
        )
        if adj_kept:
            continue
        key = f"{doc_id}_{idx}"
        kept.add(key)
        results.append(item)
        if len(results) >= top_k:
            break

    return results


class RAGPipeline:
    """混合检索 RAG 管道：BM25 + 向量，RRF 融合，按分类隔离。"""

    def __init__(self, bm25_index: BM25Index, vector_store: VectorStore):
        self.bm25 = bm25_index
        self.vector = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        doc_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        混合检索。
        - category: 限定某分类（policy/activity/data），None 表示跨全库
        - doc_ids: 进一步限定到特定文档
        """
        bm25_top = top_k * 4  # 两路各取更多候选，融合后取 top_k

        # ── BM25 ──
        bm25_raw = self.bm25.search(
            query, top_k=bm25_top,
            doc_ids=doc_ids,
            category=category,
        )

        # ── 向量 ──
        if category and category in COLLECTION_NAMES:
            vector_raw = self.vector.search(
                query, category=category,
                top_k=bm25_top, doc_ids=doc_ids,
            )
        else:
            vector_raw = self.vector.search_multi_category(
                query, top_k=bm25_top, doc_ids=doc_ids,
            )

        # ── RRF 融合 ──
        merged = _rrf_merge(bm25_raw, vector_raw, top_k=top_k)

        # ── 组装 SearchResult ──
        unique_ids = {r.get("doc_id") for r in merged if r.get("doc_id")}
        doc_map = {doc_id: get_doc(doc_id) for doc_id in unique_ids}

        results = []
        for r in merged:
            doc = doc_map.get(r.get("doc_id", ""))
            results.append(SearchResult(
                doc_id=r.get("doc_id", ""),
                doc_name=r.get("doc_name", doc.name if doc else ""),
                doc_type=doc.type if doc else DocType.TXT,
                chunk_text=r.get("text", ""),
                chunk_type=r.get("chunk_type", "paragraph"),
                heading_path=r.get("heading_path", ""),
                score=r.get("rrf_score", 0.0),
                page=r.get("page", 0),
            ))
        return results

    def build_context(self, results: List[SearchResult]) -> str:
        if not results:
            return ""
        parts = ["<reference_documents>"]
        for i, r in enumerate(results, 1):
            location = r.heading_path or "正文"
            parts.append(
                f"[{i}] {r.doc_name} — {location}\n"
                f"内容：{r.chunk_text}\n"
            )
        parts.append("</reference_documents>")
        return "\n".join(parts)

    def generate(self, request: RAGRequest) -> RAGResponse:
        results = self.retrieve(
            request.prompt,
            top_k=request.top_k,
            category=request.category,
            doc_ids=request.doc_ids or None,
        )
        context = self.build_context(results)
        generated_text, sources = generate_with_context(
            prompt=request.prompt,
            context_chunks=context,
            style=request.style,
        )
        return RAGResponse(generated_text=generated_text, sources=sources)
