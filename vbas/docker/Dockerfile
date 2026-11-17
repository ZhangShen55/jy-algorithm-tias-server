FROM pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime

LABEL authors="SeaCraft"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        jq \
        curl \
        nginx \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

WORKDIR /workspace

COPY ./vbas/requirements.txt ./vbas/requirements.txt
RUN pip3 install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --timeout 300 \
    --retries 5 \
    --trusted-host mirrors.aliyun.com \
    -r vbas/requirements.txt

COPY ./vbas ./vbas
COPY ./scripts/build_cython_modules.py ./scripts/build_cython_modules.py
COPY ./vbas/docker/nginx.conf /etc/nginx/nginx.conf

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONFIG_PATH=/workspace/vbas/config.toml

RUN chmod +x vbas/start.sh
ARG PROTECT_SOURCE=0
RUN set -e; \
    if [ "$PROTECT_SOURCE" = "1" ]; then \
        python scripts/build_cython_modules.py \
          --root /workspace \
          --package vbas/api \
          --package vbas/core \
          --package vbas/services \
          --package vbas/schemas \
          --keep-source vbas/__init__.py \
          --keep-source vbas/main.py \
          --keep-source vbas/core/__init__.py \
          --keep-source vbas/api/__init__.py \
          --keep-source vbas/services/__init__.py \
          --keep-source vbas/schemas/__init__.py \
          --exclude-glob 'vbas/vendor/**' \
          --exclude-glob 'vbas/models/**' \
          --remove-sources; \
        rm -rf build; \
        find /workspace -type d -name '__pycache__' -prune -exec rm -rf {} +; \
    fi

EXPOSE 8881
CMD ["/bin/bash", "-c", "vbas/start.sh"]
