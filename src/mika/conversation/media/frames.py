"""Decode a bounded chronological view of animated image bytes."""

from __future__ import annotations

import base64
import io

from PIL import Image, UnidentifiedImageError

_MAX_DIMENSION = 768
_ANIMATED_FRAME_MINIMUM = 2


def sample_animated_frames(
    data: bytes,
    *,
    max_frames: int = 4,
    max_dimension: int = _MAX_DIMENSION,
) -> tuple[str, ...]:
    """Return evenly spaced JPEG data URLs, or no frames for a static/invalid image."""
    if max_frames < _ANIMATED_FRAME_MINIMUM or not data:
        return ()
    try:
        with Image.open(io.BytesIO(data)) as source:
            frame_count = getattr(source, "n_frames", 1)
            if frame_count < _ANIMATED_FRAME_MINIMUM:
                return ()
            sample_count = min(frame_count, max_frames)
            indices = _even_indices(frame_count, sample_count)
            frames: list[str] = []
            for index in indices:
                source.seek(index)
                frame = source.convert("RGB")
                frame.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                frame.save(output, format="JPEG", quality=82, optimize=True)
                encoded = base64.b64encode(output.getvalue()).decode("ascii")
                frames.append(f"data:image/jpeg;base64,{encoded}")
            return tuple(frames)
    except (OSError, UnidentifiedImageError):
        return ()


def _even_indices(frame_count: int, sample_count: int) -> tuple[int, ...]:
    if sample_count == 1:
        return (0,)
    return tuple(
        round(index * (frame_count - 1) / (sample_count - 1)) for index in range(sample_count)
    )
