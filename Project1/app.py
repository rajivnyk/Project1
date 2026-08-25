import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, g, render_template, redirect, url_for
from config.database import db, init_db
import models
from controller.auth_controller import auth_bp
from controller.employee_controller import employee_bp
from controller.travel_controller import travel_bp
from controller.expense_controller import expense_bp
from controller.manager_controller import manager_bp
from controller.finance_controller import finance_bp
from controller.admin_controller import admin_bp
from controller.report_controller import report_bp
from controller.analytics_controller import analytics_bp, api_bp as analytics_api_bp

app = Flask(__name__)
init_db(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("logs", exist_ok=True)
handler = RotatingFileHandler(
    "logs/app.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)-8s [%(module)s:%(lineno)d] %(message)s")
)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG if os.getenv("FLASK_DEBUG") == "1" else logging.INFO)
for bp in (
    auth_bp,
    employee_bp,
    travel_bp,
    expense_bp,
    manager_bp,
    finance_bp,
    admin_bp,
    report_bp,
    analytics_bp,
    analytics_api_bp,
):
    app.register_blueprint(bp)


@app.context_processor
def inject_user():
    return {"current_user": g.get("user"), "current_employee": g.get("employee")}


@app.errorhandler(401)
def unauthorized(e):
    return render_template("error.html", code=401, message="Please log in."), 401


@app.errorhandler(403)
def forbidden(e):
    return (
        render_template(
            "error.html", code=403, message="You do not have permission to do that."
        ),
        403,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    app.logger.exception("Unhandled error")
    return (
        render_template(
            "error.html", code=500, message="Something went wrong. It has been logged."
        ),
        500,
    )


@app.route("/")
def root():
    return redirect(url_for("auth.login_page"))


from jinja2 import StrictUndefined

app.jinja_env.undefined = StrictUndefined
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("Tables:", ", ".join(sorted(db.metadata.tables)))
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="127.0.0.1", port=5000)
