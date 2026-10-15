# SPDX-License-Identifier: Apache-2.0
# DX-FSM AI Service – FastAPI Application

from fastapi import FastAPI
from app.routes import classify, recommend, health

app = FastAPI(
    title="DX-FSM AI Service",
    description="AI-powered ticket classification and technician recommendation",
    version="1.1.0",
    docs_url="/docs",
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(classify.router, prefix="/classify", tags=["Classification"])
app.include_router(recommend.router, prefix="/recommend", tags=["Recommendation"])


@app.get("/")
async def root():
    return {"service": "DX-FSM AI Service", "version": "1.1.0", "status": "running"}
