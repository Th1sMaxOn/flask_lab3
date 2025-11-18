# Лабораторна робота №3 — Flask + PostgreSQL + ORM  
## Тема: Валідація, обробка помилок та ORM у бекенд-застосунку

**Студент:** Пашко Максим, група ІО-32  
**Варіант:** №2 — *Користувацькі категорії витрат*  

Ця лабораторна робота **продовжує проєкт з Лабораторної роботи №2**.  
Зберігається структура ендпоінтів, але замість роботи “в пам’яті” тепер використовується:

- база даних **PostgreSQL** (у Docker-контейнері),
- **SQLAlchemy** як ORM,
- **Flask-Migrate** для міграцій,
- **Marshmallow** для валідації вхідних даних,
- єдина JSON-структура для помилок.

---

## Основний функціонал

### 1. Сутності

- **User**
  - `id: int`
  - `name: str` (унікальне ім’я)

- **Category**
  - `id: int`
  - `name: str`
  - `is_global: bool`
  - `user_id: int | null` — власник категорії або `null` для глобальних

- **Record**
  - `id: int`
  - `user_id: int`
  - `category_id: int`
  - `amount: float`
  - `created_at: datetime`

---

### 2. Логіка варіанту №2 — Користувацькі категорії витрат

- **Глобальні категорії**:
  - `is_global = true`
  - `user_id = null`
  - доступні всім користувачам

- **Користувацькі категорії**:
  - `is_global = false`
  - `user_id = <id користувача>`
  - бачить і може використовувати **тільки власник**

- При створенні запису витрати (`POST /record`):
  - якщо категорія **глобальна** → дозволено для будь-якого користувача
  - якщо категорія **користувацька** → дозволено **тільки користувачу-власнику**
  - інакше повертається помилка:
    ```json
    { "error": "forbidden_category" }
    ```

---

## Технології

- Python 3.11
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Marshmallow
- PostgreSQL (Docker)
- psycopg2-binary
- Postman (для тестування API)

---
## Скріншоти виконання роботи

[!Створення юзерів](./Screenshot_2025-11-18_111410.png)
## Структура проєкту

```text
flask_lab3/
  app.py
  config.py
  docker-compose.yaml
  requirements.txt
  migrations/
  README.md
  postman/
    Lab2 Expenses API.postman_collection.json
    env_local.postman_environment.json
    ...
