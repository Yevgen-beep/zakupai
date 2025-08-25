from fastapi import FastAPI, Header, HTTPException
import os

app = FastAPI(title="doc-service")

API_KEY = os.getenv("API_KEY", "changeme")

@app.get("/health")
def health():
    return {"status": "ok", "service": "doc-service"}

def check_api_key(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/info")
def info(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    check_api_key(x_api_key)
    return {"service": "doc-service", "message": "ready"}
