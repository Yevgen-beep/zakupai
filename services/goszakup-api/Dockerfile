FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .
# Копируем общую библиотеку из дополнительного контекста libs
COPY --from=libs /zakupai_common /app/libs/zakupai_common
RUN pip install /app/libs/zakupai_common
ENV PYTHONPATH=/app:/app/libs:${PYTHONPATH}

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
