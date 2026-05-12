import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api import routes
from api import knowledge_routes
from api import tool_routes
from knowledge.storage import load_all_chunks
from knowledge.indexer import BM25Index

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    index = BM25Index()
    chunks = load_all_chunks()
    if chunks:
        index.build(chunks)
    app.state.bm25_index = index
    logging.info(f"BM25 index ready: {index.chunk_count} chunks")
    yield


app = FastAPI(title="AI Analyst", version="2.0.0", lifespan=lifespan)

app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
app.include_router(tool_routes.router, prefix="/api")
