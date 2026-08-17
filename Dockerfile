# CN-Social-Agent Workbench
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY skills/ ./skills/
COPY scripts/ ./scripts/
COPY pyproject.toml .
COPY run_workbench.py .
COPY README.md .

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV WORKBENCH_HOST=0.0.0.0
ENV WORKBENCH_PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "run_workbench.py"]
