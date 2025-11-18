import os
from datetime import datetime

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from marshmallow import Schema, fields, validates, ValidationError
from marshmallow.validate import Length, Range

# -------------------------
# INIT ORM
# -------------------------

db = SQLAlchemy()
migrate = Migrate()


# -------------------------
# ORM MODELS
# -------------------------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

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

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=1, max=120))

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value.strip():
            raise ValidationError("Name must not be empty.")



class CategorySchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=1, max=120))
    is_global = fields.Bool(required=True)
    user_id = fields.Int(allow_none=True)


class CategoryQuerySchema(Schema):
    user_id = fields.Int(required=False, allow_none=True)


class RecordSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(required=True)
    category_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    amount = fields.Float(required=True, validate=Range(min=0.0))


class RecordQuerySchema(Schema):
    user_id = fields.Int(required=False)
    category_id = fields.Int(required=False)


# Instantiate schemas
user_schema = UserSchema()
users_schema = UserSchema(many=True)

category_schema = CategorySchema()
categories_schema = CategorySchema(many=True)

record_schema = RecordSchema()
records_schema = RecordSchema(many=True)

record_query_schema = RecordQuerySchema()
category_query_schema = CategoryQuerySchema()


# -------------------------------------------------------------
# ERROR HANDLERS
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
# APPLICATION FACTORY
# -------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)

    # Base config
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/expenses_db"
        )
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("JSON_SORT_KEYS", False)

    # load config.py if present
    app.config.from_pyfile("config.py", silent=True)

    db.init_app(app)
    migrate.init_app(app, db)

    register_error_handlers(app)
    register_routes(app)

    return app


# -------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------

def register_routes(app: Flask):

    # ----------- HEALTH ----------
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return {
            "project": "Lab3 Expenses API",
            "variant": 2,
            "note": "This is an extended version of Lab2 with ORM, DB, Validation.",
            "try": ["/users", "/category", "/record?user_id=1"]
        }

    # ----------- USERS -----------

    @app.post("/users")
    def create_user():
        data = user_schema.load(request.get_json() or {})

        # unique name check
        if User.query.filter_by(name=data["name"]).first():
            raise ValidationError({"name": ["User with this name already exists"]})

        user = User(name=data["name"])
        db.session.add(user)
        db.session.commit()
        return user_schema.dump(user), 201

    @app.get("/users")
    def list_users():
        users = User.query.order_by(User.id).all()
        return {"items": users_schema.dump(users), "total": len(users)}

    @app.get("/user/<int:user_id>")
    def get_user(user_id):
        user = User.query.get(user_id)
        if not user:
            return make_error("user_not_found", 404)
        return user_schema.dump(user)

    @app.delete("/user/<int:user_id>")
    def delete_user(user_id):
        user = User.query.get(user_id)
        if not user:
            return make_error("user_not_found", 404)
        db.session.delete(user)
        db.session.commit()
        return {"deleted": True, "user_id": user_id}

    # ----------- CATEGORIES (VARIANT 2) -----------

    @app.get("/category")
    def list_categories():
        args = category_query_schema.load(request.args)
        user_id = args.get("user_id")

        query = Category.query

        if user_id is not None:
            # all global OR user’s own categories
            query = query.filter(
                db.or_(
                    Category.is_global.is_(True),
                    Category.user_id == user_id
                )
            )

        categories = query.order_by(Category.id).all()
        return {"items": categories_schema.dump(categories), "total": len(categories)}

    @app.post("/category")
    def create_category():
        data = category_schema.load(request.get_json() or {})

        is_global = data["is_global"]
        user_id = data.get("user_id")

        if is_global and user_id is not None:
            raise ValidationError({"user_id": ["Global category must not have user_id"]})

        if not is_global:
            if user_id is None:
                raise ValidationError({"user_id": ["User-specific category requires user_id"]})
            if not User.query.get(user_id):
                return make_error("user_not_found", 404)

        category = Category(
            name=data["name"],
            is_global=is_global,
            user_id=None if is_global else user_id
        )
        db.session.add(category)
        db.session.commit()

        return category_schema.dump(category), 201

    @app.delete("/category/<int:category_id>")
    def delete_category(category_id):
        cat = Category.query.get(category_id)
        if not cat:
            return make_error("category_not_found", 404)
        db.session.delete(cat)
        db.session.commit()
        return {"deleted": True, "category_id": category_id}

    # ----------- RECORDS -----------

    @app.post("/record")
    def create_record():
        data = record_schema.load(request.get_json() or {})

        user = User.query.get(data["user_id"])
        if not user:
            return make_error("user_not_found", 404)

        category = Category.query.get(data["category_id"])
        if not category:
            return make_error("category_not_found", 404)

        # Variant 2 rule: only owner may use user-specific category
        if not category.is_global and category.user_id != user.id:
            return make_error("forbidden_category", 400)

        record = Record(
            user=user,
            category=category,
            amount=data["amount"]
        )
        db.session.add(record)
        db.session.commit()

        return record_schema.dump(record), 201

    @app.get("/record")
    def list_records():
        args = record_query_schema.load(request.args)

        user_id = args.get("user_id")
        category_id = args.get("category_id")

        if user_id is None and category_id is None:
            return make_error("need_user_id_or_category_id", 400)

        query = Record.query

        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        if category_id is not None:
            query = query.filter_by(category_id=category_id)

        records = query.order_by(Record.id).all()
        return {"items": records_schema.dump(records), "total": len(records)}


# -------------------------------------------------------------
# APP INSTANCE
# -------------------------------------------------------------

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
