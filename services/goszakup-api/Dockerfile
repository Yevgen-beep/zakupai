FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY services/goszakup-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries
COPY libs/zakupai_common /app/libs/zakupai_common
RUN pip install --no-cache-dir /app/libs/zakupai_common

# Копирование кода
COPY services/goszakup-api/ .
ENV PYTHONPATH=/app:/app/libs:${PYTHONPATH}

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
