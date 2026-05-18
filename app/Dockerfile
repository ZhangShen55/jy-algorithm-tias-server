FROM pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime

LABEL authors="SeaCraft"

# 安装 Python3、pip 和常用依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends git jq curl nginx\
    libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# 设置工作目录
WORKDIR /app
COPY requirements.txt .
# 安装 Python 依赖
RUN pip3 install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --timeout 300 \
    --retries 5 \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt

# 拷贝代码和依赖
COPY ./app ./app
COPY config.json .
COPY start.sh .
# 拷贝nginx配置文件
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# 设置环境变量（如有需要）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 给予启动脚本执行权限
RUN chmod +x start.sh

# 暴露端口
EXPOSE 8881
CMD ["/bin/bash", "-c", "./start.sh"]
