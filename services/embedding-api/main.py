from fastapi import FastAPI, Header, HTTPException
import os

app = FastAPI(title="embedding-api")
API_KEY = os.getenv("API_KEY", "changeme")

@app.get("/health")
def health():
    return {"status": "ok", "service": "embedding-api"}

def check_api_key(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.post("/embed")
def embed(payload: dict, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    check_api_key(x_api_key)
    text = payload.get("text", "")
    # Заглушка: возвращаем длину текста как "вектор"
    return {"vector": [len(text)], "dim": 1}
