#!/bin/bash

set -e

export HF_HOME=/workspace/models
export HF_HUB_CACHE=/workspace/models
export TRANSFORMERS_CACHE=/workspace/models
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Configurable via environment variables at docker run time
MODEL="${MODEL:-Qwen/Qwen3-32B}"
MODEL_NAME="${MODEL_NAME:-attacker}"
GPU_MEMORY="${GPU_MEMORY:-0.95}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
TENSOR_PARALLEL="${TENSOR_PARALLEL:-1}"
QUANTIZATION="${QUANTIZATION:-}"
REASONING_PARSER="${REASONING_PARSER:-}"
CHAT_TEMPLATE_KWARGS="${CHAT_TEMPLATE_KWARGS:-}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
ENABLE_FILTER="${ENABLE_FILTER:-false}"
ENABLE_NGINX="${ENABLE_NGINX:-false}"

echo "=== vLLM Secure Inference Server ==="
echo "Model:            $MODEL"
echo "Served as:        $MODEL_NAME"
echo "GPU memory util:  $GPU_MEMORY"
echo "Max context:      $MAX_MODEL_LEN tokens"
echo "Tensor parallel:  $TENSOR_PARALLEL"
echo "Filter proxy:     $ENABLE_FILTER"
echo "Nginx proxy:      $ENABLE_NGINX"
[ -n "$QUANTIZATION" ] && echo "Quantization:     $QUANTIZATION"
[ -n "$REASONING_PARSER" ] && echo "Reasoning parser: $REASONING_PARSER"
[ -n "$CHAT_TEMPLATE_KWARGS" ] && echo "Chat template:    $CHAT_TEMPLATE_KWARGS"
[ -n "$VLLM_EXTRA_ARGS" ] && echo "Extra args:       $VLLM_EXTRA_ARGS"
echo "===================================="

# Bind to 0.0.0.0 for direct TCP access; nginx/filter sit in front if enabled
VLLM_HOST="0.0.0.0"

# If filter or nginx are enabled, bind vLLM to localhost only
if [ "$ENABLE_FILTER" = "true" ] || [ "$ENABLE_NGINX" = "true" ]; then
  VLLM_HOST="127.0.0.1"
fi

# Build vLLM command as array for safe argument handling
VLLM_CMD=(
  python -m vllm.entrypoints.openai.api_server
  --model "$MODEL"
  --host "$VLLM_HOST"
  --port 8000
  --served-model-name "$MODEL_NAME"
  --gpu-memory-utilization "$GPU_MEMORY"
  --max-model-len "$MAX_MODEL_LEN"
  --tensor-parallel-size "$TENSOR_PARALLEL"
)

[ -n "$QUANTIZATION" ] && VLLM_CMD+=(--quantization "$QUANTIZATION")
[ -n "$REASONING_PARSER" ] && VLLM_CMD+=(--reasoning-parser "$REASONING_PARSER")
[ -n "$CHAT_TEMPLATE_KWARGS" ] && VLLM_CMD+=(--default-chat-template-kwargs "$CHAT_TEMPLATE_KWARGS")

# Split VLLM_EXTRA_ARGS on whitespace (intentional word-splitting for extra flags)
# shellcheck disable=SC2206
[ -n "$VLLM_EXTRA_ARGS" ] && VLLM_CMD+=($VLLM_EXTRA_ARGS)

echo "Starting vLLM server on $VLLM_HOST:8000..."

"${VLLM_CMD[@]}" &

sleep 10

# Optional: think-tag filter proxy (for DeepSeek/Qwen models)
if [ "$ENABLE_FILTER" = "true" ]; then
  echo "Starting think-tag filter proxy on :8001..."
  uvicorn filter_proxy:app --host 127.0.0.1 --port 8001 --app-dir /opt &
  sleep 2
else
  echo "Filter proxy disabled (set ENABLE_FILTER=true to enable)"
fi

# Optional: nginx reverse proxy
if [ "$ENABLE_NGINX" = "true" ]; then
  echo "Starting nginx reverse proxy..."
  nginx -g "daemon off;"
else
  echo "Nginx disabled (set ENABLE_NGINX=true to enable)"
  # Keep container alive — wait for vLLM
  wait
fi
