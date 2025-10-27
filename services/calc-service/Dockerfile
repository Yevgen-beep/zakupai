FROM python:3.11-slim

WORKDIR /app

# Ускорители
ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/calc-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --timeout 300 -i https://pypi.org/simple

COPY services/calc-service/ .

# Копируем общую библиотеку из корня проекта
COPY libs/zakupai_common /app/libs/zakupai_common
RUN pip install /app/libs/zakupai_common

# Ключевая правка: чтобы Python видел /app/libs/
ENV PYTHONPATH=/app:/app/services:/app/libs:${PYTHONPATH}

# Внутренний порт — 8000, внешний уже проброшен в docker-compose (7001:8000)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

