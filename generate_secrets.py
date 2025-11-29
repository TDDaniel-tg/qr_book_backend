#!/usr/bin/env python3
"""
Генератор секретных ключей для Railway деплоя.
Использование: python generate_secrets.py
"""
import secrets


def generate_secret_key(length: int = 32) -> str:
    """Генерирует безопасный случайный ключ."""
    return secrets.token_urlsafe(length)


def main():
    print("=" * 70)
    print("🔐 Генератор секретных ключей для QRBOOK Backend")
    print("=" * 70)
    print()
    
    secret_key = generate_secret_key(32)
    jwt_secret_key = generate_secret_key(32)
    
    print("📋 Скопируйте эти значения в Railway Dashboard → Variables:")
    print()
    print(f"SECRET_KEY={secret_key}")
    print(f"JWT_SECRET_KEY={jwt_secret_key}")
    print()
    print("=" * 70)
    print("⚠️  ВАЖНО:")
    print("   - Сохраните эти ключи в безопасном месте")
    print("   - НЕ коммитьте их в git")
    print("   - Используйте их только для production деплоя")
    print("=" * 70)


if __name__ == "__main__":
    main()



