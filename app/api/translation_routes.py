"""API routes for translation using TranslateGemma."""

import logging
from fastapi import APIRouter, HTTPException

from .schemas import (
    TranslateRequest,
    TranslateFromJobRequest,
    TranslateResponse,
    LanguageInfo,
    SupportedLanguagesResponse,
)
from ..core.translator import (
    TranslateGemmaTranslator,
    get_supported_languages,
    normalize_language_code,
    get_language_name,
    SUPPORTED_LANGUAGES,
)
from ..core.job_store import get_job_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate", tags=["Translation"])


@router.get("/languages", response_model=SupportedLanguagesResponse)
async def get_languages():
    """Get list of supported languages for translation.

    TranslateGemma supports 55 languages including major world languages,
    Asian languages, European languages, and more.
    """
    languages = [
        LanguageInfo(code=code, name=name)
        for code, name in sorted(SUPPORTED_LANGUAGES.items(), key=lambda x: x[1])
    ]
    return SupportedLanguagesResponse(
        languages=languages,
        total=len(languages),
    )


@router.get("/available")
async def check_availability():
    """Check if TranslateGemma is available.

    Returns availability status and which model sizes are installed.
    """
    from ..config import get_settings
    settings = get_settings()

    result = {
        "available": False,
        "models": [],
        "ollama_url": settings.ollama_base_url,
    }

    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                translate_models = [m for m in models if "translategemma" in m.lower()]
                result["available"] = len(translate_models) > 0
                result["models"] = translate_models
    except Exception as e:
        result["error"] = str(e)

    return result


@router.post("", response_model=TranslateResponse)
async def translate_text(request: TranslateRequest):
    """Translate text from one language to another.

    Uses TranslateGemma model via Ollama for high-quality translation
    between 55 supported languages.

    Example:
    ```json
    {
        "text": "Hello, how are you?",
        "source_lang": "en",
        "target_lang": "ja"
    }
    ```
    """
    # Validate languages
    try:
        source_code = normalize_language_code(request.source_lang)
        target_code = normalize_language_code(request.target_lang)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Determine model
    model = request.model or "translategemma:latest"
    if not model.startswith("translategemma"):
        # Allow shorthand like "4b" -> "translategemma:4b"
        model = f"translategemma:{model}"

    # Create translator
    from ..config import get_settings
    settings = get_settings()

    translator = TranslateGemmaTranslator(
        model=model,
        base_url=settings.ollama_base_url,
    )

    # Check availability
    if not translator.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"TranslateGemma is not available. Please install it with: ollama pull {model}",
        )

    try:
        result = await translator.translate(
            text=request.text,
            source_lang=source_code,
            target_lang=target_code,
        )

        return TranslateResponse(
            source_text=result.source_text,
            translated_text=result.translated_text,
            source_lang=result.source_lang,
            target_lang=result.target_lang,
            source_lang_name=get_language_name(result.source_lang),
            target_lang_name=get_language_name(result.target_lang),
            model=result.model,
            tokens_used=result.tokens_used,
        )

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/job", response_model=TranslateResponse)
async def translate_job(request: TranslateFromJobRequest):
    """Translate a completed transcription job.

    Retrieves the transcript from a completed job and translates it
    to the target language.
    """
    job_store = get_job_store()
    job = job_store.get_job(request.job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job['status']})",
        )

    # Get transcript text
    transcription = job.get("transcription_result")
    if not transcription:
        raise HTTPException(
            status_code=400,
            detail="Job has no transcription result",
        )

    text = transcription.get("text", "")
    if not text:
        raise HTTPException(
            status_code=400,
            detail="Transcription has no text content",
        )

    # Determine source language
    source_lang = request.source_lang
    if not source_lang:
        # Try to get from transcription result
        source_lang = transcription.get("language", "en")

    # Validate languages
    try:
        source_code = normalize_language_code(source_lang)
        target_code = normalize_language_code(request.target_lang)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Determine model
    model = request.model or "translategemma:latest"
    if not model.startswith("translategemma"):
        model = f"translategemma:{model}"

    # Create translator
    from ..config import get_settings
    settings = get_settings()

    translator = TranslateGemmaTranslator(
        model=model,
        base_url=settings.ollama_base_url,
    )

    if not translator.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"TranslateGemma is not available. Please install it with: ollama pull {model}",
        )

    try:
        result = await translator.translate(
            text=text,
            source_lang=source_code,
            target_lang=target_code,
        )

        return TranslateResponse(
            source_text=result.source_text,
            translated_text=result.translated_text,
            source_lang=result.source_lang,
            target_lang=result.target_lang,
            source_lang_name=get_language_name(result.source_lang),
            target_lang_name=get_language_name(result.target_lang),
            model=result.model,
            tokens_used=result.tokens_used,
        )

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")
