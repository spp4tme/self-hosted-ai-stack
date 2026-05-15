FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl docker.io && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn

COPY webhook.py .

EXPOSE 9100

CMD ["python", "webhook.py"]
