"""Main downloader orchestration for Twitter Spaces using yt-dlp."""

import asyncio
import logging
import re
import shutil
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import get_settings
from .parser import SpaceURLParser
from .exceptions import XDownloaderError, FFmpegError, SpaceNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class SpaceMetadata:
    """Metadata about a Twitter Space."""

    space_id: str
    title: str
    host_username: str | None = None
    host_display_name: str | None = None
    duration_seconds: float | None = None


@dataclass
class DownloadResult:
    """Result of a Space download operation."""

    success: bool
    file_path: Path | None
    metadata: SpaceMetadata | None
    error: str | None = None
    duration_seconds: float | None = None
    file_size_bytes: int | None = None

    @property
    def file_size_mb(self) -> float | None:
        """Get file size in megabytes."""
        if self.file_size_bytes:
            return self.file_size_bytes / (1024 * 1024)
        return None


class SpaceDownloader:
    """Main downloader class for Twitter Spaces using yt-dlp."""

    def __init__(self, download_dir: str | Path | None = None):
        """
        Initialize the downloader.

        Args:
            download_dir: Directory for downloads (uses config default if not provided)
        """
        self.settings = get_settings()

        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = self.settings.get_download_path()

        self._yt_dlp_path = self._find_yt_dlp()

    def _find_yt_dlp(self) -> str:
        """Find yt-dlp binary in system PATH."""
        yt_dlp = shutil.which("yt-dlp")
        if not yt_dlp:
            raise XDownloaderError(
                "yt-dlp not found in PATH. Please install it: brew install yt-dlp"
            )
        return yt_dlp

    @staticmethod
    def is_yt_dlp_available() -> bool:
        """Check if yt-dlp is available in system PATH."""
        return shutil.which("yt-dlp") is not None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        # Limit length
        return sanitized[:100]

    async def download(
        self,
        url: str,
        output_path: str | Path | None = None,
        format: str = "m4a",
        quality: str = "high",
    ) -> DownloadResult:
        """
        Download a Twitter Space from URL using yt-dlp.

        Args:
            url: Twitter Space URL
            output_path: Optional specific output path (auto-generated if not provided)
            format: Output format (m4a, mp3)
            quality: Quality preset for MP3 encoding

        Returns:
            DownloadResult with download information
        """
        logger.info(f"Starting download for: {url}")

        try:
            # Validate URL
            space_id = SpaceURLParser.extract_space_id(url)
            logger.info(f"Extracted Space ID: {space_id}")

            # Ensure download directory exists
            self.download_dir.mkdir(parents=True, exist_ok=True)

            # Build output template
            if output_path:
                output_template = str(output_path)
            else:
                output_template = str(self.download_dir / "%(title)s [%(id)s].%(ext)s")

            # For mp4, download as m4a first then convert
            download_format = "m4a" if format == "mp4" else format
            needs_conversion = format == "mp4"

            # Build yt-dlp command
            cmd = [
                self._yt_dlp_path,
                "--no-progress",
                "-x",  # Extract audio
                "--audio-format", download_format if download_format == "mp3" else "m4a",
                "-o", output_template,
                "--print-json",  # Output JSON with metadata
            ]

            # Add quality for mp3
            if download_format == "mp3":
                quality_map = {"low": "64K", "medium": "128K", "high": "192K", "highest": "320K"}
                cmd.extend(["--audio-quality", quality_map.get(quality, "192K")])

            cmd.append(url)

            logger.info(f"Running yt-dlp...")
            logger.debug(f"Command: {' '.join(cmd[:8])}...")

            # Run yt-dlp
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"yt-dlp error: {error_msg}")

                if "404" in error_msg or "not found" in error_msg.lower():
                    raise SpaceNotFoundError(f"Space not found: {space_id}")

                raise XDownloaderError(f"yt-dlp failed: {error_msg[:500]}")

            # Parse JSON output to get metadata and file path
            output = stdout.decode().strip()
            metadata = None
            file_path = None

            # yt-dlp outputs JSON for each downloaded file
            for line in output.split('\n'):
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        file_path = Path(data.get('_filename', data.get('filename', '')))
                        metadata = SpaceMetadata(
                            space_id=data.get('id', space_id),
                            title=data.get('title', 'Unknown'),
                            host_username=data.get('uploader_id'),
                            host_display_name=data.get('uploader'),
                            duration_seconds=data.get('duration'),
                        )
                        break
                    except json.JSONDecodeError:
                        continue

            # Find the output file if not in JSON
            if not file_path or not file_path.exists():
                # Look for files matching the space ID
                for ext in ['.m4a', '.mp3', '.aac']:
                    matches = list(self.download_dir.glob(f"*{space_id}*{ext}"))
                    if matches:
                        file_path = matches[0]
                        break

            if not file_path or not file_path.exists():
                raise XDownloaderError("Download completed but output file not found")

            # Convert to mp4 if needed
            if needs_conversion:
                from .converter import AudioConverter
                logger.info(f"Converting to {format}...")
                converter = AudioConverter()
                converted_path = await converter.convert(
                    input_path=file_path,
                    output_format=format,
                    quality=quality,
                    keep_original=False,
                )
                file_path = converted_path

            # Get file info
            file_size = file_path.stat().st_size
            duration = metadata.duration_seconds if metadata else None

            logger.info(f"Download complete: {file_path}")
            logger.info(f"File size: {file_size / (1024*1024):.2f} MB")

            return DownloadResult(
                success=True,
                file_path=file_path,
                metadata=metadata,
                duration_seconds=duration,
                file_size_bytes=file_size,
            )

        except (SpaceNotFoundError, XDownloaderError) as e:
            logger.error(f"Download failed: {e}")
            return DownloadResult(
                success=False,
                file_path=None,
                metadata=None,
                error=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return DownloadResult(
                success=False,
                file_path=None,
                metadata=None,
                error=f"Unexpected error: {e}",
            )

    async def get_metadata(self, url: str) -> SpaceMetadata | None:
        """
        Get metadata for a Twitter Space without downloading.

        Args:
            url: Twitter Space URL

        Returns:
            SpaceMetadata or None if failed
        """
        try:
            space_id = SpaceURLParser.extract_space_id(url)

            cmd = [
                self._yt_dlp_path,
                "--no-download",
                "--print-json",
                url,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return None

            output = stdout.decode().strip()
            for line in output.split('\n'):
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        return SpaceMetadata(
                            space_id=data.get('id', space_id),
                            title=data.get('title', 'Unknown'),
                            host_username=data.get('uploader_id'),
                            host_display_name=data.get('uploader'),
                            duration_seconds=data.get('duration'),
                        )
                    except json.JSONDecodeError:
                        continue

            return None

        except Exception as e:
            logger.warning(f"Failed to get metadata: {e}")
            return None


# Convenience function for simple usage
async def download_space(
    url: str,
    output_path: str | Path | None = None,
    format: str = "m4a",
) -> DownloadResult:
    """
    Convenience function to download a Twitter Space.

    Args:
        url: Twitter Space URL
        output_path: Optional output path
        format: Output format (m4a, mp3)

    Returns:
        DownloadResult
    """
    downloader = SpaceDownloader()
    return await downloader.download(url, output_path, format)
