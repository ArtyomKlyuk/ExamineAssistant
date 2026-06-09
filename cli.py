#!/usr/bin/env python3
"""
ExamineAssistant — невидимый ассистент на экзамене / собеседовании.

Слушает параллельно ДВА потока аудио:
  • BlackHole 2ch — голос собеседника (системный звук из Zoom/Meet/Teams)
  • Микрофон     — мой голос
По горячей клавише транскрибирует оба потока через OpenAI
(gpt-4o-transcribe → fallback gpt-4o-mini-transcribe → whisper-1),
формирует диалог с метками [Собеседник]/[Я] и отправляет в Claude Sonnet 4.6,
который отвечает от моего лица — готовая речь, которую можно произнести.

Запуск:  python3 main.py
Горячие клавиши:
    ⌘+R (или ⌘+К)  — ответить на последние 60 сек разговора
    ⌘+Y (или ⌘+Н)  — ввести свой вопрос/заметку (учтёт и аудио, и текст)
                     повторный ⌘+Y или слово `cancel`/`отмена` — закрыть ввод
    ⌘+E (или ⌘+У)  — очистить буфер и историю диалога
    Ctrl+C         — выход

Для горячих клавиш нужен доступ Accessibility (Системные настройки →
Конфиденциальность → Универсальный доступ → разрешить Terminal).
"""

import os
import io
import sys
import time
import queue
import threading
from pathlib import Path

# Загружаем .env (если он есть) — рядом с main.py
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv опционален, можно через export OPENAI_API_KEY=...
import collections
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard

from openai import OpenAI
from anthropic import Anthropic

# ─────────────────────────────── КОНФИГ ────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not OPENAI_API_KEY or not ANTHROPIC_API_KEY:
    sys.exit("ОШИБКА: создай .env файл рядом с main.py со строками:\n"
             "  OPENAI_API_KEY=sk-...\n"
             "  ANTHROPIC_API_KEY=sk-ant-...\n"
             "(см. .env.example)")

SAMPLE_RATE = 16000
CHANNELS = 1
BUFFER_SECONDS = 120         # сколько секунд аудио держим в памяти
DEFAULT_WINDOW_SEC = 60      # сколько берём по ⌘+R

CLAUDE_MODEL = "claude-sonnet-4-6"   # последняя Sonnet — быстрая и умная, без extended thinking
CLAUDE_FALLBACKS = ["claude-sonnet-4-5", "claude-opus-4-5", "claude-3-5-sonnet-latest"]
WHISPER_MODEL = "gpt-4o-transcribe"   # лучшая модель распознавания (точнее Whisper на терминах)
WHISPER_FALLBACKS = ["gpt-4o-mini-transcribe", "whisper-1"]

SYSTEM_PROMPT = """Ты — мой невидимый помощник на экзамене / собеседовании / разговоре.
КОНТЕКСТ: я сдаю экзамен по предмету «Персональный менеджмент». Все вопросы
скорее всего связаны с самоменеджментом, тайм-менеджментом, постановкой целей
(SMART, OKR), приоритизацией (матрица Эйзенхауэра, ABC/Парето, метод Альпы),
планированием (день/неделя/месяц, GTD Дэвида Аллена, Pomodoro), делегированием,
самомотивацией и самодисциплиной, работоспособностью и биоритмами, борьбой
со стрессом и выгоранием, work-life balance, личной эффективностью, развитием
карьеры, навыками и компетенциями, эмоциональным интеллектом, личным брендом,
саморазвитием и обучением, методиками самопознания (SWOT-анализ личности,
колесо жизненного баланса). Опирайся на классиков темы — Лотар Зайверт,
Стивен Кови («7 навыков высокоэффективных людей»), Питер Друкер, Глеб
Архангельский, Брайан Трейси, Дэвид Аллен. Используй терминологию из этой
области.

Тебе приходит транскрипт последних реплик: там может быть речь собеседника
(вопрос, реплика, провокация) и моя речь. Транскрипт «грязный» — Whisper мог
ошибиться в словах, расставить запятые не там, склеить реплики разных людей.

Твоя работа:

1. Сам пойми контекст разговора: кто что сказал, в чём суть, к чему всё идёт.
2. Найди главный вопрос или ситуацию, на которую мне нужно отреагировать.
   Если прямого вопроса нет — пойми, какую реплику от меня ждут прямо сейчас,
   и дай её.
3. Ответь так, как должен ответить **я сам** — от первого лица, моими словами.
   Не «студенту следует сказать…», а сразу готовая речь: «Я считаю, что…»,
   «На мой взгляд…», «Здесь работает следующий механизм…».
4. Тон: грамотный студент / молодой специалист. Уверенно, по делу, литературно,
   но без канцелярита и без академической надутости. Без «хороший вопрос»,
   без «давайте разберёмся», без вступлений вообще — сразу содержание.
5. ДЛИНА ПО УМОЛЧАНИЮ: ~30 секунд устной речи, это примерно 70-90 слов или
   3-5 предложений. Это короткий, плотный, готовый к произнесению ответ.
   Не разворачивай, не перечисляй всё что знаешь — выбери самое главное.
   Назови ключевой термин и/или автора, дай суть, при необходимости одно
   уточнение. Всё. Если вопрос технический — один-два термина, суть механизма.
   Если ситуация личная/поведенческая — конкретная реплика, которую можно
   произнести вслух.
6. Структура для короткого ответа: 1-2 коротких абзаца, без списков и
   подзаголовков. Списки и блоки появляются ТОЛЬКО когда меня просят
   подробнее (см. пункт 9).
7. Если контекст реально неоднозначен — выбери самую вероятную трактовку и
   ответь на неё. Только если двусмысленность критична — кратко покажи обе.
8. Никогда не пиши «как ИИ я…», «вот возможный ответ» и подобное. Ты — это я,
   говорящий в моменте.
9. РЕЖИМ «ПОДРОБНЕЕ». Если в транскрипте или в моей текстовой заметке
   звучит «подробнее», «расскажи глубже», «разверни», «можно полнее»,
   «детальнее», «объясни подробно», «ещё», «развёрнуто», «полный ответ»,
   «с примерами» — переключайся в развёрнутый режим: 2-4 минуты устной
   речи, можно списком или подзаголовками, больше контекста, термины с
   расшифровкой, авторы, примеры, нюансы. Всё ещё от первого лица, всё
   ещё без воды — просто объёма больше, потому что собеседник запросил.
   Без явной просьбы — всегда короткий 30-секундный ответ (пункт 5).
10. Иногда я буду сам присылать тебе текстовую заметку (мой вопрос или
    уточнение) ВМЕСТЕ с транскриптом. Эта заметка — приоритетный сигнал:
    учитывай контекст разговора из транскрипта, но отвечай именно на то,
    что я написал в заметке. Если заметка пустая — работай только по
    транскрипту, как обычно.
"""

OUT_DIR = Path(__file__).parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────── АУДИО БУФЕР ───────────────────────────────

class RollingAudioBuffer:
    """Кольцевой буфер аудио в numpy float32."""
    def __init__(self, seconds: int, sample_rate: int):
        self.sample_rate = sample_rate
        self.max_samples = seconds * sample_rate
        self.buf = collections.deque(maxlen=self.max_samples)
        self.lock = threading.Lock()

    def append(self, chunk: np.ndarray):
        with self.lock:
            self.buf.extend(chunk.tolist())

    def last_seconds(self, seconds: int) -> np.ndarray:
        n = min(seconds * self.sample_rate, len(self.buf))
        with self.lock:
            if n == 0:
                return np.zeros(0, dtype=np.float32)
            data = list(self.buf)[-n:]
        return np.array(data, dtype=np.float32)

    def clear(self):
        with self.lock:
            self.buf.clear()


# ─────────────────────────── ВЫБОР УСТРОЙСТВ ───────────────────────────

def pick_devices() -> tuple[int | None, int | None]:
    """Возвращает (system_device_idx, mic_device_idx).
    system — BlackHole/Loopback/Aggregate (голос собеседника).
    mic — встроенный/внешний микрофон (мой голос).
    Любое может быть None — тогда соответствующий поток не запускается.
    """
    devices = sd.query_devices()
    print("\n=== Доступные аудиоустройства (вход) ===")
    candidates = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}  (in:{d['max_input_channels']}ch, sr:{int(d['default_samplerate'])})")
            candidates.append((i, d))

    sys_idx = None
    mic_idx = None

    # 1) Системный звук — BlackHole / Loopback / Aggregate
    for i, d in candidates:
        name = d["name"].lower()
        if "blackhole" in name or "loopback" in name:
            sys_idx = i
            break
    if sys_idx is None:
        for i, d in candidates:
            if "aggregate" in d["name"].lower():
                sys_idx = i
                break

    # 2) Микрофон — НЕ BlackHole/Loopback/Aggregate, предпочитаем MacBook/встроенный/внешний микрофон
    def _is_loopback(name: str) -> bool:
        n = name.lower()
        return "blackhole" in n or "loopback" in n or "aggregate" in n

    # сначала ищем явный микрофон по ключевым словам
    for i, d in candidates:
        n = d["name"].lower()
        if _is_loopback(n):
            continue
        if "macbook" in n or "встроен" in n or "built" in n:
            mic_idx = i
            break
    # потом любое первое не-loopback
    if mic_idx is None:
        for i, d in candidates:
            if not _is_loopback(d["name"]):
                mic_idx = i
                break

    # ENV override
    env_sys = os.environ.get("AUDIO_DEVICE_SYSTEM") or os.environ.get("AUDIO_DEVICE")
    env_mic = os.environ.get("AUDIO_DEVICE_MIC")
    if env_sys:
        try: sys_idx = int(env_sys)
        except ValueError: pass
    if env_mic:
        try: mic_idx = int(env_mic)
        except ValueError: pass

    print()
    if sys_idx is not None:
        print(f">>> Голос СОБЕСЕДНИКА: [{sys_idx}] {devices[sys_idx]['name']}")
    else:
        print(">>> Голос СОБЕСЕДНИКА: НЕ НАЙДЕН (поставь BlackHole + Multi-Output Device)")
    if mic_idx is not None:
        print(f">>> МОЙ голос:         [{mic_idx}] {devices[mic_idx]['name']}")
    else:
        print(">>> МОЙ голос:         выключен")

    if sys_idx is None and mic_idx is None:
        raise RuntimeError("Не найдено ни одного устройства ввода")
    return sys_idx, mic_idx


# ─────────────────────────── РАБОТА С API ──────────────────────────────

openai_client = OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

def transcribe(audio: np.ndarray, sample_rate: int) -> str:
    """Отправляет аудио в OpenAI (gpt-4o-transcribe), возвращает текст."""
    if audio.size == 0:
        return ""
    # Не отправляем фактическую тишину
    rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0
    if rms < 1e-4:
        return ""
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    raw = buf.getvalue()

    last_err = None
    for model in [WHISPER_MODEL, *WHISPER_FALLBACKS]:
        try:
            file_buf = io.BytesIO(raw)
            file_buf.name = "audio.wav"
            kwargs = dict(model=model, file=file_buf, language="ru")
            # gpt-4o-transcribe не поддерживает response_format=verbose_json,
            # но дефолтный text/json работает у всех трёх.
            resp = openai_client.audio.transcriptions.create(**kwargs)
            return resp.text.strip()
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Все модели транскрипции недоступны: {last_err}")


def transcribe_two(sys_audio: np.ndarray, mic_audio: np.ndarray, sample_rate: int) -> str:
    """Транскрибирует два потока параллельно, возвращает диалог с метками."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_sys = ex.submit(transcribe, sys_audio, sample_rate)
        f_mic = ex.submit(transcribe, mic_audio, sample_rate)
        sys_text = f_sys.result()
        mic_text = f_mic.result()

    parts = []
    if sys_text:
        parts.append(f"[Собеседник]: {sys_text}")
    if mic_text:
        parts.append(f"[Я]: {mic_text}")
    return "\n".join(parts)

def ask_claude(transcript: str, history: list, user_note: str = "") -> str:
    """Спрашивает Claude. Возвращает ответ. Обновляет history in-place.
    user_note — опциональная заметка от меня (мой вопрос/уточнение)."""
    transcript = transcript.strip()
    user_note = user_note.strip()

    if user_note and not transcript:
        # Чисто текстовый режим — никакого аудио
        user_msg = (
            "Мой вопрос / задание (текстом, аудио нет):\n"
            "---\n"
            f"{user_note}\n"
            "---\n\n"
            "Ответь от моего лица — так, как я должен это сказать или написать."
        )
    elif user_note and transcript:
        user_msg = (
            "Транскрипт последних реплик (может быть с ошибками распознавания):\n"
            "---\n"
            f"{transcript}\n"
            "---\n\n"
            "Моя заметка / вопрос (приоритетный сигнал):\n"
            "---\n"
            f"{user_note}\n"
            "---\n\n"
            "Учитывай транскрипт как контекст, но отвечай именно на мою заметку — от моего лица."
        )
    else:
        user_msg = (
            "Транскрипт последних реплик (может быть с ошибками распознавания):\n"
            "---\n"
            f"{transcript if transcript else '(пусто)'}\n"
            "---\n\n"
            "Скажи от моего лица то, что я должен ответить прямо сейчас."
        )
    history.append({"role": "user", "content": user_msg})

    models_to_try = [CLAUDE_MODEL] + CLAUDE_FALLBACKS
    last_err = None
    for model in models_to_try:
        try:
            resp = anthropic_client.messages.create(
                model=model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=history,
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            history.append({"role": "assistant", "content": text})
            return text
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Все модели Claude недоступны: {last_err}")


# ─────────────────────────── ОСНОВНОЙ ЦИКЛ ──────────────────────────────

sys_buffer = RollingAudioBuffer(BUFFER_SECONDS, SAMPLE_RATE)   # голос собеседника
mic_buffer = RollingAudioBuffer(BUFFER_SECONDS, SAMPLE_RATE)   # мой голос
chat_history: list = []
# В очередь кладём кортеж (window_sec, user_note)
work_queue: "queue.Queue[tuple[int, str]]" = queue.Queue()
running = True
# Флаг режима ввода — пока True, hotkeys игнорируем (чтобы клавиши уходили в stdin)
input_mode = threading.Event()


def _make_callback(buffer: RollingAudioBuffer, label: str):
    def _cb(indata, frames, time_info, status):
        if status:
            print(f"[audio:{label}] {status}", file=sys.stderr)
        if indata.shape[1] > 1:
            mono = indata.mean(axis=1)
        else:
            mono = indata[:, 0]
        buffer.append(mono.astype(np.float32))
    return _cb


def worker():
    while running:
        try:
            item = work_queue.get(timeout=0.3)
        except queue.Empty:
            continue
        try:
            window_sec, user_note = item
            handle_request(window_sec, user_note)
        except Exception as e:
            print(f"\n[ОШИБКА] {e}\n", file=sys.stderr)


def handle_request(window_sec: int, user_note: str = ""):
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Беру последние {window_sec} сек аудио...")
    sys_audio = sys_buffer.last_seconds(window_sec)
    mic_audio = mic_buffer.last_seconds(window_sec)

    transcript = ""
    if sys_audio.size > 0 or mic_audio.size > 0:
        print(f"Транскрибирую оба потока через {WHISPER_MODEL}...")
        t0 = time.time()
        transcript = transcribe_two(sys_audio, mic_audio, SAMPLE_RATE)
        print(f"  ({time.time()-t0:.1f}s)")
        for line in transcript.splitlines():
            print(f"  {line[:300]}{'...' if len(line)>300 else ''}")
    else:
        print("Буферы пусты — иду без транскрипта (только по заметке).")

    if not transcript and not user_note.strip():
        print("Нет ни транскрипта, ни заметки — пропускаю.")
        return

    if user_note.strip():
        print(f"С заметкой: {user_note[:200]}{'...' if len(user_note)>200 else ''}")

    print("Думаю в Claude...")
    t0 = time.time()
    answer = ask_claude(transcript, chat_history, user_note=user_note)
    print(f"  ({time.time()-t0:.1f}s)\n")

    print("─── ОТВЕТ ─────────────────────────────────────────────────────")
    print(answer)
    print("───────────────────────────────────────────────────────────────")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUT_DIR / f"answer_{ts}.md"
    note_block = f"\n\n## My note\n\n{user_note}\n" if user_note.strip() else ""
    out_file.write_text(
        f"# {ts}\n\n## Transcript\n\n{transcript}{note_block}\n\n## Answer\n\n{answer}\n",
        encoding="utf-8",
    )
    print(f"Сохранено: {out_file}")


# Состояние модификаторов
_cmd_down = False
# Флаг "отменить текущий ввод заметки" — выставляется при повторном ⌘+Y
_cancel_note = threading.Event()

# Зеркальные пары EN/RU для нужных букв
ANSWER_KEYS = {"r", "к"}    # ⌘+R / ⌘+К  → ответить
CLEAR_KEYS  = {"e", "у"}    # ⌘+E / ⌘+У  → очистить
NOTE_KEYS   = {"y", "н"}    # ⌘+Y / ⌘+Н  → ввести свой вопрос/заметку


def _key_char(key) -> str | None:
    """Достаём символ нажатой клавиши вне зависимости от раскладки."""
    # Обычный символ
    ch = getattr(key, "char", None)
    if ch:
        return ch.lower()
    # KeyCode (на macOS pynput может отдавать vk без char при не-латинской раскладке)
    vk = getattr(key, "vk", None)
    if vk is not None:
        # таблица virtual key codes macOS для нужных букв
        # R=15, E=14, Y=16  (https://developer.apple.com/library/archive/documentation/mac/Toolbox/Toolbox-117.html)
        mapping = {15: "r", 14: "e", 16: "y"}
        if vk in mapping:
            return mapping[vk]
    return None


def _prompt_note_async():
    """Запускает ввод заметки в отдельном потоке. Повторный ⌘+Y → отмена."""
    def _watch_cancel():
        # Поток-наблюдатель: как только пришёл сигнал отмены — закрываем stdin
        # чтобы input() в основном потоке выкинул EOFError и вышел.
        while input_mode.is_set():
            if _cancel_note.wait(timeout=0.2):
                try:
                    sys.stdin.close()
                except Exception:
                    pass
                return

    def _run():
        if input_mode.is_set():
            return
        input_mode.set()
        _cancel_note.clear()
        # Запоминаем оригинальный stdin, чтобы вернуть его после отмены
        orig_stdin = sys.stdin
        watcher = threading.Thread(target=_watch_cancel, daemon=True)
        watcher.start()
        try:
            print("\n" + "─" * 70)
            print("Введи свой вопрос/заметку (для Claude). Многострочно: пустая строка = отправить.")
            print(f"Окно аудио: {DEFAULT_WINDOW_SEC} сек (можно изменить — впиши первой строкой: window=30)")
            print("Отмена: ⌘+Y (⌘+Н) ещё раз, либо набери `cancel` / `отмена` и Enter")
            print("─" * 70)
            lines = []
            window_sec = DEFAULT_WINDOW_SEC
            cancelled = False
            while True:
                try:
                    line = input("> ")
                except (EOFError, ValueError):
                    cancelled = True
                    break
                if _cancel_note.is_set():
                    cancelled = True
                    break
                # Текстовый путь отмены — на случай если хоткей не работает (нет accessibility)
                if line.strip().lower() in ("cancel", "отмена", ":q", "/cancel"):
                    cancelled = True
                    break
                if not line.strip():
                    if not lines:
                        cancelled = True
                        break
                    break
                if not lines and line.strip().lower().startswith("window="):
                    try:
                        window_sec = max(1, int(line.split("=", 1)[1].strip()))
                        print(f"  → окно аудио = {window_sec} сек")
                        continue
                    except ValueError:
                        pass
                lines.append(line)
            if cancelled:
                print("(отмена)")
                return
            note = "\n".join(lines).strip()
            if note:
                work_queue.put((window_sec, note))
        finally:
            # Восстанавливаем stdin если мы его закрыли
            try:
                if sys.stdin.closed:
                    sys.stdin = orig_stdin if not orig_stdin.closed else open("/dev/tty", "r")
            except Exception:
                pass
            _cancel_note.clear()
            input_mode.clear()
    threading.Thread(target=_run, daemon=True).start()


def on_press(key):
    global _cmd_down
    try:
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            _cmd_down = True
            return

        if not _cmd_down:
            return

        ch = _key_char(key)
        if ch is None:
            return

        # В режиме ввода реагируем ТОЛЬКО на ⌘+Y → отменить
        if input_mode.is_set():
            if ch in NOTE_KEYS:
                _cancel_note.set()
            return

        if ch in ANSWER_KEYS:
            work_queue.put((DEFAULT_WINDOW_SEC, ""))
        elif ch in CLEAR_KEYS:
            sys_buffer.clear()
            mic_buffer.clear()
            chat_history.clear()
            print("\n[CLEAR] Буферы и история очищены.\n")
        elif ch in NOTE_KEYS:
            _prompt_note_async()
    except Exception as e:
        print(f"[hotkey error] {e}", file=sys.stderr)


def on_release(key):
    global _cmd_down
    if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
        _cmd_down = False


def main():
    global running
    sys_idx, mic_idx = pick_devices()

    print(f"\n=== ExamineAssistant запущен ===")
    print(f"  Sample rate:  {SAMPLE_RATE} Hz")
    print(f"  Буфер:        {BUFFER_SECONDS} сек на каждый поток")
    print(f"  Горячие клавиши:")
    print(f"    ⌘+R  (⌘+К)  — ответить (последние {DEFAULT_WINDOW_SEC} сек разговора)")
    print(f"    ⌘+Y  (⌘+Н)  — ввести свой вопрос/заметку для Claude")
    print(f"    ⌘+E  (⌘+У)  — очистить буфер и историю")
    print(f"    Ctrl+C      — выход")
    print(f"\n(на macOS первый раз попросит разрешение Микрофон / Input Monitoring)")
    print(f"(для системного звука: brew install blackhole-2ch, потом Multi-Output Device в Audio MIDI Setup)\n")

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Контекстный менеджер сразу для двух потоков (или одного, если другой None)
    import contextlib
    streams = contextlib.ExitStack()
    try:
        if sys_idx is not None:
            streams.enter_context(sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                device=sys_idx,
                callback=_make_callback(sys_buffer, "sys"),
                blocksize=int(SAMPLE_RATE * 0.1),
            ))
        if mic_idx is not None:
            streams.enter_context(sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                device=mic_idx,
                callback=_make_callback(mic_buffer, "mic"),
                blocksize=int(SAMPLE_RATE * 0.1),
            ))
        with streams:
            print("Слушаю... (нажми ⌘+R / ⌘+К чтобы получить ответ)\n")
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nВыхожу.")
    finally:
        running = False
        listener.stop()


if __name__ == "__main__":
    main()
