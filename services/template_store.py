from __future__ import annotations
import os, json, tempfile
from typing import Any, List, Dict

TEMPLATES_PATH = os.path.join(tempfile.gettempdir(), "reply_templates_store.json")

def _ensure_file():
    if not os.path.exists(TEMPLATES_PATH):
        data = [{
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
        with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def load_all() -> List[Dict[str, Any]]:
    _ensure_file()
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_all(templates: List[Dict[str, Any]]):
    for i, t in enumerate(templates):
        t["id"] = i
    with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

def get_path() -> str:
    _ensure_file()
    return TEMPLATES_PATH
