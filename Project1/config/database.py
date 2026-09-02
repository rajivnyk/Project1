import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy

load_dotenv()
db = SQLAlchemy()


def init_db(app):
    db_url = os.getenv("MYSQL_DB_URL")
    if db_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        user = os.getenv("DB_USER", "root")
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME", "travel_2")
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
        )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    from datetime import timedelta

    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-flask-secret")
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        days=int(os.getenv("JWT_ACCESS_DAYS", 7))
    )
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(
        days=int(os.getenv("JWT_REFRESH_DAYS", 7))
    )
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_SESSION_COOKIE"] = False
    app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token"
    app.config["JWT_REFRESH_COOKIE_NAME"] = "refresh_token"
    from flask_jwt_extended import JWTManager

    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        from flask import request, redirect, url_for, jsonify

        if "text/html" in request.headers.get("Accept", ""):
            return redirect(url_for("auth.login_page"))
        return jsonify({"error": "Missing token."}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        from flask import request, redirect, url_for, jsonify

        if "text/html" in request.headers.get("Accept", ""):
            return redirect(url_for("auth.login_page"))
        return jsonify({"error": "Token expired."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        from flask import request, redirect, url_for, jsonify

        if "text/html" in request.headers.get("Accept", ""):
            return redirect(url_for("auth.login_page"))
        return jsonify({"error": "Invalid token."}), 401

    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads/receipts")
    app.config["ALLOWED_EXTENSIONS"] = {"pdf", "png", "jpg", "jpeg"}
    app.config["MAX_CONTENT_LENGTH"] = (
        int(os.getenv("MAX_CONTENT_LENGTH_MB", 5)) * 1024 * 1024
    )
    db.init_app(app)
