"""Audio transcription using faster-whisper."""

import logging
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Add faster-whisper to path if installed locally
FASTER_WHISPER_PATH = Path(__file__).parent.parent.parent / "faster-whisper"
if FASTER_WHISPER_PATH.exists():
    sys.path.insert(0, str(FASTER_WHISPER_PATH))


class WhisperModel(str, Enum):
    """Available Whisper model sizes."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"
    LARGE_V3_TURBO = "turbo"
    DISTIL_LARGE_V3 = "distil-large-v3"


class TranscriptionFormat(str, Enum):
    """Output format for transcription."""

    TEXT = "text"  # Plain text
    SRT = "srt"  # SubRip subtitle
    VTT = "vtt"  # WebVTT subtitle
    JSON = "json"  # JSON with timestamps


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""

    success: bool
    text: Optional[str] = None
    segments: Optional[list[TranscriptionSegment]] = None
    language: Optional[str] = None
    language_probability: Optional[float] = None
    duration: Optional[float] = None
    error: Optional[str] = None


class AudioTranscriber:
    """Transcribe audio files using faster-whisper."""

    _model = None
    _current_model_size = None

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        """
        Initialize the transcriber.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3, turbo)
            device: Device to use (auto, cpu, cuda)
            compute_type: Compute type (auto, int8, float16, float32)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def _get_model(self):
        """Get or create the Whisper model (lazy loading with singleton pattern)."""
        if (
            AudioTranscriber._model is None
            or AudioTranscriber._current_model_size != self.model_size
        ):
            try:
                from faster_whisper import WhisperModel as FasterWhisperModel

                logger.info(f"Loading Whisper model: {self.model_size}")

                # Determine device and compute type
                device = self.device
                compute_type = self.compute_type

                if device == "auto":
                    try:
                        import torch

                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except ImportError:
                        device = "cpu"

                if compute_type == "auto":
                    compute_type = "int8" if device == "cpu" else "float16"

                AudioTranscriber._model = FasterWhisperModel(
                    self.model_size,
                    device=device,
                    compute_type=compute_type,
                )
                AudioTranscriber._current_model_size = self.model_size
                logger.info(
                    f"Model loaded: {self.model_size} on {device} with {compute_type}"
                )

            except ImportError as e:
                raise ImportError(
                    "faster-whisper not installed. Install it with: pip install faster-whisper"
                ) from e

        return AudioTranscriber._model

    async def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        task: str = "transcribe",
        vad_filter: bool = True,
        word_timestamps: bool = False,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to the audio file
            language: Language code (auto-detect if None)
            task: "transcribe" or "translate" (to English)
            vad_filter: Use VAD to filter silence
            word_timestamps: Include word-level timestamps
            initial_prompt: Optional prompt to guide transcription

        Returns:
            TranscriptionResult with text and segments
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            return TranscriptionResult(
                success=False,
                error=f"Audio file not found: {audio_path}",
            )

        try:
            model = self._get_model()

            logger.info(f"Transcribing: {audio_path.name}")

            # Run transcription (synchronous, but we wrap for async API)
            segments_generator, info = model.transcribe(
                str(audio_path),
                language=language,
                task=task,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps,
                initial_prompt=initial_prompt,
                beam_size=5,
            )

            # Collect segments
            segments = []
            full_text_parts = []

            for segment in segments_generator:
                segments.append(
                    TranscriptionSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                    )
                )
                full_text_parts.append(segment.text.strip())

            full_text = " ".join(full_text_parts)

            logger.info(
                f"Transcription complete: {len(segments)} segments, "
                f"language={info.language} ({info.language_probability:.2%})"
            )

            return TranscriptionResult(
                success=True,
                text=full_text,
                segments=segments,
                language=info.language,
                language_probability=info.language_probability,
                duration=info.duration,
            )

        except Exception as e:
            logger.exception(f"Transcription error: {e}")
            return TranscriptionResult(
                success=False,
                error=str(e),
            )

    @staticmethod
    def format_as_srt(segments: list[TranscriptionSegment]) -> str:
        """Format segments as SRT subtitle."""
        lines = []
        for i, seg in enumerate(segments, 1):
            start = _format_timestamp_srt(seg.start)
            end = _format_timestamp_srt(seg.end)
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def format_as_vtt(segments: list[TranscriptionSegment]) -> str:
        """Format segments as WebVTT subtitle."""
        lines = ["WEBVTT", ""]
        for seg in segments:
            start = _format_timestamp_vtt(seg.start)
            end = _format_timestamp_vtt(seg.end)
            lines.append(f"{start} --> {end}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def is_available() -> bool:
        """Check if faster-whisper is available."""
        try:
            from faster_whisper import WhisperModel

            return True
        except ImportError:
            return False


def _format_timestamp_srt(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    """Format seconds as VTT timestamp (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


# Convenience function
async def transcribe_audio(
    audio_path: str | Path,
    model_size: str = "base",
    language: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe an audio file.

    Args:
        audio_path: Path to audio file
        model_size: Whisper model size
        language: Language code (auto-detect if None)

    Returns:
        TranscriptionResult
    """
    transcriber = AudioTranscriber(model_size=model_size)
    return await transcriber.transcribe(audio_path, language=language)
