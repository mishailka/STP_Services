from flask import Flask, render_template, jsonify
import importlib
import pkgutil
from services.base import ServiceBase
import pathlib
import os


def create_app():
    app = Flask(
        __name__,
        template_folder=str(pathlib.Path(__file__).parent / "templates"),
        static_folder=str(pathlib.Path(__file__).parent / "static"),
    )
    app.config["JSON_AS_ASCII"] = False

    # ✅ секрет для cookie-сессий
    app.secret_key = os.environ.get("SECRET_KEY", "devkey-change-me")

    # 🔓 Снимаем/поднимаем лимиты Flask/Werkzeug, которые дают 413
    # Если хочешь полностью отключить — закомментируй MAX_CONTENT_LENGTH
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 ГБ на тело запроса
    app.config["MAX_FORM_MEMORY_SIZE"] = 512 * 1024 * 1024      # 512 МБ на «нефайловые» поля (textarea)
    app.config["MAX_FORM_PARTS"] = 200000                       # много частей формы (если понадобится)


    # Динамический поиск сервисов
    services = []
    services_path = pathlib.Path(__file__).parent / "services"
    for finder, name, ispkg in pkgutil.iter_modules([str(services_path)]):
        if name in ("base", "__pycache__"):
            continue
        module = importlib.import_module(f"services.{name}")
        svc = getattr(module, "service", None)
        if isinstance(svc, ServiceBase):
            services.append(svc)
            if svc.blueprint is not None:
                app.register_blueprint(svc.blueprint, url_prefix=f"/services/{svc.id}")

    services.sort(key=lambda s: s.name.lower())
    app.extensions["services"] = services

    # === ГЛАВНАЯ СТРАНИЦА ===
    @app.route("/")
    def index():
        tiles = [{
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "icon": s.icon,
            "path": f"/services/{s.id}" if s.blueprint else None
        } for s in services]
        return render_template("index.html", tiles=tiles)

    # Опционально: JSON-список сервисов
    @app.route("/api/services")
    def api_services():
        return jsonify([{
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "icon": s.icon,
        } for s in services])


    return app

    # Не обязательно, но удобно: дружелюбная страница на 413
    from werkzeug.exceptions import RequestEntityTooLarge
    @app.errorhandler(RequestEntityTooLarge)
    def handle_413(e):
        # Можно вернуть свой шаблон или редирект на нужный сервис
        return render_template(
            "index.html",
            tiles=[{
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "icon": s.icon,
                "path": f"/services/{s.id}" if s.blueprint else None
            } for s in app.extensions["services"]],
            # Положи на страницу заметный баннер/алерт, если в шаблоне предусмотрено
        ), 413

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
