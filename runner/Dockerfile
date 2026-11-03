FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RUNNER_TMP=/tmp
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY runner ./runner
# Student code runs as this user, with no capabilities (docker-compose.yml drops them all).
RUN useradd --system --uid 10002 --no-create-home sandbox
USER sandbox
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["uvicorn", "runner.app:app", "--host", "0.0.0.0", "--port", "8000"]
