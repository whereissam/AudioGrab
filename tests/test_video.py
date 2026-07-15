"""Tests for the audio-to-video (YouTube-ready MP4) module."""

import json as _json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import FFmpegError
from app.core.video import (
    AudioToVideo,
    _default_output_path,
    _resolution_dims,
)


@pytest.fixture
def maker(monkeypatch):
    """AudioToVideo with ffmpeg/ffprobe presence faked."""
    monkeypatch.setattr("app.core.video.shutil.which", lambda name: f"/usr/bin/{name}")
    return AudioToVideo()


def test_default_output_path_derives_youtube_suffix():
    assert _default_output_path(Path("a/b/podcast.m4a")) == Path("a/b/podcast.youtube.mp4")


def test_default_output_path_handles_non_ascii_and_spaces():
    assert _default_output_path(Path("对话 周晨.m4a")) == Path("对话 周晨.youtube.mp4")


def test_resolution_dims_known():
    assert _resolution_dims("480p") == (854, 480)
    assert _resolution_dims("720p") == (1280, 720)
    assert _resolution_dims("1080p") == (1920, 1080)


def test_resolution_dims_unknown_raises():
    with pytest.raises(FFmpegError, match="Unsupported resolution"):
        _resolution_dims("240p")


def test_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr("app.core.video.shutil.which", lambda name: None)
    with pytest.raises(FFmpegError, match="not found in PATH"):
        AudioToVideo()


def test_maker_constructs_with_binaries(maker):
    assert maker._ffmpeg == "/usr/bin/ffmpeg"
    assert maker._ffprobe == "/usr/bin/ffprobe"


async def test_probe_audio_codec_selects_primary_stream(maker):
    payload = _json.dumps({"streams": [{"codec_name": "AAC"}]})
    maker._run = AsyncMock(return_value=(payload, "", 0))
    codec = await maker._probe_audio_codec(Path("in.m4a"))
    assert codec == "aac"  # normalized lowercase
    cmd = maker._run.call_args.args[0]
    assert "-select_streams" in cmd and "a:0" in cmd  # primary audio only


async def test_probe_audio_codec_no_stream_raises(maker):
    maker._run = AsyncMock(return_value=('{"streams": []}', "", 0))
    with pytest.raises(FFmpegError, match="No audio stream"):
        await maker._probe_audio_codec(Path("in.m4a"))


async def test_find_attached_cover_returns_index(maker):
    payload = _json.dumps({"streams": [
        {"index": 0, "codec_type": "audio", "disposition": {"attached_pic": 0}},
        {"index": 1, "codec_type": "video", "disposition": {"attached_pic": 1}},
    ]})
    maker._run = AsyncMock(return_value=(payload, "", 0))
    assert await maker._find_attached_cover(Path("in.m4a")) == 1


async def test_find_attached_cover_ignores_normal_video(maker):
    payload = _json.dumps({"streams": [
        {"index": 0, "codec_type": "audio", "disposition": {"attached_pic": 0}},
        {"index": 1, "codec_type": "video", "disposition": {"attached_pic": 0}},
    ]})
    maker._run = AsyncMock(return_value=(payload, "", 0))
    assert await maker._find_attached_cover(Path("in.m4a")) is None


async def test_find_attached_cover_none_when_audio_only(maker):
    payload = _json.dumps({"streams": [
        {"index": 0, "codec_type": "audio", "disposition": {"attached_pic": 0}},
    ]})
    maker._run = AsyncMock(return_value=(payload, "", 0))
    assert await maker._find_attached_cover(Path("in.m4a")) is None


async def test_extract_cover_writes_png_and_maps_index(maker, tmp_path):
    async def fake_run(cmd):
        Path(cmd[-1]).write_bytes(b"\x89PNG")  # simulate ffmpeg writing the file
        return ("", "", 0)

    maker._run = fake_run
    out = await maker._extract_cover(Path("in.m4a"), 3, tmp_path)
    assert out == tmp_path / "cover.png"
    assert out.exists()


async def test_extract_cover_uses_exact_stream_map(maker, tmp_path):
    captured = {}

    async def fake_run(cmd):
        captured["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"\x89PNG")
        return ("", "", 0)

    maker._run = fake_run
    await maker._extract_cover(Path("in.m4a"), 3, tmp_path)
    assert "-map" in captured["cmd"]
    assert "0:3" in captured["cmd"]
    assert "-frames:v" in captured["cmd"]


async def test_extract_cover_failure_raises(maker, tmp_path):
    maker._run = AsyncMock(return_value=("", "boom", 1))
    with pytest.raises(FFmpegError, match="cover art"):
        await maker._extract_cover(Path("in.m4a"), 3, tmp_path)


def _build(maker, **overrides):
    kwargs = dict(
        image=None, image_is_generated=True,
        audio_path=Path("in.m4a"), output_path=Path("out.tmp.mp4"),
        width=1280, height=720, fps=2, audio_copy=True,
    )
    kwargs.update(overrides)
    return maker._build_command(**kwargs)


def test_build_command_generated_background(maker):
    cmd = _build(maker, image_is_generated=True)
    joined = " ".join(cmd)
    assert "lavfi" in joined
    assert "color=c=0x0f0f14:s=1280x720:r=2" in joined
    assert "-loop" not in cmd  # generated bg is not a looped image


def test_build_command_with_image_loops(maker):
    cmd = _build(maker, image=Path("cover.png"), image_is_generated=False)
    assert "-loop" in cmd and "1" in cmd
    assert "-framerate" in cmd
    assert str(Path("cover.png")) in cmd


def test_build_command_explicit_mapping_and_codecs(maker):
    cmd = _build(maker)
    assert cmd.count("-map") == 2
    assert "0:v:0" in cmd and "1:a:0" in cmd
    assert "libx264" in cmd
    assert "yuv420p" in cmd
    assert "-fps_mode" in cmd and "cfr" in cmd
    assert "-shortest" in cmd
    assert "+faststart" in cmd
    assert cmd[-1] == str(Path("out.tmp.mp4"))


def test_build_command_aspect_preserving_filter(maker):
    cmd = _build(maker)
    vf = cmd[cmd.index("-vf") + 1]
    assert "force_original_aspect_ratio=decrease" in vf
    assert "pad=1280:720" in vf
    assert "format=yuv420p" in vf


def test_build_command_audio_copy(maker):
    cmd = _build(maker, audio_copy=True)
    idx = cmd.index("-c:a")
    assert cmd[idx + 1] == "copy"
    assert "aac" not in cmd


def test_build_command_audio_encode(maker):
    cmd = _build(maker, audio_copy=False)
    idx = cmd.index("-c:a")
    assert cmd[idx + 1] == "aac"
    assert "128k" in cmd
