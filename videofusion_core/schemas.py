from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemporalStep(StrictModel):
    frames: str = Field(
        description="涉及的帧范围，例如1-2、3-4或5-6"
    )
    description: str = Field(
        description="该时间段内可见的动作或画面变化"
    )


class CameraInfo(StrictModel):
    shot_scale: str = Field(
        description="景别，例如特写、近景、中景、全景"
    )
    angle: str = Field(
        description="拍摄角度和机位"
    )
    movement: str = Field(
        description="固定、推拉、摇移、跟随或无法判断"
    )


class VisualQuality(StrictModel):
    clarity: str = Field(
        description="画面清晰度"
    )
    occlusion: str = Field(
        description="主体遮挡情况"
    )
    invalid_frames: list[int] = Field(
        default_factory=list,
        description="黑帧、白帧、透明帧或损坏帧编号"
    )
    usable: bool = Field(
        description="该片段是否适合进入剪辑素材库"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="影响使用的画面问题"
    )


class ClipAnalysis(StrictModel):
    summary: str = Field(
        description="视频片段内容概述"
    )
    scene: str = Field(
        description="场景、地点和环境"
    )
    subjects: list[str] = Field(
        description="主要人物、动物或物体"
    )
    sport: str | None = Field(
        default=None,
        description="运动项目，无法判断时为null"
    )
    actions: list[str] = Field(
        description="主体可见动作"
    )
    temporal_progression: list[TemporalStep] = Field(
        description="第1帧至第6帧的时间变化"
    )
    camera: CameraInfo
    visual_quality: VisualQuality
    editing_tags: list[str] = Field(
        description="用于检索和剪辑的中文标签"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="总体置信度"
    )


class AnalysisResponse(StrictModel):
    request_id: str
    project_id: str
    video_id: str
    clip_id: str
    model: str
    analysis: ClipAnalysis
    preprocessing_warnings: list[str] = Field(default_factory=list)
