"""文本嵌入模块 — 使用 sentence-transformers 多语言模型（支持中文）"""
import logging
from typing import List

logger = logging.getLogger(__name__)

# 优先使用轻量多语言模型，首次运行会自动下载（约 280MB）
# paraphrase-multilingual-MiniLM-L12-v2：支持 50+ 语言，中文效果好，速度快
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded, dim=%d", _model.get_sentence_embedding_dimension())
    return _model


def embed(texts: List[str]) -> List[List[float]]:
    """将文本列表转为嵌入向量列表。"""
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


def embed_dim() -> int:
    """返回嵌入维度。"""
    return _get_model().get_sentence_embedding_dimension()
