FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1 PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    pip install --prefer-binary --no-cache-dir -r requirements.txt

COPY . .
# Копируем общую библиотеку из дополнительного контекста libs
COPY --from=libs /zakupai_common /app/libs/zakupai_common

CMD ["python","/app/main.py"]
