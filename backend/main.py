from fastapi import FastAPI
from api import routes

app = FastAPI(title="AI Analyst", version="1.0.0")

app.include_router(routes.router, prefix="/api")
