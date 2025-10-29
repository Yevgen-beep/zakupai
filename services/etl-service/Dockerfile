FROM python:3.11-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/etl-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --timeout 300 -i https://pypi.org/simple

COPY services/etl-service/ .

# Копируем общую библиотеку из корня проекта
COPY libs/zakupai_common /app/libs/zakupai_common
RUN pip install /app/libs/zakupai_common

ENV PYTHONPATH=/app:/app/services:/app/libs:${PYTHONPATH}

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
