FROM pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime

LABEL authors="SeaCraft"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
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

COPY ./tias/requirements.txt ./tias/requirements.txt
RUN pip3 install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --timeout 300 \
    --retries 5 \
    --trusted-host mirrors.aliyun.com \
    -r tias/requirements.txt

COPY ./tias ./tias
COPY ./tias/docker/nginx.conf /etc/nginx/nginx.conf

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONFIG_PATH=/workspace/tias/config.toml

RUN chmod +x tias/start.sh

EXPOSE 8881
CMD ["/bin/bash", "-c", "tias/start.sh"]
