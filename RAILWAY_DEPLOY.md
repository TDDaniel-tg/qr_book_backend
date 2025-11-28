# 🚂 Деплой QRBOOK Backend на Railway

## 🚀 Быстрый старт (5 минут)

### 1. Генерируем секретные ключи
```bash
python3 generate_secrets.py
# Сохраните полученные ключи - понадобятся в шаге 3
```

### 2. Railway Setup
1. Перейдите на [railway.app](https://railway.app) и войдите через GitHub
2. Нажмите **"New Project"** → **"Deploy from GitHub repo"**
3. Выберите ваш репозиторий
4. Нажмите **"+ New"** → **"Database"** → **"Add PostgreSQL"**

### 3. Добавьте минимальные переменные окружения

В разделе **Settings → Variables**:

```bash
SECRET_KEY=<ваш-ключ-из-generate_secrets>
JWT_SECRET_KEY=<ваш-jwt-ключ-из-generate_secrets>
DATABASE_URL=${{Postgres.DATABASE_URL}}
STATIC_QR_PATH=/app/app/static/qr
JWT_COOKIE_SECURE=true
JWT_CSRF_CHECK_FORM=true
FLASK_ENV=production
FLASK_DEBUG=0
PORT=8080
```

### 4. Дождитесь деплоя (~3-5 минут)

### 5. Обновите URL переменные

После получения Railway URL добавьте:
```bash
QR_BASE_URL=https://ваш-backend-url/static/qr
SERVER_EXTERNAL_BASE=https://ваш-backend-url/
CORS_ORIGINS=https://ваш-frontend-url
FRONTEND_BASE_URL=https://ваш-frontend-url
```

### 6. Проверка
```bash
curl https://ваш-backend-url/health
# Ответ: {"status": "healthy", "database": "connected", ...}
```

---

## 📋 Детальная инструкция

### Подготовка проекта

Проект уже содержит необходимые файлы для Railway:
- ✅ `Dockerfile` - контейнеризация
- ✅ `railway.toml` - конфигурация
- ✅ `start.sh` - скрипт запуска с миграциями
- ✅ `requirements.txt` - зависимости
- ✅ `generate_secrets.py` - генератор ключей

### Автоматические процессы при деплое

Скрипт `start.sh` выполняет:
1. ✅ Проверку подключения к БД
2. ✅ Применение миграций (`flask db upgrade`)
3. ✅ Заполнение начальными данными если БД пустая (`seed.py`)
4. ✅ Запуск Gunicorn сервера

### Все переменные окружения

#### Обязательные:
```bash
SECRET_KEY=<random-32-chars>           # Из generate_secrets.py
JWT_SECRET_KEY=<random-32-chars>       # Из generate_secrets.py
DATABASE_URL=${{Postgres.DATABASE_URL}} # Автоматически от Railway
STATIC_QR_PATH=/app/app/static/qr
JWT_COOKIE_SECURE=true
JWT_CSRF_CHECK_FORM=true
FLASK_ENV=production
FLASK_DEBUG=0
PORT=8080
```

#### После получения URL:
```bash
QR_BASE_URL=https://ваш-backend.up.railway.app/static/qr
SERVER_EXTERNAL_BASE=https://ваш-backend.up.railway.app/
CORS_ORIGINS=https://ваш-frontend.up.railway.app
FRONTEND_BASE_URL=https://ваш-frontend.up.railway.app
```

#### Опциональные (настройка производительности):
```bash
WORKERS=4                              # Количество Gunicorn workers
TIMEOUT=120                            # Таймаут запросов в секундах
RATELIMIT_STORAGE_URI=memory://
RATELIMIT_DEFAULTS=6000 per hour;100000 per day
```

### Тестовые пользователи (создаются автоматически)

| Username | Password | Role |
|----------|----------|------|
| admin | admin1234 | admin |
| teacher | teacher1234 | teacher |
| student | student1234 | student |
| guest | guest1234 | student |

⚠️ **ВАЖНО**: Измените пароли в production!

### Настройка домена

1. В настройках сервиса: **Settings** → **Networking**
2. Railway предоставит: `backend-production-xxxx.up.railway.app`
3. Свой домен: **Custom Domain** → добавить

---

## 🔧 Troubleshooting

### База данных не подключается
```bash
# Проверьте:
# 1. PostgreSQL сервис запущен в Railway
# 2. Переменная DATABASE_URL=${{Postgres.DATABASE_URL}}
# 3. Логи PostgreSQL в Railway Dashboard
```

### Миграции не применяются
```bash
# Проверьте:
# 1. Директория migrations/ в git
# 2. Логи деплоя: Railway → Deployments → View Logs
# 3. DATABASE_URL корректен
```

### QR коды не работают
```bash
# Проверьте переменные:
STATIC_QR_PATH=/app/app/static/qr
QR_BASE_URL=https://ваш-backend-url/static/qr
```

### CORS ошибки
```bash
# Убедитесь что CORS_ORIGINS содержит URL фронтенда
CORS_ORIGINS=https://точный-url-frontend
# БЕЗ trailing slash!
```

### 500 Internal Server Error
```bash
# 1. Проверьте логи: Railway → Deployments → View Logs
# 2. Убедитесь что все обязательные переменные установлены
# 3. Проверьте что база данных подключена
```

---

## 📊 Мониторинг

- **Логи**: Railway Dashboard → Deployments → View Logs
- **Метрики**: Railway Dashboard → Metrics (CPU, Memory, Network)
- **Healthcheck**: Автоматически проверяет `/health` каждые 5 минут
- **Статус**: Зелёный кружок = всё работает

---

## 🛠 Railway CLI (опционально)

```bash
# Установка
npm i -g @railway/cli

# Авторизация
railway login

# Связать с проектом
railway link

# Просмотр логов
railway logs

# Выполнить команду
railway run python seed.py

# Открыть в браузере
railway open
```

---

## 🔒 Безопасность

- ✅ Генерируйте случайные ключи: `python3 generate_secrets.py`
- ✅ Измените дефолтные пароли после деплоя
- ✅ Ограничьте CORS только доверенными доменами
- ✅ Используйте `JWT_COOKIE_SECURE=true` в production
- ✅ Не коммитьте `.env` файлы в git
- ✅ Регулярно обновляйте зависимости: `pip list --outdated`

---

## ⚡ Масштабирование

Railway автоматически масштабирует. Для ручной настройки:

1. **Settings** → **Resources**
2. Настройте CPU и RAM
3. Измените `WORKERS` для большего количества Gunicorn workers

Рекомендации:
- 1 GB RAM → `WORKERS=2`
- 2 GB RAM → `WORKERS=4`
- 4 GB RAM → `WORKERS=8`

---

## ✅ Чеклист деплоя

### Перед деплоем
- [ ] Все изменения в git
- [ ] Проект на GitHub
- [ ] Сгенерированы секретные ключи

### Railway Setup
- [ ] Создан проект на railway.app
- [ ] Подключен GitHub репозиторий
- [ ] Добавлен PostgreSQL
- [ ] Добавлены обязательные переменные

### После первого деплоя
- [ ] Получен Railway URL
- [ ] Обновлены URL переменные
- [ ] `/health` возвращает 200 OK
- [ ] Протестирована авторизация
- [ ] Изменены дефолтные пароли

### Безопасность
- [ ] Случайные SECRET_KEY и JWT_SECRET_KEY
- [ ] JWT_COOKIE_SECURE=true
- [ ] CORS настроен правильно
- [ ] Дефолтные пароли изменены

---

## 📚 Полезные ссылки

- [Railway Documentation](https://docs.railway.app)
- [Railway CLI](https://docs.railway.app/develop/cli)
- [PostgreSQL на Railway](https://docs.railway.app/databases/postgresql)
- [Railway Discord](https://discord.gg/railway)
- [Railway Status](https://status.railway.app)

---

## 🧪 Тестирование после деплоя

```bash
# Health check
curl https://ваш-backend-url/health

# Логин админа
curl -X POST https://ваш-backend-url/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin1234"}' \
  -c cookies.txt

# Получить список комнат
curl https://ваш-backend-url/api/rooms \
  -b cookies.txt

# Создать комнату (требует права admin)
curl -X POST https://ваш-backend-url/api/rooms \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"TestRoom","room_type":"public"}'
```

---

**Готово! 🎉 Ваш backend развернут на Railway и готов к работе!**

При проблемах проверьте логи в Railway Dashboard или обратитесь в Railway Discord.
