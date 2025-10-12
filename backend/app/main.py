from fastapi import FastAPI
from app.routers import resolve, property as property_router, chat

app = FastAPI(title="PropertyFish API", version="0.1.0")

app.include_router(resolve.router, prefix="/resolve", tags=["resolve"])
app.include_router(property_router.router, prefix="/property", tags=["property"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

@app.get("/")
def root():
    return {"ok": True, "service": "propertyfish"}
