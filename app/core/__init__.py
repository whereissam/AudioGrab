"""Core downloader functionality."""

from .exceptions import (
    XDownloaderError,
    AuthenticationError,
    SpaceNotFoundError,
    SpaceNotAvailableError,
    DownloadError,
    FFmpegError,
)
from .parser import SpaceURLParser
from .downloader import SpaceDownloader, SpaceMetadata, DownloadResult

__all__ = [
    # Exceptions
    "XDownloaderError",
    "AuthenticationError",
    "SpaceNotFoundError",
    "SpaceNotAvailableError",
    "DownloadError",
    "FFmpegError",
    # Classes
    "SpaceURLParser",
    "SpaceMetadata",
    "SpaceDownloader",
    "DownloadResult",
]
