FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RUNNER_TMP=/tmp RUNNER_SOCKET=/run/runner/runner.sock
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY runner ./runner
# Student code runs as this user, with no capabilities (docker-compose.yml drops them all).
RUN useradd --system --uid 10002 --no-create-home sandbox
USER sandbox
# No network at all (docker-compose.yml: network_mode none): the API reaches the runner through
# this Unix socket on a small shared volume. umask 0 lets the API's user connect to it.
HEALTHCHECK CMD python -m runner.healthcheck || exit 1
CMD ["sh", "-c", "umask 0000 && exec uvicorn runner.app:app --uds \"$RUNNER_SOCKET\""]
