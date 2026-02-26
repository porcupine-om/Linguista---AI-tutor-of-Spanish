from data.level_test.questions import QUESTIONS


LEVEL_ORDER = ["A1", "A2", "B1"]

THRESHOLDS = {
    "A1": 4,
    "A2": 3,
    "B1": 3,
}


def calculate_level(results: dict[int, bool]) -> str:
    """
    Определяет уровень пользователя на основе ответов.
    
    results: {question_id: True/False}
    return: уровень ("A1", "A2", "B1")
    """

    # Группируем вопросы по уровням
    level_stats = {
        "A1": {"total": 0, "correct": 0},
        "A2": {"total": 0, "correct": 0},
        "B1": {"total": 0, "correct": 0},
    }

    for q in QUESTIONS:
        q_id = q["id"]
        level = q["level"]

        if level not in level_stats:
            continue

        level_stats[level]["total"] += 1
        if results.get(q_id):
            level_stats[level]["correct"] += 1

    # Проверяем уровни по порядку
    if level_stats["A1"]["correct"] < THRESHOLDS["A1"]:
        return "A1"

    if level_stats["A2"]["correct"] < THRESHOLDS["A2"]:
        return "A1"

    if level_stats["B1"]["correct"] < THRESHOLDS["B1"]:
        return "A2"

    return "B1"
