FROM python:3.11-slim
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/embedding-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries
COPY libs/zakupai_common /app/libs/zakupai_common
RUN pip install --no-cache-dir /app/libs/zakupai_common

# Copy application code
COPY services/embedding-api/ .
ENV PYTHONPATH=/app:/app/libs:${PYTHONPATH}
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000"]
