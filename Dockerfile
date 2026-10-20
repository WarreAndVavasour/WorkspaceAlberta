FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY mcp-servers/canadabuys/requirements.txt ./mcp-servers/canadabuys/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r mcp-servers/canadabuys/requirements.txt

COPY procurement_core ./procurement_core
COPY mcp-servers/canadabuys ./mcp-servers/canadabuys

WORKDIR /app/mcp-servers/canadabuys

# Run as an unprivileged user. The app writes only to $HOME/.canadabuys
# (CANADABUYS_DATA_DIR default) and /tmp; the code stays root-owned and read-only.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app
USER 10001:10001
ENV HOME=/home/app

ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn server_http:app --host 0.0.0.0 --port ${PORT}
