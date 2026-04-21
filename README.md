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

### Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
### venv\Scripts\activate  # Windows

### Установка зависимостей
pip install -r requirements.txt

### Настройка переменных окружения
cp .env.example .env

### Применение миграций
python manage.py migrate

### Запуск сервера
python manage.py runserver

## Docker

### Сборка и запуск
docker-compose up --build

### Остановка
docker-compose down

## Документация API

- ReDoc: http://127.0.0.1:8000/api/schema/redoc/
- Swagger UI: http://127.0.0.1:8000/api/schema/swagger-ui/
- OpenAPI Schema: http://127.0.0.1:8000/api/schema/

## Postman коллекция
### Файл postman_collection.json содержит все запросы для тестирования API.

- Импорт в Postman:
- Откройте Postman
- Нажмите Import → Upload Files
- Выберите postman_collection.json

## Тестирование

### Запуск всех тестов
- python manage.py test

### Запуск с покрытием
- coverage run --source='users' manage.py test users
- coverage report -m
- coverage html

## Лицензия
- Этот проект создан в рамках курсовой работы.

## Автор
- Аведян Амаяк