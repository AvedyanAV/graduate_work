# Указываем базовый образ
FROM python:3.12-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /config

# Устанавливаем системные зависимости
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем только requirements.txt без сохранения кеширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Создаем и даем права для создания директории статичных файлов
RUN mkdir -p /app/staticfiles && chmod -R 755 /app/staticfiles

# Открываем порт 8000 для взаимодействия с приложением
EXPOSE 8000

# Команда для запуска приложения
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]