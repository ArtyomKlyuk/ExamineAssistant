# ExamineAssistant

Невидимый ассистент на экзамене / собеседовании / разговоре. Десктоп-приложение для macOS.

Слушает одновременно:
- голос **собеседника** через BlackHole (системный звук из Zoom/Teams/Meet)
- **мой голос** через микрофон

По горячей клавише транскрибирует оба потока, формирует диалог с метками `[Собеседник]:` / `[Я]:` и отправляет в Claude. Ответ приходит **от первого лица** — готовая речь которую можно сразу произнести.

Окно overlay поверх всех — **невидимо для записи экрана** (Zoom/Teams не видят).

## Стек

- **UI:** PyQt6, тёмная тема в стиле Linear/Raycast
- **Транскрипция:** OpenAI `gpt-4o-transcribe` (fallback: `gpt-4o-mini-transcribe`, `whisper-1`)
- **Ответы:** Anthropic `claude-sonnet-4-6` (fallback: `claude-sonnet-4-5`, `claude-opus-4-5`)
- **Аудио:** `sounddevice` + `BlackHole 2ch`
- **Хоткеи:** `pynput` (глобальные, требуют Accessibility на macOS)
- **Невидимость окна:** `pyobjc` → `NSWindow.setSharingType_(NSWindowSharingNone)`

## Установка

### 1. Зависимости

```bash
cd /Users/artyomklyukovskiy/PycharmProjects/ExamineAssistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. BlackHole для захвата системного звука

```bash
brew install blackhole-2ch
```

Открой **Audio MIDI Setup**, создай **Multi-Output Device** (твои наушники + BlackHole 2ch, с галкой *Drift Correction* напротив BlackHole). В Системных настройках → Звук → Выход выбери Многовыходное устройство.

### 3. API ключи

Скопируй шаблон и впиши свои ключи:

```bash
cp .env.example .env
# отредактируй .env, вставь ключи OpenAI и Anthropic
```

### 4. Разрешения macOS

Системные настройки → Конфиденциальность и безопасность → разреши **Terminal**:
- **Микрофон** — для записи звука
- **Универсальный доступ (Accessibility)** — для глобальных хоткеев

После добавления Accessibility **полностью закрой Terminal** (⌘Q) и открой заново.

## Запуск

```bash
cd /Users/artyomklyukovskiy/PycharmProjects/ExamineAssistant
source .venv/bin/activate
python3 main.py
```

Появится маленькое окно поверх всех. В консоли увидишь:
```
✓ Окно невидимо для screen capture
✓ Audio: sys=N, mic=M
```

## Использование

В шапке окна — выпадающий список профилей (предметы). Выбери нужный. Можно менять во время разговора.

### Горячие клавиши

| Клавиша | Что делает |
|---------|------------|
| **⌘+R** или **⌘+К** | Ответить — берёт последние 60 сек обоих потоков, шлёт в Claude, показывает ответ |
| **⌘+Y** или **⌘+Н** | Открыть поле ввода своей заметки. ⌘↵ — отправить (вместе с аудио-контекстом). Esc — отмена |
| **⌘+E** или **⌘+У** | Очистить буфер и историю диалога |
| **⌘+H** или **⌘+Р** | Скрыть / показать окно |

Хоткеи работают **глобально** — даже когда фокус в Zoom/Teams. Русская раскладка работает зеркально (через virtual key code).

### Профили

Все профили в `profiles/*.yaml`. Создать свой — скопируй любой существующий и отредактируй:

```yaml
name: "Мой предмет"
description: "Описание для UI"
icon: "📚"
answer_length: short   # short | medium | long
system_prompt: |
  Ты — мой помощник на экзамене по ...
  ...
```

Перезапусти приложение — профиль появится в списке.

### Счётчик стоимости

В правом нижнем углу — реальная себестоимость текущей сессии по API:
- gpt-4o-transcribe: $0.006 / мин
- Claude Sonnet 4.6: $3 / 1M input, $15 / 1M output

Без наценок — просто для информации сколько уходит.

## Невидимость для записи экрана

На macOS приложение делает `NSWindow.setSharingType_(NSWindowSharingNone)` — окно физически не попадает в screen capture. Это работает с Zoom, Meet, Teams, OBS, QuickTime записью экрана.

**Что видят те, кто смотрит твой экран:** ничего на месте окна (пустой рабочий стол).
**Что видишь ты:** окно поверх всех.

## Структура проекта

```
ExamineAssistant/
├── main.py                    # точка входа десктоп-приложения
├── cli.py                     # старая CLI-версия (для отладки)
├── requirements.txt
├── .env.example               # шаблон ключей
├── profiles/                  # YAML-профили предметов
│   ├── general.yaml
│   ├── personal_management.yaml
│   ├── intercultural_comm.yaml
│   ├── innovation_project.yaml
│   └── interview_it.yaml
├── app/
│   ├── core/                  # бизнес-логика без UI
│   │   ├── audio.py           # кольцевые буферы, выбор устройств
│   │   ├── transcribe.py      # OpenAI Whisper / gpt-4o-transcribe
│   │   ├── claude.py          # Anthropic Claude
│   │   ├── profiles.py        # загрузка YAML профилей
│   │   ├── billing.py         # счётчик стоимости
│   │   └── config.py          # ключи, модели, цены
│   └── ui/                    # PyQt6 интерфейс
│       ├── main_window.py     # окно
│       ├── controller.py      # связь UI ↔ worker ↔ хоткеи
│       ├── worker.py          # фоновая обработка в QThread
│       ├── hotkeys.py         # глобальные хоткеи pynput
│       ├── theme.py           # тёмная тема (QSS)
│       └── macos.py           # невидимость окна через PyObjC
└── outputs/                   # сохранённые ответы (auto-created)
```

## Конфигурация через ENV

В `.env` или прямо в shell:

| Переменная | Что |
|---|---|
| `OPENAI_API_KEY` | обязательно |
| `ANTHROPIC_API_KEY` | обязательно |
| `AUDIO_DEVICE_SYSTEM` | индекс устройства для звука собеседника (по умолчанию автопоиск BlackHole) |
| `AUDIO_DEVICE_MIC` | индекс микрофона |

## Без сертификатов

Это обычный Python-скрипт. Никакой нотаризации/подписи. Запускается локально из терминала.

## CLI-версия

Старая версия без GUI осталась в `cli.py`:
```bash
python3 cli.py
```
Те же хоткеи, тот же ответ — только в терминале без окна.

## Поддерживаемые ОС

- ✅ macOS — всё работает
- ⚠ Linux — UI работает, невидимость окна не работает (нужен Wayland-API)
- ⚠ Windows — не тестировалось, скорее всего понадобятся правки в `app/ui/macos.py`
