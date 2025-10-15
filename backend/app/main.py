from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.routers import resolve, property as property_router, chat
from app import routes as api_routes

app = FastAPI(title="PropertyFish API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(resolve.router, prefix="/resolve", tags=["resolve"])
app.include_router(property_router.router)
app.include_router(property_router.legacy_router)
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(api_routes.router, prefix="/api", tags=["chat-query"])


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/version")
def version():
    return {"service": "propertyfish-chat", "env": os.getenv("ENV", "dev")}

@app.get("/")
def root():
    return {"ok": True, "service": "propertyfish"}
