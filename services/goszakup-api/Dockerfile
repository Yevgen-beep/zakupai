# --- Base image ---
FROM python:3.11-slim

WORKDIR /app

# --- Dependencies ---
COPY services/goszakup-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --timeout 300 -i https://pypi.org/simple

# --- Copy application code (only the service) ---
COPY services/goszakup-api/ .

# --- Copy shared library from libs image ---
COPY --from=libs /zakupai_common /app/libs/zakupai_common
RUN pip install /app/libs/zakupai_common

# --- Environment setup ---
ENV PYTHONPATH=/app:/app/libs:${PYTHONPATH}

# --- Expose port for FastAPI ---
EXPOSE 8001

# --- Run service ---
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

