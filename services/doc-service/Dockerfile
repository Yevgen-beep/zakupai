FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/doc-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --timeout 300 -i https://pypi.org/simple

COPY services/doc-service/ .

# Копируем общую библиотеку из корня проекта
COPY libs/zakupai_common /app/libs/zakupai_common
RUN pip install /app/libs/zakupai_common

ENV PYTHONPATH=/app:/app/services:/app/libs:${PYTHONPATH}

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
