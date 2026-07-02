from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import requests


class VideoProcessingError(RuntimeError):
    """视频下载、读取或抽帧失败。"""


@dataclass(frozen=True)
class FramePoint:
    timestamp_seconds: float
    minute_no: int
    frame_index: int


@dataclass(frozen=True)
class ExtractedFrame:
    point: FramePoint
    image: object


def build_frame_points(duration_seconds: float, interval_seconds: int = 30) -> List[FramePoint]:
    if duration_seconds <= 0 or interval_seconds <= 0:
        return []
    points: List[FramePoint] = []
    timestamp = interval_seconds / 2.0
    frame_index = 0
    while timestamp < duration_seconds:
        points.append(FramePoint(
            timestamp_seconds=float(timestamp),
            minute_no=int(timestamp // 60),
            frame_index=frame_index,
        ))
        timestamp += interval_seconds
        frame_index += 1
    return points


def download_video(
        url: str,
        destination: Path,
        timeout_seconds: int = 60,
        progress_callback: Optional[Callable[[], None]] = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            with destination.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        _notify_progress(progress_callback)
    except Exception as exc:
        raise VideoProcessingError(f"下载视频失败: {url}: {exc}") from exc
    if destination.stat().st_size <= 0:
        raise VideoProcessingError(f"下载视频为空: {url}")
    return destination


def get_video_duration_seconds(video_path: Path) -> float:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise VideoProcessingError(f"无法打开视频: {video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps and fps > 0 and frame_count and frame_count > 0:
            return float(frame_count / fps)
        milliseconds = capture.get(cv2.CAP_PROP_POS_MSEC)
        if milliseconds and milliseconds > 0:
            return float(milliseconds / 1000.0)
    finally:
        capture.release()
    raise VideoProcessingError(f"无法读取视频时长: {video_path}")


def extract_frame_at(video_path: Path, point: FramePoint):
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise VideoProcessingError(f"无法打开视频: {video_path}")
        capture.set(cv2.CAP_PROP_POS_MSEC, point.timestamp_seconds * 1000.0)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise VideoProcessingError(f"抽帧失败: {video_path} at {point.timestamp_seconds}s")
        return frame
    finally:
        capture.release()


def extract_frames(
        video_path: Path,
        interval_seconds: int = 30,
        progress_callback: Optional[Callable[[], None]] = None) -> List[ExtractedFrame]:
    duration = get_video_duration_seconds(video_path)
    frames = []
    for point in build_frame_points(duration, interval_seconds):
        frames.append(ExtractedFrame(point=point, image=extract_frame_at(video_path, point)))
        _notify_progress(progress_callback)
    if not frames:
        raise VideoProcessingError(f"视频无有效抽帧点: {video_path}")
    return frames


def _notify_progress(progress_callback: Optional[Callable[[], None]]) -> None:
    if progress_callback is not None:
        progress_callback()
