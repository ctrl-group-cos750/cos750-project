FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
# Run as an unprivileged user: code that breaks out of the API process can't change the image.
RUN useradd --system --uid 10001 --no-create-home app
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
# Only our own proxies (Traefik, nginx; private Docker networks) may say who the client is, so
# X-Forwarded-For can't be faked from outside. See app/rate_limit.py: client_ip.
# Apply pending migrations, then serve. A failed migration stops the container, so a bad
# schema change fails the deploy instead of running against the wrong schema.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '10.0.0.0/8,172.16.0.0/12,192.168.0.0/16'"]
