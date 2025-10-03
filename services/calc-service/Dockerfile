FROM python:3.11-slim
WORKDIR /app

# Ускорители
ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Копируем общую библиотеку из дополнительного контекста libs
COPY --from=libs /zakupai_common /app/libs/zakupai_common
RUN pip install /app/libs/zakupai_common
# Общие сервисные утилиты
COPY --from=common / /app/services/common
ENV PYTHONPATH=/app:/app/services:/app/libs:${PYTHONPATH}
# Стандартный порт внутри контейнера
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
