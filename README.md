# vLLM Secure

A Docker container that serves LLMs as an OpenAI-compatible API with HTTPS reverse proxy, API key authentication, and automatic `<think>` tag stripping.

Built for GPU cloud providers (RunPod, AWS, Azure, GCP) and local workstations to provide a private attacker LLM for AI red teaming engagements.

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

- NVIDIA GPU with 24GB+ VRAM (see [GPU Sizing](#gpu-sizing) for model-specific requirements)
- NVIDIA Container Toolkit / GPU drivers on the host
- 80GB+ disk for model storage (downloaded on first boot, cached for subsequent runs)

## Configuration

All parameters are configurable via environment variables — no rebuild required.

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `deepseek-ai/DeepSeek-R1-Distill-Qwen-32B` | HuggingFace model ID |
| `MODEL_NAME` | `attacker` | Name exposed via `/v1/models` endpoint |
| `GPU_MEMORY` | `0.95` | GPU memory utilisation (0.0–1.0) |
| `MAX_MODEL_LEN` | `8192` | Maximum context window in tokens |
| `TENSOR_PARALLEL` | `1` | Number of GPUs for tensor parallelism |
| `QUANTIZATION` | *(empty)* | Quantization method: `awq`, `gptq`, `squeezellm` |
| `VLLM_API_KEY` | *(empty)* | API key — clients must send `Authorization: Bearer <key>` |
| `VLLM_EXTRA_ARGS` | *(empty)* | Any additional vLLM CLI flags |
| `HUGGING_FACE_HUB_TOKEN` | *(empty)* | HuggingFace token for gated models |

### Examples

```bash
# Defaults (DeepSeek-R1 32B, single GPU, FP16)
docker run -d --gpus all \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 -p 443:443 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure

# Different model
docker run -d --gpus all \
  -e MODEL=meta-llama/Llama-3.1-70B-Instruct \
  -e MODEL_NAME=llama70b \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure

# Dual GPU with quantization
docker run -d --gpus all \
  -e TENSOR_PARALLEL=2 \
  -e QUANTIZATION=awq \
  -e MAX_MODEL_LEN=16384 \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure

# Lower memory usage for smaller GPUs
docker run -d --gpus all \
  -e GPU_MEMORY=0.85 \
  -e MAX_MODEL_LEN=4096 \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure

# Extra vLLM flags
docker run -d --gpus all \
  -e VLLM_EXTRA_ARGS="--enforce-eager --dtype float16" \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -v /data/models:/workspace/models \
  deepcyberx/vllm-secure
```

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8080 | HTTP | For cloud proxy access (RunPod, load balancers). TLS is terminated upstream |
| 443 | HTTPS | For direct IP access with self-signed certificate |

## GPU Sizing

| GPU Setup | VRAM | Recommended Config |
|-----------|------|--------------------|
| 1x RTX 4090 (24GB) | 24GB | `QUANTIZATION=awq MAX_MODEL_LEN=8192` (32B models) |
| 2x RTX 4090 (24GB each) | 48GB | `TENSOR_PARALLEL=2` (32B FP16, or 70B AWQ) |
| 1x A100 (80GB) | 80GB | Default settings (32B FP16 with headroom) |
| 1x A6000 (48GB) | 48GB | Default settings (32B FP16) |
| 2x RTX 5090 (32GB each) | 64GB | `TENSOR_PARALLEL=2` (70B AWQ or 32B FP16 with large context) |

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

### Local Workstation

For running on a local machine with NVIDIA GPU(s). This avoids cloud costs and keeps everything on your network.

#### Prerequisites

1. **NVIDIA drivers** installed (check with `nvidia-smi`)
2. **Docker** with GPU support:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install docker.io nvidia-container-toolkit
   sudo systemctl restart docker

   # Verify GPU access
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```
3. **Storage**: ~80GB free for model cache (first download only)

#### Single RTX 4090 (24GB VRAM)

Not enough VRAM for FP16, so use AWQ 4-bit quantization (~18GB):

```bash
# Create model cache directory
mkdir -p /data/vllm-models

# Run with AWQ quantization
docker run -d --gpus all \
  --name vllm-secure \
  --restart unless-stopped \
  -e MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-32B \
  -e QUANTIZATION=awq \
  -e GPU_MEMORY=0.92 \
  -e MAX_MODEL_LEN=8192 \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -p 443:443 \
  -v /data/vllm-models:/workspace/models \
  deepcyberx/vllm-secure
```

> **Note**: AWQ quantization requires an AWQ-quantized model variant. Use a pre-quantized model like `TheBloke/DeepSeek-R1-Distill-Qwen-32B-AWQ` or let vLLM download and quantize on the fly if supported.

#### Dual RTX 4090 (48GB total VRAM)

Full FP16 precision with tensor parallelism across both GPUs:

```bash
docker run -d --gpus all \
  --name vllm-secure \
  --restart unless-stopped \
  -e MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-32B \
  -e TENSOR_PARALLEL=2 \
  -e GPU_MEMORY=0.92 \
  -e MAX_MODEL_LEN=8192 \
  -e VLLM_API_KEY=your-secret-key \
  -p 8080:8080 \
  -p 443:443 \
  -v /data/vllm-models:/workspace/models \
  deepcyberx/vllm-secure
```

#### Remote Access via SSH Tunnel

If your workstation is at home and you need to access it remotely (e.g. from a client site):

```bash
# From your laptop — tunnel local port 8080 to the workstation
ssh -L 8080:localhost:8080 user@your-workstation-ip

# Then use it locally as:
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer your-secret-key"
```

For persistent access, set up an SSH tunnel service or use a tool like [Tailscale](https://tailscale.com) for a private mesh VPN.

#### Expose via Cloudflare Tunnel (Optional)

If you need cloud tools (e.g. HumanBound) to reach your local server:

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# Quick tunnel (ephemeral URL, no account needed)
cloudflared tunnel --url http://localhost:8080
# Gives you: https://xxxx.trycloudflare.com

# Named tunnel (persistent, requires Cloudflare account)
cloudflared tunnel create vllm-secure
cloudflared tunnel route dns vllm-secure llm.yourdomain.com
cloudflared tunnel run vllm-secure
```

#### Management Commands

```bash
# View startup logs (wait for "Started server process" message)
docker logs -f vllm-secure

# Check GPU usage
nvidia-smi

# Stop
docker stop vllm-secure

# Start again (uses cached model)
docker start vllm-secure

# Update to latest image
docker pull deepcyberx/vllm-secure
docker stop vllm-secure && docker rm vllm-secure
# Then re-run the docker run command above
```

## Usage

### Authentication

All requests require the `Authorization: Bearer <VLLM_API_KEY>` header.

### List Models

```bash
curl http://<host>:8080/v1/models \
  -H "Authorization: Bearer your-secret-key"
```

### Chat Completion

```bash
curl http://<host>:8080/v1/chat/completions \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "attacker",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Health Check (filter proxy)

```bash
curl http://<host>:8080/health \
  -H "Authorization: Bearer your-secret-key"
```

Returns: `{"status": "ok", "filter": "think-tag-strip"}`

## Using with OpenAI-Compatible Tools

The API is fully OpenAI-compatible. Configure any tool that supports custom OpenAI endpoints:

```
OPENAI_API_KEY=your-secret-key
OPENAI_API_BASE=http://<host>:8080/v1
```

The model is served as `attacker` by default (configurable via `MODEL_NAME`).

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
