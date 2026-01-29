"""Telegram bot implementation for X Spaces Downloader."""

import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ..config import get_settings
from ..core import (
    AuthManager,
    SpaceDownloader,
    SpaceURLParser,
    TwitterClient,
    AuthenticationError,
    SpaceNotFoundError,
    SpaceNotAvailableError,
    XDownloaderError,
)

logger = logging.getLogger(__name__)


class SpacesBot:
    """Telegram bot for downloading Twitter Spaces."""

    def __init__(self, token: str):
        """
        Initialize the bot.

        Args:
            token: Telegram bot token from @BotFather
        """
        self.token = token
        self.settings = get_settings()

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /start command."""
        welcome_message = (
            "Welcome to X Spaces Downloader Bot!\n\n"
            "Send me a Twitter/X Space link and I'll download the audio for you.\n\n"
            "Supported formats:\n"
            "- https://x.com/i/spaces/xxxxx\n"
            "- https://twitter.com/i/spaces/xxxxx\n\n"
            "Commands:\n"
            "/start - Show this message\n"
            "/help - Show help\n"
            "/status - Check bot status"
        )
        await update.message.reply_text(welcome_message)

    async def help_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /help command."""
        help_message = (
            "How to use this bot:\n\n"
            "1. Copy a Twitter Space link\n"
            "2. Send it to this chat\n"
            "3. Wait for the download to complete\n"
            "4. Receive the audio file\n\n"
            "Note: Only recorded Spaces (replays) can be downloaded. "
            "Live Spaces cannot be downloaded until they end and a replay "
            "is made available by the host."
        )
        await update.message.reply_text(help_message)

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /status command."""
        from ..core.merger import AudioMerger

        ffmpeg_ok = AudioMerger.is_ffmpeg_available()
        auth_ok = self.settings.has_auth

        status_lines = [
            "Bot Status:\n",
            f"FFmpeg: {'OK' if ffmpeg_ok else 'Not Found'}",
            f"Authentication: {'Configured' if auth_ok else 'Not Configured'}",
        ]

        await update.message.reply_text("\n".join(status_lines))

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle incoming messages with Space URLs."""
        text = update.message.text.strip()

        # Check if it's a Space URL
        if not SpaceURLParser.is_valid_space_url(text):
            await update.message.reply_text(
                "Please send a valid Twitter Space link.\n"
                "Example: https://x.com/i/spaces/1vOxwdyYrlqKB"
            )
            return

        # Check authentication
        if not self.settings.has_auth:
            await update.message.reply_text(
                "Bot is not configured with Twitter authentication. "
                "Please contact the bot administrator."
            )
            return

        # Start download process
        status_message = await update.message.reply_text(
            "Processing Space URL..."
        )

        try:
            auth = AuthManager.from_env()

            # Get metadata first
            await status_message.edit_text("Fetching Space metadata...")

            async with TwitterClient(auth) as client:
                space_id = SpaceURLParser.extract_space_id(text)
                metadata = await client.get_space_metadata(space_id)

            # Update status with Space info
            info_lines = [
                f"Space: {metadata.title}",
                f"Host: @{metadata.host_username or 'Unknown'}",
                f"Status: {metadata.state}",
            ]
            if metadata.duration_seconds:
                info_lines.append(
                    f"Duration: {self._format_duration(metadata.duration_seconds)}"
                )
            info_lines.append("\nDownloading audio, please wait...")

            await status_message.edit_text("\n".join(info_lines))

            # Download
            downloader = SpaceDownloader(auth=auth)
            result = await downloader.download(url=text, format="m4a")

            if not result.success:
                await status_message.edit_text(
                    f"Download failed: {result.error}"
                )
                return

            # Send the file
            await status_message.edit_text("Uploading audio file...")

            file_path = result.file_path
            file_size_mb = result.file_size_mb or 0

            # Check Telegram file size limit (50MB for bots, 2GB for premium)
            if file_size_mb > 50:
                await status_message.edit_text(
                    f"File too large for Telegram ({file_size_mb:.1f} MB). "
                    "Maximum size is 50 MB."
                )
                # Clean up
                file_path.unlink(missing_ok=True)
                return

            # Build caption
            caption_lines = [
                f"Title: {metadata.title}",
                f"Host: @{metadata.host_username or 'Unknown'}",
            ]
            if result.duration_seconds:
                caption_lines.append(
                    f"Duration: {self._format_duration(result.duration_seconds)}"
                )
            caption_lines.append(f"Size: {file_size_mb:.1f} MB")

            # Send audio file
            with open(file_path, "rb") as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=metadata.title,
                    performer=metadata.host_display_name or metadata.host_username,
                    caption="\n".join(caption_lines),
                )

            # Clean up
            await status_message.delete()
            file_path.unlink(missing_ok=True)

            logger.info(
                f"Successfully sent Space {space_id} to user {update.effective_user.id}"
            )

        except AuthenticationError as e:
            await status_message.edit_text(
                f"Authentication error: {e}\n"
                "Please contact the bot administrator."
            )
        except SpaceNotFoundError as e:
            await status_message.edit_text(
                f"Space not found: {e}"
            )
        except SpaceNotAvailableError as e:
            await status_message.edit_text(
                f"Space not available: {e}\n"
                "The Space may be live or the host has not enabled replay."
            )
        except Exception as e:
            logger.exception(f"Error processing Space for user {update.effective_user.id}")
            await status_message.edit_text(
                f"An error occurred: {e}"
            )

    def build_application(self) -> Application:
        """Build and configure the Telegram application."""
        application = Application.builder().token(self.token).build()

        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        return application

    def run(self) -> None:
        """Run the bot with polling."""
        application = self.build_application()
        logger.info("Starting Telegram bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def run_bot():
    """Entry point to run the Telegram bot."""
    settings = get_settings()

    if not settings.telegram_bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is required"
        )

    bot = SpacesBot(settings.telegram_bot_token)
    bot.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_bot()
