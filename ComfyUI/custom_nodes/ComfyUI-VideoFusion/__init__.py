import asyncio
import json
import os
import sys
import uuid
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

CLOUD_ROOT = Path(__file__).resolve().parents[3]
if str(CLOUD_ROOT) in sys.path:
    sys.path.remove(str(CLOUD_ROOT))
if True:
    sys.path.insert(0, str(CLOUD_ROOT))

from videofusion_core.image_processing import (
    FrameValidationError,
    duplicate_distance,
    prepare_frame,
)
from videofusion_core.schemas import AnalysisResponse
from videofusion_core.vllm_client import VLLMClientError, analyze_frames


def tensor_to_png(image_tensor) -> bytes:
    tensor = image_tensor[0].detach().cpu().numpy()
    array = np.clip(tensor * 255.0, 0, 255).astype(np.uint8)

    if array.shape[-1] == 4:
        image = Image.fromarray(array, "RGBA")
    else:
        image = Image.fromarray(array[..., :3], "RGB")

    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class VideoFusionSixFrameAnalyzer:
    CATEGORY = "VideoFusion"
    FUNCTION = "analyze"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("analysis_json",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "frame_01": ("IMAGE",),
                "project_id": (
                    "STRING",
                    {"default": "project-001"},
                ),
                "video_id": (
                    "STRING",
                    {"default": "video-001"},
                ),
                "clip_id": (
                    "STRING",
                    {"default": "clip-0001"},
                ),
                "analysis_prompt": (
                    "STRING",
                    {
                        "default": (
                            "请分析输入画面中的主体、场景、动作、"
                            "时间变化和适合剪辑的内容。"
                        ),
                        "multiline": True,
                    },
                ),
            },
            "optional": {
                "frame_02": ("IMAGE",),
                "frame_03": ("IMAGE",),
                "frame_04": ("IMAGE",),
                "frame_05": ("IMAGE",),
                "frame_06": ("IMAGE",),
                "frame_07": ("IMAGE",),
                "frame_08": ("IMAGE",),
            },
        }

    async def analyze(
        self,
        frame_01,
        project_id,
        video_id,
        clip_id,
        analysis_prompt,
        frame_02=None,
        frame_03=None,
        frame_04=None,
        frame_05=None,
        frame_06=None,
        frame_07=None,
        frame_08=None,
    ):
        tensors = [
            frame_01,
            frame_02,
            frame_03,
            frame_04,
            frame_05,
            frame_06,
            frame_07,
            frame_08,
        ]

        max_bytes = int(os.environ.get(
            "VIDEOFUSION_MAX_IMAGE_BYTES",
            "15728640",
        ))
        long_edge = int(os.environ.get(
            "VIDEOFUSION_IMAGE_LONG_EDGE",
            "1024",
        ))

        prepared = []
        warnings = []

        for index, tensor in enumerate(tensors, 1):
            if tensor is None:
                continue
            try:
                frame = prepare_frame(
                    tensor_to_png(tensor),
                    index=index,
                    max_bytes=max_bytes,
                    long_edge=long_edge,
                )
            except FrameValidationError as exc:
                raise RuntimeError(str(exc)) from exc

            prepared.append(frame.jpeg)
            warnings.extend(frame.warnings)

        if not prepared:
            raise RuntimeError("至少需要连接 frame_01")

        for index in range(1, len(prepared)):
            distance = duplicate_distance(
                prepared[index - 1],
                prepared[index],
            )
            if distance < 1.0:
                warnings.append(
                    f"第{index}帧与第{index + 1}帧可能重复"
                )

        try:
            analysis, _usage = await analyze_frames(
            prepared,
            analysis_prompt,
        )
        except VLLMClientError as exc:
            raise RuntimeError(str(exc)) from exc

        response = AnalysisResponse(
            request_id=str(uuid.uuid4()),
            project_id=project_id,
            video_id=video_id,
            clip_id=clip_id,
            model=os.environ.get(
                "VIDEOFUSION_MODEL_NAME",
                "videofusion-qwen3-vl",
            ),
            analysis=analysis,
            preprocessing_warnings=warnings,
        )

        result = json.dumps(
            response.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        return {
            "ui": {"text": [result]},
            "result": (result,),
        }


class VideoFusionJsonOutput:
    CATEGORY = "VideoFusion"
    FUNCTION = "show"
    RETURN_TYPES = ()
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "analysis_json": (
                    "STRING",
                    {"forceInput": True},
                ),
            }
        }

    def show(self, analysis_json):
        return {
            "ui": {
                "text": [analysis_json],
            }
        }


NODE_CLASS_MAPPINGS = {
    "VideoFusionSixFrameAnalyzer": VideoFusionSixFrameAnalyzer,
    "VideoFusionJsonOutput": VideoFusionJsonOutput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoFusionSixFrameAnalyzer": "VideoFusion 自适应帧分析（1-8帧）",
    "VideoFusionJsonOutput": "VideoFusion JSON 输出",
}
