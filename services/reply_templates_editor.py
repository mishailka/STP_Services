from __future__ import annotations
from typing import Any, Dict, List

from flask import Blueprint, render_template_string, request, jsonify
from .base import ServiceBase
from .template_store import load_all, save_all, get_path

bp = Blueprint("reply_templates_editor", __name__)

HTML = """
<!doctype html>
<html lang="ru"><meta charset="utf-8">
<title>Редактор шаблонов (визуальный)</title>
<link rel="stylesheet" href="/static/style.css">
<style>
.help{display:inline-block;border-bottom:1px dotted #9aa0a6;cursor:help}
:root{color-scheme:dark}
body{font-family:system-ui,Inter,Segoe UI,Roboto,Arial;background:#0f1116;color:#e6e6e6;margin:0}
.container{max-width:1200px;margin:0 auto;padding:20px}
.grid{display:grid;grid-template-columns:300px 1fr;gap:16px;align-items:start}
.card{background:#131720;border:1px solid #232837;border-radius:12px;padding:12px}
h2,h3{margin:6px 0 12px}
input[type=text],textarea,select{width:100%;padding:8px 10px;border-radius:10px;border:1px solid #262b33;background:#0e1116;color:#e6e6e6}
textarea{min-height:80px}
button{padding:8px 12px;border:1px solid #334155;background:#1f2937;color:#e5e7eb;border-radius:10px;cursor:pointer}
button:hover{background:#324155}
.list a{display:block;padding:6px 8px;border-radius:8px;text-decoration:none;color:#e6e6e6;border:1px solid transparent}
.list a:hover{background:#1a1f2b;border-color:#2a3142}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.badge{display:inline-block;padding:2px 8px;border:1px solid #334155;border-radius:999px;font-size:12px;color:#cbd5e1}
.block{background:#0e1116;border:1px solid #2a3142;border-radius:10px;padding:10px;margin:8px 0}
.block-head{display:flex;gap:8px;align-items:center;justify-content:space-between}
.block-title{font-weight:600;display:flex;align-items:center;gap:6px}
.block-body{margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:8px}
.block small{color:#9aa0a6}
.kv{display:grid;grid-template-columns:160px 1fr;gap:8px;align-items:center}
.hr{height:1px;background:#232837;margin:10px 0}
</style>
<body><div class="container">
  <h2>🛠️ Редактор шаблонов</h2>
  <div class="grid">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <strong>Шаблоны</strong>
        <span class="badge" id="store-path"></span>
      </div>
      <div class="list" id="tpl-list"></div>
      <div class="row" style="margin-top:8px">
        <button onclick="createNew()">＋ Новый</button>
        <button onclick="loadTemplates()">Обновить</button>
      </div>
    </div>
    <div class="card">
      <div class="row">
        <div class="kv"><label>Название</label><input id="tpl-name" type="text"></div>
        <div class="kv"><label>Описание</label><input id="tpl-desc" type="text" placeholder="Подсказка при использовании"></div>
      </div>
      <div class="hr"></div>
      <div class="row">
        <strong>Добавить блок:</strong>
        <button onclick="addBlock('Greeting')">Greeting</button>
        <button onclick="addBlock('StaticText')">StaticText</button>
        <button onclick="addBlock('InputField')">InputField</button>
        <button onclick="addBlock('ConditionalInput')">ConditionalInput</button>
        <button onclick="addBlock('Choice')">Choice</button>
        <button onclick="addBlock('Toggle')">Toggle</button>
        <button onclick="addBlock('Repeater')">Repeater</button>
        <button onclick="addBlock('Table')">Table</button>
        <button onclick="addBlock('Separator')">Separator</button>
        <button onclick="addBlock('DateTime')">DateTime</button>
      </div>
      <div id="blocks"></div>
      <div class="hr"></div>
      <div class="row">
        <button onclick="saveTemplate()">💾 Сохранить</button>
        <button onclick="deleteTemplate()">🗑 Удалить</button>
      </div>
    </div>
  </div>
</div>
<script>

let currentId = null;
function $id(x){return document.getElementById(x)}

const FLAG_FIELDS = [
  ["newline","С новой строки"],["newlineAfter","После — новая строка"],
  ["spaceBefore","Пробел до"],["spaceAfter","Пробел после"],
  ["upper","UPPER"],["lower","lower"],["capitalize","Capitalize"]
];

function makeInfoIcon(titleText){
  const i = document.createElement('span');
  i.className = 'help';
  i.textContent = 'ⓘ';
  i.title = String(titleText || '');
  i.style.marginLeft = '6px';
  return i;
}

function blockDefaults(type){
  switch(type){
    case "Greeting": return {type, label:"Приветствие", desc:"Автоприветствие по времени", flags:{newlineAfter:true}};
    case "StaticText": return {type, label:"Неизменный текст", text:"Текст...", desc:"Просто текст", flags:{newline:true}};
    case "InputField": 
      return {
        type,
        label:"Поле ввода",
        name:"field",
        desc:"Значение всегда вставляется",
        multiline:false,        // ⬅️ новое поле
        flags:{}
      };
     case "ConditionalInput": 
      return {
        type,
        label:"Условное поле",
        name:"opt",
        prefix:"По заявке: ",
        desc:"Показывается, если поле заполнено",
        multiline:false,        // ⬅️ новое поле
        flags:{newlineAfter:true}
      };
    case "Choice": return {type, label:"Выбор", name:"state", choices:{"ok":"Готов к вводу в оборот","km":"Готов к заказу КМ"}, desc:"Выбор по ключу", flags:{newline:true}};
    case "Toggle": return {type, label:"Переключатель (секция)", name:"need_note", children:[{type:"StaticText", label:"Текст секции", text:"Примечание...", flags:{newline:true}}], desc:"Вкл/выкл секцию", flags:{}};
    case "Repeater": return {type, label:"Повторитель", name:"items", children:[{type:"StaticText", text:"• ", flags:{}},{type:"InputField", name:"value", flags:{newlineAfter:true}}], desc:"Повторить блоки по массиву", flags:{}};
    case "Table": return {type, label:"Таблица", name:"rows", headers:["GTIN","Статус","Комментарий"], desc:"Markdown-таблица из массива объектов", flags:{newline:true}};
    case "Separator": return {type, label:"Разделитель", char:"—", repeat:20, desc:"Линия", flags:{newline:true,newlineAfter:true}};
    case "DateTime": return {type, label:"Дата/время", format:"%Y-%m-%d %H:%M", desc:"Текущие дата/время на момент генерации", flags:{newline:true}};
  }
  return {type, label:type, flags:{}};
}

function renderFlagInputs(flags, idxPath){
  let html = '<div style="grid-column:1/-1"><small>Флаги форматирования:</small><div class="row" style="margin-top:4px">';
  for (let [key,title] of FLAG_FIELDS){
    const id = `flag_${idxPath}_${key}`;
    html += `<label><input type="checkbox" id="${id}" ${flags && flags[key]?'checked':''} onchange="setFlag('${idxPath}','${key}',this.checked)"> ${title}</label>`;
  }
  html += '</div></div>';
  return html;
}

function blockCard(b, idx, parentPath=""){
  const idxPath = parentPath? `${parentPath}.${idx}` : `${idx}`;
  // добавим id в заголовок, чтобы потом DOM-ом навесить иконку и title
  let head = `
    <div class="block-head">
      <div class="block-title" id="title_${idxPath}">${b.label || b.type} <small class="muted">(${b.type})</small></div>
      <div class="row">
        <button onclick="moveBlock('${idxPath}',-1)">↑</button>
        <button onclick="moveBlock('${idxPath}',1)">↓</button>
        <button onclick="removeBlock('${idxPath}')">✖</button>
      </div>
    </div>`;
  let body = `<div class="block-body">
    <div class="kv"><label>Метка</label><input type="text" value="${b.label||''}" onchange="setVal('${idxPath}','label',this.value)"></div>
    <div class="kv"><label>Описание</label><input type="text" value="${b.desc||''}" onchange="setVal('${idxPath}','desc',this.value)"></div>
  `;
  switch(b.type){
    case "StaticText":
      body += `<div class="kv"><label>Текст</label><textarea onchange="setVal('${idxPath}','text',this.value)">${b.text||''}</textarea></div>`;
      break;
       case "InputField":
      body += `
        <div class="kv">
          <label>Имя поля</label>
          <input type="text" value="${b.name||''}" 
                 onchange="setVal('${idxPath}','name',this.value)">
        </div>
        <div class="kv">
          <label>Мультиввод</label>
          <label style="display:flex;align-items:center;gap:4px;">
            <input type="checkbox" ${b.multiline ? 'checked' : ''} 
                   onchange="setVal('${idxPath}','multiline',this.checked)">
            <span>Несколько строк</span>
          </label>
        </div>
      `;
      break;

    case "ConditionalInput":
      body += `
        <div class="kv">
          <label>Имя поля</label>
          <input type="text" value="${b.name||''}" 
                 onchange="setVal('${idxPath}','name',this.value)">
        </div>
        <div class="kv">
          <label>Префикс</label>
          <input type="text" value="${b.prefix||''}" 
                 onchange="setVal('${idxPath}','prefix',this.value)">
        </div>
        <div class="kv">
          <label>Мультиввод</label>
          <label style="display:flex;align-items:center;gap:4px;">
            <input type="checkbox" ${b.multiline ? 'checked' : ''} 
                   onchange="setVal('${idxPath}','multiline',this.checked)">
            <span>Несколько строк</span>
          </label>
        </div>
      `;
      break;
    case "Choice":
      body += `<div class="kv"><label>Имя поля</label><input type="text" value="${b.name||''}" onchange="setVal('${idxPath}','name',this.value)"></div>
               <div class="kv" style="grid-column:1/-1"><label>Варианты (key = text <small class='muted'>или JSON</small>)</label>
                 <textarea onchange="setJSON('${idxPath}','choices',this.value)">${JSON.stringify(b.choices||{},null,2)}</textarea>
               </div>`;
      break;
    case "Toggle":
      body += `<div class="kv"><label>Имя флага</label><input type="text" value="${b.name||''}" onchange="setVal('${idxPath}','name',this.value)"></div>
               <div style="grid-column:1/-1"><small>Дочерние блоки:</small><div id="children_${idxPath}"></div>
               <button onclick="addChild('${idxPath}')">＋ Блок внутрь</button></div>`;
      break;
    case "Repeater":
      body += `<div class="kv"><label>Имя массива</label><input type="text" value="${b.name||''}" onchange="setVal('${idxPath}','name',this.value)"></div>
               <div style="grid-column:1/-1"><small>Дочерние блоки (рендерятся для каждого элемента):</small><div id="children_${idxPath}"></div>
               <button onclick="addChild('${idxPath}')">＋ Блок внутрь</button></div>`;
      break;
    case "Table":
      body += `<div class="kv"><label>Имя массива</label><input type="text" value="${b.name||''}" onchange="setVal('${idxPath}','name',this.value)"></div>
               <div class="kv"><label>Заголовки</label><input type="text" value="${(b.headers||[]).join(',')}" onchange="setVal('${idxPath}','headers',this.value.split(',').map(s=>s.trim()).filter(Boolean))"></div>`;
      break;
    case "Separator":
      body += `<div class="kv"><label>Символ</label><input type="text" value="${b.char||'—'}" onchange="setVal('${idxPath}','char',this.value)"></div>
               <div class="kv"><label>Повторов</label><input type="text" value="${b.repeat||20}" onchange="setVal('${idxPath}','repeat',parseInt(this.value)||0)"></div>`;
      break;
    case "DateTime":
      body += `<div class="kv"><label>Формат</label><input type="text" value="${b.format||'%Y-%m-%d %H:%M'}" onchange="setVal('${idxPath}','format',this.value)"></div>`;
      break;
  }
  body += renderFlagInputs(b.flags||{}, idxPath) + "</div>";

  let inner = `<div class="block">${head}${body}</div>`;

  if (b.children){
    setTimeout(()=>{
      renderBlocksInto(`children_${idxPath}`, b.children, idxPath);
    }, 0);
  }
  return inner;
}

function renderBlocksInto(rootId, blocksArr, parentPath=""){
  const root = document.getElementById(rootId);
  // 1) рендерим HTML строкой
  root.innerHTML = blocksArr.map((b,i)=>blockCard(b,i,parentPath)).join("") || '<div class="muted">Пусто</div>';

  // 2) DOM-ом навешиваем иконку с title на заголовок каждого блока (надёжные тултипы)
  blocksArr.forEach((b,i)=>{
    const idxPath = parentPath ? `${parentPath}.${i}` : `${i}`;
    const titleEl = document.getElementById(`title_${idxPath}`);
    if (titleEl){
      const hint = (b.desc || '') + (b.flags ? ('\\n' + flagHint(b.flags)) : '');
      titleEl.appendChild(makeInfoIcon(hint));
    }
  });
}

function renderAll(){
  const tpl = state.tpl;

  // значения из state.tpl
  $id("tpl-name").value = tpl.name || "";
  $id("tpl-desc").value = tpl.description || "";

  // ДВУСТОРОННЯЯ СВЯЗКА (фикс "сбрасывается имя")
  $id("tpl-name").oninput = (e)=>{ state.tpl.name = e.target.value; };
  $id("tpl-desc").oninput = (e)=>{ state.tpl.description = e.target.value; };

  renderBlocksInto("blocks", tpl.blocks||[]);
}

const state = { list: [], tpl: {name:"Новый шаблон", description:"", version:1, blocks:[]} };

function createNew(){ currentId = null; state.tpl = {name:"Новый шаблон", description:"", version:1, blocks:[]}; renderAll(); }

async function loadTemplates(){
  const res = await fetch("list"); state.list = await res.json();
  const meta = await fetch("meta").then(r=>r.json()); $id("store-path").textContent = meta.path || "";
  const listEl = document.getElementById("tpl-list");
  listEl.innerHTML = state.list.map(t=>`<a href="#" onclick="loadOne(${t.id});return false;">${t.name}</a>`).join("") || '<span class="muted">Нет шаблонов</span>';
}

async function loadOne(id){
  const r = await fetch("get?id="+id); const tpl = await r.json();
  currentId = id; state.tpl = tpl; renderAll();
}

function addBlock(type){
  state.tpl.blocks = state.tpl.blocks || [];
  state.tpl.blocks.push(blockDefaults(type));
  renderAll();
}

function addChild(idxPath){
  const b = getByPath(idxPath);
  b.children = b.children || [];
  b.children.push(blockDefaults("StaticText"));
  renderAll();
}

function removeBlock(idxPath){
  const {arr,i} = getArrAndIndex(idxPath);
  arr.splice(i,1);
  renderAll();
}

function moveBlock(idxPath, dir){
  const {arr,i} = getArrAndIndex(idxPath);
  const j = i + dir; if (j<0 || j>=arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  renderAll();
}

function setVal(idxPath, key, val){
  const b = getByPath(idxPath); b[key]=val; renderAll();
}
function setFlag(idxPath, key, val){
  const b = getByPath(idxPath); b.flags = b.flags||{}; b.flags[key]=val;
}

// ФИКС: сохранение choices (и любых объектов) из textarea
function parseKeyValueOrJSON(raw) {
  try {
    const j = JSON.parse(raw);
    if (j && typeof j === 'object' && !Array.isArray(j)) return j;
  } catch (e) {}
  const out = {};
  for (let line of String(raw||'').split('\\n')) {
    const s = line.trim(); if (!s) continue;
    const eq = s.indexOf('=');
    if (eq === -1) continue;
    const k = s.slice(0, eq).trim();
    const v = s.slice(eq + 1).trim();
    if (k) out[k] = v;
  }
  return out;
}
function setJSON(idxPath, key, raw) {
  const b = getByPath(idxPath);
  b[key] = parseKeyValueOrJSON(raw);
  renderAll();
}

function getByPath(path){
  const parts = path.split(".").map(n=>parseInt(n,10));
  let arr = state.tpl.blocks, item=null;
  for (let i=0;i<parts.length;i++){
    item = arr[parts[i]];
    if (i<parts.length-1){ arr = item.children; }
  }
  return item;
}

function getArrAndIndex(path){
  const parts = path.split(".").map(n=>parseInt(n,10));
  let arr = state.tpl.blocks;
  for (let i=0;i<parts.length-1;i++) arr = arr[parts[i]].children;
  return {arr, i: parts[parts.length-1]};
}

async function saveTemplate(){
  state.tpl.name = $id("tpl-name").value.trim() || "Без имени";
  state.tpl.description = $id("tpl-desc").value.trim();
  let payload = {...state.tpl};
  if (currentId!==null) payload.id = currentId;
  await fetch("save", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
  await loadTemplates();
  if (currentId===null){ const last = state.list[state.list.length-1]; if (last) loadOne(last.id); }
}

async function deleteTemplate(){
  if (currentId===null) return;
  await fetch("delete", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({id: currentId})});
  currentId = null; await loadTemplates(); createNew();
}

loadTemplates(); createNew();
</script>
</body></html>
"""

@bp.route("/")
def index():
    return render_template_string(HTML)

@bp.route("/meta")
def meta():
    return jsonify({"path": get_path()})

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

@bp.route("/save", methods=["POST"])
def save_template():
    t = request.get_json(force=True)
    data = load_all()
    if "id" in t and isinstance(t["id"], int) and 0 <= t["id"] < len(data):
        data[t["id"]] = t
    else:
        t["id"] = len(data)
        data.append(t)
    save_all(data)
    return jsonify({"ok": True, "id": t["id"]})

@bp.route("/delete", methods=["POST"])
def delete_template():
    payload = request.get_json(force=True)
    idx = payload.get("id")
    data = load_all()
    if isinstance(idx, int) and 0 <= idx < len(data):
        del data[idx]
        save_all(data)
    return jsonify({"ok": True})

service = ServiceBase(
    id="reply-templates-editor",
    name="Редактор шаблонов",
    description="Визуальный редактор блоков (без JSON), хранение на диске",
    icon="🛠️",
    blueprint=bp,
)
