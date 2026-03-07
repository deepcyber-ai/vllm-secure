# vLLM Secure

A Docker container that serves DeepSeek-R1-Distill-Qwen-32B as an OpenAI-compatible API with HTTPS reverse proxy, API key authentication, and automatic `<think>` tag stripping.

Built for GPU cloud providers (RunPod, AWS, Azure, GCP) to provide a private attacker LLM for AI red teaming engagements.

## Architecture

```
Client
  |
  v
nginx (port 8080 HTTP / port 443 HTTPS)
  |
  v
filter_proxy (port 8001) — strips <think>...</think> tags from DeepSeek-R1 responses
  |
  v
vLLM (port 8000) — serves the model as an OpenAI-compatible API
```

- **nginx** handles external access (TLS termination for direct IP, plain HTTP for cloud proxy)
- **filter_proxy** intercepts `/v1/chat/completions` responses and removes chain-of-thought `<think>` blocks that DeepSeek-R1 generates, which would otherwise corrupt JSON parsing in downstream tools
- **vLLM** serves the model with native `Authorization: Bearer` authentication via the `VLLM_API_KEY` environment variable

## Container Image

```
docker.io/deepcyberx/vllm-secure:latest
```

Pre-built for `linux/amd64` with CUDA 12.4.1.

## Requirements

- NVIDIA GPU with 40GB+ VRAM (e.g. A100 80GB, A6000 48GB, or 2x A6000)
- NVIDIA Container Toolkit / GPU drivers on the host
- 80GB+ disk for model storage (downloaded on first boot, cached for subsequent runs)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VLLM_API_KEY` | Yes | API key for authentication. Clients must send `Authorization: Bearer <key>` |
| `HUGGING_FACE_HUB_TOKEN` | No | HuggingFace token if using gated models |

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8080 | HTTP | For cloud proxy access (RunPod, load balancers). TLS is terminated upstream |
| 443 | HTTPS | For direct IP access with self-signed certificate |

## Deployment

### RunPod

1. Create a GPU Pod
2. Set **Container Image** to `docker.io/deepcyberx/vllm-secure`
3. Set **Container Disk** to 20GB+
4. Set **Volume Disk** to 80GB+ (mounted at `/workspace`)
5. Add environment variable `VLLM_API_KEY` with your chosen key
6. Expose **port 8080** (HTTP) and optionally **port 443** (HTTPS)
7. Start the pod

Access via: `https://<pod-id>-8080.proxy.runpod.net`

### AWS (ECS / EKS)

Run on a `p4d.24xlarge` (A100) or `g5.12xlarge` (A10G) instance:

```bash
docker run -d --gpus all \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -p 443:443 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure
```

### Azure (AKS / ACI)

Use a GPU-enabled node pool (e.g. `Standard_NC24ads_A100_v4`) or Azure Container Instances with GPU:

```bash
docker run -d --gpus all \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -p 443:443 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure
```

### GCP (GKE)

Use a node pool with `nvidia-tesla-a100` or `nvidia-l4` GPUs. Same `docker run` command as above.

## Usage

### Authentication

All requests require the `Authorization: Bearer <VLLM_API_KEY>` header.

### List Models

```bash
curl https://<host>:8080/v1/models \
  -H "Authorization: Bearer your-secret-key"
```

### Chat Completion

```bash
curl https://<host>:8080/v1/chat/completions \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "attacker",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Health Check (filter proxy)

```bash
curl https://<host>:8080/health \
  -H "Authorization: Bearer your-secret-key"
```

Returns: `{"status": "ok", "filter": "think-tag-strip"}`

## Using with OpenAI-Compatible Tools

The API is fully OpenAI-compatible. Configure any tool that supports custom OpenAI endpoints:

```
OPENAI_API_KEY=your-secret-key
OPENAI_API_BASE=https://<host>:8080/v1
```

The model is served as `attacker`.

## Model Details

| Property | Value |
|----------|-------|
| Model | deepseek-ai/DeepSeek-R1-Distill-Qwen-32B |
| Served Name | `attacker` |
| Max Context | 8192 tokens |
| GPU Memory | 95% utilisation |
| Parameters | 32B |

## First Boot

On first start, the container downloads the model from HuggingFace (~20GB). This is cached at `/workspace/models` on the persistent volume. Subsequent starts load from cache.

## Building from Source

```bash
git clone <repo>
cd vllm-secure

docker buildx build \
  --platform linux/amd64 \
  -t your-registry/vllm-secure \
  --push .
```

## Repository Layout

```
vllm-secure/
  Dockerfile          — Container build
  nginx.conf          — Reverse proxy config (HTTP + HTTPS)
  filter_proxy.py     — FastAPI proxy that strips <think> tags
  start.sh            — Entrypoint: starts vLLM, filter proxy, nginx
  test_strip_think.py — Unit tests for the think-tag filter
  README.md           — This file
```

## Customisation

### Change the model

Edit `start.sh` and replace the `--model` flag:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model your-org/your-model \
  --host 127.0.0.1 \
  --port 8000 \
  --served-model-name attacker \
  --gpu-memory-utilization 0.95 \
  --max-model-len 8192 &
```

### Disable think-tag filtering

Point nginx directly at vLLM (port 8000) instead of the filter proxy (port 8001) in `nginx.conf`.

### Add IP allowlisting

Add `allow` / `deny` directives to the nginx `location` block:

```nginx
location / {
    allow 1.2.3.4;
    deny all;
    proxy_pass http://127.0.0.1:8001;
    ...
}
```

(c) 2026 Deep Cyber Ltd. All rights reserved.
