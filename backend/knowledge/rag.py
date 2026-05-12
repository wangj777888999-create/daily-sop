import logging
from typing import List, Optional
from .models import SearchResult, RAGRequest, RAGResponse
from .indexer import BM25Index
from .generator import generate_with_context
from .storage import get_doc

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(self, index: BM25Index):
        self.index = index

    def retrieve(self, query: str, top_k: int = 5,
                 doc_ids: Optional[List[str]] = None) -> List[SearchResult]:
        raw_results = self.index.search(query, top_k=top_k, doc_ids=doc_ids)

        unique_ids = {r.get("doc_id") for r in raw_results if r.get("doc_id")}
        doc_map = {doc_id: get_doc(doc_id) for doc_id in unique_ids}

        results = []
        for r in raw_results:
            doc = doc_map.get(r.get("doc_id", ""))
            results.append(SearchResult(
                doc_id=r.get("doc_id", ""),
                doc_name=r.get("doc_name", doc.name if doc else ""),
                doc_type=doc.type if doc else "TXT",
                chunk_text=r.get("text", ""),
                chunk_type=r.get("chunk_type", "paragraph"),
                heading_path=r.get("heading_path", ""),
                score=r.get("score", 0),
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
        if request.doc_ids and len(request.doc_ids) > 0:
            search_doc_ids = request.doc_ids
        else:
            search_doc_ids = None

        results = self.retrieve(request.prompt, top_k=request.top_k, doc_ids=search_doc_ids)
        context = self.build_context(results)
        generated_text, sources = generate_with_context(
            prompt=request.prompt,
            context_chunks=context,
            style=request.style,
        )

        return RAGResponse(
            generated_text=generated_text,
            sources=sources,
        )
