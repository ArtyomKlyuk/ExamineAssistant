"""Профили предметов — system prompts из YAML."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import PROFILES_DIR

DEFAULT_PROFILE_ID = "general"


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
