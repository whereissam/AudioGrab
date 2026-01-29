"""Spotify downloader implementation using spotDL."""

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from ...config import get_settings
from ..base import Platform, PlatformDownloader, AudioMetadata, DownloadResult
from ..exceptions import AudioGrabError, ContentNotFoundError, ToolNotFoundError

logger = logging.getLogger(__name__)


class SpotifyDownloader(PlatformDownloader):
    """Downloads from Spotify using spotDL (finds YouTube matches)."""

    # URL patterns for Spotify
    URL_PATTERNS = [
        r"open\.spotify\.com/episode/([a-zA-Z0-9]+)",
        r"open\.spotify\.com/track/([a-zA-Z0-9]+)",
        r"open\.spotify\.com/album/([a-zA-Z0-9]+)",
        r"open\.spotify\.com/playlist/([a-zA-Z0-9]+)",
    ]

    def __init__(self, download_dir: Optional[Path] = None):
        """Initialize the Spotify downloader."""
        self.settings = get_settings()

        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = self.settings.get_download_path()

        self._spotdl_path = self._find_spotdl()

    def _find_spotdl(self) -> str:
        """Find spotdl binary in PATH."""
        spotdl = shutil.which("spotdl")
        if not spotdl:
            raise ToolNotFoundError(
                "spotdl not found. Install with: pip install spotdl"
            )
        return spotdl

    @property
    def platform(self) -> Platform:
        return Platform.SPOTIFY

    @classmethod
    def can_handle_url(cls, url: str) -> bool:
        """Check if URL is a valid Spotify URL."""
        return "open.spotify.com" in url

    @classmethod
    def extract_content_id(cls, url: str) -> str:
        """Extract content ID from Spotify URL."""
        for pattern in cls.URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ContentNotFoundError(f"Could not extract Spotify ID from URL: {url}")

    @classmethod
    def is_available(cls) -> bool:
        """Check if spotdl is available."""
        return shutil.which("spotdl") is not None

    def _get_content_type(self, url: str) -> str:
        """Determine the type of Spotify content."""
        if "/track/" in url:
            return "track"
        elif "/episode/" in url:
            return "episode"
        elif "/album/" in url:
            return "album"
        elif "/playlist/" in url:
            return "playlist"
        return "unknown"

    async def download(
        self,
        url: str,
        output_path: Optional[Path] = None,
        output_format: str = "mp3",
        quality: str = "high",
    ) -> DownloadResult:
        """Download from Spotify using spotDL."""
        logger.info(f"Starting Spotify download for: {url}")

        try:
            content_id = self.extract_content_id(url)
            content_type = self._get_content_type(url)
            logger.info(f"Spotify {content_type} ID: {content_id}")

            self.download_dir.mkdir(parents=True, exist_ok=True)

            # Map quality to bitrate
            bitrate_map = {
                "low": "128k",
                "medium": "192k",
                "high": "256k",
                "highest": "320k",
            }
            bitrate = bitrate_map.get(quality, "256k")

            # Build spotdl command
            output_template = str(self.download_dir / "{artist} - {title}")

            cmd = [
                self._spotdl_path,
                "download",
                url,
                "--output", output_template,
                "--format", output_format if output_format in ["mp3", "m4a", "flac", "ogg", "opus"] else "mp3",
                "--bitrate", bitrate,
                "--print-errors",
            ]

            logger.info("Running spotdl... (this may take a while)")
            logger.debug(f"Command: {' '.join(cmd[:6])}...")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.download_dir),
            )

            stdout, stderr = await process.communicate()

            stdout_text = stdout.decode() if stdout else ""
            stderr_text = stderr.decode() if stderr else ""

            if process.returncode != 0:
                error_msg = stderr_text or stdout_text or "Unknown error"
                logger.error(f"spotdl error: {error_msg}")

                if "no results" in error_msg.lower() or "not found" in error_msg.lower():
                    raise ContentNotFoundError(f"Could not find audio for: {url}")

                raise AudioGrabError(f"spotdl failed: {error_msg[:500]}")

            # Find the downloaded file
            # spotdl outputs files in format: "Artist - Title.ext"
            file_path = None
            ext = f".{output_format}" if output_format in ["mp3", "m4a", "flac", "ogg", "opus"] else ".mp3"

            # Look for recently created files
            for f in self.download_dir.glob(f"*{ext}"):
                # Check if file was created recently (within last 5 minutes)
                if f.stat().st_mtime > (asyncio.get_event_loop().time() - 300):
                    file_path = f
                    break

            # If not found, try to find any matching file
            if not file_path:
                matches = list(self.download_dir.glob(f"*{ext}"))
                if matches:
                    # Get the most recently modified
                    file_path = max(matches, key=lambda p: p.stat().st_mtime)

            if not file_path or not file_path.exists():
                raise AudioGrabError("Download completed but output file not found")

            # Extract metadata from filename
            filename = file_path.stem
            parts = filename.split(" - ", 1)
            artist = parts[0] if len(parts) > 1 else None
            title = parts[1] if len(parts) > 1 else filename

            metadata = AudioMetadata(
                platform=Platform.SPOTIFY,
                content_id=content_id,
                title=title,
                creator_name=artist,
            )

            file_size = file_path.stat().st_size

            logger.info(f"Download complete: {file_path}")
            logger.info(f"File size: {file_size / (1024*1024):.2f} MB")

            return DownloadResult(
                success=True,
                file_path=file_path,
                metadata=metadata,
                file_size_bytes=file_size,
            )

        except (ContentNotFoundError, AudioGrabError, ToolNotFoundError) as e:
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

    async def get_metadata(self, url: str) -> Optional[AudioMetadata]:
        """Get metadata for Spotify content without downloading."""
        try:
            content_id = self.extract_content_id(url)
            content_type = self._get_content_type(url)

            # Use spotdl to get metadata
            cmd = [
                self._spotdl_path,
                "save",
                url,
                "--save-file", "/dev/stdout",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return None

            # Try to parse JSON output
            try:
                output = stdout.decode().strip()
                if output.startswith("["):
                    data = json.loads(output)
                    if data:
                        item = data[0]
                        return AudioMetadata(
                            platform=Platform.SPOTIFY,
                            content_id=content_id,
                            title=item.get("name", "Unknown"),
                            creator_name=", ".join(item.get("artists", [])),
                            duration_seconds=item.get("duration"),
                            artwork_url=item.get("cover_url"),
                        )
            except json.JSONDecodeError:
                pass

            # Return basic metadata
            return AudioMetadata(
                platform=Platform.SPOTIFY,
                content_id=content_id,
                title=f"Spotify {content_type}",
            )

        except Exception as e:
            logger.warning(f"Failed to get metadata: {e}")
            return None
