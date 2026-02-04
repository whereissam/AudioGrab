"""Platform-specific downloader implementations."""

from .xspaces import XSpacesDownloader
from .apple_podcasts import ApplePodcastsDownloader
from .spotify import SpotifyDownloader
from .youtube import YouTubeDownloader
from .x_video import XVideoDownloader
from .youtube_video import YouTubeVideoDownloader
from .xiaoyuzhou import XiaoyuzhouDownloader
from .instagram_video import InstagramVideoDownloader
from .xiaohongshu_video import XiaohongshuVideoDownloader

__all__ = [
    # Audio
    "XSpacesDownloader",
    "ApplePodcastsDownloader",
    "SpotifyDownloader",
    "YouTubeDownloader",
    "XiaoyuzhouDownloader",
    # Video
    "XVideoDownloader",
    "YouTubeVideoDownloader",
    "InstagramVideoDownloader",
    "XiaohongshuVideoDownloader",
]
