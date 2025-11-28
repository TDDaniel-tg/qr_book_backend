# QRBOOK Backend

Backend для системы бронирования комнат с QR-кодами.

## 🚀 Деплой на Railway

```bash
# 1. Генерируем ключи
python3 generate_secrets.py

# 2. Следуем инструкции
```

📖 **Полная инструкция**: [RAILWAY_DEPLOY.md](RAILWAY_DEPLOY.md)

## 🛠 Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка БД
flask --app app db upgrade

# Заполнение тестовыми данными
python seed.py

# Запуск
flask --app app run
```

## 📦 Технологии

- Flask 3.0
- PostgreSQL (psycopg3)
- SQLAlchemy
- JWT Authentication
- Gunicorn
- QR Code Generation

## 📂 Структура

```
backend/
├── app/
│   ├── routes/          # API endpoints
│   ├── services/        # Business logic
│   ├── models.py        # Database models
│   └── config.py        # Configuration
├── migrations/          # Database migrations
├── Dockerfile           # Docker configuration
├── start.sh            # Production startup script
└── requirements.txt    # Python dependencies
```

## 🔑 API Endpoints

- `GET /health` - Health check
- `POST /api/auth/login` - Авторизация
- `POST /api/auth/logout` - Выход
- `GET /api/rooms` - Список комнат
- `POST /api/rooms` - Создание комнаты
- `GET /api/reservations` - Бронирования
- `POST /api/reservations` - Создать бронь

## 👥 Тестовые пользователи (после seed)

| Username | Password | Role |
|----------|----------|------|
| admin | admin1234 | admin |
| teacher | teacher1234 | teacher |
| student | student1234 | student |

## 📝 Лицензия

Проект для учебных целей.

