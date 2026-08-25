from functools import wraps
from flask import request, jsonify, g, redirect, url_for, render_template
from flask_jwt_extended import (
    jwt_required as flask_jwt_required,
    get_jwt_identity,
    get_jwt,
)
from models.user import User
from models.employee import Employee


def _load_g():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if user:
        g.user = user
        g.employee = Employee.query.filter_by(user_id=user.id).first()
        g.jwt_payload = get_jwt()


def jwt_required(view_or_optional_arg=None, **kwargs):
    if view_or_optional_arg is None or not callable(view_or_optional_arg):

        def decorator(view):
            @wraps(view)
            @flask_jwt_required(**kwargs)
            def wrapper(*args, **kwargs2):
                _load_g()
                return view(*args, **kwargs2)

            return wrapper

        return decorator
    else:
        view = view_or_optional_arg

        @wraps(view)
        @flask_jwt_required()
        def wrapper(*args, **kwargs2):
            _load_g()
            return view(*args, **kwargs2)

        return wrapper


def jwt_role_required(*roles):
    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapper(*args, **kwargs):
            if g.user.role not in roles:
                if "text/html" in request.headers.get("Accept", ""):
                    return (
                        render_template(
                            "error.html",
                            code=403,
                            message="You do not have permission to do that.",
                        ),
                        403,
                    )
                return jsonify(error="Forbidden for this role."), 403
            return view(*args, **kwargs)

        return wrapper

    return decorator
