from __future__ import annotations

import argparse
import json
import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


FRAME_WIDTH = 192
FRAME_HEIGHT = 208
SHEET_COLUMNS = 8
SHEET_ROWS = 9
TARGET_MAX_WIDTH = 156
TARGET_MAX_HEIGHT = 184
TARGET_CENTER_X = 96
TARGET_BASELINE_Y = 196
ALPHA_THRESHOLD = 8


@dataclass(frozen=True, slots=True)
class MotionSource:
    name: str
    row: int
    frame_count: int
    alpha_strip: Path


@dataclass(frozen=True, slots=True)
class FrameStats:
    motion: str
    frame: int
    bbox: tuple[int, int, int, int]
    removed_components: int


def _component_mask(alpha: Image.Image) -> tuple[Image.Image, int]:
    width, height = alpha.size
    pixels = alpha.load()
    seen = [[False for _ in range(width)] for _ in range(height)]
    components: list[list[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if seen[y][x] or pixels[x, y] <= ALPHA_THRESHOLD:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen[y][x] = True
            component: list[tuple[int, int]] = []
            while queue:
                current_x, current_y = queue.popleft()
                component.append((current_x, current_y))
                for next_x, next_y in (
                    (current_x + 1, current_y),
                    (current_x - 1, current_y),
                    (current_x, current_y + 1),
                    (current_x, current_y - 1),
                ):
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and not seen[next_y][next_x]
                        and pixels[next_x, next_y] > ALPHA_THRESHOLD
                    ):
                        seen[next_y][next_x] = True
                        queue.append((next_x, next_y))
            components.append(component)

    if not components:
        return Image.new("L", alpha.size, 0), 0

    largest_area = max(len(component) for component in components)
    min_area = max(32, int(largest_area * 0.02))
    clean_mask = Image.new("L", alpha.size, 0)
    clean_pixels = clean_mask.load()
    removed = 0
    for component in components:
        if len(component) < min_area:
            removed += 1
            continue
        for x, y in component:
            clean_pixels[x, y] = 255
    return clean_mask, removed


def _clean_frame(frame: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int], int]:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    clean_mask, removed = _component_mask(alpha)
    bbox = clean_mask.getbbox()
    if bbox is None:
        raise ValueError("frame has no visible alpha content")
    cleaned = rgba.copy()
    cleaned.putalpha(Image.eval(alpha, lambda value: value if value > ALPHA_THRESHOLD else 0))
    cleaned.putalpha(Image.composite(cleaned.getchannel("A"), Image.new("L", alpha.size, 0), clean_mask))
    return cleaned, bbox, removed


def _split_strip(strip: Image.Image, frame_count: int) -> list[Image.Image]:
    width, height = strip.size
    frames: list[Image.Image] = []
    for index in range(frame_count):
        left = round(index * width / frame_count)
        right = round((index + 1) * width / frame_count)
        frames.append(strip.crop((left, 0, right, height)))
    return frames


def _normalize_motion(source: MotionSource) -> tuple[list[Image.Image], list[FrameStats]]:
    with Image.open(source.alpha_strip) as image:
        raw_frames = _split_strip(image.convert("RGBA"), source.frame_count)

    cleaned_frames: list[tuple[Image.Image, tuple[int, int, int, int], int]] = []
    for frame in raw_frames:
        cleaned_frames.append(_clean_frame(frame))

    max_width = max(bbox[2] - bbox[0] for _, bbox, _ in cleaned_frames)
    max_height = max(bbox[3] - bbox[1] for _, bbox, _ in cleaned_frames)
    scale = min(TARGET_MAX_WIDTH / max_width, TARGET_MAX_HEIGHT / max_height)

    normalized: list[Image.Image] = []
    stats: list[FrameStats] = []
    for index, (frame, bbox, removed) in enumerate(cleaned_frames, start=1):
        crop = frame.crop(bbox)
        scaled_size = (
            max(1, round(crop.width * scale)),
            max(1, round(crop.height * scale)),
        )
        resized = crop.resize(scaled_size, Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
        paste_x = round(TARGET_CENTER_X - resized.width / 2)
        paste_y = round(TARGET_BASELINE_Y - resized.height)
        cell.alpha_composite(resized, (paste_x, paste_y))
        final_bbox = cell.getchannel("A").point(lambda value: 255 if value > ALPHA_THRESHOLD else 0).getbbox()
        if final_bbox is None:
            raise ValueError(f"{source.name} frame {index} became empty after normalization")
        normalized.append(cell)
        stats.append(FrameStats(source.name, index, final_bbox, removed))
    return normalized, stats


def _motion_sources(base_dir: Path) -> list[MotionSource]:
    return [
        MotionSource("idle", 0, 6, base_dir / "idle" / "alpha" / "idle_strip_v01_alpha.png"),
        MotionSource(
            "running-right",
            1,
            8,
            base_dir / "running-right" / "alpha" / "running-right_strip_v01_alpha.png",
        ),
        MotionSource(
            "running-left",
            2,
            8,
            base_dir / "running-left" / "alpha" / "running-left_strip_v01_alpha.png",
        ),
        MotionSource("waving", 3, 4, base_dir / "waving" / "alpha" / "waving_strip_v01_alpha.png"),
        MotionSource("jumping", 4, 5, base_dir / "jumping" / "alpha" / "jumping_strip_v02_alpha.png"),
        MotionSource("failed", 5, 8, base_dir / "failed" / "alpha" / "failed_strip_v02_alpha.png"),
        MotionSource("waiting", 6, 6, base_dir / "waiting" / "alpha" / "waiting_strip_v02_alpha.png"),
        MotionSource("running", 7, 6, base_dir / "running" / "alpha" / "running_strip_v01_alpha.png"),
        MotionSource("review", 8, 6, base_dir / "review" / "alpha" / "review_strip_v01_alpha.png"),
    ]


def _unused_cells_are_transparent(atlas: Image.Image, counts_by_row: dict[int, int]) -> list[str]:
    errors: list[str] = []
    alpha = atlas.getchannel("A")
    for row in range(SHEET_ROWS):
        used = counts_by_row[row]
        for column in range(used, SHEET_COLUMNS):
            cell = alpha.crop(
                (
                    column * FRAME_WIDTH,
                    row * FRAME_HEIGHT,
                    (column + 1) * FRAME_WIDTH,
                    (row + 1) * FRAME_HEIGHT,
                )
            )
            if cell.getbbox() is not None:
                errors.append(f"row {row} column {column} is not transparent")
    return errors


def _write_reports(
    output_dir: Path,
    atlas_path: Path,
    stats: list[FrameStats],
    unused_errors: list[str],
) -> None:
    payload = {
        "atlas": str(atlas_path),
        "size": [SHEET_COLUMNS * FRAME_WIDTH, SHEET_ROWS * FRAME_HEIGHT],
        "grid": [SHEET_COLUMNS, SHEET_ROWS],
        "cell": [FRAME_WIDTH, FRAME_HEIGHT],
        "target": {
            "max_width": TARGET_MAX_WIDTH,
            "max_height": TARGET_MAX_HEIGHT,
            "center_x": TARGET_CENTER_X,
            "baseline_y": TARGET_BASELINE_Y,
        },
        "unused_cell_errors": unused_errors,
        "frames": [
            {
                "motion": stat.motion,
                "frame": stat.frame,
                "bbox": list(stat.bbox),
                "width": stat.bbox[2] - stat.bbox[0],
                "height": stat.bbox[3] - stat.bbox[1],
                "center_x": (stat.bbox[0] + stat.bbox[2]) / 2,
                "bottom": stat.bbox[3],
                "removed_components": stat.removed_components,
            }
            for stat in stats
        ],
    }
    (output_dir / "candidate_atlas_v01_geometry_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    grouped: dict[str, list[FrameStats]] = {}
    for stat in stats:
        grouped.setdefault(stat.motion, []).append(stat)

    lines = [
        "# 候选 atlas v01 统一整理 QA 记录",
        "",
        "## 处理性质",
        "",
        "本文件记录的是 atlas 前统一整理后的候选版结果，不是正式运行时通过版。",
        "",
        "## 整理动作",
        "",
        "- 输入来自九行已通过单行动作 QA 的 alpha strip。",
        "- 按 `192x208` 单格重新切帧。",
        "- 清理低 alpha 边缘与孤立小连通块。",
        "- 统一视觉最大高度、最大宽度、底部锚点与水平视觉中心。",
        "- 未使用格保持透明。",
        "",
        "## 几何统计",
        "",
        "| 动作 | 帧数 | 宽度范围 | 高度范围 | 顶部范围 | 底部范围 | 中心范围 | 清理碎片数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for motion, motion_stats in grouped.items():
        widths = [stat.bbox[2] - stat.bbox[0] for stat in motion_stats]
        heights = [stat.bbox[3] - stat.bbox[1] for stat in motion_stats]
        tops = [stat.bbox[1] for stat in motion_stats]
        bottoms = [stat.bbox[3] for stat in motion_stats]
        centers = [(stat.bbox[0] + stat.bbox[2]) / 2 for stat in motion_stats]
        removed = sum(stat.removed_components for stat in motion_stats)
        lines.append(
            f"| `{motion}` | {len(motion_stats)} | {min(widths)}-{max(widths)} | "
            f"{min(heights)}-{max(heights)} | {min(tops)}-{max(tops)} | "
            f"{min(bottoms)}-{max(bottoms)} | {min(centers):.1f}-{max(centers):.1f} | {removed} |"
        )
    lines.extend(
        [
            "",
            "## 自动 QA 结论",
            "",
            f"- atlas 尺寸目标：`1536x1872`。",
            f"- 网格目标：`8x9`，单格 `192x208`。",
            f"- 未用格透明检查：{'通过' if not unused_errors else '未通过'}。",
        ]
    )
    if unused_errors:
        lines.append("")
        lines.append("未用格问题：")
        for error in unused_errors:
            lines.append(f"- {error}")
    lines.extend(
        [
            "",
            "## 后续边界",
            "",
            "- 本候选版仍需人工视觉 QA。",
            "- 本候选版尚未做 PySide smoke test。",
            "- 只有几何 QA、视觉 QA 和 PySide smoke test 都通过后，才可称为正式可接入版。",
            "",
        ]
    )
    (output_dir / "candidate_atlas_v01_qa_2026-05-13.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def build_candidate_atlas(base_dir: Path, manifest_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGBA", (SHEET_COLUMNS * FRAME_WIDTH, SHEET_ROWS * FRAME_HEIGHT), (0, 0, 0, 0))
    all_stats: list[FrameStats] = []
    counts_by_row: dict[int, int] = {}

    for source in _motion_sources(base_dir):
        if not source.alpha_strip.exists():
            raise FileNotFoundError(source.alpha_strip)
        frames, stats = _normalize_motion(source)
        counts_by_row[source.row] = source.frame_count
        all_stats.extend(stats)
        for column, frame in enumerate(frames):
            atlas.alpha_composite(frame, (column * FRAME_WIDTH, source.row * FRAME_HEIGHT))

    atlas_path = output_dir / "candidate_spritesheet_v01.png"
    webp_path = output_dir / "candidate_spritesheet_v01.webp"
    manifest_copy = output_dir / "motion_manifest.json"
    atlas.save(atlas_path)
    atlas.save(webp_path, lossless=True, quality=100, method=6)
    shutil.copyfile(manifest_path, manifest_copy)
    unused_errors = _unused_cells_are_transparent(atlas, counts_by_row)
    _write_reports(output_dir, atlas_path, all_stats, unused_errors)
    return [
        atlas_path,
        webp_path,
        manifest_copy,
        output_dir / "candidate_atlas_v01_geometry_report.json",
        output_dir / "candidate_atlas_v01_qa_2026-05-13.md",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a normalized candidate atlas from motion trials.")
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    generated = build_candidate_atlas(args.base_dir, args.manifest, args.output)
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
