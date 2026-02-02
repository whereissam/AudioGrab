"""LLM-powered sentiment analysis service for transcripts."""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from .summarizer import LiteLLMProvider

logger = logging.getLogger(__name__)


@dataclass
class SegmentSentiment:
    """Sentiment analysis for a single transcript segment."""

    segment_index: int
    start: float
    end: float
    text: str
    # Core sentiment dimensions
    polarity: float  # -1.0 (negative) to 1.0 (positive)
    energy: str  # "aggressive", "calm", "neutral"
    energy_score: float  # 0.0 to 1.0
    excitement: int  # 0 to 100
    # Emotion breakdown
    emotions: dict[str, float]  # joy, anger, fear, surprise, sadness (0-1 each)
    # Combined metrics
    heat_score: float  # 0.0 to 1.0 - overall intensity
    is_heated: bool  # True if above threshold
    speaker: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "segment_index": self.segment_index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "polarity": self.polarity,
            "energy": self.energy,
            "energy_score": self.energy_score,
            "excitement": self.excitement,
            "emotions": self.emotions,
            "heat_score": self.heat_score,
            "is_heated": self.is_heated,
            "speaker": self.speaker,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SegmentSentiment":
        """Create from dictionary."""
        return cls(
            segment_index=data["segment_index"],
            start=data["start"],
            end=data["end"],
            text=data["text"],
            polarity=data["polarity"],
            energy=data["energy"],
            energy_score=data["energy_score"],
            excitement=data["excitement"],
            emotions=data["emotions"],
            heat_score=data["heat_score"],
            is_heated=data["is_heated"],
            speaker=data.get("speaker"),
        )


@dataclass
class TimeWindowAggregate:
    """Aggregated sentiment for a time window."""

    window_index: int
    start: float
    end: float
    avg_polarity: float
    avg_heat_score: float
    dominant_emotion: str
    segment_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "window_index": self.window_index,
            "start": self.start,
            "end": self.end,
            "avg_polarity": self.avg_polarity,
            "avg_heat_score": self.avg_heat_score,
            "dominant_emotion": self.dominant_emotion,
            "segment_count": self.segment_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimeWindowAggregate":
        """Create from dictionary."""
        return cls(
            window_index=data["window_index"],
            start=data["start"],
            end=data["end"],
            avg_polarity=data["avg_polarity"],
            avg_heat_score=data["avg_heat_score"],
            dominant_emotion=data["dominant_emotion"],
            segment_count=data["segment_count"],
        )


@dataclass
class EmotionalArc:
    """Overall emotional summary of the content."""

    overall_sentiment: str  # "positive", "negative", "neutral", "mixed"
    avg_heat_score: float
    peak_moments: list[dict]  # List of {timestamp, description, heat_score}
    dominant_emotions: list[str]  # Top 3 emotions
    emotional_journey: str  # Brief narrative description
    total_heated_segments: int
    heated_percentage: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "overall_sentiment": self.overall_sentiment,
            "avg_heat_score": self.avg_heat_score,
            "peak_moments": self.peak_moments,
            "dominant_emotions": self.dominant_emotions,
            "emotional_journey": self.emotional_journey,
            "total_heated_segments": self.total_heated_segments,
            "heated_percentage": self.heated_percentage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalArc":
        """Create from dictionary."""
        return cls(
            overall_sentiment=data["overall_sentiment"],
            avg_heat_score=data["avg_heat_score"],
            peak_moments=data["peak_moments"],
            dominant_emotions=data["dominant_emotions"],
            emotional_journey=data["emotional_journey"],
            total_heated_segments=data["total_heated_segments"],
            heated_percentage=data["heated_percentage"],
        )


@dataclass
class SentimentAnalysisResult:
    """Complete sentiment analysis result."""

    success: bool
    job_id: str
    segments: list[SegmentSentiment] = field(default_factory=list)
    time_windows: list[TimeWindowAggregate] = field(default_factory=list)
    emotional_arc: Optional[EmotionalArc] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "job_id": self.job_id,
            "segments": [s.to_dict() for s in self.segments],
            "time_windows": [w.to_dict() for w in self.time_windows],
            "emotional_arc": self.emotional_arc.to_dict() if self.emotional_arc else None,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SentimentAnalysisResult":
        """Create from dictionary."""
        return cls(
            success=data["success"],
            job_id=data["job_id"],
            segments=[SegmentSentiment.from_dict(s) for s in data.get("segments", [])],
            time_windows=[TimeWindowAggregate.from_dict(w) for w in data.get("time_windows", [])],
            emotional_arc=EmotionalArc.from_dict(data["emotional_arc"]) if data.get("emotional_arc") else None,
            model=data.get("model"),
            provider=data.get("provider"),
            tokens_used=data.get("tokens_used"),
            error=data.get("error"),
        )


# System prompt for sentiment analysis
SENTIMENT_SYSTEM_PROMPT = """You are an expert at analyzing emotional tone and sentiment in transcripts.
You provide accurate, nuanced sentiment analysis identifying emotional intensity, polarity, and specific emotions.
You output structured JSON responses following the exact schema provided."""

# Prompt for analyzing segment batches
SEGMENT_ANALYSIS_PROMPT = """Analyze the emotional sentiment of each transcript segment below.

For each segment, determine:
1. **polarity**: -1.0 (very negative) to 1.0 (very positive), 0 = neutral
2. **energy**: "aggressive", "calm", or "neutral"
3. **energy_score**: 0.0 (very calm) to 1.0 (very intense/energetic)
4. **excitement**: 0 to 100 scale
5. **emotions**: Scores for joy, anger, fear, surprise, sadness (each 0.0 to 1.0)
6. **heat_score**: Overall emotional intensity 0.0 to 1.0 (combine energy, excitement, strong emotions)

Segments to analyze:
{segments}

Return a JSON array with one object per segment, in order. Each object must have:
- segment_index (integer matching the input)
- polarity (float)
- energy (string)
- energy_score (float)
- excitement (integer)
- emotions (object with joy, anger, fear, surprise, sadness keys)
- heat_score (float)

Return ONLY the JSON array, no other text."""

# Prompt for generating emotional arc summary
EMOTIONAL_ARC_PROMPT = """Based on the sentiment analysis of a transcript, create an emotional arc summary.

Analysis data:
- Total segments: {total_segments}
- Average heat score: {avg_heat}
- Segments with heat >= 0.6: {heated_count}
- Top heated moments (timestamp, text snippet):
{top_moments}

Emotion totals across all segments:
{emotion_totals}

Create a summary with:
1. **overall_sentiment**: "positive", "negative", "neutral", or "mixed"
2. **emotional_journey**: 2-3 sentence description of how emotions evolve through the content
3. **dominant_emotions**: Top 3 emotions that appear most strongly (from: joy, anger, fear, surprise, sadness)

Return JSON with these three fields only. No other text."""


class SentimentAnalyzer:
    """Service for analyzing sentiment in transcripts using LLMs."""

    # Analysis settings
    BATCH_SIZE = 20  # Segments per LLM call
    HEAT_THRESHOLD = 0.6  # Score above this = "heated"
    DEFAULT_WINDOW_SIZE = 30  # Seconds per time window

    def __init__(self, provider: Optional[LiteLLMProvider] = None):
        self.provider = provider

    @classmethod
    def from_settings(cls) -> "SentimentAnalyzer":
        """Create analyzer from application settings or database config."""
        from ..config import get_settings
        from .job_store import get_job_store

        settings = get_settings()
        provider: Optional[LiteLLMProvider] = None

        # Try to get settings from database first
        try:
            job_store = get_job_store()
            ai_settings = job_store.get_ai_settings()
            if ai_settings:
                model = cls._build_litellm_model(
                    ai_settings["provider"], ai_settings["model"]
                )
                provider = LiteLLMProvider(
                    model=model,
                    api_key=ai_settings.get("api_key"),
                    base_url=ai_settings.get("base_url"),
                    provider=ai_settings["provider"],
                )
                return cls(provider=provider)
        except Exception as e:
            logger.debug(f"Could not load AI settings from database: {e}")

        # Fall back to environment settings
        if settings.llm_provider == "ollama":
            model = f"ollama/{settings.ollama_model}"
            provider = LiteLLMProvider(
                model=model,
                base_url=settings.ollama_base_url,
                provider="ollama",
            )
        elif settings.llm_provider == "openai" and settings.openai_api_key:
            provider = LiteLLMProvider(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                provider="openai",
            )
        elif settings.llm_provider == "openai_compatible" and settings.openai_api_key:
            model = f"openai/{settings.openai_model}"
            provider = LiteLLMProvider(
                model=model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                provider="custom",
            )
        elif settings.llm_provider == "anthropic" and settings.anthropic_api_key:
            provider = LiteLLMProvider(
                model=settings.anthropic_model,
                api_key=settings.anthropic_api_key,
                provider="anthropic",
            )
        elif settings.llm_provider == "groq" and settings.groq_api_key:
            model = f"groq/{settings.groq_model}"
            provider = LiteLLMProvider(
                model=model,
                api_key=settings.groq_api_key,
                provider="groq",
            )
        elif settings.llm_provider == "deepseek" and settings.deepseek_api_key:
            model = f"deepseek/{settings.deepseek_model}"
            provider = LiteLLMProvider(
                model=model,
                api_key=settings.deepseek_api_key,
                provider="deepseek",
            )
        elif settings.llm_provider == "gemini" and settings.gemini_api_key:
            model = f"gemini/{settings.gemini_model}"
            provider = LiteLLMProvider(
                model=model,
                api_key=settings.gemini_api_key,
                provider="gemini",
            )

        return cls(provider=provider)

    @staticmethod
    def _build_litellm_model(provider: str, model: str) -> str:
        """Build the LiteLLM model string from provider and model name."""
        if provider == "ollama":
            return f"ollama/{model}"
        elif provider == "groq":
            return f"groq/{model}"
        elif provider == "deepseek":
            return f"deepseek/{model}"
        elif provider == "gemini":
            return f"gemini/{model}"
        elif provider == "custom":
            return f"openai/{model}"
        else:
            # OpenAI and Anthropic models don't need prefix
            return model

    @staticmethod
    def is_available() -> bool:
        """Check if sentiment analysis is available."""
        from ..config import get_settings
        from .job_store import get_job_store

        settings = get_settings()

        # Check database settings first
        try:
            job_store = get_job_store()
            ai_settings = job_store.get_ai_settings()
            if ai_settings:
                provider = ai_settings["provider"]
                if provider == "ollama":
                    import httpx

                    base_url = ai_settings.get("base_url") or "http://localhost:11434"
                    with httpx.Client(timeout=5.0) as client:
                        response = client.get(f"{base_url.rstrip('/')}/api/tags")
                        if response.status_code == 200:
                            return True
                else:
                    # Cloud providers with API key
                    return bool(ai_settings.get("api_key"))
        except Exception:
            pass

        # Fall back to environment settings
        if settings.llm_provider == "ollama":
            try:
                import httpx

                with httpx.Client(timeout=5.0) as client:
                    response = client.get(f"{settings.ollama_base_url}/api/tags")
                    if response.status_code == 200:
                        return True
            except Exception:
                pass

        if settings.llm_provider in ("openai", "openai_compatible") and settings.openai_api_key:
            return True
        if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
            return True
        if settings.llm_provider == "groq" and settings.groq_api_key:
            return True
        if settings.llm_provider == "deepseek" and settings.deepseek_api_key:
            return True
        if settings.llm_provider == "gemini" and settings.gemini_api_key:
            return True

        return False

    async def analyze_sentiment(
        self,
        segments: list[dict],
        job_id: str,
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> SentimentAnalysisResult:
        """Analyze sentiment for transcript segments.

        Args:
            segments: List of segment dicts with start, end, text, speaker
            job_id: Job identifier
            window_size: Time window size in seconds for aggregation

        Returns:
            SentimentAnalysisResult with analysis data
        """
        if not self.provider:
            return SentimentAnalysisResult(
                success=False,
                job_id=job_id,
                error="No AI provider configured",
            )

        if not self.provider.is_available():
            return SentimentAnalysisResult(
                success=False,
                job_id=job_id,
                error=f"AI provider {self.provider.name} is not available",
            )

        if not segments:
            return SentimentAnalysisResult(
                success=False,
                job_id=job_id,
                error="No segments to analyze",
            )

        logger.info(f"Analyzing sentiment for {len(segments)} segments")
        total_tokens = 0

        try:
            # Analyze segments in batches
            analyzed_segments: list[SegmentSentiment] = []

            for batch_start in range(0, len(segments), self.BATCH_SIZE):
                batch_end = min(batch_start + self.BATCH_SIZE, len(segments))
                batch = segments[batch_start:batch_end]

                logger.info(f"Processing batch {batch_start // self.BATCH_SIZE + 1}")

                # Format segments for prompt
                segments_text = "\n".join(
                    f"[{i + batch_start}] ({seg['start']:.1f}s - {seg['end']:.1f}s): {seg['text']}"
                    for i, seg in enumerate(batch)
                )

                prompt = SEGMENT_ANALYSIS_PROMPT.format(segments=segments_text)
                response, tokens = await self.provider.generate(
                    prompt, SENTIMENT_SYSTEM_PROMPT
                )
                total_tokens += tokens

                # Parse response
                batch_results = self._parse_segment_analysis(response, batch, batch_start)
                analyzed_segments.extend(batch_results)

            # Mark heated segments
            for seg in analyzed_segments:
                seg.is_heated = seg.heat_score >= self.HEAT_THRESHOLD

            # Aggregate time windows
            time_windows = self._aggregate_time_windows(analyzed_segments, window_size)

            # Generate emotional arc
            emotional_arc = await self._generate_emotional_arc(
                analyzed_segments, total_tokens
            )

            return SentimentAnalysisResult(
                success=True,
                job_id=job_id,
                segments=analyzed_segments,
                time_windows=time_windows,
                emotional_arc=emotional_arc,
                model=self.provider.model_name,
                provider=self.provider.name,
                tokens_used=total_tokens,
            )

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return SentimentAnalysisResult(
                success=False,
                job_id=job_id,
                error=str(e),
                model=self.provider.model_name if self.provider else None,
                provider=self.provider.name if self.provider else None,
            )

    def _parse_segment_analysis(
        self, response: str, segments: list[dict], batch_start: int
    ) -> list[SegmentSentiment]:
        """Parse LLM response for segment analysis."""
        results = []

        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            parsed = json.loads(response.strip())

            if not isinstance(parsed, list):
                parsed = [parsed]

            for i, seg in enumerate(segments):
                seg_idx = batch_start + i

                # Find matching analysis result
                analysis = None
                for item in parsed:
                    if item.get("segment_index") == seg_idx:
                        analysis = item
                        break

                # If no match by index, use position
                if analysis is None and i < len(parsed):
                    analysis = parsed[i]

                if analysis:
                    # Helper to safely get float values with clamping
                    def safe_float(val, default, min_val=None, max_val=None):
                        if val is None:
                            return default
                        try:
                            result = float(val)
                            if min_val is not None:
                                result = max(min_val, result)
                            if max_val is not None:
                                result = min(max_val, result)
                            return result
                        except (ValueError, TypeError):
                            return default

                    def safe_int(val, default, min_val=None, max_val=None):
                        if val is None:
                            return default
                        try:
                            result = int(val)
                            if min_val is not None:
                                result = max(min_val, result)
                            if max_val is not None:
                                result = min(max_val, result)
                            return result
                        except (ValueError, TypeError):
                            return default

                    # Get emotions with defaults (clamped to 0-1)
                    emotions_raw = analysis.get("emotions") or {}
                    emotions = {
                        "joy": safe_float(emotions_raw.get("joy"), 0.0, 0.0, 1.0),
                        "anger": safe_float(emotions_raw.get("anger"), 0.0, 0.0, 1.0),
                        "fear": safe_float(emotions_raw.get("fear"), 0.0, 0.0, 1.0),
                        "surprise": safe_float(emotions_raw.get("surprise"), 0.0, 0.0, 1.0),
                        "sadness": safe_float(emotions_raw.get("sadness"), 0.0, 0.0, 1.0),
                    }

                    results.append(
                        SegmentSentiment(
                            segment_index=seg_idx,
                            start=seg["start"],
                            end=seg["end"],
                            text=seg["text"],
                            polarity=safe_float(analysis.get("polarity"), 0.0, -1.0, 1.0),
                            energy=analysis.get("energy") or "neutral",
                            energy_score=safe_float(analysis.get("energy_score"), 0.5, 0.0, 1.0),
                            excitement=safe_int(analysis.get("excitement"), 50, 0, 100),
                            emotions=emotions,
                            heat_score=safe_float(analysis.get("heat_score"), 0.3, 0.0, 1.0),
                            is_heated=False,  # Set later
                            speaker=seg.get("speaker"),
                        )
                    )
                else:
                    # Default values if parsing fails
                    results.append(
                        SegmentSentiment(
                            segment_index=seg_idx,
                            start=seg["start"],
                            end=seg["end"],
                            text=seg["text"],
                            polarity=0.0,
                            energy="neutral",
                            energy_score=0.5,
                            excitement=50,
                            emotions={"joy": 0, "anger": 0, "fear": 0, "surprise": 0, "sadness": 0},
                            heat_score=0.3,
                            is_heated=False,
                            speaker=seg.get("speaker"),
                        )
                    )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse segment analysis: {e}")
            # Return default values for all segments
            for i, seg in enumerate(segments):
                results.append(
                    SegmentSentiment(
                        segment_index=batch_start + i,
                        start=seg["start"],
                        end=seg["end"],
                        text=seg["text"],
                        polarity=0.0,
                        energy="neutral",
                        energy_score=0.5,
                        excitement=50,
                        emotions={"joy": 0, "anger": 0, "fear": 0, "surprise": 0, "sadness": 0},
                        heat_score=0.3,
                        is_heated=False,
                        speaker=seg.get("speaker"),
                    )
                )

        return results

    def _aggregate_time_windows(
        self, segments: list[SegmentSentiment], window_size: int
    ) -> list[TimeWindowAggregate]:
        """Aggregate sentiment data into time windows."""
        if not segments:
            return []

        # Find total duration
        max_end = max(seg.end for seg in segments)
        windows = []
        window_idx = 0
        current_start = 0.0

        while current_start < max_end:
            current_end = min(current_start + window_size, max_end)

            # Find segments in this window
            window_segments = [
                seg
                for seg in segments
                if seg.start < current_end and seg.end > current_start
            ]

            if window_segments:
                # Calculate averages
                avg_polarity = sum(s.polarity for s in window_segments) / len(window_segments)
                avg_heat = sum(s.heat_score for s in window_segments) / len(window_segments)

                # Find dominant emotion
                emotion_totals: dict[str, float] = {}
                for seg in window_segments:
                    for emotion, score in seg.emotions.items():
                        emotion_totals[emotion] = emotion_totals.get(emotion, 0) + score

                dominant_emotion = max(emotion_totals.items(), key=lambda x: x[1])[0] if emotion_totals else "neutral"

                windows.append(
                    TimeWindowAggregate(
                        window_index=window_idx,
                        start=current_start,
                        end=current_end,
                        avg_polarity=round(avg_polarity, 3),
                        avg_heat_score=round(avg_heat, 3),
                        dominant_emotion=dominant_emotion,
                        segment_count=len(window_segments),
                    )
                )

            window_idx += 1
            current_start = current_end

        return windows

    async def _generate_emotional_arc(
        self, segments: list[SegmentSentiment], tokens_so_far: int
    ) -> Optional[EmotionalArc]:
        """Generate overall emotional arc summary."""
        if not segments or not self.provider:
            return None

        try:
            # Calculate statistics
            heated_segments = [s for s in segments if s.is_heated]
            avg_heat = sum(s.heat_score for s in segments) / len(segments)

            # Get top heated moments
            top_heated = sorted(segments, key=lambda s: s.heat_score, reverse=True)[:5]
            top_moments_text = "\n".join(
                f"- {s.start:.1f}s: \"{s.text[:80]}...\" (heat: {s.heat_score:.2f})"
                for s in top_heated
            )

            # Aggregate emotions
            emotion_totals: dict[str, float] = {}
            for seg in segments:
                for emotion, score in seg.emotions.items():
                    emotion_totals[emotion] = emotion_totals.get(emotion, 0) + score

            emotion_text = "\n".join(
                f"- {emotion}: {total:.1f}" for emotion, total in sorted(emotion_totals.items(), key=lambda x: -x[1])
            )

            prompt = EMOTIONAL_ARC_PROMPT.format(
                total_segments=len(segments),
                avg_heat=f"{avg_heat:.2f}",
                heated_count=len(heated_segments),
                top_moments=top_moments_text,
                emotion_totals=emotion_text,
            )

            response, _ = await self.provider.generate(prompt, SENTIMENT_SYSTEM_PROMPT)

            # Parse response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            parsed = json.loads(response.strip())

            # Get dominant emotions (top 3 by total)
            sorted_emotions = sorted(emotion_totals.items(), key=lambda x: -x[1])
            raw_emotions = parsed.get("dominant_emotions", [e[0] for e in sorted_emotions[:3]])

            # Handle case where LLM returns objects instead of strings
            dominant_emotions = []
            for em in raw_emotions:
                if isinstance(em, str):
                    dominant_emotions.append(em)
                elif isinstance(em, dict):
                    # LLM might return {"emotion": "joy", "value": 0.5}
                    dominant_emotions.append(em.get("emotion", em.get("name", str(em))))
                else:
                    dominant_emotions.append(str(em))

            # Fallback to statistics-based emotions if parsing fails
            if not dominant_emotions:
                dominant_emotions = [e[0] for e in sorted_emotions[:3]]

            # Handle emotional_journey - might be string or object
            journey_raw = parsed.get("emotional_journey", "Unable to determine emotional journey.")
            if isinstance(journey_raw, str):
                emotional_journey = journey_raw
            elif isinstance(journey_raw, dict):
                # LLM might return complex object - extract text or convert to string
                emotional_journey = journey_raw.get("description", journey_raw.get("text", str(journey_raw)))
            else:
                emotional_journey = str(journey_raw)

            # Create peak moments list
            peak_moments = [
                {
                    "timestamp": s.start,
                    "description": s.text[:100],
                    "heat_score": s.heat_score,
                }
                for s in top_heated[:3]
            ]

            return EmotionalArc(
                overall_sentiment=parsed.get("overall_sentiment", "neutral") or "neutral",
                avg_heat_score=round(avg_heat, 3),
                peak_moments=peak_moments,
                dominant_emotions=dominant_emotions[:3],
                emotional_journey=emotional_journey,
                total_heated_segments=len(heated_segments),
                heated_percentage=round(len(heated_segments) / len(segments) * 100, 1),
            )

        except Exception as e:
            logger.warning(f"Failed to generate emotional arc: {e}")
            # Return basic arc from statistics
            heated_segments = [s for s in segments if s.is_heated]
            avg_heat = sum(s.heat_score for s in segments) / len(segments)
            avg_polarity = sum(s.polarity for s in segments) / len(segments)

            emotion_totals: dict[str, float] = {}
            for seg in segments:
                for emotion, score in seg.emotions.items():
                    emotion_totals[emotion] = emotion_totals.get(emotion, 0) + score

            sorted_emotions = sorted(emotion_totals.items(), key=lambda x: -x[1])
            top_heated = sorted(segments, key=lambda s: s.heat_score, reverse=True)[:3]

            return EmotionalArc(
                overall_sentiment="positive" if avg_polarity > 0.2 else "negative" if avg_polarity < -0.2 else "neutral",
                avg_heat_score=round(avg_heat, 3),
                peak_moments=[
                    {
                        "timestamp": s.start,
                        "description": s.text[:100],
                        "heat_score": s.heat_score,
                    }
                    for s in top_heated
                ],
                dominant_emotions=[e[0] for e in sorted_emotions[:3]],
                emotional_journey="Analysis based on statistical aggregation.",
                total_heated_segments=len(heated_segments),
                heated_percentage=round(len(heated_segments) / len(segments) * 100, 1),
            )

    def get_heated_moments(
        self, segments: list[SegmentSentiment], limit: int = 10
    ) -> list[SegmentSentiment]:
        """Get top heated moments from analyzed segments."""
        heated = [s for s in segments if s.is_heated]
        return sorted(heated, key=lambda s: s.heat_score, reverse=True)[:limit]
