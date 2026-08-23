import base64
import os
from typing import Any

import httpx

from videofusion_core.schemas import ClipAnalysis


class VLLMClientError(RuntimeError):
    pass


def strip_json_fence(content: str) -> str:
    value = content.strip()

    if value.startswith("```json"):
        value = value[7:]
    elif value.startswith("```"):
        value = value[3:]

    if value.endswith("```"):
        value = value[:-3]

    return value.strip()


def build_content(
    jpegs: list[bytes],
    analysis_prompt: str,
) -> list[dict[str, Any]]:
    user_prompt = analysis_prompt.strip()
    if not user_prompt:
        raise VLLMClientError("analysis_prompt不能为空")

    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            "以下是同一个视频片段按时间顺序抽取的8帧。"
            "必须联合分析全部8帧，不要把它们当成无关图片。"
        ),
    }]

    for index, jpeg in enumerate(jpegs, 1):
        encoded = base64.b64encode(jpeg).decode("ascii")
        content.extend([
            {
                "type": "text",
                "text": f"第{index}帧：",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded}",
                },
            },
        ])

    content.append({
        "type": "text",
        "text": (
            "用户本次分析要求：\\n"
            f"{user_prompt}\\n\\n"
            "只描述八帧中有证据支持的内容，不要虚构声音、"
            "人物身份、比赛结果或画面外事件。"
            "temporal_progression必须按帧范围描述变化。"
            "editing_tags使用简洁中文。"
            "只返回符合指定协议的JSON对象。"
        ),
    })

    return content


async def analyze_frames(
    jpegs: list[bytes],
    analysis_prompt: str,
) -> tuple[ClipAnalysis, dict[str, Any] | None]:
    if len(jpegs) != 8:
        raise VLLMClientError(
            f"请求必须包含8帧，实际为{len(jpegs)}帧"
        )

    base_url = os.environ.get(
        "VIDEOFUSION_VLLM_URL",
        "http://127.0.0.1:8000",
    ).rstrip("/")
    model = os.environ.get(
        "VIDEOFUSION_MODEL_NAME",
        "videofusion-qwen3-vl",
    )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": build_content(jpegs, analysis_prompt),
        }],
        "temperature": 0,
        "max_tokens": 3600,
        "chat_template_kwargs": {
            "enable_thinking": False,
        },
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "clip_analysis",
                "strict": True,
                "schema": ClipAnalysis.model_json_schema(),
            },
        },
    }

    timeout = httpx.Timeout(
        connect=10,
        read=600,
        write=120,
        pool=10,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
            )

            if response.status_code == 400:
                payload["response_format"] = {
                    "type": "json_object",
                }
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json=payload,
                )

            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise VLLMClientError(
            f"vLLM HTTP {exc.response.status_code}: "
            f"{exc.response.text[:1500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise VLLMClientError(
            f"无法连接vLLM：{exc}"
        ) from exc

    try:
        content = data["choices"][0]["message"]["content"]
        analysis = ClipAnalysis.model_validate_json(
            strip_json_fence(content)
        )
    except Exception as exc:
        raise VLLMClientError(
            f"模型返回内容不符合JSON协议：{exc}"
        ) from exc

    return analysis, data.get("usage")
