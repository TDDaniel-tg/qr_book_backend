#!/bin/bash
# Скрипт запуска backend для Railway с автоматическими миграциями

set -e  # Выход при ошибке

echo "🚀 Starting QRBOOK Backend..."

# Проверка подключения к базе данных
echo "📊 Checking database connection..."
python -c "from app import create_app; app = create_app(); print('✅ Database connected')" || exit 1

# Применение миграций
echo "🔄 Running database migrations..."
flask --app app db upgrade

# Проверка наличия данных в базе
echo "🔍 Checking if database is seeded..."
SEED_CHECK=$(python -c "
from app import create_app
from app.models import User
app = create_app()
with app.app_context():
    print(User.query.count())
")

if [ "$SEED_CHECK" = "0" ]; then
    echo "🌱 Seeding database with initial data..."
    python seed.py
else
    echo "✅ Database already seeded (found $SEED_CHECK users)"
fi

# Запуск приложения
echo "🎯 Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:${PORT:-8080} \
    --workers ${WORKERS:-4} \
    --timeout ${TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "app:create_app()"

