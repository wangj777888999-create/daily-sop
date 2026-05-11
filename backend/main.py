import logging
from fastapi import FastAPI
from api import routes
from api import knowledge_routes

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Analyst", version="2.0.0")


@app.on_event("startup")
async def startup():
    logging.info("Loading embedding service...")
    from knowledge.embedder import get_embedding_service
    get_embedding_service()
    logging.info("Embedding service ready.")


app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
