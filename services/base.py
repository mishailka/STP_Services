from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from flask import Blueprint

@dataclass
class ServiceBase:
    id: str                    # URL-safe id, например "file-compare"
    name: str                  # Человеческое имя
    description: str           # Короткое описание
    icon: str = "🧩"           # Эмодзи/иконка
    blueprint: Optional[Blueprint] = None  # Flask blueprint, если есть UI/API
