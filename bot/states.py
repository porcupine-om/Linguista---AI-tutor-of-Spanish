from aiogram.fsm.state import StatesGroup, State


# ─────────────────────────────
# Onboarding / старт
# ─────────────────────────────
class OnboardingStates(StatesGroup):
    path_choice = State()
    intro = State()
    ready_check = State()


class ZeroStates(StatesGroup):
    welcome = State()
    card = State()
    quiz = State()
    zero_complete = State()  # поздравительное сообщение после прохождения ZERO


class A1States(StatesGroup):
    welcome = State()
    theory = State()
    card = State()
    exercise = State()  # choice / fill_text / dialogue


class A2States(StatesGroup):
    welcome = State()
    theory = State()
    card = State()
    exercise = State()


class B1States(StatesGroup):
    welcome = State()
    theory = State()
    card = State()
    exercise = State()


class LevelTestStates(StatesGroup):
    question = State()
    answer = State()
    result = State()


# ─────────────────────────────
# Главное меню
# ─────────────────────────────
class MainMenuStates(StatesGroup):
    menu = State()              # пользователь находится в главном меню


# ─────────────────────────────
# Уроки
# ─────────────────────────────
class LessonStates(StatesGroup):
    lesson_in_progress = State()    # идёт урок (карточки, вопросы)
    lesson_feedback = State()       # финальный фидбек по уроку


# ─────────────────────────────
# Повторение (spaced repetition)
# ─────────────────────────────
class ReviewStates(StatesGroup):
    item = State()


# ─────────────────────────────
# Профиль и статистика
# ─────────────────────────────
class ProfileStates(StatesGroup):
    profile_view = State()          # просмотр профиля
    stats_view = State()            # подробная статистика
