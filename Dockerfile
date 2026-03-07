FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
    nginx \
    nano \
    tmux \
    git \
    curl \
    openssl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install vllm
RUN pip install fastapi httpx uvicorn

RUN mkdir -p /etc/nginx/ssl

RUN openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/server.key \
  -out /etc/nginx/ssl/server.crt \
  -subj "/C=GB/ST=London/L=London/O=AI/OU=Security/CN=localhost"

COPY nginx.conf /etc/nginx/nginx.conf
COPY filter_proxy.py /opt/filter_proxy.py
COPY start.sh /start.sh

RUN chmod +x /start.sh

ENV HF_HOME=/workspace/models
ENV HF_HUB_CACHE=/workspace/models
ENV TRANSFORMERS_CACHE=/workspace/models

WORKDIR /workspace

EXPOSE 443 8080

CMD ["/start.sh"]
