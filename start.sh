#!/bin/bash

set -e

export HF_HOME=/workspace/models
export HF_HUB_CACHE=/workspace/models
export TRANSFORMERS_CACHE=/workspace/models
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Starting vLLM server..."

python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/DeepSeek-R1-Distill-Qwen-32B \
  --host 127.0.0.1 \
  --port 8000 \
  --served-model-name attacker \
  --gpu-memory-utilization 0.95 \
  --max-model-len 8192 &

sleep 10

echo "Starting think-tag filter proxy..."

uvicorn filter_proxy:app --host 127.0.0.1 --port 8001 --app-dir /opt &

sleep 2

echo "Starting nginx reverse proxy..."

nginx -g "daemon off;"
