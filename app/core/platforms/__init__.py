"""Platform-specific downloader implementations."""

from .xspaces import XSpacesDownloader
from .apple_podcasts import ApplePodcastsDownloader
from .spotify import SpotifyDownloader

__all__ = [
    "XSpacesDownloader",
    "ApplePodcastsDownloader",
    "SpotifyDownloader",
]
