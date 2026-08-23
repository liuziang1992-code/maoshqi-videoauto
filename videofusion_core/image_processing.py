from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError


Image.MAX_IMAGE_PIXELS = 50_000_000


class FrameValidationError(ValueError):
    pass


@dataclass
class PreparedFrame:
    index: int
    jpeg: bytes
    width: int
    height: int
    brightness_mean: float
    variation: float
    warnings: list[str]


def prepare_frame(
    raw: bytes,
    index: int,
    max_bytes: int,
    long_edge: int,
) -> PreparedFrame:
    if not raw:
        raise FrameValidationError(f"第{index}帧为空文件")

    if len(raw) > max_bytes:
        raise FrameValidationError(
            f"第{index}帧超过大小限制：{len(raw)} bytes"
        )

    try:
        with Image.open(BytesIO(raw)) as source:
            source.load()

            if source.width < 64 or source.height < 64:
                raise FrameValidationError(
                    f"第{index}帧尺寸过小：{source.size}"
                )

            warnings: list[str] = []

            if "A" in source.getbands():
                alpha = source.getchannel("A")
                alpha_range = alpha.getextrema()

                if alpha_range == (0, 0):
                    raise FrameValidationError(
                        f"第{index}帧完全透明"
                    )

                if alpha_range != (255, 255):
                    warnings.append(f"第{index}帧包含透明区域")

                background = Image.new("RGBA", source.size, "white")
                rgba = source.convert("RGBA")
                image = Image.alpha_composite(background, rgba).convert("RGB")
            else:
                image = source.convert("RGB")

    except FrameValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise FrameValidationError(
            f"第{index}帧无法解码：{exc}"
        ) from exc

    grayscale = image.convert("L")
    statistics = ImageStat.Stat(grayscale)
    brightness_mean = float(statistics.mean[0])
    variation = float(statistics.stddev[0])

    if variation < 2.0 and (
        brightness_mean < 8.0 or brightness_mean > 247.0
    ):
        raise FrameValidationError(
            f"第{index}帧接近纯黑或纯白"
        )

    if variation < 8.0:
        warnings.append(f"第{index}帧画面变化较少")

    image.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)

    output = BytesIO()
    image.save(output, "JPEG", quality=85, optimize=True)

    return PreparedFrame(
        index=index,
        jpeg=output.getvalue(),
        width=image.width,
        height=image.height,
        brightness_mean=round(brightness_mean, 2),
        variation=round(variation, 2),
        warnings=warnings,
    )


def duplicate_distance(
    first_jpeg: bytes,
    second_jpeg: bytes,
) -> float:
    with Image.open(BytesIO(first_jpeg)) as first:
        first_hash = first.convert("L").resize((32, 32))

    with Image.open(BytesIO(second_jpeg)) as second:
        second_hash = second.convert("L").resize((32, 32))

    difference = ImageChops.difference(first_hash, second_hash)
    return round(float(ImageStat.Stat(difference).rms[0]), 2)
