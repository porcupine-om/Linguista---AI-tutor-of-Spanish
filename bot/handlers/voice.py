"""
Обработчик голосовых сообщений:
- Упражнение voice (waiting_for_voice): транскрипция → проверка LLM → следующий шаг
- Упражнения fill_text/dialogue: транскрипция → проверка как текст → следующий шаг
- Упражнение choice: «Выбери ответ, нажав на кнопку»
- Вне урока: «🎙 Я услышал: {text}»
"""
import logging
import os

from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.services.speech import transcribe_voice
from bot.services.llm import check_voice_answer, check_fill_text, evaluate_dialogue
from bot.services.review import add_mistake
from bot.services.achievements_service import check_achievements
from bot.db.user_repo import add_xp, increment_voice_practice, get_user_by_telegram_id
from bot.db.session import async_session
from bot.handlers.a1 import _extract_russian_from_question

router = Router()
logger = logging.getLogger(__name__)


async def _process_voice_as_text_answer(message: Message, state: FSMContext, text: str) -> bool:
    """
    Обрабатывает распознанный текст как ответ на fill_text/dialogue.
    Возвращает True, если обработано.
    """
    data = await state.get_data()
    exercises = data.get("exercises", [])
    if not exercises:
        return False

    ex_idx = data.get("exercise_index", 0)
    ex = exercises[ex_idx]
    ex_type = ex.get("type", "")

    if ex_type == "choice":
        await message.answer("Выбери ответ, нажав на кнопку.")
        return True

    if ex_type not in ("fill_text", "dialogue"):
        return False

    lesson_num = data.get("lesson_num", 1)
    level = data.get("lesson_level", "A2")
    prefix = "a1" if level == "A1" else "a2"

    if ex_type == "fill_text":
        await message.answer("Проверяю твой ответ…")
        correct, feedback = await check_fill_text(text, ex.get("answer", ""))
        await message.answer(feedback)
        if not correct:
            expected = ex.get("answer", "")
            question = ex.get("question", "")
            if "___" in question:
                content = question.replace("___", expected).replace("«", "").replace("»", "").strip()
            else:
                content = expected
            answer_ru = _extract_russian_from_question(question) or expected
            await add_mistake(
                telegram_id=message.from_user.id,
                item_id=f"{prefix}_{lesson_num}_fill_{ex_idx}",
                item_type="exercise",
                content=content if content else expected,
                answer=answer_ru,
            )
    else:  # dialogue
        await message.answer("Проверяю твой ответ…")
        lesson = data.get("lesson", {})
        theory = lesson.get("theory", "")
        feedback = await evaluate_dialogue(text, ex.get("prompt", ""), theory=theory)
        await message.answer(feedback)
        if feedback.strip().startswith("❌"):
            content = ex.get("review_content", "")
            answer_ru = ex.get("review_answer", "")
            if not content or not answer_ru:
                content = ex.get("prompt", "")
                answer_ru = ex.get("prompt", "")
            await add_mistake(
                telegram_id=message.from_user.id,
                item_id=f"{prefix}_{lesson_num}_dialogue_{ex_idx}",
                item_type="exercise",
                content=content,
                answer=answer_ru,
            )

    ex_idx += 1
    if ex_idx >= len(exercises):
        if level == "A1":
            from bot.handlers.a1 import _complete_a1_lesson
            await _complete_a1_lesson(message, state)
        elif level == "B1":
            from bot.handlers.b1 import _complete_b1_lesson
            await _complete_b1_lesson(message, state)
        else:
            from bot.handlers.a2 import _complete_a2_lesson
            await _complete_a2_lesson(message, state)
    else:
        await state.update_data(exercise_index=ex_idx)
        if level == "A1":
            from bot.handlers.a1 import _show_exercise
            await _show_exercise(message, state, exercises[ex_idx], ex_idx)
        elif level == "B1":
            from bot.handlers.b1 import _show_exercise
            await _show_exercise(message, state, exercises[ex_idx], ex_idx)
        else:
            from bot.handlers.a2 import _show_exercise
            await _show_exercise(message, state, exercises[ex_idx], ex_idx)

    return True


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot, state: FSMContext):
    # ZERO и A1 — голосовых заданий нет; просим писать текстом
    state_key = str(await state.get_state() or "")
    data = await state.get_data()
    waiting = data.get("waiting_for_voice", False)
    in_zero = "ZeroStates" in state_key
    in_a1_exercise = "A1States" in state_key and "exercise" in state_key

    if (in_zero or (in_a1_exercise and not waiting)):
        await message.answer("Голосовой ввод не требуется, напиши свой ответ.")
        return

    os.makedirs("tmp", exist_ok=True)
    file = await bot.get_file(message.voice.file_id)
    path = f"tmp/{message.voice.file_id}.ogg"

    try:
        await bot.download_file(file.file_path, path)
        await message.answer("🎙 Обрабатываю голосовое сообщение…")
        text = await transcribe_voice(path)

        if not text:
            await message.answer("Не удалось распознать речь. Попробуй записать ещё раз.")
            return

        state_key = str(await state.get_state() or "")
        in_lesson = "exercise" in state_key and ("A1States" in state_key or "A2States" in state_key or "B1States" in state_key)

        # Текущее упражнение — voice, fill_text или dialogue?
        exercises = data.get("exercises", [])
        ex_idx = data.get("exercise_index", 0)
        current_ex = exercises[ex_idx] if ex_idx < len(exercises) else {}
        ex_type = current_ex.get("type", "")
        is_voice_exercise = ex_type == "voice"
        is_text_exercise_with_voice = ex_type in ("fill_text", "dialogue", "open")
        expected_voice = data.get("lesson_voice_expected") or current_ex.get("expected", "")
        # Для fill_text — эталон ответа; для dialogue/open — открытая проверка
        if ex_type == "fill_text":
            expected_for_check = current_ex.get("answer", "")
        elif ex_type in ("dialogue", "open"):
            expected_for_check = "любая допустимая фраза (проверка будет от LLM)"
        else:
            expected_for_check = expected_voice

        # Voice-упражнение ИЛИ fill_text/dialogue, на которые ответили голосом — проверяем как voice
        if waiting or (in_lesson and is_voice_exercise and expected_voice) or (in_lesson and is_text_exercise_with_voice and expected_for_check):
            # Голосовое упражнение или fill_text/dialogue, на которые ответили голосом
            await message.answer(f"🎙 Я услышал:\n{text}")
            expected = data.get("lesson_voice_expected") or expected_voice or expected_for_check
            await message.answer("Проверяю произношение…")
            correct, feedback_ru, corrected = await check_voice_answer(expected, text)
            if correct:
                await message.answer(f"✅ Верно!\n{feedback_ru}")
            else:
                msg = f"❌ Почти правильно\n\n{feedback_ru}\n\n👉 Правильно: {corrected}"
                await message.answer(msg)
            await state.update_data(waiting_for_voice=False)

            await add_xp(message.from_user.id, 20)
            await increment_voice_practice(message.from_user.id)
            async with async_session() as session:
                user = await get_user_by_telegram_id(message.from_user.id, session)
            new_achievements = await check_achievements(user)
            for ach in new_achievements:
                await message.answer_dice(emoji="🎲")
                await message.answer(
                    f"🏆 Новое достижение!\n\n<b>{ach['title']}</b>\n{ach['desc']}"
                )

            exercises = data.get("exercises", [])
            ex_idx = data.get("exercise_index", 0) + 1
            level = data.get("lesson_level", "A2")

            if ex_idx >= len(exercises):
                if level == "A1":
                    from bot.handlers.a1 import _complete_a1_lesson
                    await _complete_a1_lesson(message, state)
                elif level == "B1":
                    from bot.handlers.b1 import _complete_b1_lesson
                    await _complete_b1_lesson(message, state)
                else:
                    from bot.handlers.a2 import _complete_a2_lesson
                    await _complete_a2_lesson(message, state)
            else:
                await state.update_data(exercise_index=ex_idx)
                if level == "A1":
                    from bot.handlers.a1 import _show_exercise
                    await _show_exercise(message, state, exercises[ex_idx], ex_idx)
                elif level == "B1":
                    from bot.handlers.b1 import _show_exercise
                    await _show_exercise(message, state, exercises[ex_idx], ex_idx)
                else:
                    from bot.handlers.a2 import _show_exercise
                    await _show_exercise(message, state, exercises[ex_idx], ex_idx)
        elif in_lesson:
            # fill_text или dialogue — голос как альтернатива тексту
            await message.answer(f"🎙 Я услышал:\n{text}")
            await _process_voice_as_text_answer(message, state, text)
        else:
            # Вне урока — просто показать распознанное
            await message.answer(f"🎙 Я услышал:\n{text}")

    except Exception as e:
        logger.exception("Voice error: %s", e)
        await message.answer("Не удалось распознать речь. Попробуй записать ещё раз.")
    finally:
        if os.path.exists(path):
            os.remove(path)
