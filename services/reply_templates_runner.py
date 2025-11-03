from __future__ import annotations
import io, datetime, json
from typing import Any, Dict, List

from flask import Blueprint, render_template_string, request, jsonify, send_file
from .base import ServiceBase
from .template_store import load_all

bp = Blueprint("reply_templates_runner", __name__)

def _greeting() -> str:
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:  return "Доброе утро!"
    if 12 <= hour < 18: return "Добрый день!"
    if 18 <= hour < 23: return "Добрый вечер!"
    return "Доброй ночи!"

def _flags_wrap(text: str, flags: Dict[str, Any]) -> str:
    flags = flags or {}
    prefix = "\n" if flags.get("newline") else (" " if flags.get("spaceBefore") else "")
    suffix = "\n" if flags.get("newlineAfter") else (" " if flags.get("spaceAfter") else "")
    t = text or ""
    if flags.get("upper"): t = t.upper()
    if flags.get("lower"): t = t.lower()
    if flags.get("capitalize"): t = t.capitalize()
    return prefix + t + suffix

def render_block(block: Dict[str, Any], values: Dict[str, Any]) -> str:
    t = block.get("type")
    flags = block.get("flags", {}) or {}
    out = ""

    if t == "StaticText":
        out = block.get("text","")

    elif t == "InputField":
        val = values.get(block.get("name"), "")
        if isinstance(val,(list,dict)): out = json.dumps(val, ensure_ascii=False)
        else: out = str(val or "")

    elif t == "ConditionalInput":
        val = values.get(block.get("name"), "")
        if val not in (None,"",[]): out = f"{block.get('prefix','')}{val}"

    elif t == "Greeting":
        out = _greeting()

    elif t == "DateTime":
        out = datetime.datetime.now().strftime(block.get("format","%Y-%m-%d %H:%M"))

    elif t == "Separator":
        out = str(block.get("char","—")) * int(block.get("repeat",20))

    elif t == "Choice":
        key = values.get(block.get("name"))
        choice = (block.get("choices") or {}).get(key)
        if choice is not None: out = str(choice)

    elif t == "Toggle":
        if values.get(block.get("name")):
            for ch in block.get("children", []):
                out += render_block(ch, values)

    elif t == "Repeater":
        for item in (values.get(block.get("name")) or []):
            for ch in block.get("children", []):
                out += render_block(ch, item if isinstance(item, dict) else {"value":item})

    elif t == "Table":
        headers = block.get("headers", [])
        rows = values.get(block.get("name"), [])
        if headers:
            md = "|" + "|".join(headers) + "|\n|" + "|".join(["---"]*len(headers)) + "|\n"
            for r in rows:
                md += "|" + "|".join([str((r or {}).get(h,"")) for h in headers]) + "|\n"
            out = md.strip()

    return _flags_wrap(out, flags)

def render_template_obj(tpl: Dict[str, Any], values: Dict[str, Any]) -> str:
    res = ""
    for b in tpl.get("blocks", []):
        res += render_block(b, values)
    return res.strip()

HTML = """
<!doctype html>
<html lang="ru"><meta charset="utf-8">
<title>Генератор ответов</title>
<link rel="stylesheet" href="/static/style.css">
<style>
:root{color-scheme:dark}
body{font-family:system-ui,Inter,Segoe UI,Roboto,Arial;background:#0f1116;color:#e6e6e6;margin:0}
.container{max-width:1200px;margin:0 auto;padding:20px}
.grid{display:grid;grid-template-columns:300px 1fr 1fr;gap:16px;align-items:start}
.card{background:#131720;border:1px solid #232837;border-radius:12px;padding:12px}
h2,h3{margin:6px 0 12px}
input[type=text],textarea,select{width:100%;padding:8px 10px;border-radius:10px;border:1px solid #262b33;background:#0e1116;color:#e6e6e6}
textarea{min-height:120px}
button{padding:8px 12px;border:1px solid #334155;background:#1f2937;color:#e5e7eb;border-radius:10px;cursor:pointer}
button:hover{background:#324155}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.kv{display:grid;grid-template-columns:150px 1fr;gap:8px;align-items:center;margin:6px 0}
pre{white-space:pre-wrap;word-break:break-word;background:#0e1116;border:1px solid #262b33;border-radius:10px;padding:10px;min-height:220px}
.muted{color:#9aa0a6}
.help{border-bottom:1px dotted #9aa0a6;cursor:help}
</style>
<body><div class="container">
  <h2>🧩 Генератор ответов</h2>
  <div class="grid">
    <div class="card">
      <strong>Шаблоны</strong>
      <div id="tpl-list"></div>
      <div class="row" style="margin-top:8px">
        <input id="q" type="text" placeholder="Поиск по имени..." oninput="filterList()">
      </div>
    </div>
    <div class="card">
      <strong id="tpl-name">(не выбран)</strong>
      <div id="inputs"></div>
      <div class="row" style="margin-top:8px">
        <button onclick="renderPreview()">🔄 Обновить предпросмотр</button>
        <button onclick="clearValues()">Сбросить</button>
      </div>
    </div>
    <div class="card">
      <strong>Предпросмотр</strong>
      <pre id="preview"></pre>
      <div class="row">
        <button onclick="copyResult()">📋 Копировать</button>
        <button onclick="downloadTxt()">⬇️ Скачать .txt</button>
      </div>
    </div>
  </div>
</div>
<script>
let items=[], current=null, values={};
function $id(x){return document.getElementById(x)}

async function loadList(){
  const res = await fetch("list");
  items = await res.json();
  renderList(items);
}
function renderList(arr){
  const box = $id("tpl-list"); box.innerHTML = "";
  arr.forEach(t=>{
    const a = document.createElement("a");
    a.href="#"; a.textContent=t.name;
    a.style.display="block"; a.style.padding="6px 8px"; a.style.borderRadius="8px";
    a.onclick=(e)=>{e.preventDefault(); openTemplate(t.id)};
    box.appendChild(a);
  });
}
function filterList(){
  const q = ($id("q").value || "").toLowerCase();
  const filtered = items.filter(x=>(x.name||"").toLowerCase().includes(q));
  renderList(filtered);
}
async function openTemplate(id){
  const data = await fetch("get?id="+id).then(r=>r.json());
  current = data; values = {};
  $id("tpl-name").textContent = current.name || "(без имени)";
  renderInputs();
  $id("preview").textContent = "";
}
function flagHint(flags){
  const f = flags||{}; const arr = [];
  if (f.newline) arr.push("новая строка (до)");
  if (f.newlineAfter) arr.push("новая строка (после)");
  if (f.spaceBefore) arr.push("пробел до");
  if (f.spaceAfter) arr.push("пробел после");
  if (f.upper) arr.push("UPPER");
  if (f.lower) arr.push("lower");
  if (f.capitalize) arr.push("Capitalize");
  return arr.join(", ");
}
function renderInputs(){
  const root = $id("inputs"); root.innerHTML="";
  if (!current){ root.innerHTML='<span class="muted">Выберите шаблон слева</span>'; return; }
  if (current.description){
    const p = document.createElement("p");
    p.innerHTML = `<span class="help" title="${current.description}">ℹ️ Подсказка к шаблону</span>`;
    root.appendChild(p);
  }
  (current.blocks||[]).forEach((b)=>{
    const wrap = document.createElement("div"); wrap.className="kv";
    const lab = document.createElement("label");
    lab.innerHTML = `${b.label || b.type} <span class="muted" title="${(b.desc||'') + (b.flags? ('\\n'+flagHint(b.flags)) : '')}">ⓘ</span>`;
    wrap.appendChild(lab);
    let ctrl = document.createElement("div");
    if (b.type==="StaticText" || b.type==="Greeting" || b.type==="Separator" || b.type==="DateTime" || b.type==="Table"){
      ctrl.innerHTML = `<span class="muted">Автоматический блок • ${b.type}</span>`;
    } else if (b.type==="InputField" || b.type==="ConditionalInput"){
      const inp = document.createElement("input"); inp.type="text"; inp.placeholder = b.name || "field";
      inp.oninput = ()=>{ values[b.name]=inp.value; };
      ctrl.appendChild(inp);
    } else if (b.type==="Choice"){
      const sel = document.createElement("select");
      const ch = b.choices || {};
      sel.innerHTML = '<option value="">— выберите —</option>' + Object.keys(ch).map(k=>`<option value="${k}">${k} — ${ch[k]}</option>`).join("");
      sel.onchange = ()=>{ values[b.name]=sel.value; };
      ctrl.appendChild(sel);
    } else if (b.type==="Toggle"){
      const cb = document.createElement("input"); cb.type="checkbox"; cb.onchange = ()=>{ values[b.name]=cb.checked; };
      ctrl.appendChild(cb);
    } else if (b.type==="Repeater"){
      const area = document.createElement("textarea");
      area.placeholder = "По одному значению в строке (будет доступно как { value })";
      area.oninput = ()=>{ values[b.name] = area.value.split("\\n").map(s=>s.trim()).filter(Boolean).map(x=>({value:x})); };
      ctrl.appendChild(area);
    } else {
      ctrl.innerHTML = `<span class="muted">Неизвестный блок: ${b.type}</span>`;
    }
    wrap.appendChild(ctrl); root.appendChild(wrap);
  });
}
async function renderPreview(){
  if (!current){ return; }
  const res = await fetch("render", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({template: current, values})});
  $id("preview").textContent = await res.text();
}
function clearValues(){ values={}; renderInputs(); $id("preview").textContent=""; }
function copyResult(){ const t = $id("preview").textContent||""; navigator.clipboard.writeText(t); }
function downloadTxt(){
  const t = $id("preview").textContent||"";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([t], {type:"text/plain;charset=utf-8"}));
  a.download = (current?.name||"reply") + ".txt"; a.click();
}
loadList();
</script>
</body></html>
"""

@bp.route("/")
def index():
    return render_template_string(HTML)

@bp.route("/list")
def list_templates():
    data = load_all()
    return jsonify([{"id": t.get("id", i), "name": t.get("name") or f"Шаблон {i+1}"} for i, t in enumerate(data)])

@bp.route("/get")
def get_template():
    data = load_all()
    idx = int(request.args.get("id", 0))
    if 0 <= idx < len(data):
        return jsonify(data[idx])
    return jsonify({})

@bp.route("/render", methods=["POST"])
def render_view():
    payload = request.get_json(force=True)
    tpl = payload.get("template", {})
    vals = payload.get("values", {})
    return render_template_obj(tpl, vals)

service = ServiceBase(
    id="reply-templates-runner",
    name="Генератор ответов",
    description="Выбор шаблона, ввод значений, предпросмотр и экспорт .txt",
    icon="🧩",
    blueprint=bp,
)
