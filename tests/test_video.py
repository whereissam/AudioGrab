"""Tests for the audio-to-video (YouTube-ready MP4) module."""

from pathlib import Path

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
