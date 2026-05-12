import logging
from fastapi import FastAPI
from api import routes
from api import knowledge_routes
from knowledge.storage import load_all_chunks
from knowledge.indexer import BM25Index

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Analyst", version="2.0.0")


@app.on_event("startup")
async def startup():
    index = BM25Index()
    chunks = load_all_chunks()
    if chunks:
        index.build(chunks)
    app.state.bm25_index = index
    logging.info(f"BM25 index ready: {index.chunk_count} chunks")


app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
