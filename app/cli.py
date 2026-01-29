"""Simple CLI for testing the downloader."""

import argparse
import asyncio
import logging
import sys

from .core import SpaceDownloader, SpaceURLParser
from .config import get_settings


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download Twitter/X Spaces audio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://x.com/i/spaces/1vOxwdyYrlqKB
  %(prog)s -f mp3 -o my_space.mp3 https://x.com/i/spaces/1vOxwdyYrlqKB
        """,
    )

    parser.add_argument(
        "url",
        help="Twitter Space URL to download",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (auto-generated if not specified)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["m4a", "mp3", "aac"],
        default="m4a",
        help="Output format (default: m4a)",
    )
    parser.add_argument(
        "-q", "--quality",
        choices=["low", "medium", "high", "highest"],
        default="high",
        help="Quality preset for MP3 (default: high)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Validate URL
    if not SpaceURLParser.is_valid_space_url(args.url):
        print(f"Error: Invalid Twitter Space URL: {args.url}", file=sys.stderr)
        sys.exit(1)

    # Check configuration
    settings = get_settings()
    if not settings.has_auth:
        print(
            "Error: Missing authentication. Set TWITTER_AUTH_TOKEN and TWITTER_CT0 "
            "environment variables, or create a .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Download
    print(f"Downloading Space: {args.url}")

    downloader = SpaceDownloader()
    result = await downloader.download(
        url=args.url,
        output_path=args.output,
        format=args.format,
        quality=args.quality,
    )

    if result.success:
        print(f"\nDownload complete!")
        print(f"File: {result.file_path}")
        if result.file_size_mb:
            print(f"Size: {result.file_size_mb:.2f} MB")
        if result.duration_seconds:
            mins = int(result.duration_seconds // 60)
            secs = int(result.duration_seconds % 60)
            print(f"Duration: {mins}m {secs}s")
    else:
        print(f"\nDownload failed: {result.error}", file=sys.stderr)
        sys.exit(1)


def cli():
    """Synchronous CLI wrapper."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
