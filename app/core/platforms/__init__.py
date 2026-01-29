"""Platform-specific downloader implementations."""

from .xspaces import XSpacesDownloader
from .apple_podcasts import ApplePodcastsDownloader
from .spotify import SpotifyDownloader
from .youtube import YouTubeDownloader

__all__ = [
    "XSpacesDownloader",
    "ApplePodcastsDownloader",
    "SpotifyDownloader",
    "YouTubeDownloader",
]
