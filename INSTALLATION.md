# Установка Lingüista ES

## Требования

- **Python** 3.10 или выше
- **Telegram Bot Token** — получить у [@BotFather](https://t.me/BotFather)
- **API-ключ** для LLM и Whisper:
  - [ProxyAPI](https://proxyapi.io) (OpenAI-совместимый прокси) — рекомендуется
  - или прямой [OpenAI API](https://platform.openai.com)

---

## Шаги установки

### 1. Клонирование репозитория

```bash
git clone https://github.com/porcupine-om/Linguista---AI-tutor-of-Spanish.git
cd Linguista---AI-tutor-of-Spanish
```

### 2. Виртуальное окружение

```bash
python -m venv venv
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создай файл `.env` в корне проекта (можно скопировать из `.env.example`):

```bash
cp .env.example .env
```

Отредактируй `.env`:

```env
# Обязательно
BOT_TOKEN=your_telegram_bot_token

# LLM и Whisper через ProxyAPI (рекомендуется)
PROXYAPI_BASE_URL=https://api.proxyapi.io/v1
PROXYAPI_API_KEY=your_proxyapi_api_key

# Альтернатива: прямой OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=
```

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `PROXYAPI_API_KEY` | Ключ ProxyAPI (LLM + Whisper) |
| `OPENAI_API_KEY` | Ключ OpenAI (если не используешь ProxyAPI) |
| `OPENAI_BASE_URL` | Базовый URL (пусто = api.openai.com) |

### 5. Запуск

```bash
python main.py
```

При успешном запуске в консоли появится сообщение о начале polling.

---

## Структура проекта

```
├── main.py              # Точка входа
├── bot/
│   ├── handlers/        # Обработчики сообщений (меню, уроки, голос)
│   ├── services/        # LLM, Whisper, повторения
│   ├── db/              # Модели и сессия БД
│   └── states.py        # FSM-состояния
├── data/
│   ├── zero_lessons/    # Уроки ZERO
│   ├── a1_lessons/     # Уроки A1
│   ├── a2_lessons/     # Уроки A2
│   ├── b1_lessons/     # Уроки B1
│   ├── cards_seed.json # Словарь и транскрипции
│   └── level_test/     # Вопросы теста уровня
├── requirements.txt
├── .env                 # Создаётся вручную (не в git)
└── .env.example
```

---

## Устранение неполадок

**`BOT_TOKEN не найден`** — проверь, что файл `.env` в корне проекта и содержит `BOT_TOKEN=...`.

**Ошибки при проверке ответов / голоса** — убедись, что задан `PROXYAPI_API_KEY` или `OPENAI_API_KEY`.

**База данных** — SQLite создаётся автоматически при первом запуске в файле `linguista.db` (или как указано в настройках сессии).
