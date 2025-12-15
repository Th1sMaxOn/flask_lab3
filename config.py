import os

raw = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/expenses_db",
)

if raw.startswith("postgres://"):
    raw = raw.replace("postgres://", "postgresql+psycopg://", 1)

if raw.startswith("postgresql://") and "+psycopg" not in raw:
    raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)

SQLALCHEMY_DATABASE_URI = raw
SQLALCHEMY_TRACK_MODIFICATIONS = False
JSON_SORT_KEYS = False

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600"))
