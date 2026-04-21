# Указываем базовый образ
FROM python:3.12-slim

# Предотвращает создание .pyc файлов и буферизацию
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем рабочую директорию (должна совпадать с docker-compose)
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update \
    && apt-get install -y gcc libpq-dev postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Создаем директории для статики и медиа
RUN mkdir -p /app/staticfiles /app/media \
    && chmod -R 755 /app/staticfiles /app/media

# Открываем порт
EXPOSE 8000