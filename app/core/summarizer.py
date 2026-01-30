"""LLM-powered summarization service for transcripts."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SummaryType(str, Enum):
    """Types of summaries that can be generated."""
    BULLET_POINTS = "bullet_points"
    CHAPTERS = "chapters"
    KEY_TOPICS = "key_topics"
    ACTION_ITEMS = "action_items"
    FULL = "full"  # Comprehensive summary with all elements


@dataclass
class SummaryResult:
    """Result of a summarization operation."""
    summary_type: SummaryType
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> tuple[str, int]:
        """Generate a response from the LLM.

        Returns:
            Tuple of (response_text, tokens_used)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name being used."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._available: Optional[bool] = None

    async def generate(self, prompt: str, system_prompt: str = "") -> tuple[str, int]:
        import httpx

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "")
        tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
        return content, tokens

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available

        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                self._available = response.status_code == 200
        except Exception:
            self._available = False

        return self._available

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (also supports compatible endpoints)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def generate(self, prompt: str, system_prompt: str = "") -> tuple[str, int]:
        import httpx

        base = self.base_url or "https://api.openai.com/v1"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return content, tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def name(self) -> str:
        if self.base_url:
            return "openai_compatible"
        return "openai"

    @property
    def model_name(self) -> str:
        return self.model


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, system_prompt: str = "") -> tuple[str, int]:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": system_prompt if system_prompt else "You are a helpful assistant.",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["content"][0]["text"]
        tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
        return content, tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self.model


# Summarization prompts
SYSTEM_PROMPT = """You are an expert at analyzing and summarizing transcripts.
You provide clear, accurate, and well-structured summaries.
Always maintain the original meaning and key points.
Format your responses using markdown for better readability."""

PROMPTS = {
    SummaryType.BULLET_POINTS: """Summarize the following transcript into clear, concise bullet points.
Focus on the main ideas, key arguments, and important details.
Use nested bullets for supporting points.
Aim for 5-15 bullet points depending on content length.

Transcript:
{transcript}

Provide the bullet-point summary:""",

    SummaryType.CHAPTERS: """Analyze this transcript and create chapter markers with timestamps.
Each chapter should have:
- A timestamp (use the format [HH:MM:SS] or [MM:SS])
- A descriptive title
- A brief 1-2 sentence description

Identify natural topic transitions and segment the content accordingly.

Transcript:
{transcript}

Provide the chapters:""",

    SummaryType.KEY_TOPICS: """Extract the key topics and themes from this transcript.
For each topic:
- Provide a clear topic name
- Explain why it's significant
- Note how much of the discussion it covers (major/minor topic)

Group related topics together.

Transcript:
{transcript}

Provide the key topics:""",

    SummaryType.ACTION_ITEMS: """Extract all action items, tasks, commitments, and follow-ups from this transcript.
For each action item:
- What needs to be done
- Who is responsible (if mentioned)
- Any deadlines or timeframes mentioned
- Priority level (high/medium/low) based on context

If this is not a meeting-style transcript, note that and provide any implicit recommendations or suggested actions.

Transcript:
{transcript}

Provide the action items:""",

    SummaryType.FULL: """Provide a comprehensive summary of this transcript including:

## Overview
A 2-3 sentence executive summary of the entire content.

## Key Points
The main ideas and arguments presented (as bullet points).

## Topics Discussed
Major themes and subjects covered.

## Notable Quotes
2-3 significant or memorable quotes from the transcript.

## Conclusion
How the content wraps up and any final takeaways.

Transcript:
{transcript}

Provide the comprehensive summary:""",
}


class TranscriptSummarizer:
    """Service for summarizing transcripts using LLMs."""

    # Approximate token limits for chunking (conservative estimates)
    CHUNK_SIZE = 6000  # ~6000 words per chunk
    OVERLAP = 500  # Overlap between chunks for context

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider

    @classmethod
    def from_settings(cls) -> "TranscriptSummarizer":
        """Create summarizer from application settings."""
        from ..config import get_settings
        settings = get_settings()

        provider: Optional[LLMProvider] = None

        if settings.llm_provider == "ollama":
            provider = OllamaProvider(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
            )
        elif settings.llm_provider == "openai" and settings.openai_api_key:
            provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url,
            )
        elif settings.llm_provider == "openai_compatible" and settings.openai_api_key:
            provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url,
            )
        elif settings.llm_provider == "anthropic" and settings.anthropic_api_key:
            provider = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )

        return cls(provider=provider)

    @staticmethod
    def is_available() -> bool:
        """Check if any summarization provider is available."""
        from ..config import get_settings
        settings = get_settings()

        # Check Ollama
        if settings.llm_provider == "ollama":
            try:
                import httpx
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(f"{settings.ollama_base_url}/api/tags")
                    if response.status_code == 200:
                        return True
            except Exception:
                pass

        # Check OpenAI
        if settings.llm_provider in ("openai", "openai_compatible") and settings.openai_api_key:
            return True

        # Check Anthropic
        if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
            return True

        return False

    def _chunk_transcript(self, transcript: str) -> list[str]:
        """Split transcript into chunks for processing."""
        words = transcript.split()
        if len(words) <= self.CHUNK_SIZE:
            return [transcript]

        chunks = []
        start = 0
        while start < len(words):
            end = start + self.CHUNK_SIZE
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            start = end - self.OVERLAP  # Overlap for context

        return chunks

    async def summarize(
        self,
        transcript: str,
        summary_type: SummaryType = SummaryType.BULLET_POINTS,
    ) -> SummaryResult:
        """Summarize a transcript.

        Args:
            transcript: The transcript text to summarize
            summary_type: Type of summary to generate

        Returns:
            SummaryResult with the generated summary
        """
        if not self.provider:
            raise ValueError("No LLM provider configured")

        if not self.provider.is_available():
            raise ValueError(f"LLM provider {self.provider.name} is not available")

        chunks = self._chunk_transcript(transcript)
        logger.info(f"Summarizing transcript in {len(chunks)} chunk(s)")

        if len(chunks) == 1:
            # Single chunk - direct summarization
            prompt = PROMPTS[summary_type].format(transcript=transcript)
            content, tokens = await self.provider.generate(prompt, SYSTEM_PROMPT)
        else:
            # Multiple chunks - summarize each then combine
            chunk_summaries = []
            total_tokens = 0

            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i + 1}/{len(chunks)}")
                prompt = PROMPTS[summary_type].format(transcript=chunk)
                summary, tokens = await self.provider.generate(prompt, SYSTEM_PROMPT)
                chunk_summaries.append(summary)
                total_tokens += tokens

            # Combine chunk summaries
            combined = "\n\n---\n\n".join(chunk_summaries)
            combine_prompt = f"""The following are summaries of different parts of a longer transcript.
Please combine them into a single coherent {summary_type.value.replace('_', ' ')} summary,
removing any redundancy while preserving all unique information.

Part summaries:
{combined}

Provide the combined summary:"""

            content, final_tokens = await self.provider.generate(combine_prompt, SYSTEM_PROMPT)
            tokens = total_tokens + final_tokens

        return SummaryResult(
            summary_type=summary_type,
            content=content,
            model=self.provider.model_name,
            provider=self.provider.name,
            tokens_used=tokens,
        )

    async def summarize_all(self, transcript: str) -> dict[SummaryType, SummaryResult]:
        """Generate all types of summaries for a transcript.

        Returns:
            Dictionary mapping summary types to their results
        """
        results = {}
        for summary_type in SummaryType:
            if summary_type != SummaryType.FULL:  # Skip full to avoid redundancy
                results[summary_type] = await self.summarize(transcript, summary_type)
        return results
