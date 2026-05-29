import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api import routes
from api import knowledge_routes
from api import tool_routes
from api import photo_checkin_routes
from api import yolo_training_routes
from api import settings_routes
from api import database_routes
from knowledge.storage import load_all_chunks
from knowledge.indexer import BM25Index
from knowledge.embedder import embed
from knowledge.vector_store import VectorStore
from settings_storage import load_settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 从 settings.json 加载 API Key 到环境变量
    settings = load_settings()
    api_key = settings.get("anthropic_api_key", "")
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        logging.info("ANTHROPIC_API_KEY loaded from settings.json")
    else:
        logging.warning("ANTHROPIC_API_KEY not configured — visit /settings to set it up")

    # 构建 BM25 索引
    index = BM25Index()
    chunks = load_all_chunks()
    if chunks:
        index.build(chunks)
    app.state.bm25_index = index
    logging.info(f"BM25 index ready: {index.chunk_count} chunks")

    # 初始化向量存储（ChromaDB，三个 collection）
    vector_store = VectorStore(embed_fn=embed)
    app.state.vector_store = vector_store
    logging.info(f"VectorStore ready: {vector_store.count()} vectors total")

    yield


app = FastAPI(title="AI Analyst", version="2.0.0", lifespan=lifespan)

app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
app.include_router(tool_routes.router, prefix="/api")
app.include_router(photo_checkin_routes.router, prefix="/api")
app.include_router(yolo_training_routes.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(database_routes.router, prefix="/api")
