FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# git is needed at runtime by GitPython for the memory repo.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY cli ./cli

RUN pip install --upgrade pip \
 && pip install -e ".[cli]"

# Default data dirs; in production these are mounted from a volume.
RUN mkdir -p /data/memory

EXPOSE 8000

CMD ["uvicorn", "buddy.main:app", "--host", "0.0.0.0", "--port", "8000"]
