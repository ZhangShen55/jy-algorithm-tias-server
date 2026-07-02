FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONFIG_PATH=/workspace/ai_quality/config.toml

WORKDIR /workspace

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY ./tias/requirements.txt ./tias/requirements.txt
RUN pip install --no-cache-dir -r tias/requirements.txt

COPY ./ai_quality ./ai_quality
COPY ./tias/core ./tias/core
COPY ./tias/__init__.py ./tias/__init__.py

CMD ["python", "-m", "ai_quality.app", "serve"]
