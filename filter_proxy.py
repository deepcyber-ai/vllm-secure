import re
import json
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("think-filter")

app = FastAPI(title="DeepSeek Think Tag Filter Proxy")

VLLM_URL = "http://127.0.0.1:8000"


def strip_think(text: str) -> str:
    if not text or ("<think>" not in text and "</think>" not in text):
        return text

    original_len = len(text)
    # Strip complete <think>...</think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip unclosed <think> at end
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
    # Strip content before orphaned </think> (thinking leaked without opening tag)
    cleaned = re.sub(r"^.*?</think>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    chars_removed = original_len - len(cleaned)
    if chars_removed > 0:
        logger.warning("Stripped <think> block(s) (%d chars removed)", chars_removed)

    return cleaned


def extract_first_json(text: str) -> str:
    """Extract the first valid JSON object from text with trailing garbage.

    DeepSeek-R1 often outputs a valid JSON object then continues generating
    repeated fields (e.g. , "metadata": "...", "metadata": "...") or
    additional JSON objects. This extracts just the first complete object.

    Only activates when the (stripped) text starts with '{'. Plain text
    responses pass through unchanged.
    """
    if not text:
        return text

    trimmed = text.strip()
    if not trimmed.startswith("{"):
        return text

    # Fast path: already valid JSON
    try:
        json.loads(trimmed)
        return trimmed
    except json.JSONDecodeError:
        pass

    # Track brace depth to find end of first object
    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(trimmed):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = trimmed[: i + 1]
                try:
                    json.loads(candidate)
                    garbage = trimmed[i + 1 :].strip()
                    if garbage:
                        logger.warning(
                            "Extracted first JSON object, discarded %d chars of trailing output",
                            len(garbage),
                        )
                    return candidate
                except json.JSONDecodeError:
                    continue

    # Could not extract a valid object — return as-is
    return text


def forward_headers(request: Request) -> dict:
    return {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}


def clean_content(text: str) -> str:
    """Strip <think> tags then extract first JSON object if applicable."""
    text = strip_think(text)
    text = extract_first_json(text)
    return text


@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    payload = await request.json()
    headers = forward_headers(request)

    if payload.get("stream", False):
        return await proxy_chat_stream(payload, headers)

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(f"{VLLM_URL}/v1/chat/completions", json=payload, headers=headers)

    data = r.json()

    if "choices" in data:
        for choice in data["choices"]:
            if "message" in choice and "content" in choice["message"]:
                choice["message"]["content"] = clean_content(choice["message"]["content"])

    return data


async def proxy_chat_stream(payload: dict, headers: dict):
    async def generate():
        buffer = ""
        full_content = ""
        inside_think = False
        last_chunk = None

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{VLLM_URL}/v1/chat/completions", json=payload, headers=headers) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        yield line + "\n"
                        continue

                    data_str = line[6:]

                    if data_str.strip() == "[DONE]":
                        # At end of stream, apply JSON extraction to the
                        # accumulated content in case the model rambled
                        cleaned = extract_first_json(full_content)
                        if cleaned != full_content and last_chunk:
                            # Re-emit the full cleaned content as a final delta
                            last_chunk["choices"][0]["delta"]["content"] = cleaned
                            yield f"data: {json.dumps(last_chunk)}\n\n"
                            logger.warning(
                                "Stream JSON cleanup: replaced %d chars with %d",
                                len(full_content), len(cleaned),
                            )
                        elif buffer and not inside_think:
                            yield f"data: {buffer}\n\n"
                        yield "data: [DONE]\n\n"
                        continue

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")

                        if not delta:
                            yield line + "\n"
                            continue

                        for char in delta:
                            buffer += char
                            if buffer.endswith("<think>"):
                                buffer = buffer[:-7]
                                inside_think = True
                            if inside_think and buffer.endswith("</think>"):
                                buffer = buffer[:-8]
                                inside_think = False
                                logger.warning("Stripped <think> block from stream")

                        if not inside_think and buffer:
                            chunk["choices"][0]["delta"]["content"] = buffer
                            full_content += buffer
                            last_chunk = chunk
                            yield f"data: {json.dumps(chunk)}\n\n"
                            buffer = ""

                    except json.JSONDecodeError:
                        yield line + "\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok", "filter": "think-tag-strip,json-extract"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def passthrough(request: Request, path: str):
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.request(
            method=request.method,
            url=f"{VLLM_URL}/{path}",
            content=await request.body(),
            headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
        )
    return Response(content=r.content, status_code=r.status_code, headers=dict(r.headers))
