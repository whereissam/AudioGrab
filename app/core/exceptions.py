"""Custom exceptions for AudioGrab."""


class AudioGrabError(Exception):
    """Base exception for all AudioGrab errors."""

    pass


# Backward compatibility alias
XDownloaderError = AudioGrabError


class AuthenticationError(AudioGrabError):
    """Invalid or expired authentication credentials."""

    pass


class ContentNotFoundError(AudioGrabError):
    """Content not found (Space, episode, track)."""

    pass


# Backward compatibility alias
SpaceNotFoundError = ContentNotFoundError


class ContentNotAvailableError(AudioGrabError):
    """Content exists but not available for download."""

    pass


# Backward compatibility alias
SpaceNotAvailableError = ContentNotAvailableError


class DownloadError(AudioGrabError):
    """Failed to download audio."""

    pass


class FFmpegError(AudioGrabError):
    """FFmpeg processing failed."""

    pass


class ToolNotFoundError(AudioGrabError):
    """Required external tool not found (yt-dlp, spotdl, ffmpeg)."""

    pass


class RateLimitError(AudioGrabError):
    """API rate limit exceeded."""

    pass


class UnsupportedPlatformError(AudioGrabError):
    """URL does not match any supported platform."""

    pass
