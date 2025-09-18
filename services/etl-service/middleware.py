from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class FileSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to check file size limits for upload endpoints"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only check file size for batch upload endpoint
        if request.url.path == "/etl/upload-batch" and request.method == "POST":
            content_length = request.headers.get("content-length")

            if content_length:
                content_length = int(content_length)
                if content_length > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB",
                    )

        response = await call_next(request)
        return response
