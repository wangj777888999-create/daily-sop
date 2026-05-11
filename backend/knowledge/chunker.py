import re
from typing import List
from .models import ParsedDocument


def chunk_document(parsed: ParsedDocument, max_chunk_size: int = 500, overlap: int = 50) -> List[dict]:
    """
    Chinese document chunking optimized for policy/report documents:
    1. Respect heading/paragraph boundaries from parser
    2. Merge short adjacent paragraphs (<50 chars)
    3. Split long paragraphs (>500 chars) at sentence boundaries
    4. Each chunk carries heading_path for context
    5. Adjacent chunks have overlap
    """
    if not parsed.chunks:
        return []

    merged = _merge_short_chunks(parsed.chunks)
    result = []

    for i, chunk in enumerate(merged):
        text = chunk["text"]
        if len(text) <= max_chunk_size:
            result.append(_enrich_chunk(chunk, i))
        else:
            sub_chunks = _split_long_text(text, max_chunk_size, overlap)
            for j, sub_text in enumerate(sub_chunks):
                result.append({
                    "chunk_type": chunk["chunk_type"],
                    "level": chunk["level"],
                    "text": sub_text,
                    "page": chunk.get("page", 0),
                    "heading_path": chunk.get("heading_path", ""),
                    "chunk_index": len(result),
                })

    if overlap > 0:
        result = _add_overlap(result, overlap)

    for idx, c in enumerate(result):
        c["chunk_index"] = idx

    return result


def _merge_short_chunks(chunks: List[dict], min_len: int = 50) -> List[dict]:
    merged = []
    buffer = None

    for chunk in chunks:
        if buffer is None:
            buffer = dict(chunk)
            continue

        if len(buffer["text"]) < min_len or len(chunk["text"]) < min_len:
            buffer["text"] += "\n" + chunk["text"]
            if chunk["chunk_type"] == "heading" or buffer["chunk_type"] == "heading":
                buffer["chunk_type"] = "paragraph"
        else:
            merged.append(buffer)
            buffer = dict(chunk)

    if buffer is not None:
        merged.append(buffer)

    return merged


def _split_long_text(text: str, max_size: int, overlap: int) -> List[str]:
    """Split long text at sentence boundaries (。！？\n)"""
    sentences = re.split(r"(?<=[。！？\n])", text)
    chunks = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) <= max_size:
            current += sent
        else:
            if current:
                chunks.append(current.strip())
            current = sent

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_size]]


def _add_overlap(chunks: List[dict], overlap: int) -> List[dict]:
    for i in range(1, len(chunks)):
        prev_text = chunks[i - 1]["text"]
        if len(prev_text) > overlap:
            chunks[i]["text"] = prev_text[-overlap:] + "\n" + chunks[i]["text"]
    return chunks


def _enrich_chunk(chunk: dict, index: int) -> dict:
    return {
        "chunk_type": chunk.get("chunk_type", "paragraph"),
        "level": chunk.get("level", 0),
        "text": chunk.get("text", ""),
        "page": chunk.get("page", 0),
        "heading_path": chunk.get("heading_path", ""),
        "chunk_index": index,
    }
