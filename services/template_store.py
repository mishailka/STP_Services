from __future__ import annotations
import os
import json
import psycopg2
from urllib.parse import urlparse
from typing import Any, Dict, List

# ---------- конфиг ----------

DB_URL = os.environ.get("DATABASE_URL")

if not DB_URL:
    raise RuntimeError(
        "DATABASE_URL не задан. "
        "В Render в Environment переменных веб-сервиса нужно указать DATABASE_URL "
        "с Internal Database URL от PostgreSQL."
    )


def _get_conn():
    """Открывает новое соединение с БД."""
    return psycopg2.connect(DB_URL)


def _ensure_table():
    """Создаёт таблицу для шаблонов, если её ещё нет."""
    sql = """
    CREATE TABLE IF NOT EXISTS reply_templates (
        id      SERIAL PRIMARY KEY,
        payload TEXT NOT NULL
    );
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


# ---------- дефолтные данные ----------

def _default_data() -> List[Dict[str, Any]]:
    # Взято из твоего прежнего _default_data без изменений
    return [{
        "id": 0,
        "name": "НК/ГИС МТ — Отказ отчёта о нанесении",
        "description": "Автоприветствие, заявка/заказы опционально, текст с инструкциями",
        "version": 1,
        "blocks": [
            {"type": "Greeting", "label": "Приветствие", "desc": "Автоприветствие по времени",
             "flags": {"newlineAfter": True}},
            {"type": "ConditionalInput", "label": "Заявка", "name": "req_number",
             "prefix": "По заявке: ",
             "desc": "Показывается, только если поле заполнено",
             "flags": {"newlineAfter": True}},
            {"type": "ConditionalInput", "label": "Заказы", "name": "orders",
             "prefix": "По заказам: ",
             "desc": "Список номеров через запятую",
             "flags": {"newlineAfter": True}},
            {"type": "StaticText", "label": "Причина отказа",
             "text": "Отчёты о нанесении отклонились из-за ошибки \"Отсутствует карточка товара (GTIN) в НК\".",
             "flags": {"newline": True}},
            {"type": "StaticText", "label": "Состояния карточек",
             "text": "Карточки в НК есть, но товары в состоянии \"Готов к заказу КМ\" вместо \"Готов к вводу в оборот\".",
             "flags": {"newline": True}},
            {"type": "StaticText", "label": "Ожидает подписания",
             "text": "Карточки товаров в статусе \"Ожидает подписания\".",
             "flags": {"newline": True}},
            {"type": "StaticText", "label": "Просьба",
             "text": "Внесите необходимые изменения (см. карточку), затем сообщите нам — мы переотправим документы нанесения и выпуска ГП.",
             "flags": {"newline": True}},
            {"type": "ConditionalInput", "label": "Подпись", "name": "signature", "prefix": "",
             "desc": "Если заполнено — добавится внизу",
             "flags": {"newline": True}}
        ]
    }]


# ---------- операции ----------

def load_all() -> List[Dict[str, Any]]:
    """
    Читает все шаблоны из PostgreSQL.
    Если таблица пустая — заполняет её значениями по умолчанию и возвращает их.
    """
    _ensure_table()

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM reply_templates ORDER BY id")
            rows = cur.fetchall()

    if not rows:
        # если шаблонов нет — заселяем дефолтными
        data = _default_data()
        save_all(data)
        return data

    templates: List[Dict[str, Any]] = []
    for (payload_str,) in rows:
        try:
            templates.append(json.loads(payload_str))
        except Exception:
            # если вдруг битая строка в БД — просто пропускаем
            continue

    # На всякий случай, если всё сброшено или всё побилось
    if not templates:
        data = _default_data()
        save_all(data)
        return data

    return templates


def save_all(templates: List[Dict[str, Any]]) -> None:
    """
    Перенумеровывает id по порядку (как раньше),
    очищает таблицу и сохраняет всё заново.
    """
    _ensure_table()

    # Перенумерация id: 0,1,2,... как у тебя было в файловой версии
    for i, t in enumerate(templates):
        t["id"] = i

    with _get_conn() as conn:
        with conn.cursor() as cur:
            # Полная перезапись — аналог твоего "перезаписать файл"
            cur.execute("TRUNCATE reply_templates RESTART IDENTITY;")
            for t in templates:
                cur.execute(
                    "INSERT INTO reply_templates (payload) VALUES (%s)",
                    (json.dumps(t, ensure_ascii=False),)
                )
        conn.commit()


def get_path() -> str:
    """
    Используется только для отображения в UI.
    Вернём красивую строку типа PostgreSQL://host/dbname без пароля.
    """
    parsed = urlparse(DB_URL)
    host = parsed.hostname or "db"
    db = (parsed.path or "").lstrip("/") or "database"
    return f"PostgreSQL://{host}/{db}"
