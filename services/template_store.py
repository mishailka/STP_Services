from __future__ import annotations
import os
import json
import tempfile
import time
import shutil
from typing import Any, List, Dict

# --------- конфиг пути ---------
# 1) Явно через ENV:
#    REPLY_TEMPLATES_PATH=/var/lib/myapp/reply_templates_store.json
ENV_PATH = os.environ.get("REPLY_TEMPLATES_PATH", "").strip()

def _user_data_dir() -> str:
    """
    Возвращает каталог для данных приложения:
      - Windows: %APPDATA%\ReplyTemplates
      - Linux/macOS: ${XDG_DATA_HOME:-~/.local/share}/reply-templates
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(base, "ReplyTemplates")
    # POSIX
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "reply-templates")

def _default_store_path() -> str:
    return os.path.join(_user_data_dir(), "reply_templates_store.json")

def _legacy_temp_path() -> str:
    # старое расположение из раннего MVP — во временной папке ОС
    return os.path.join(tempfile.gettempdir(), "reply_templates_store.json")

def _ensure_dir(path: str):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)

def _atomic_write(path: str, data: bytes):
    """
    Безопасная запись: пишем во временный соседний файл и атомарно заменяем.
    """
    _ensure_dir(path)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def _backup_file(path: str):
    """
    Создаём версионированный .bak и чистим старые бэкапы, оставляя последние 10.
    """
    if not os.path.exists(path):
        return
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{ts}"
    shutil.copy2(path, bak)

    # Ротация: оставляем последние 10
    folder = os.path.dirname(path)
    prefix = os.path.basename(path) + ".bak-"
    backups = sorted([f for f in os.listdir(folder) if f.startswith(prefix)])
    excess = len(backups) - 10
    for i in range(excess):
        try:
            os.remove(os.path.join(folder, backups[i]))
        except Exception:
            pass

def _migrate_from_legacy(dest_path: str):
    """
    Если найдён старый файл во временной папке — переносим его в новое постоянное место.
    """
    legacy = _legacy_temp_path()
    if os.path.exists(legacy) and not os.path.exists(dest_path):
        _ensure_dir(dest_path)
        try:
            shutil.move(legacy, dest_path)
        except Exception:
            # если move не удался (например, разные диски) — пробуем copy
            shutil.copy2(legacy, dest_path)

# --------- путь хранилища ---------
TEMPLATES_PATH = ENV_PATH or _default_store_path()
_migrate_from_legacy(TEMPLATES_PATH)

# --------- операции ---------

def _default_data() -> List[Dict[str, Any]]:
    return [{
        "id": 0,
        "name": "НК/ГИС МТ — Отказ отчёта о нанесении",
        "description": "Автоприветствие, заявка/заказы опционально, текст с инструкциями",
        "version": 1,
        "blocks": [
            {"type":"Greeting","label":"Приветствие","desc":"Автоприветствие по времени","flags":{"newlineAfter":True}},
            {"type":"ConditionalInput","label":"Заявка","name":"req_number","prefix":"По заявке: ","desc":"Показывается, только если поле заполнено","flags":{"newlineAfter":True}},
            {"type":"ConditionalInput","label":"Заказы","name":"orders","prefix":"По заказам: ","desc":"Список номеров через запятую","flags":{"newlineAfter":True}},
            {"type":"StaticText","label":"Причина отказа","text":"Отчёты о нанесении отклонились из-за ошибки \"Отсутствует карточка товара (GTIN) в НК\".","flags":{"newline":True}},
            {"type":"StaticText","label":"Состояния карточек","text":"Карточки в НК есть, но товары в состоянии \"Готов к заказу КМ\" вместо \"Готов к вводу в оборот\".","flags":{"newline":True}},
            {"type":"StaticText","label":"Ожидает подписания","text":"Карточки товаров в статусе \"Ожидает подписания\".","flags":{"newline":True}},
            {"type":"StaticText","label":"Просьба","text":"Внесите необходимые изменения (см. карточку), затем сообщите нам — мы переотправим документы нанесения и выпуска ГП.","flags":{"newline":True}},
            {"type":"ConditionalInput","label":"Подпись","name":"signature","prefix":"","desc":"Если заполнено — добавится внизу","flags":{"newline":True}}
        ]
    }]

def _ensure_file():
    """
    Создаёт файл со значениями по умолчанию, если его нет.
    """
    if not os.path.exists(TEMPLATES_PATH):
        _ensure_dir(TEMPLATES_PATH)
        data = json.dumps(_default_data(), ensure_ascii=False, indent=2).encode("utf-8")
        _atomic_write(TEMPLATES_PATH, data)

def load_all() -> List[Dict[str, Any]]:
    """
    Читает все шаблоны. Если файл битый — создаёт заново по умолчанию (с бэкапом).
    """
    _ensure_file()
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # бэкапнем проблемный файл и перезапишем дефолт
        try:
            _backup_file(TEMPLATES_PATH)
        except Exception:
            pass
        data = _default_data()
        _atomic_write(TEMPLATES_PATH, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
        return data

def save_all(templates: List[Dict[str, Any]]):
    """
    Перенумеровывает id, делает бэкап текущего файла и атомарно сохраняет новое содержимое.
    """
    for i, t in enumerate(templates):
        t["id"] = i
    payload = json.dumps(templates, ensure_ascii=False, indent=2).encode("utf-8")
    _ensure_file()
    _backup_file(TEMPLATES_PATH)
    _atomic_write(TEMPLATES_PATH, payload)

def get_path() -> str:
    return TEMPLATES_PATH
