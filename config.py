import os

SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/expenses_db",
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
JSON_SORT_KEYS = False

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600"))
