import os
from datetime import datetime
from typing import Any, Dict, cast

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from passlib.hash import pbkdf2_sha256
from marshmallow import Schema, fields, validates, ValidationError
from marshmallow.validate import Length, Range

# -------------------------
# INIT ORM
# -------------------------

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


# -------------------------
# ORM MODELS
# -------------------------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # keep "name" column to avoid breaking Lab3 DB; treat it as username
    name = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    categories = db.relationship(
        "Category",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    records = db.relationship(
        "Record",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )


class Category(db.Model):
    """
    VARIANT 2 — user-specific categories.
    Global category:
        is_global = True
        user_id = NULL
    User category:
        is_global = False
        user_id = <id>
    """
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    is_global = db.Column(db.Boolean, nullable=False, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    user = db.relationship("User", back_populates="categories")
    records = db.relationship("Record", back_populates="category", lazy=True)


class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)

    user = db.relationship("User", back_populates="records")
    category = db.relationship("Category", back_populates="records")


# -------------------------
# SCHEMAS
# -------------------------

class RegisterSchema(Schema):
    name = fields.Str(required=True, validate=Length(min=1, max=120))
    password = fields.Str(required=True, validate=Length(min=6, max=128))

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value.strip():
            raise ValidationError("Name must not be empty.")


class LoginSchema(Schema):
    name = fields.Str(required=True, validate=Length(min=1, max=120))
    password = fields.Str(required=True, validate=Length(min=1, max=128))


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=1, max=120))


class CategorySchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=1, max=120))
    is_global = fields.Bool(required=True)
    user_id = fields.Int(allow_none=True)


class CategoryCreateSchema(Schema):
    name = fields.Str(required=True, validate=Length(min=1, max=120))
    is_global = fields.Bool(required=True)


class RecordSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    category_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    amount = fields.Float(required=True, validate=Range(min=0.0))


class RecordQuerySchema(Schema):
    category_id = fields.Int(required=False)


register_schema = RegisterSchema()
login_schema = LoginSchema()

user_schema = UserSchema()
users_schema = UserSchema(many=True)

category_schema = CategorySchema()
categories_schema = CategorySchema(many=True)
category_create_schema = CategoryCreateSchema()

record_schema = RecordSchema()
records_schema = RecordSchema(many=True)
record_query_schema = RecordQuerySchema()


# -------------------------------------------------------------
# ERROR HELPERS
# -------------------------------------------------------------

def make_error(message: str, status_code: int = 400, extra=None):
    payload = {"error": message}
    if extra:
        payload.update(extra)
    r = jsonify(payload)
    r.status_code = status_code
    return r


def register_error_handlers(app: Flask):
    @app.errorhandler(ValidationError)
    def handle_validation(err: ValidationError):
        return make_error("validation_error", 400, extra={"details": err.messages})

    @app.errorhandler(404)
    def handle_404(err):
        return make_error("not_found", 404, extra={"details": str(err)})

    @app.errorhandler(Exception)
    def handle_exception(err):
        return make_error("internal_error", 500, extra={"details": str(err)})


# -------------------------------------------------------------
# JWT ERROR HANDLERS
# -------------------------------------------------------------

def register_jwt_handlers(_jwt: JWTManager):
    @_jwt.unauthorized_loader
    def missing_token(err: str):
        return make_error("missing_token", 401, extra={"details": err})

    @_jwt.invalid_token_loader
    def invalid_token(err: str):
        return make_error("invalid_token", 401, extra={"details": err})

    @_jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return make_error("expired_token", 401)

    @_jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return make_error("revoked_token", 401)


# -------------------------------------------------------------
# APPLICATION FACTORY
# -------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)

    # Database: prefer env in Docker; fallback for local
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/expenses_db"
        )
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("JSON_SORT_KEYS", False)

    # JWT
    app.config.setdefault("JWT_SECRET_KEY", os.environ.get("JWT_SECRET_KEY", "change-me"))
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", "3600")))

    # load config.py if present (should not overwrite DATABASE_URL / JWT_SECRET_KEY ideally)
    app.config.from_pyfile("config.py", silent=True)

    db.init_app(app)
    migrate.init_app(app, db)

    jwt.init_app(app)
    register_jwt_handlers(jwt)

    register_error_handlers(app)
    register_routes(app)

    return app


# -------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------

def register_routes(app: Flask):

    # ----------- PUBLIC ----------
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    def index():
        return jsonify({
            "project": "Lab4 Expenses API (JWT)",
            "variant": 2,
            "auth": {"register": "/auth/register", "login": "/auth/login"}
        })

    # ----------- AUTH (PUBLIC) -----------

    @app.post("/auth/register")
    def auth_register():
        data = cast(Dict[str, Any], register_schema.load(request.get_json() or {}))
        name = data["name"].strip()
        password = data["password"]

        if User.query.filter_by(name=name).first():
            raise ValidationError({"name": ["User with this name already exists"]})

        user = User(name=name, password_hash=pbkdf2_sha256.hash(password))
        db.session.add(user)
        db.session.commit()

        r = jsonify({"id": user.id, "name": user.name})
        r.status_code = 201
        return r

    @app.post("/auth/login")
    def auth_login():
        data = cast(Dict[str, Any], login_schema.load(request.get_json() or {}))
        name = data["name"].strip()
        password = data["password"]

        user = User.query.filter_by(name=name).first()
        if not user or not pbkdf2_sha256.verify(password, user.password_hash):
            return make_error("invalid_credentials", 401)

        access_token = create_access_token(identity=str(user.id))
        return jsonify({"access_token": access_token, "user": {"id": user.id, "name": user.name}})

    # ----------- PROTECTED ----------
    # Everything below requires JWT

    @app.get("/me")
    @jwt_required()
    def me():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user:
            return make_error("user_not_found", 404)
        return jsonify(user_schema.dump(user))

    # Optional: list users (protected)
    @app.get("/users")
    @jwt_required()
    def list_users():
        users = User.query.order_by(User.id).all()
        return jsonify({"items": users_schema.dump(users), "total": len(users)})

    # ----------- CATEGORIES (VARIANT 2) -----------

    @app.get("/category")
    @jwt_required()
    def list_categories():
        user_id = int(get_jwt_identity())
        categories = (
            Category.query.filter(
                db.or_(Category.is_global.is_(True), Category.user_id == user_id)
            )
            .order_by(Category.id)
            .all()
        )
        return jsonify({"items": categories_schema.dump(categories), "total": len(categories)})

    @app.post("/category")
    @jwt_required()
    def create_category():
        user_id = int(get_jwt_identity())
        data = cast(Dict[str, Any], category_create_schema.load(request.get_json() or {}))

        is_global = bool(data["is_global"])
        if is_global:
            category = Category(name=data["name"], is_global=True, user_id=None)
        else:
            category = Category(name=data["name"], is_global=False, user_id=user_id)

        db.session.add(category)
        db.session.commit()

        r = jsonify(category_schema.dump(category))
        r.status_code = 201
        return r

    @app.delete("/category/<int:category_id>")
    @jwt_required()
    def delete_category(category_id: int):
        user_id = int(get_jwt_identity())

        cat = Category.query.get(category_id)
        if not cat:
            return make_error("category_not_found", 404)

        if not cat.is_global and cat.user_id != user_id:
            return make_error("forbidden_category", 403)

        db.session.delete(cat)
        db.session.commit()
        return jsonify({"deleted": True, "category_id": category_id})

    # keep Lab3 alias too (protected)
    @app.delete("/category")
    @jwt_required()
    def delete_category_by_query():
        category_id = request.args.get("id", type=int)
        if not category_id:
            return make_error("missing_category_id", 400)
        return delete_category(category_id)

    # ----------- RECORDS -----------

    @app.post("/record")
    @jwt_required()
    def create_record():
        user_id = int(get_jwt_identity())
        data = cast(Dict[str, Any], record_schema.load(request.get_json() or {}))

        category = Category.query.get(data["category_id"])
        if not category:
            return make_error("category_not_found", 404)

        if not category.is_global and category.user_id != user_id:
            return make_error("forbidden_category", 403)

        record = Record(
            user_id=user_id,
            category_id=category.id,
            amount=float(data["amount"])
        )
        db.session.add(record)
        db.session.commit()

        r = jsonify(record_schema.dump(record))
        r.status_code = 201
        return r

    @app.get("/record")
    @jwt_required()
    def list_records():
        user_id = int(get_jwt_identity())
        args = cast(Dict[str, Any], record_query_schema.load(request.args))
        category_id = args.get("category_id")

        query = Record.query.filter_by(user_id=user_id)
        if category_id is not None:
            query = query.filter_by(category_id=category_id)

        records = query.order_by(Record.id).all()
        return jsonify({"items": records_schema.dump(records), "total": len(records)})

    @app.get("/record/<int:record_id>")
    @jwt_required()
    def get_record(record_id: int):
        user_id = int(get_jwt_identity())
        record = Record.query.get(record_id)
        if not record:
            return make_error("record_not_found", 404)
        if record.user_id != user_id:
            return make_error("forbidden_record", 403)
        return jsonify(record_schema.dump(record))

    @app.delete("/record/<int:record_id>")
    @jwt_required()
    def delete_record(record_id: int):
        user_id = int(get_jwt_identity())
        record = Record.query.get(record_id)
        if not record:
            return make_error("record_not_found", 404)
        if record.user_id != user_id:
            return make_error("forbidden_record", 403)
        db.session.delete(record)
        db.session.commit()
        return jsonify({"deleted": True, "record_id": record_id})


# -------------------------------------------------------------
# APP INSTANCE
# -------------------------------------------------------------

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
