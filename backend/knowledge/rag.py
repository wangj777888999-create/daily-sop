import logging
from typing import List, Optional
from .models import SearchResult, RAGRequest, RAGResponse
from .embedder import EmbeddingService
from .vector_store import VectorStore
from .generator import generate_with_context

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(self, embedder: EmbeddingService, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 5,
                 doc_ids: Optional[List[str]] = None) -> List[SearchResult]:
        query_embedding = self.embedder.embed_query(query)
        raw_results = self.vector_store.search(query_embedding, top_k=top_k, doc_ids=doc_ids)

        results = []
        for r in raw_results:
            results.append(SearchResult(
                doc_id=r["doc_id"],
                doc_name=r["doc_name"],
                doc_type="TXT",
                chunk_text=r["chunk_text"],
                chunk_type=r["chunk_type"],
                heading_path=r["heading_path"],
                score=r["score"],
                page=r["page"],
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

    def generate(self, request: RAGRequest, api_key: str = None) -> RAGResponse:
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
            api_key=api_key,
        )

        return RAGResponse(
            generated_text=generated_text,
            sources=sources,
        )
