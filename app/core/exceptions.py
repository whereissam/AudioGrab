"""Custom exceptions for the X Spaces Downloader."""


class XDownloaderError(Exception):
    """Base exception for all X Downloader errors."""

    pass


class AuthenticationError(XDownloaderError):
    """Invalid or expired authentication credentials."""

    pass


class SpaceNotFoundError(XDownloaderError):
    """Space ID not found or has been deleted."""

    pass


class SpaceNotAvailableError(XDownloaderError):
    """Space exists but replay is not available for download."""

    pass


class DownloadError(XDownloaderError):
    """Failed to download audio stream."""

    pass


class FFmpegError(XDownloaderError):
    """FFmpeg processing failed."""

    pass


class RateLimitError(XDownloaderError):
    """API rate limit exceeded."""

    pass
