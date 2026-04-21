# Сервис авторизации по номеру телефона

## Описание
Реферальная система с авторизацией по номеру телефона и инвайт-кодами.

## Технологии
- Python 
- Django 
- Django REST Framework
- PostgreSQL 
- Docker

## Быстрый старт

### Локальная разработка
```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env

# Применение миграций
python manage.py migrate

# Запуск сервера
python manage.py runserver