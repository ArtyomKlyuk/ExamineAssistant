"""Профили предметов — system prompts из YAML."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import PROFILES_DIR

DEFAULT_PROFILE_ID = "general"
RESERVED_IDS = {"general", "study", "interview_it"}  # дефолтные не удаляем


def _slugify(name: str) -> str:
    """Простой slug: латиница/цифры/подчёркивания. Кириллица → транслит."""
    translit = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    })
    name = name.lower().translate(translit)
    name = re.sub(r"[^a-z0-9_]+", "_", name).strip("_")
    return name or "custom"


@dataclass
class Profile:
    id: str
    name: str
    description: str
    system_prompt: str
    answer_length: str = "short"   # short | medium | long
    icon: str = "📝"

    @classmethod
    def from_yaml(cls, path: Path) -> "Profile":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            id=path.stem,
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            system_prompt=data["system_prompt"].strip(),
            answer_length=data.get("answer_length", "short"),
            icon=data.get("icon", "📝"),
        )


def load_profiles() -> dict[str, Profile]:
    """Загружает все YAML файлы из profiles/. Возвращает {id: Profile}."""
    result: dict[str, Profile] = {}
    if not PROFILES_DIR.exists():
        return result
    for path in sorted(PROFILES_DIR.glob("*.yaml")):
        try:
            p = Profile.from_yaml(path)
            result[p.id] = p
        except Exception as e:
            print(f"[profiles] не смог загрузить {path.name}: {e}")
    return result


def save_profile(profile: Profile) -> Path:
    """Сохраняет профиль в profiles/<id>.yaml. Возвращает путь."""
    PROFILES_DIR.mkdir(exist_ok=True)
    path = PROFILES_DIR / f"{profile.id}.yaml"
    data = {
        "name": profile.name,
        "description": profile.description,
        "icon": profile.icon,
        "answer_length": profile.answer_length,
        "system_prompt": profile.system_prompt,
    }
    # PyYAML — multiline для system_prompt через | block scalar
    text = yaml.safe_dump(
        {k: v for k, v in data.items() if k != "system_prompt"},
        allow_unicode=True, sort_keys=False, default_flow_style=False,
    )
    text += f"\nsystem_prompt: |\n"
    for line in profile.system_prompt.splitlines():
        text += f"  {line}\n"
    path.write_text(text, encoding="utf-8")
    return path


def delete_profile(profile_id: str) -> bool:
    """Удаляет YAML профиля. Запрещено для зарезервированных."""
    if profile_id in RESERVED_IDS:
        return False
    path = PROFILES_DIR / f"{profile_id}.yaml"
    if path.exists():
        path.unlink()
        return True
    return False


def make_id(name: str, existing: dict[str, Profile]) -> str:
    """Генерит уникальный id из имени."""
    base = _slugify(name)
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def get_default(profiles: dict[str, Profile]) -> Profile:
    """Возвращает дефолтный профиль (general) или первый попавшийся."""
    if DEFAULT_PROFILE_ID in profiles:
        return profiles[DEFAULT_PROFILE_ID]
    if profiles:
        return next(iter(profiles.values()))
    # Фоллбэк если папка пустая
    return Profile(
        id="general",
        name="Общий",
        description="Базовый ассистент без специализации",
        system_prompt="Ты мой ассистент. Отвечай кратко и по делу, от первого лица.",
    )
