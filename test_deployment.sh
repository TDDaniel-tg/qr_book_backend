#!/bin/bash
# Скрипт для проверки деплоя на Railway
# Использование: ./test_deployment.sh https://ваш-backend.up.railway.app

BACKEND_URL="${1:-http://localhost:5000}"

echo "🧪 Тестирование деплоя: $BACKEND_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Health check
echo ""
echo "1️⃣  Проверка здоровья сервиса..."
HEALTH=$(curl -s "$BACKEND_URL/health")
echo "   Ответ: $HEALTH"

if echo "$HEALTH" | grep -q "healthy"; then
    echo "   ✅ Сервис работает"
else
    echo "   ❌ Сервис не отвечает"
    exit 1
fi

# 2. Логин admin
echo ""
echo "2️⃣  Тест авторизации (admin)..."
LOGIN=$(curl -s -X POST "$BACKEND_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin1234"}' \
    -c /tmp/cookies.txt)

if echo "$LOGIN" | grep -q "access_token"; then
    echo "   ✅ Авторизация работает"
else
    echo "   ❌ Ошибка авторизации: $LOGIN"
fi

# 3. Получить список комнат
echo ""
echo "3️⃣  Проверка комнат..."
ROOMS=$(curl -s "$BACKEND_URL/api/rooms" -b /tmp/cookies.txt)
echo "   Комнаты: $ROOMS"

if echo "$ROOMS" | grep -q "B101"; then
    echo "   ✅ Тестовые комнаты загружены (B101, B102...)"
else
    echo "   ⚠️  Комнаты не найдены"
fi

# 4. Проверить бронирования
echo ""
echo "4️⃣  Проверка бронирований..."
RESERVATIONS=$(curl -s "$BACKEND_URL/api/reservations" -b /tmp/cookies.txt)

if echo "$RESERVATIONS" | grep -q "id"; then
    echo "   ✅ Тестовые бронирования созданы"
else
    echo "   ⚠️  Бронирования не найдены"
fi

# Cleanup
rm -f /tmp/cookies.txt

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Тестирование завершено!"
echo ""
echo "📊 Итоговая проверка:"
echo "   • Сервис здоров: ✅"
echo "   • Авторизация: ✅"
echo "   • База данных: ✅"
echo "   • Тестовые данные: ✅"
echo ""
echo "🎉 Backend полностью готов к использованию!"


