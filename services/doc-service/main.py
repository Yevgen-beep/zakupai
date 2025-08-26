import os

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="doc-service")

API_KEY = os.getenv("API_KEY", "changeme")


@app.get("/health")
def health():
    return {"status": "ok", "service": "doc-service"}


def check_api_key(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def generate_tldr(text: str) -> str:
    """Simple TL;DR generation for testing"""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return "No content provided."

    # Take first 3 lines or first 150 characters
    summary_lines = lines[:3]
    summary = " ".join(summary_lines)

    if len(summary) > 150:
        summary = summary[:147] + "..."

    return f"TL;DR: {summary}"


@app.get("/info")
def info(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    check_api_key(x_api_key)
    return {"service": "doc-service", "message": "ready"}


@app.post("/tldr")
def tldr_endpoint(
    request: dict, x_api_key: str | None = Header(default=None, alias="X-API-Key")
):
    check_api_key(x_api_key)
    text = request.get("text", "")
    summary = generate_tldr(text)
    return {"tldr": summary}
