"""Bounded chronological frame sampling for animated media."""

from __future__ import annotations

import base64
import io

from PIL import Image

from mika.conversation.contracts import MediaAsset
from mika.conversation.media.frames import sample_animated_frames
from mika.conversation.media.sampler import TemporalMediaSampler, media_context


def _gif(frame_count: int = 7) -> bytes:
    frames = [Image.new("RGB", (8, 8), (index * 30, 0, 0)) for index in range(frame_count)]
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=20)
    return output.getvalue()


def test_sampler_picks_bounded_chronological_frames() -> None:
    frames = sample_animated_frames(_gif(), max_frames=4)

    assert len(frames) == 4
    assert all(frame.startswith("data:image/jpeg;base64,") for frame in frames)
    colors = []
    for frame in frames:
        encoded = frame.partition(",")[2]
        image = Image.open(io.BytesIO(base64.b64decode(encoded)))
        colors.append(image.getpixel((0, 0))[0])
    assert colors == sorted(colors)
    assert colors[0] < colors[-1]


async def test_temporal_sampler_expands_gif_but_keeps_static_url() -> None:
    async def fetch(url: str) -> tuple[bytes, str]:
        return _gif(), "image/gif"

    sampler = TemporalMediaSampler(fetch=fetch, max_frames=3)
    assets = (
        MediaAsset("gif", "https://cdn.test/a.gif", content_type="image/gif"),
        MediaAsset("image", "https://cdn.test/b.png", content_type="image/png"),
    )

    prepared = await sampler.prepare(assets)

    assert len(prepared) == 4
    assert prepared[:3] == tuple(value for value in prepared[:3] if value.startswith("data:"))
    assert prepared[-1] == "https://cdn.test/b.png"


def test_media_context_tells_model_sampled_frames_are_chronological() -> None:
    assets = (MediaAsset("gif", "https://cdn.test/a.gif", content_type="image/gif"),)

    context = media_context(assets)

    assert "chronological" in context
    assert "do not narrate" in context.casefold()
