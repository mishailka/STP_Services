# from __future__ import annotations
# from flask import Blueprint, request, jsonify, render_template_string
# from .base import ServiceBase
# import json, requests
#
# bp = Blueprint("request_sender", __name__, template_folder="../templates")
#
# HTML = """
# <!doctype html>
# <meta charset="utf-8">
# <title>Отправка запроса</title>
# <link rel="stylesheet" href="/static/style.css">
# <div class="container">
#   <h2>Отправка HTTP-запроса</h2>
#   <p class="muted">Укажи URL и JSON-тело. Ответ вернётся ниже.</p>
#   <form id="reqForm">
#     <input type="url" name="url" placeholder="https://example.com/api" required style="width:100%">
#     <textarea name="payload" rows="10" placeholder='{"ping":"pong"}'></textarea>
#     <button type="submit">Отправить</button>
#   </form>
#   <pre id="out" class="pre"></pre>
# </div>
# <script>
# document.getElementById('reqForm').addEventListener('submit', async (e) => {
#   e.preventDefault();
#   const fd = new FormData(e.target);
#   const url = fd.get('url');
#   let body = fd.get('payload') || "{}";
#   try { body = JSON.parse(body); } catch(e){ alert("Некорректный JSON"); return; }
#   const res = await fetch('send', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, body}) });
#   const data = await res.json();
#   document.getElementById('out').textContent = JSON.stringify(data, null, 2);
# });
# </script>
# """
#
# @bp.route("/", methods=["GET"])
# def page():
#     return render_template_string(HTML)
#
# @bp.route("/send", methods=["POST"])
# def send():
#     data = request.get_json(silent=True) or {}
#     url = data.get("url")
#     body = data.get("body") or {}
#     if not url:
#         return jsonify({"error": "URL обязателен"}), 400
#     try:
#         r = requests.post(url, json=body, timeout=15)
#         return jsonify({
#             "status": r.status_code,
#             "headers": dict(r.headers),
#             "text": r.text[:2000]  # ограничим вывод
#         })
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
#
# service = ServiceBase(
#     id="request-sender",
#     name="HTTP-запрос",
#     description="Отправляет POST-запрос с JSON и показывает ответ.",
#     icon="📡",
#     blueprint=bp
# )
