"""LLM-powered structured data extraction service for transcripts."""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .summarizer import LiteLLMProvider

logger = logging.getLogger(__name__)


class ExtractionPreset(str, Enum):
    """Available extraction presets."""

    MEETING_NOTES = "meeting_notes"
    INTERVIEW = "interview"
    TUTORIAL = "tutorial"
    NEWS_ANALYSIS = "news_analysis"
    PRODUCT_REVIEW = "product_review"
    CUSTOM = "custom"


@dataclass
class ExtractedField:
    """Individual extracted field."""

    key: str
    value: object  # Can be str, list, dict, etc.
    field_type: str  # "string", "list", "object_list", etc.

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "field_type": self.field_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedField":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            field_type=data["field_type"],
        )


@dataclass
class ExtractionResult:
    """Complete extraction result."""

    success: bool
    job_id: str
    preset: Optional[str] = None
    fields: list[ExtractedField] = field(default_factory=list)
    raw_output: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "job_id": self.job_id,
            "preset": self.preset,
            "fields": [f.to_dict() for f in self.fields],
            "raw_output": self.raw_output,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractionResult":
        """Create from dictionary."""
        return cls(
            success=data["success"],
            job_id=data["job_id"],
            preset=data.get("preset"),
            fields=[ExtractedField.from_dict(f) for f in data.get("fields", [])],
            raw_output=data.get("raw_output"),
            model=data.get("model"),
            provider=data.get("provider"),
            tokens_used=data.get("tokens_used"),
            error=data.get("error"),
        )


# Preset descriptions for the frontend
PRESET_INFO = {
    ExtractionPreset.MEETING_NOTES: {
        "name": "Meeting Notes",
        "description": "Extract attendees, agenda items, decisions, action items, and key quotes",
        "example_fields": ["attendees", "agenda_items", "decisions", "action_items", "key_quotes"],
    },
    ExtractionPreset.INTERVIEW: {
        "name": "Interview",
        "description": "Extract interviewer/interviewee, Q&A pairs, key quotes, and topics",
        "example_fields": ["interviewer", "interviewee", "questions", "key_quotes", "topics_discussed"],
    },
    ExtractionPreset.TUTORIAL: {
        "name": "Tutorial",
        "description": "Extract title, prerequisites, step-by-step instructions, tools, and links",
        "example_fields": ["title", "prerequisites", "steps", "tools_mentioned", "links_mentioned"],
    },
    ExtractionPreset.NEWS_ANALYSIS: {
        "name": "News / Analysis",
        "description": "Extract claims with evidence, predictions, entities, and key takeaways",
        "example_fields": ["claims", "predictions", "entities", "key_takeaways"],
    },
    ExtractionPreset.PRODUCT_REVIEW: {
        "name": "Product Review",
        "description": "Extract product name, rating, pros, cons, comparisons, and verdict",
        "example_fields": ["product_name", "overall_rating", "pros", "cons", "comparisons", "verdict"],
    },
}

# System prompt for extraction
EXTRACTION_SYSTEM_PROMPT = """You are an expert at extracting structured data from transcripts.
You analyze transcripts carefully and extract accurate, well-organized information matching the requested schema.
You output ONLY valid JSON responses following the exact schema provided. No other text."""

# Preset-specific prompts
PRESET_PROMPTS = {
    ExtractionPreset.MEETING_NOTES: """Extract structured meeting notes from the following transcript.

Return a JSON object with this exact schema:
{{
  "attendees": ["list of people mentioned or participating"],
  "agenda_items": ["list of topics/agenda items discussed"],
  "decisions": [
    {{"decision": "what was decided", "context": "brief context for the decision"}}
  ],
  "action_items": [
    {{"task": "description of the task", "assignee": "person responsible (if mentioned)", "deadline": "deadline (if mentioned)"}}
  ],
  "key_quotes": ["notable direct quotes from the transcript"]
}}

Transcript:
{transcript}

Return ONLY the JSON object, no other text.""",

    ExtractionPreset.INTERVIEW: """Extract structured interview data from the following transcript.

Return a JSON object with this exact schema:
{{
  "interviewer": "name or role of the interviewer",
  "interviewee": "name or role of the interviewee",
  "questions": [
    {{"question": "the question asked", "answer": "summary of the answer", "timestamp": "approximate timestamp if available"}}
  ],
  "key_quotes": ["notable direct quotes from the interview"],
  "topics_discussed": ["list of main topics covered"]
}}

Transcript:
{transcript}

Return ONLY the JSON object, no other text.""",

    ExtractionPreset.TUTORIAL: """Extract structured tutorial data from the following transcript.

Return a JSON object with this exact schema:
{{
  "title": "title or topic of the tutorial",
  "prerequisites": ["list of prerequisites or prior knowledge needed"],
  "steps": [
    {{"step_number": 1, "description": "what to do in this step", "timestamp": "approximate timestamp if available"}}
  ],
  "tools_mentioned": ["list of tools, software, or technologies mentioned"],
  "links_mentioned": ["list of URLs or resources mentioned"]
}}

Transcript:
{transcript}

Return ONLY the JSON object, no other text.""",

    ExtractionPreset.NEWS_ANALYSIS: """Extract structured news/analysis data from the following transcript.

Return a JSON object with this exact schema:
{{
  "claims": [
    {{"claim": "a claim or assertion made", "evidence": "supporting evidence if provided", "source": "source cited if any"}}
  ],
  "predictions": ["list of predictions or forecasts made"],
  "entities": [
    {{"name": "person, org, or place", "type": "person/organization/location/event", "context": "brief context of their mention"}}
  ],
  "key_takeaways": ["list of main takeaways or conclusions"]
}}

Transcript:
{transcript}

Return ONLY the JSON object, no other text.""",

    ExtractionPreset.PRODUCT_REVIEW: """Extract structured product review data from the following transcript.

Return a JSON object with this exact schema:
{{
  "product_name": "name of the product being reviewed",
  "overall_rating": "overall assessment (e.g., '4/5', 'Recommended', 'Mixed')",
  "pros": ["list of positive points"],
  "cons": ["list of negative points"],
  "comparisons": ["comparisons to other products mentioned"],
  "verdict": "final verdict or recommendation"
}}

Transcript:
{transcript}

Return ONLY the JSON object, no other text.""",
}

# Prompt for merging chunked extraction results
MERGE_PROMPT = """You have extracted structured data from multiple chunks of the same transcript.
Merge and deduplicate the following partial results into a single consolidated result.

Partial results:
{partial_results}

Return a single consolidated JSON object that:
- Combines all items from each partial result
- Removes exact duplicates
- Preserves all unique information
- Follows the same schema as the partial results

Return ONLY the merged JSON object, no other text."""

# Prompt for custom schema extraction
CUSTOM_EXTRACTION_PROMPT = """Extract structured data from the following transcript according to the custom schema below.

Custom schema fields:
{schema_description}

Return a JSON object where each key matches a field name from the schema, with values matching the described types.

Transcript:
{transcript}

Return ONLY the JSON object, no other text."""


class StructuredExtractor:
    """Service for extracting structured data from transcripts using LLMs."""

    CHUNK_SIZE = 6000  # ~6000 words per chunk
    OVERLAP = 500  # Overlap between chunks for context

    def __init__(self, provider: Optional[LiteLLMProvider] = None):
        self.provider = provider

    @classmethod
    def from_settings(cls) -> "StructuredExtractor":
        """Create extractor from application settings or database config."""
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
            return model

    @staticmethod
    def is_available() -> bool:
        """Check if structured extraction is available."""
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
            start = end - self.OVERLAP

        return chunks

    def _build_prompt(
        self, transcript: str, preset: ExtractionPreset, custom_schema: Optional[dict] = None
    ) -> str:
        """Build extraction prompt for a given preset."""
        if preset == ExtractionPreset.CUSTOM and custom_schema:
            fields = custom_schema.get("fields", [])
            schema_lines = []
            for f in fields:
                name = f.get("name", "unknown")
                ftype = f.get("type", "string")
                desc = f.get("description", "")
                schema_lines.append(f'- "{name}" ({ftype}): {desc}')
            schema_description = "\n".join(schema_lines)
            return CUSTOM_EXTRACTION_PROMPT.format(
                schema_description=schema_description,
                transcript=transcript,
            )

        prompt_template = PRESET_PROMPTS.get(preset)
        if not prompt_template:
            raise ValueError(f"Unknown preset: {preset}")

        return prompt_template.format(transcript=transcript)

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response, handling code blocks."""
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    def _json_to_fields(self, data: dict) -> list[ExtractedField]:
        """Convert a parsed JSON dict into a list of ExtractedField."""
        fields = []
        for key, value in data.items():
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    field_type = "object_list"
                else:
                    field_type = "list"
            elif isinstance(value, dict):
                field_type = "object"
            elif isinstance(value, (int, float)):
                field_type = "number"
            elif isinstance(value, bool):
                field_type = "boolean"
            else:
                field_type = "string"
            fields.append(ExtractedField(key=key, value=value, field_type=field_type))
        return fields

    async def extract(
        self,
        transcript: str,
        job_id: str,
        preset: ExtractionPreset,
        custom_schema: Optional[dict] = None,
    ) -> ExtractionResult:
        """Extract structured data from a transcript.

        Args:
            transcript: Full transcript text
            job_id: Job identifier
            preset: Extraction preset to use
            custom_schema: Custom schema dict (only for CUSTOM preset)

        Returns:
            ExtractionResult with extracted fields
        """
        if not self.provider:
            return ExtractionResult(
                success=False,
                job_id=job_id,
                preset=preset.value,
                error="No AI provider configured",
            )

        if not self.provider.is_available():
            return ExtractionResult(
                success=False,
                job_id=job_id,
                preset=preset.value,
                error=f"AI provider {self.provider.name} is not available",
            )

        if not transcript or not transcript.strip():
            return ExtractionResult(
                success=False,
                job_id=job_id,
                preset=preset.value,
                error="No transcript text to extract from",
            )

        logger.info(f"Extracting structured data with preset '{preset.value}' for job {job_id}")
        total_tokens = 0

        try:
            chunks = self._chunk_transcript(transcript)

            if len(chunks) == 1:
                # Single chunk — direct extraction
                prompt = self._build_prompt(chunks[0], preset, custom_schema)
                response, tokens = await self.provider.generate(
                    prompt, EXTRACTION_SYSTEM_PROMPT
                )
                total_tokens += tokens

                parsed = self._parse_json_response(response)
                fields = self._json_to_fields(parsed)
                raw_output = json.dumps(parsed, indent=2, ensure_ascii=False)

            else:
                # Multiple chunks — extract from each, then merge
                logger.info(f"Transcript split into {len(chunks)} chunks")
                partial_results = []

                for i, chunk in enumerate(chunks):
                    logger.info(f"Processing chunk {i + 1}/{len(chunks)}")
                    prompt = self._build_prompt(chunk, preset, custom_schema)
                    response, tokens = await self.provider.generate(
                        prompt, EXTRACTION_SYSTEM_PROMPT
                    )
                    total_tokens += tokens

                    try:
                        parsed = self._parse_json_response(response)
                        partial_results.append(parsed)
                    except (json.JSONDecodeError, IndexError):
                        logger.warning(f"Failed to parse chunk {i + 1} response")

                if not partial_results:
                    return ExtractionResult(
                        success=False,
                        job_id=job_id,
                        preset=preset.value,
                        error="Failed to parse any extraction results",
                        model=self.provider.model_name,
                        provider=self.provider.name,
                        tokens_used=total_tokens,
                    )

                # Merge partial results
                merge_prompt = MERGE_PROMPT.format(
                    partial_results=json.dumps(partial_results, indent=2, ensure_ascii=False)
                )
                merge_response, merge_tokens = await self.provider.generate(
                    merge_prompt, EXTRACTION_SYSTEM_PROMPT
                )
                total_tokens += merge_tokens

                parsed = self._parse_json_response(merge_response)
                fields = self._json_to_fields(parsed)
                raw_output = json.dumps(parsed, indent=2, ensure_ascii=False)

            return ExtractionResult(
                success=True,
                job_id=job_id,
                preset=preset.value,
                fields=fields,
                raw_output=raw_output,
                model=self.provider.model_name,
                provider=self.provider.name,
                tokens_used=total_tokens,
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed during extraction: {e}")
            return ExtractionResult(
                success=False,
                job_id=job_id,
                preset=preset.value,
                error=f"Failed to parse extraction result as JSON: {e}",
                model=self.provider.model_name if self.provider else None,
                provider=self.provider.name if self.provider else None,
                tokens_used=total_tokens,
            )
        except Exception as e:
            logger.error(f"Structured extraction failed: {e}")
            return ExtractionResult(
                success=False,
                job_id=job_id,
                preset=preset.value,
                error=str(e),
                model=self.provider.model_name if self.provider else None,
                provider=self.provider.name if self.provider else None,
                tokens_used=total_tokens,
            )
