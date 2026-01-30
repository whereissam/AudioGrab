"""Translation service using TranslateGemma via LiteLLM/Ollama."""

import logging
from dataclasses import dataclass
from typing import Optional

from litellm import acompletion

logger = logging.getLogger(__name__)


# TranslateGemma supported languages (55 languages)
SUPPORTED_LANGUAGES = {
    "af": "Afrikaans",
    "am": "Amharic",
    "ar": "Arabic",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "ga": "Irish",
    "gl": "Galician",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "hy": "Armenian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ka": "Georgian",
    "kk": "Kazakh",
    "km": "Khmer",
    "kn": "Kannada",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "mn": "Mongolian",
    "mr": "Marathi",
    "ms": "Malay",
    "my": "Burmese",
    "ne": "Nepali",
    "nl": "Dutch",
    "no": "Norwegian",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tl": "Filipino",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "zh-Hans": "Chinese (Simplified)",
    "zh-Hant": "Chinese (Traditional)",
}

# Common language aliases
LANGUAGE_ALIASES = {
    "zh": "zh-Hans",
    "chinese": "zh-Hans",
    "zh-cn": "zh-Hans",
    "zh-tw": "zh-Hant",
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "russian": "ru",
    "italian": "it",
    "dutch": "nl",
    "arabic": "ar",
    "hindi": "hi",
    "thai": "th",
    "vietnamese": "vi",
    "indonesian": "id",
    "turkish": "tr",
    "polish": "pl",
    "swedish": "sv",
    "norwegian": "no",
    "danish": "da",
    "finnish": "fi",
    "greek": "el",
    "hebrew": "he",
    "czech": "cs",
    "hungarian": "hu",
    "romanian": "ro",
    "ukrainian": "uk",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "punjabi": "pa",
    "urdu": "ur",
    "persian": "fa",
    "farsi": "fa",
    "malay": "ms",
    "filipino": "tl",
    "tagalog": "tl",
    "burmese": "my",
    "khmer": "km",
    "nepali": "ne",
    "mongolian": "mn",
    "kazakh": "kk",
    "uzbek": "uz",
    "azerbaijani": "az",
    "georgian": "ka",
    "armenian": "hy",
    "albanian": "sq",
    "serbian": "sr",
    "croatian": "hr",
    "slovenian": "sl",
    "slovak": "sk",
    "bulgarian": "bg",
    "macedonian": "mk",
    "lithuanian": "lt",
    "latvian": "lv",
    "estonian": "et",
    "belarusian": "be",
    "icelandic": "is",
    "welsh": "cy",
    "irish": "ga",
    "galician": "gl",
    "catalan": "ca",
    "afrikaans": "af",
    "swahili": "sw",
    "amharic": "am",
}


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    model: str
    tokens_used: Optional[int] = None


def normalize_language_code(lang: str) -> str:
    """Normalize a language code or name to standard code."""
    lang_lower = lang.lower().strip()

    # Check if it's an alias
    if lang_lower in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[lang_lower]

    # Check if it's already a valid code
    if lang in SUPPORTED_LANGUAGES:
        return lang

    # Check case-insensitive
    for code in SUPPORTED_LANGUAGES:
        if code.lower() == lang_lower:
            return code

    raise ValueError(f"Unsupported language: {lang}")


def get_language_name(code: str) -> str:
    """Get the full language name for a code."""
    normalized = normalize_language_code(code)
    return SUPPORTED_LANGUAGES.get(normalized, code)


class TranslateGemmaTranslator:
    """Translator using TranslateGemma model via Ollama/LiteLLM."""

    # Default model sizes available
    MODELS = {
        "4b": "translategemma:4b",
        "12b": "translategemma:12b",
        "27b": "translategemma:27b",
        "latest": "translategemma:latest",
    }

    def __init__(
        self,
        model: str = "translategemma:4b",
        base_url: str = "http://localhost:11434",
    ):
        """Initialize the translator.

        Args:
            model: Model name (translategemma:4b, 12b, or 27b)
            base_url: Ollama base URL
        """
        self.model = model
        self.base_url = base_url
        self._available: Optional[bool] = None

    def _build_prompt(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Build the TranslateGemma prompt format."""
        source_code = normalize_language_code(source_lang)
        target_code = normalize_language_code(target_lang)
        source_name = SUPPORTED_LANGUAGES[source_code]
        target_name = SUPPORTED_LANGUAGES[target_code]

        # TranslateGemma expects this specific format with two blank lines before text
        prompt = f"""You are a professional {source_name} ({source_code}) to {target_name} ({target_code}) translator. Your goal is to accurately convey the meaning and nuances of the original {source_name} text while adhering to {target_name} grammar, vocabulary, and cultural sensitivities.
Produce only the {target_name} translation, without any additional explanations or commentary. Please translate the following {source_name} text into {target_name}:


{text}"""
        return prompt

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        """Translate text from source language to target language.

        Args:
            text: Text to translate
            source_lang: Source language code or name
            target_lang: Target language code or name

        Returns:
            TranslationResult with translated text
        """
        # Normalize language codes
        source_code = normalize_language_code(source_lang)
        target_code = normalize_language_code(target_lang)

        if source_code == target_code:
            return TranslationResult(
                source_text=text,
                translated_text=text,
                source_lang=source_code,
                target_lang=target_code,
                model=self.model,
                tokens_used=0,
            )

        prompt = self._build_prompt(text, source_code, target_code)

        # Use LiteLLM to call Ollama
        response = await acompletion(
            model=f"ollama/{self.model}",
            messages=[{"role": "user", "content": prompt}],
            base_url=self.base_url,
        )

        translated = response.choices[0].message.content.strip()
        tokens = response.usage.total_tokens if response.usage else None

        return TranslationResult(
            source_text=text,
            translated_text=translated,
            source_lang=source_code,
            target_lang=target_code,
            model=self.model,
            tokens_used=tokens,
        )

    def is_available(self) -> bool:
        """Check if TranslateGemma is available."""
        if self._available is not None:
            return self._available

        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url.rstrip('/')}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Check if any translategemma model is available
                    self._available = any("translategemma" in m for m in models)
                else:
                    self._available = False
        except Exception:
            self._available = False

        return self._available

    @classmethod
    def from_settings(cls) -> "TranslateGemmaTranslator":
        """Create translator from application settings."""
        from ..config import get_settings
        settings = get_settings()

        return cls(
            model=getattr(settings, "translategemma_model", "translategemma:4b"),
            base_url=settings.ollama_base_url,
        )


def get_supported_languages() -> dict[str, str]:
    """Get all supported languages."""
    return SUPPORTED_LANGUAGES.copy()