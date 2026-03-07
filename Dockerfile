FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY frontend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY frontend ./frontend
COPY generator/catalog.json ./generator/catalog.json

EXPOSE 8080

CMD ["sh", "-c", "cd frontend && gunicorn app:app --bind 0.0.0.0:${PORT:-8080}"]
