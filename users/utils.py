import random
import time
from django.core.cache import cache
from django.conf import settings


class SMSVerificationService:
    """Сервис для работы с кодами подтверждения по SMS."""

    @staticmethod
    def generate_verification_code():
        """
        Генерирует случайный 4-значный код.
        """
        if settings.DEBUG or getattr(settings, 'TESTING', False):
            return '1234'

        return str(random.randint(1000, 9999))

    @staticmethod
    def _get_cache_key(phone_number):
        """Формирует ключ для хранения кода в кеше."""
        normalized_phone = ''.join(filter(str.isdigit, phone_number))
        return f"sms_code:{normalized_phone}"

    @staticmethod
    def save_code(phone_number, code, timeout=300):
        """Сохраняет код подтверждения в кеш."""
        cache_key = SMSVerificationService._get_cache_key(phone_number)
        cache.set(cache_key, code, timeout)

        if settings.DEBUG:
            print(f"[SMS SIMULATION] Phone: {phone_number}, Code: {code}, Cache Key: {cache_key}")

    @staticmethod
    def verify_code(phone_number, code):
        """Проверяет код подтверждения."""
        cache_key = SMSVerificationService._get_cache_key(phone_number)
        stored_code = cache.get(cache_key)

        if settings.DEBUG:
            print(f"[VERIFY] Phone: {phone_number}, Input Code: {code}, Stored: {stored_code}")

        if stored_code and stored_code == code:
            cache.delete(cache_key)
            return True

        return False

    @staticmethod
    def simulate_sms_delay():
        """Имитирует задержку отправки SMS."""
        if getattr(settings, 'TESTING', False):
            return 0

        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)
        return delay
