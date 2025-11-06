from __future__ import annotations
import io
import json
import os
import re
import tempfile
from typing import Any, Dict, List, Iterable, Optional

from flask import Blueprint, request, render_template_string, session, Response, stream_with_context

from .base import ServiceBase

bp = Blueprint("json_inspector", __name__)

# --- настройки/ключи сессии ---
# Чтобы убрать лимит — оставьте MAX_BYTES = None
MAX_BYTES: Optional[int] = None  # например: 2 * 1024 * 1024 * 1024 для 2 ГБ
SESSION_PATH = "json_inspector_tmp"    # путь к загруженному файлу (не обязателен для логики)
SESSION_CORE = "json_inspector_core"   # ядро (producer/owner/date/type)
SESSION_PROD = "json_inspector_prod"   # поля продукта (tnved/cert*/vsd/production_date)

HTML = """
<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<title>JSON Инспектор</title>
<link rel="stylesheet" href="/static/style.css">
<style>
  .row{margin:12px 0}
  .muted{color:#9aa0a6}
  .ok{color:#15a34a}
  .err{color:#b00020}
  .grid2{display:grid; grid-template-columns: 1fr auto; gap:10px; align-items:end}
  table{width:100%; border-collapse:collapse; margin-top:8px}
  th,td{border:1px solid #262b33; padding:6px; vertical-align:top}
  th{width:260px; text-align:left; background:#10141c}
  textarea{width:100%; min-height:180px; font-family:ui-monospace,Menlo,Consolas,monospace}
  .actions{display:flex; gap:8px; flex-wrap:wrap; margin-top:12px}
  .badge{display:inline-block; padding:2px 8px; border:1px solid #334155; border-radius:999px; font-size:12px; color:#cbd5e1}
  .grid-form{display:grid; grid-template-columns: 1fr 300px; gap:12px; align-items:start}
  .stack{display:flex; flex-direction:column; gap:8px}
  input[type="text"], input[type="date"]{width:100%; padding:8px 10px; border-radius:10px; border:1px solid #262b33; background:#0e1116; color:#e6e6e6}
  .grid2cols{display:grid; grid-template-columns: 1fr 1fr; gap:10px}
  .card{border:1px solid #262b33; border-radius:12px; padding:12px}
  .hstack{display:flex; gap:8px; align-items:center; flex-wrap:wrap}
  .btn-row{display:flex; flex-direction:column; gap:8px}
  button{padding:8px 12px}
</style>
<body>
<div class="container">
  <h2>JSON Инспектор</h2>
  <p class="muted">Шаг 1: загрузите JSON — поля ниже заполнятся автоматически. Шаг 2: при необходимости отредактируйте данные. Шаг 3: вставьте коды и скачайте файлы.</p>

  <!-- Загрузка (парсим сразу) -->
  <form class="row" method="POST" action="upload" enctype="multipart/form-data">
    <div class="grid2">
      <input type="file" name="json_file" accept=".json,application/json" required>
      <button type="submit">Загрузить JSON</button>
    </div>
    <div class="muted">
      {% if max_mb %}
        Лимит файла: {{ max_mb }} МБ
      {% else %}
        Лимит файла: <b>отключён</b>
      {% endif %}
    </div>
  </form>

  {% if file_info %}
    <div class="row">
      <span class="badge">Файл загружен</span>
      <span class="muted">Имя: <b>{{ file_info.name }}</b>, размер: <b>{{ file_info.size_h }}</b></span>
    </div>
  {% endif %}

  {% if message %}
    <div class="row {{ 'ok' if ok else 'err' }}"><b>{{ message }}</b></div>
  {% endif %}

  {% if core %}
    <!-- Одна большая форма: редактируемые поля + коды + имя файла + кнопки действия -->
    <form method="POST">
      <div class="grid-form">

        <div class="stack">
          <div class="card">
            <h3>Данные (ядро)</h3>
            <div class="grid2cols">
              <div>
                <label class="muted">producer_inn</label>
                <input type="text" name="producer_inn" value="{{ core.producer_inn or '' }}">
              </div>
              <div>
                <label class="muted">owner_inn</label>
                <input type="text" name="owner_inn" value="{{ core.owner_inn or '' }}">
              </div>
              <div>
                <label class="muted">production_date</label>
                <input type="text" name="production_date" placeholder="YYYY-MM-DD" value="{{ core.production_date or '' }}">
              </div>
              <div>
                <label class="muted">production_type</label>
                <input type="text" name="production_type" placeholder="OWN_PRODUCTION / CONTRACT_PRODUCTION" value="{{ core.production_type or '' }}">
              </div>
            </div>
          </div>

          <div class="card" style="margin-top:12px">
            <h3>Данные (product)</h3>
            <div class="grid2cols">
              <div>
                <label class="muted">tnved_code</label>
                <input type="text" name="tnved_code" value="{{ prod.tnved_code or '' }}">
              </div>
              <div>
                <label class="muted">certificate_type</label>
                <input type="text" name="certificate_type" placeholder="CONFORMITY_DECLARATION" value="{{ prod.certificate_type or '' }}">
              </div>
              <div>
                <label class="muted">certificate_number</label>
                <input type="text" name="certificate_number" value="{{ prod.certificate_number or '' }}">
              </div>
              <div>
                <label class="muted">certificate_date</label>
                <input type="text" name="certificate_date" placeholder="YYYY-MM-DD" value="{{ prod.certificate_date or '' }}">
              </div>
              <div>
                <label class="muted">vsd_number</label>
                <input type="text" name="vsd_number" value="{{ prod.vsd_number or '' }}">
              </div>
              <div>
                <label class="muted">production_date (product)</label>
                <input type="text" name="prod_production_date" placeholder="YYYY-MM-DD" value="{{ prod.production_date or '' }}">
              </div>
            </div>
            <div class="hstack" style="margin-top:10px">
              <button type="submit" formaction="update">Обновить данные</button>
              <span class="muted">Нажмите, чтобы сохранить введённые значения в сессию и обновить превью.</span>
            </div>
          </div>

          <div class="card" style="margin-top:12px">
            <h3>Коды</h3>
            <label class="muted">Коды (по одному в строку)</label>
            <textarea name="codes" placeholder="вставьте сюда коды (KI)…"></textarea>
            <div class="muted" style="margin-top:8px">
              Для XML: всё после &lt;GT&gt; в коде отбрасывается (и сам маркер тоже).<br>
              Поддерживается <code>&lt;GS&gt;</code> → символ 0x1D.
            </div>
          </div>

        </div>

        <div class="btn-row">
          <div class="stack">
            <label class="muted">Имя файла (без расширения)</label>
            <input type="text" name="fname" placeholder="например: introduce_2025-11-02">
            <button type="submit" formaction="download/json">Скачать JSON (ядро+шаблон)</button>
            <button type="submit" formaction="download/csv">Скачать CSV (коды)</button>
            <button type="submit" formaction="download/xml">Скачать XML (ввод в оборот)</button>
          </div>
        </div>

      </div>
    </form>
  {% endif %}
</div>
</body>
</html>
"""

# ---------- helpers ----------

def _humansize(n: int) -> str:
    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    i = 0
    val = float(n)
    while val >= 1024 and i < len(units)-1:
        val /= 1024.0
        i += 1
    return f"{val:.1f} {units[i]}"

def _read_limited(file_storage, limit: Optional[int] = MAX_BYTES) -> bytes:
    """
    Читаем поток файла порциями. Если limit=None, лимит отключён.
    """
    total = 0
    chunks = []
    while True:
        chunk = file_storage.stream.read(1024 * 1024)  # 1 МБ
        if not chunk:
            break
        total += len(chunk)
        if limit is not None and total > limit:
            raise ValueError(f"Размер файла превышает лимит {limit} байт")
        chunks.append(chunk)
    return b"".join(chunks)

def _coalesce_str(d: Dict[str, Any], key: str, default: str = "") -> str:
    v = d.get(key, default)
    if isinstance(v, str):
        return v.strip()
    return default if v is None else str(v)

def _sanitize_fname(name: str, default: str = "export") -> str:
    """
    Очищает имя файла: запрещённые символы → '_', обрезает длину.
    Пустая строка -> default.
    """
    if not name:
        return default
    name = re.sub(r'[\\/:*?"<>|\\r\\n\\t]+', "_", name)
    name = name.strip(" .") or default
    if len(name) > 128:
        name = name[:128]
    return name

def _extract_product_template(raw: Dict[str, Any], core_prod_date: str) -> Dict[str, str]:
    """
    Шаблон полей продукта:
      - Берём первый продукт из products или products_list (если есть).
      - certificate_* берём из первого элемента certificate_document_data[0], если есть.
      - production_date продукта → если пусто, подставляем core_prod_date.
    """
    p: Dict[str, Any] = {}
    if isinstance(raw.get("products"), list) and raw["products"]:
        p = raw["products"][0] or {}
    elif isinstance(raw.get("products_list"), list) and raw["products_list"]:
        p = raw["products_list"][0] or {}
    else:
        p = {}

    cert_type, cert_num, cert_date = "", "", ""
    certs = p.get("certificate_document_data") or []
    if isinstance(certs, list) and certs:
        c0 = certs[0] or {}
        cert_type = _coalesce_str(c0, "certificate_type", "CONFORMITY_DECLARATION") or "CONFORMITY_DECLARATION"
        cert_num  = _coalesce_str(c0, "certificate_number")
        cert_date = _coalesce_str(c0, "certificate_date")

    prod_date = _coalesce_str(p, "production_date") or core_prod_date

    return {
        "tnved_code": _coalesce_str(p, "tnved_code"),
        "certificate_type": cert_type or "CONFORMITY_DECLARATION",
        "certificate_number": cert_num,
        "certificate_date": cert_date,
        "vsd_number": _coalesce_str(p, "vsd_number"),
        "production_date": prod_date,
    }

def _normalize_core(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "producer_inn": _coalesce_str(raw, "producer_inn") or _coalesce_str(raw, "participant_inn"),
        "owner_inn": _coalesce_str(raw, "owner_inn"),
        "production_date": _coalesce_str(raw, "production_date"),
        "production_type": _coalesce_str(raw, "production_type") or _coalesce_str(raw, "production_order") or "OWN_PRODUCTION",
    }

def _parse_codes(text: str) -> Iterable[str]:
    """
    Возвращает ИТЕРАТОР по кодам (без загрузки всех строк в память).
    Поддержка <GS> → \x1D.
    Пустые строки пропускаются.
    """
    if not text:
        return []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = s.replace("<GS>", "\\x1D").replace("&lt;GS&gt;", "\\x1D")
        # заменим текстовый маркер на реальный символ для внутренней обработки,
        # он всё равно будет очищен для XML и заменён для CSV
        yield s.replace("\\x1D", "\x1D")

_GT_SPLIT = re.compile(r"(?:<GT>|&lt;GT&gt;)")

def _cut_at_gt(code: str) -> str:
    """
    Возвращает всё слева от <GT> / &lt;GT&gt;.
    Если маркера нет — возвращает исходную строку.
    """
    if not code:
        return ""
    return _GT_SPLIT.split(code, 1)[0]

def _xml_prepare_code(raw_code: str) -> str:
    """
    Для XML:
      - режем по <GT> (или &lt;GT&gt;), отбрасывая всё справа и сам маркер,
      - убираем управляющие символы группы и текстовые маркеры GS.
    """
    s = (raw_code or "").strip()
    s = _cut_at_gt(s)  # <--- теперь гарантированно обрезает всё справа от <GT>
    s = s.replace("\x1D", "").replace("<GS>", "").replace("&lt;GS&gt;", "")
    return s

def _csv_stream(codes_iter: Iterable[str]) -> Iterable[bytes]:
    """
    Стриминг CSV: одна колонка, одна строка на код.
    <GT>/&lt;GT&gt; → \x1D только для CSV.
    """
    first_yielded = False
    for c in codes_iter:
        c = (c or "")
        c = c.replace("<GT>", "\x1D").replace("&lt;GT&gt;", "\x1D")
        c = c.replace("\r", "")
        # добавляем \n построчно
        line = (c + "\n").encode("utf-8-sig") if not first_yielded else (c + "\n").encode("utf-8")
        first_yielded = True
        yield line

def _xml_stream(core: Dict[str, Any], prod: Dict[str, Any], codes_iter: Iterable[str]) -> Iterable[bytes]:
    """
    Стриминг XML: не буферим весь документ.
    """
    is_contract = (core.get("production_type") == "CONTRACT_PRODUCTION")
    tnved_code  = (prod.get("tnved_code") or "").strip()
    cert_type   = (prod.get("certificate_type") or "CONFORMITY_DECLARATION").strip()
    cert_num    = (prod.get("certificate_number") or "").strip()
    cert_date   = (prod.get("certificate_date") or "").strip()
    vsd_number  = (prod.get("vsd_number") or "").strip()
    prod_date_fallback = (core.get("production_date") or "").strip()
    per_item_prod_date = (prod.get("production_date") or prod_date_fallback or "").strip()

    if is_contract:
        head = [
            '<introduce_contract version="7">',
            f'  <producer_inn>{core.get("producer_inn","")}</producer_inn>',
            f'  <owner_inn>{core.get("owner_inn","")}</owner_inn>',
            f'  <production_date>{core.get("production_date","")}</production_date>',
            f'  <production_order>{core.get("production_type","")}</production_order>',
            '  <products_list>',
        ]
        tail = ['  </products_list>', '</introduce_contract>']
    else:
        head = [
            '<introduce_rf version="9">',
            f'  <trade_participant_inn>{core.get("producer_inn","")}</trade_participant_inn>',
            f'  <producer_inn>{core.get("producer_inn","")}</producer_inn>',
            f'  <owner_inn>{core.get("owner_inn","")}</owner_inn>',
            f'  <production_date>{core.get("production_date","")}</production_date>',
            f'  <production_order>{core.get("production_type","")}</production_order>',
            '  <products_list>',
        ]
        tail = ['  </products_list>', '</introduce_rf>']

    yield ("\n".join(head) + "\n").encode("utf-8")

    for raw_code in codes_iter:
        code = _xml_prepare_code(raw_code)
        if not code:
            continue
        block = [
            '    <product>',
            f'      <ki><![CDATA[{code}]]></ki>',
            f'      <production_date>{per_item_prod_date}</production_date>',
            f'      <tnved_code>{tnved_code}</tnved_code>',
            f'      <certificate_type>{cert_type or "CONFORMITY_DECLARATION"}</certificate_type>',
            f'      <certificate_number>{cert_num}</certificate_number>',
            f'      <certificate_date>{cert_date}</certificate_date>',
            f'      <vsd_number>{vsd_number}</vsd_number>',
            '    </product>',
        ]
        yield ("\n".join(block) + "\n").encode("utf-8")

    yield ("\n".join(tail)).encode("utf-8")

def _build_core_from_form(form) -> Dict[str, Any]:
    return {
        "producer_inn": (form.get("producer_inn") or "").strip(),
        "owner_inn": (form.get("owner_inn") or "").strip(),
        "production_date": (form.get("production_date") or "").strip(),
        "production_type": (form.get("production_type") or "").strip() or "OWN_PRODUCTION",
    }

def _build_prod_from_form(form, core_prod_date: str) -> Dict[str, Any]:
    prod_date = (form.get("prod_production_date") or "").strip() or (core_prod_date or "")
    return {
        "tnved_code": (form.get("tnved_code") or "").strip(),
        "certificate_type": (form.get("certificate_type") or "").strip() or "CONFORMITY_DECLARATION",
        "certificate_number": (form.get("certificate_number") or "").strip(),
        "certificate_date": (form.get("certificate_date") or "").strip(),
        "vsd_number": (form.get("vsd_number") or "").strip(),
        "production_date": prod_date,
    }

# ---------- маршруты ----------

@bp.route("/", methods=["GET"])
def page():
    info = None
    path = session.get(SESSION_PATH)
    if path and os.path.exists(path):
        info = {"name": os.path.basename(path), "size_h": _humansize(os.path.getsize(path))}
    core = session.get(SESSION_CORE)
    prod = session.get(SESSION_PROD) or {}
    return render_template_string(
        HTML,
        file_info=info,
        message=None,
        ok=False,
        core=core,
        prod=prod,
        max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024)
    )

@bp.route("/upload", methods=["POST"])
def upload():
    """
    Загружаем файл, проверяем тип, ПАРСИМ СРАЗУ:
      - core (producer/owner/date/type)
      - prod (tnved/cert*/vsd/product.production_date с фолбэком на core.production_date)
    Сохраняем в сессию и показываем на странице без дополнительных шагов.
    """
    f = request.files.get("json_file")
    message = None
    ok = False
    info = None

    if not f:
        message = "Файл не выбран"
        return render_template_string(HTML, file_info=None, message=message, ok=ok, core=session.get(SESSION_CORE), prod=session.get(SESSION_PROD) or {}, max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024))

    filename = (f.filename or "").lower()
    mimetype = (f.mimetype or "").lower()
    if not (filename.endswith(".json") or "json" in mimetype):
        message = "Можно загрузить только JSON (.json)"
        return render_template_string(HTML, file_info=None, message=message, ok=ok, core=session.get(SESSION_CORE), prod=session.get(SESSION_PROD) or {}, max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024))

    try:
        data_bytes = _read_limited(f, MAX_BYTES)
    except Exception as e:
        message = f"Ошибка чтения файла: {e}"
        return render_template_string(HTML, file_info=None, message=message, ok=ok, core=session.get(SESSION_CORE), prod=session.get(SESSION_PROD) or {}, max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024))

    try:
        text = data_bytes.decode("utf-8", errors="strict")
        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise ValueError("Ожидался JSON-объект (dict) на корне")

        core = _normalize_core(raw)
        prod = _extract_product_template(raw, core_prod_date=core.get("production_date",""))

        session[SESSION_CORE] = core
        session[SESSION_PROD] = prod
        session.modified = True

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                tmp.write(data_bytes)
                tmp_path = tmp.name
            session[SESSION_PATH] = tmp_path
        except Exception:
            pass

        ok = True
        info = {"name": os.path.basename(filename or "file.json"), "size_h": _humansize(len(data_bytes))}
        message = "Файл загружен и распарсен"

        return render_template_string(HTML, file_info=info, message=message, ok=ok, core=core, prod=prod, max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024))
    except UnicodeDecodeError:
        message = "Файл не в UTF-8 или содержит некорректные байты"
    except json.JSONDecodeError as e:
        message = f"Некорректный JSON: {e}"
    except Exception as e:
        message = f"Ошибка парсинга: {e}"

    return render_template_string(HTML, file_info=None, message=message, ok=False, core=None, prod=None, max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024))

@bp.route("/update", methods=["POST"])
def update_data():
    """
    Сохраняем введённые пользователем значения core/prod в сессию.
    """
    core_form = _build_core_from_form(request.form)
    prod_form = _build_prod_from_form(request.form, core_form.get("production_date",""))

    session[SESSION_CORE] = core_form
    session[SESSION_PROD] = prod_form
    session.modified = True

    info = None
    path = session.get(SESSION_PATH)
    if path and os.path.exists(path):
        info = {"name": os.path.basename(path), "size_h": _humansize(os.path.getsize(path))}

    return render_template_string(
        HTML,
        file_info=info,
        message="Данные обновлены",
        ok=True,
        core=core_form,
        prod=prod_form,
        max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024)
    )

# --- скачивания (берут имя файла, коды и ПОЛЯ ИЗ ФОРМЫ) ---

@bp.route("/download/json", methods=["POST"])
def download_json():
    # Строим core/prod по приоритету: из формы -> из сессии
    core = _build_core_from_form(request.form)
    if not any(core.values()):  # если кнопка нажата без полей — fallback к сессии
        core = session.get(SESSION_CORE) or {}
    prod = _build_prod_from_form(request.form, core.get("production_date",""))
    if not any(prod.values()):
        prod = session.get(SESSION_PROD) or {}

    fname = _sanitize_fname(request.form.get("fname", "") or "core_and_template")
    payload = json.dumps({"core": core, "product_template": prod}, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}.json"'}
    )

@bp.route("/download/csv", methods=["POST"])
def download_csv():
    codes_iter = _parse_codes(request.form.get("codes", ""))
    fname = _sanitize_fname(request.form.get("fname", "") or "codes")
    generator = _csv_stream(codes_iter)
    # Первая строка отдаётся UTF-8-SIG для BOM совместимости с Excel
    return Response(
        stream_with_context(generator),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'}
    )

@bp.route("/download/xml", methods=["POST"])
def download_xml():
    # core/prod из формы (приоритет) или из сессии
    core = _build_core_from_form(request.form)
    if not any(core.values()):
        core = session.get(SESSION_CORE)
    prod = _build_prod_from_form(request.form, (core or {}).get("production_date","") if core else "")
    if not any(prod.values()):
        prod = session.get(SESSION_PROD) or {}

    if not core:
        return render_template_string(HTML, file_info=None, message="Нет данных: загрузите JSON или заполните поля", ok=False, core=None, prod=None, max_mb=None if MAX_BYTES is None else MAX_BYTES // (1024*1024))

    codes_iter = _parse_codes(request.form.get("codes", ""))
    fname = _sanitize_fname(request.form.get("fname", "") or "introduce")
    generator = _xml_stream(core, prod or {}, codes_iter)
    return Response(
        stream_with_context(generator),
        mimetype="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}.xml"'}
    )

# экспорт сервиса
service = ServiceBase(
    id="json-inspector",
    name="JSON Инспектор",
    description="Редактируемые поля ядра и продукта. Стриминговая выгрузка CSV/XML. CONTRACT/OWN. Резка по <GT>.",
    icon="🧪",
    blueprint=bp,
)


if __name__ == "__main__":
    # вход
    raw = "01KI123456789<GT>что-то справа"
    print(_xml_prepare_code(raw))
    # -> "01KI123456789"

    raw = "01KI123\x1D<GS>ABC&lt;GT&gt;RIGHT"
    print(_xml_prepare_code(raw))
    # -> "01KI123ABC"