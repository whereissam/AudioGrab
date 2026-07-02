"""Platform-specific downloader implementations."""

from .xspaces import XSpacesDownloader
from .apple_podcasts import ApplePodcastsDownloader
from .spotify import SpotifyDownloader
from .youtube import YouTubeDownloader
from .x_video import XVideoDownloader
from .youtube_video import YouTubeVideoDownloader
from .xiaoyuzhou import XiaoyuzhouDownloader
from .ximalaya import XimalayaDownloader
from .instagram_video import InstagramVideoDownloader
from .xiaohongshu_video import XiaohongshuVideoDownloader
from .discord_audio import DiscordAudioDownloader

__all__ = [
    # Audio
    "XSpacesDownloader",
    "ApplePodcastsDownloader",
    "SpotifyDownloader",
    "YouTubeDownloader",
    "XiaoyuzhouDownloader",
    "XimalayaDownloader",
    "DiscordAudioDownloader",
    # Video
    "XVideoDownloader",
    "YouTubeVideoDownloader",
    "InstagramVideoDownloader",
    "XiaohongshuVideoDownloader",
]
