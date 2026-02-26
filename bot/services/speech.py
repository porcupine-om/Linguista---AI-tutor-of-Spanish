"""
Сервис распознавания речи (Whisper) через OpenAI API.
"""
from bot.services.llm import _get_llm_client


async def transcribe_voice(file_path: str) -> str:
    """
    Транскрибирует голосовой файл через OpenAI Whisper (speech-to-text).
    Возвращает распознанный текст или пустую строку при ошибке.
    """
    client = _get_llm_client()
    if not client:
        return ""

    with open(file_path, "rb") as f:
        transcript = await client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f,
            language="es",  # Испанский — чтобы не транскрибировать в русскую транскрипцию
        )

    return (transcript.text or "").strip()
