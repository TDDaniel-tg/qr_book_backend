# Dockerfile для backend
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости для PostgreSQL и pillow
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Создаем директорию для QR кодов
RUN mkdir -p app/static/qr && chmod -R 755 app/static

# Устанавливаем переменную окружения для Flask
ENV FLASK_APP=app

# Копируем скрипт запуска
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Открываем порт
EXPOSE 8080

# Запускаем приложение через start.sh (включает миграции и seed)
CMD ["/app/start.sh"]

