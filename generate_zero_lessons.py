"""
Генерация 21 ZERO-урока из cards_zero.json.
Структура как в zero_01.json: 5 карточек + 1-2 quiz-вопроса (choice).
"""
import json
import random
import re
from pathlib import Path

random.seed(42)

CARDS_PATH = Path(__file__).parent / "data" / "cards_zero.json"
LESSONS_DIR = Path(__file__).parent / "data" / "zero_lessons"

TOPIC_TITLES = {
    "phonetics": "Фонетика",
    "greetings": "Приветствия",
    "numbers": "Числа",
    "verbs": "Глаголы",
    "yes_no": "Да и нет",
    "pronouns": "Местоимения",
    "grammar_ser": "Глагол ser",
    "basic_nouns": "Базовые слова",
    "colors": "Цвета",
    "adjectives": "Прилагательные",
    "articles": "Артикли",
    "time": "Время",
    "first_sentence": "Первая фраза",
}


def slug(s: str) -> str:
    """Безопасный card_id из spanish."""
    s = re.sub(r"[/\s]+", "_", s.strip())
    return re.sub(r"[^\w\-]", "", s) or "card"


def make_lesson_cards(cards: list[dict]) -> list[dict]:
    return [
        {
            "card_id": slug(c["spanish"]),
            "spanish": c["spanish"],
            "russian": c["translation"],
            "example": c.get("example", ""),
            "note": c.get("note", ""),
            "order": c["order"],
        }
        for c in cards
    ]


def make_quiz_questions(cards: list[dict], all_cards: list[dict], lesson_idx: int) -> list[dict]:
    """1-2 простых choice-вопроса по карточкам урока."""
    questions = []
    spanishes = [c["spanish"] for c in cards]
    russians = [c["translation"] for c in cards]
    rng = random.Random(lesson_idx + 42)

    # Вопрос 1: "Как переводится X?"
    if spanishes:
        idx = 0
        correct_ru = russians[idx]
        wrong = [c["translation"] for c in all_cards if c["translation"] != correct_ru and len(c["translation"]) < 50]
        wrong = rng.sample(wrong, min(3, len(wrong)))
        options = [correct_ru] + wrong
        rng.shuffle(options)
        correct_idx = options.index(correct_ru)
        questions.append({
            "question": f"Как переводится «{spanishes[idx]}»?",
            "options": options,
            "correct_index": correct_idx,
        })

    # Вопрос 2: "Какое испанское слово означает Y?"
    if len(cards) >= 2:
        idx = 1
        correct_es = spanishes[idx]
        correct_ru = russians[idx]
        wrong_es = [c["spanish"] for c in all_cards if c["spanish"] != correct_es and len(c["spanish"]) < 30]
        wrong_es = rng.sample(wrong_es, min(3, len(wrong_es)))
        options = [correct_es] + wrong_es
        rng.shuffle(options)
        correct_idx = options.index(correct_es)
        questions.append({
            "question": f"Какое испанское слово означает «{correct_ru}»?",
            "options": options,
            "correct_index": correct_idx,
        })

    return questions[:2]


def main():
    with open(CARDS_PATH, encoding="utf-8") as f:
        all_cards = sorted(json.load(f), key=lambda c: c["order"])

    if len(all_cards) != 105:
        print(f"Ожидалось 105 карточек, найдено {len(all_cards)}")
        return

    LESSONS_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(21):
        lesson_num = i + 1
        lesson_id = f"zero_{lesson_num:02d}"
        start = i * 5
        end = start + 5
        lesson_cards = all_cards[start:end]

        topic = lesson_cards[0].get("topic", "phonetics")
        title = TOPIC_TITLES.get(topic, "Урок")
        first_spanish = lesson_cards[0]["spanish"]
        description = f"Изучаем: {first_spanish} и ещё {len(lesson_cards) - 1} карточек"

        quiz_questions = make_quiz_questions(lesson_cards, all_cards, i)
        if len(quiz_questions) < 1:
            quiz_questions = [{
                "question": f"Как переводится «{lesson_cards[0]['spanish']}»?",
                "options": [lesson_cards[0]["translation"], "да", "нет", "не знаю"],
                "correct_index": 0,
            }]

        lesson = {
            "lesson_id": lesson_id,
            "level": "ZERO",
            "title": title,
            "description": description,
            "cards": make_lesson_cards(lesson_cards),
            "quiz": {
                "type": "choice",
                "questions": quiz_questions,
            },
            "success_message": "Отлично! Урок пройден.",
        }

        out_path = LESSONS_DIR / f"{lesson_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(lesson, f, ensure_ascii=False, indent=2)

        print(f"Создан {lesson_id}.json ({len(lesson_cards)} карточек, {len(quiz_questions)} вопросов)")

    # Генерируем список для user_repo
    ids = [f"zero_{n:02d}" for n in range(1, 22)]
    print(f"\nZERO_LESSON_IDS = {json.dumps(ids)}")


if __name__ == "__main__":
    main()
