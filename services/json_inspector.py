from __future__ import annotations
import io
import json
import os
import re
import tempfile
from typing import Any, Dict, List

from flask import Blueprint, request, render_template_string, session, send_file

from .base import ServiceBase

bp = Blueprint("json_inspector", __name__)

# --- настройки/ключи сессии ---
MAX_BYTES   = 5 * 1024 * 1024  # 5 MB
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
  .grid-form{display:grid; grid-template-columns: 1fr 240px; gap:12px; align-items:start}
  .stack{display:flex; flex-direction:column; gap:8px}
  input[type="text"]{width:100%; padding:8px 10px; border-radius:10px; border:1px solid #262b33; background:#0e1116; color:#e6e6e6}
</style>
<body>
<div class="container">
  <h2>JSON Инспектор</h2>
  <p class="muted">Шаг 1: загрузите JSON — поля ниже обновятся автоматически. Шаг 2: вставьте коды построчно и скачайте файлы.</p>

  <!-- Загрузка (парсим сразу) -->
  <form class="row" method="POST" action="upload" enctype="multipart/form-data">
    <div class="grid2">
      <input type="file" name="json_file" accept=".json,application/json" required>
      <button type="submit">Загрузить JSON</button>
    </div>
    <div class="muted">Лимит файла: {{ max_mb }} МБ</div>
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
    <h3>Данные</h3>
    <table>
      <tr><th>producer_inn</th><td>{{ core.producer_inn }}</td></tr>
      <tr><th>owner_inn</th><td>{{ core.owner_inn }}</td></tr>
      <tr><th>production_date</th><td>{{ core.production_date }}</td></tr>
      <tr><th>production_type</th><td>{{ core.production_type }}</td></tr>

      <tr><th>tnved_code</th><td>{{ prod.tnved_code }}</td></tr>
      <tr><th>certificate_type</th><td>{{ prod.certificate_type }}</td></tr>
      <tr><th>certificate_number</th><td>{{ prod.certificate_number }}</td></tr>
      <tr><th>certificate_date</th><td>{{ prod.certificate_date }}</td></tr>
      <tr><th>vsd_number</th><td>{{ prod.vsd_number }}</td></tr>
      <tr><th>production_date (product)</th><td>{{ prod.production_date }}</td></tr>
    </table>

    <!-- Одна форма: имя файла + коды + кнопки скачивания берут значения напрямую -->
    <h3>Коды и выгрузка</h3>
    <form method="POST">
      <div class="grid-form">
        <div class="stack">
          <label class="muted">Коды (по одному в строку)</label>
          <textarea name="codes" placeholder="вставьте сюда коды (KI)…"></textarea>
        </div>
        <div class="stack">
          <label class="muted">Имя файла (без расширения)</label>
          <input type="text" name="fname" placeholder="например: introduce_2025-11-02">
          <button type="submit" formaction="download/json">Скачать JSON (ядро+шаблон)</button>
          <button type="submit" formaction="download/csv">Скачать CSV (коды)</button>
          <button type="submit" formaction="download/xml">Скачать XML (ввод в оборот)</button>
        </div>
      </div>
      <div class="muted" style="margin-top:8px">XML: всё после &lt;GT&gt; в коде отбрасывается (и сам маркер тоже).</div>
    </form>
  {% endif %}
</div>
</body>
</html>
"""

# ---------- helpers ----------

def _humansize(n: int) -> str:
    units = ["Б", "КБ", "МБ", "ГБ"]
    i = 0
    val = float(n)
    while val >= 1024 and i < len(units)-1:
        val /= 1024.0
        i += 1
    return f"{val:.1f} {units[i]}"

def _read_limited(file_storage, limit: int = MAX_BYTES) -> bytes:
    total = 0
    chunks = []
    while True:
        chunk = file_storage.stream.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
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
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name)
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

def _parse_codes(text: str) -> List[str]:
    codes: List[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        # Поддержка <GS> → 0x1D
        s = s.replace("<GS>", "\x1D").replace("&lt;GS&gt;", "\x1D")
        codes.append(s)
    return codes

def _cut_at_gt(code: str) -> str:
    """
    Режем строку по маркеру <GT> или &lt;GT&gt;:
      'AAA<GT>BBB'    -> 'AAA'
      'AAA&lt;GT&gt;B' -> 'AAA'
    Если маркера нет — возвращаем как есть.
    """
    # сначала буквальный <GT>
    idx = code.find("<GT>")
    if idx >= 0:
        return code[:idx]
    # затем HTML-энкод
    idx = code.find("&lt;GT&gt;")
    if idx >= 0:
        return code[:idx]
    return code

def _csv_from_codes(codes: List[str]) -> bytes:
    safe = [(c or "").replace("\r", "").replace("\n", "") for c in codes if c]
    out = "\n".join(safe) + ("\n" if safe else "")
    return out.encode("utf-8-sig")

def _xml_from(core: Dict[str, Any], prod: Dict[str, Any], codes: List[str]) -> bytes:
    """
    Генерируем XML:
      - CONTRACT_PRODUCTION → <introduce_contract version="7">
      - OWN_PRODUCTION     → <introduce_rf version="9">
    Для каждого кода создаём <product>, причём:
      - код берём ДО маркера <GT> (и &lt;GT&gt;), сам маркер и хвост отбрасываем;
      - в <product> всегда: <ki>, <production_date>, <tnved_code>, <certificate_type>,
        <certificate_number>, <certificate_date>, <vsd_number>.
    """
    is_contract = (core.get("production_type") == "CONTRACT_PRODUCTION")

    lines = []
    if is_contract:
        lines.append('<introduce_contract version="7">')
        lines.append(f'  <producer_inn>{core.get("producer_inn","")}</producer_inn>')
        lines.append(f'  <owner_inn>{core.get("owner_inn","")}</owner_inn>')
        lines.append(f'  <production_date>{core.get("production_date","")}</production_date>')
        lines.append(f'  <production_order>{core.get("production_type","")}</production_order>')
    else:
        lines.append('<introduce_rf version="9">')
        lines.append(f'  <trade_participant_inn>{core.get("producer_inn","")}</trade_participant_inn>')
        lines.append(f'  <producer_inn>{core.get("producer_inn","")}</producer_inn>')
        lines.append(f'  <owner_inn>{core.get("owner_inn","")}</owner_inn>')
        lines.append(f'  <production_date>{core.get("production_date","")}</production_date>')
        lines.append(f'  <production_order>{core.get("production_type","")}</production_order>')

    tnved_code  = (prod.get("tnved_code") or "").strip()
    cert_type   = (prod.get("certificate_type") or "CONFORMITY_DECLARATION").strip()
    cert_num    = (prod.get("certificate_number") or "").strip()
    cert_date   = (prod.get("certificate_date") or "").strip()
    vsd_number  = (prod.get("vsd_number") or "").strip()
    prod_date_fallback = (core.get("production_date") or "").strip()

    lines.append('  <products_list>')
    for raw_code in codes:
        code = _cut_at_gt((raw_code or "").strip())
        if not code:
            continue
        per_item_prod_date = (prod.get("production_date") or prod_date_fallback or "").strip()

        lines.append('    <product>')
        lines.append(f'      <ki><![CDATA[{code}]]></ki>')
        lines.append(f'      <production_date>{per_item_prod_date}</production_date>')
        lines.append(f'      <tnved_code>{tnved_code}</tnved_code>')
        lines.append(f'      <certificate_type>{cert_type or "CONFORMITY_DECLARATION"}</certificate_type>')
        lines.append(f'      <certificate_number>{cert_num}</certificate_number>')
        lines.append(f'      <certificate_date>{cert_date}</certificate_date>')
        lines.append(f'      <vsd_number>{vsd_number}</vsd_number>')
        lines.append('    </product>')
    lines.append('  </products_list>')
    lines.append('</introduce_contract>' if is_contract else '</introduce_rf>')
    return ("\n".join(lines)).encode("utf-8")

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
        max_mb=MAX_BYTES // (1024*1024)
    )

@bp.route("/upload", methods=["POST"])
def upload():
    """
    Загружаем файл, проверяем размер/тип, ПАРСИМ СРАЗУ:
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
        return render_template_string(HTML, file_info=None, message=message, ok=ok, core=session.get(SESSION_CORE), prod=session.get(SESSION_PROD) or {}, max_mb=MAX_BYTES // (1024*1024))

    filename = (f.filename or "").lower()
    mimetype = (f.mimetype or "").lower()
    if not (filename.endswith(".json") or "json" in mimetype):
        message = "Можно загрузить только JSON (.json)"
        return render_template_string(HTML, file_info=None, message=message, ok=ok, core=session.get(SESSION_CORE), prod=session.get(SESSION_PROD) or {}, max_mb=MAX_BYTES // (1024*1024))

    try:
        data_bytes = _read_limited(f, MAX_BYTES)
    except Exception as e:
        message = f"Ошибка чтения файла: {e}"
        return render_template_string(HTML, file_info=None, message=message, ok=ok, core=session.get(SESSION_CORE), prod=session.get(SESSION_PROD) or {}, max_mb=MAX_BYTES // (1024*1024))

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

        return render_template_string(HTML, file_info=info, message=message, ok=ok, core=core, prod=prod, max_mb=MAX_BYTES // (1024*1024))
    except UnicodeDecodeError:
        message = "Файл не в UTF-8 или содержит некорректные байты"
    except json.JSONDecodeError as e:
        message = f"Некорректный JSON: {e}"
    except Exception as e:
        message = f"Ошибка парсинга: {e}"

    return render_template_string(HTML, file_info=None, message=message, ok=False, core=None, prod=None, max_mb=MAX_BYTES // (1024*1024))

# --- скачивания (берут имя файла и коды из текущей формы) ---
@bp.route("/download/json", methods=["POST"])
def download_json():
    core = session.get(SESSION_CORE)
    prod = session.get(SESSION_PROD)
    if not core:
        return render_template_string(HTML, file_info=None, message="Нет данных: загрузите JSON", ok=False, core=None, prod=None, max_mb=MAX_BYTES // (1024*1024))
    fname = _sanitize_fname(request.form.get("fname", "") or "core_and_template")
    buf = io.BytesIO(json.dumps({"core": core, "product_template": prod}, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(buf, mimetype="application/json", as_attachment=True, download_name=f"{fname}.json")

@bp.route("/download/csv", methods=["POST"])
def download_csv():
    codes = _parse_codes(request.form.get("codes", ""))
    payload = _csv_from_codes(codes)
    fname = _sanitize_fname(request.form.get("fname", "") or "codes")
    return send_file(io.BytesIO(payload), mimetype="text/csv", as_attachment=True, download_name=f"{fname}.csv")

@bp.route("/download/xml", methods=["POST"])
def download_xml():
    core = session.get(SESSION_CORE)
    prod = session.get(SESSION_PROD) or {}
    if not core:
        return render_template_string(HTML, file_info=None, message="Нет данных: загрузите JSON", ok=False, core=None, prod=None, max_mb=MAX_BYTES // (1024*1024))
    codes = _parse_codes(request.form.get("codes", ""))
    payload = _xml_from(core, prod, codes)
    fname = _sanitize_fname(request.form.get("fname", "") or "introduce")
    return send_file(io.BytesIO(payload), mimetype="application/xml", as_attachment=True, download_name=f"{fname}.xml")

# экспорт сервиса
service = ServiceBase(
    id="json-inspector",
    name="JSON Инспектор",
    description="Парсит сразу при загрузке. Один <product> на код (ki). CONTRACT/OWN. Задание имени файла. Резка по <GT>.",
    icon="🧪",
    blueprint=bp,
)
