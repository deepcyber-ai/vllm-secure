#!/bin/bash

set -e

export HF_HOME=/workspace/models
export HF_HUB_CACHE=/workspace/models
export TRANSFORMERS_CACHE=/workspace/models
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Configurable via environment variables at docker run time
MODEL="${MODEL:-deepseek-ai/DeepSeek-R1-Distill-Qwen-32B}"
MODEL_NAME="${MODEL_NAME:-attacker}"
GPU_MEMORY="${GPU_MEMORY:-0.95}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
TENSOR_PARALLEL="${TENSOR_PARALLEL:-1}"
QUANTIZATION="${QUANTIZATION:-}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

echo "=== vLLM Secure Inference Server ==="
echo "Model:            $MODEL"
echo "Served as:        $MODEL_NAME"
echo "GPU memory util:  $GPU_MEMORY"
echo "Max context:      $MAX_MODEL_LEN tokens"
echo "Tensor parallel:  $TENSOR_PARALLEL"
[ -n "$QUANTIZATION" ] && echo "Quantization:     $QUANTIZATION"
[ -n "$VLLM_EXTRA_ARGS" ] && echo "Extra args:       $VLLM_EXTRA_ARGS"
echo "===================================="

QUANT_FLAG=""
if [ -n "$QUANTIZATION" ]; then
  QUANT_FLAG="--quantization $QUANTIZATION"
fi

echo "Starting vLLM server..."

python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --host 127.0.0.1 \
  --port 8000 \
  --served-model-name "$MODEL_NAME" \
  --gpu-memory-utilization "$GPU_MEMORY" \
  --max-model-len "$MAX_MODEL_LEN" \
  --tensor-parallel-size "$TENSOR_PARALLEL" \
  $QUANT_FLAG \
  $VLLM_EXTRA_ARGS &

sleep 10

echo "Starting think-tag filter proxy..."

uvicorn filter_proxy:app --host 127.0.0.1 --port 8001 --app-dir /opt &

sleep 2

echo "Starting nginx reverse proxy..."

nginx -g "daemon off;"
