# from __future__ import annotations
# from flask import Blueprint, request, jsonify, render_template_string
# from .base import ServiceBase
#
# bp = Blueprint("file_compare", __name__, template_folder="../templates")
#
# HTML = """
# <!doctype html>
# <meta charset="utf-8">
# <title>Сравнение файлов</title>
# <link rel="stylesheet" href="/static/style.css">
# <div class="container">
#   <h2>Сравнение файлов</h2>
#   <p class="muted">Загрузите два файла для сравнения. Возвращается отчёт о различиях по строкам.</p>
#   <form id="cmpForm">
#     <input type="file" name="a" required>
#     <input type="file" name="b" required>
#     <button type="submit">Сравнить</button>
#   </form>
#   <pre id="out" class="pre"></pre>
# </div>
# <script>
# document.getElementById('cmpForm').addEventListener('submit', async (e) => {
#   e.preventDefault();
#   const fd = new FormData(e.target);
#   const res = await fetch('diff', { method:'POST', body: fd });
#   const data = await res.json();
#   document.getElementById('out').textContent = data.report || data.error;
# });
# </script>
# """
#
# @bp.route("/", methods=["GET"])
# def page():
#     return render_template_string(HTML)
#
# @bp.route("/diff", methods=["POST"])
# def diff():
#     a = request.files.get("a")
#     b = request.files.get("b")
#     if not a or not b:
#         return jsonify({"error": "Нужно выбрать оба файла"}), 400
#     a_lines = a.read().decode("utf-8", "ignore").splitlines()
#     b_lines = b.read().decode("utf-8", "ignore").splitlines()
#     report = []
#     max_len = max(len(a_lines), len(b_lines))
#     for i in range(max_len):
#         la = a_lines[i] if i < len(a_lines) else ""
#         lb = b_lines[i] if i < len(b_lines) else ""
#         if la != lb:
#             report.append(f"Строка {i+1}: A={la!r} | B={lb!r}")
#     if not report:
#         report.append("Файлы идентичны ✅")
#     return jsonify({"report": "\n".join(report)})
#
# service = ServiceBase(
#     id="file-compare",
#     name="Сравнение файлов",
#     description="Сравнивает два загруженных файла и показывает отличия по строкам.",
#     icon="📄",
#     blueprint=bp
# )
