from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.crypto import get_random_string
from django.core.exceptions import ValidationError


class CustomUserManager(BaseUserManager):
    """Кастомный менеджер для модели User."""

    def create_user(self, phone_number, password=None, **extra_fields):
        """Создает и сохраняет пользователя с указанным номером телефона."""
        if not phone_number:
            raise ValueError('Номер телефона обязателен')

        phone_number = self.normalize_phone_number(phone_number)

        extra_fields.setdefault('username', phone_number)

        user = self.model(phone_number=phone_number, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        """Создает суперпользователя."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_phone_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)

    @staticmethod
    def normalize_phone_number(phone_number):
        """Нормализует номер телефона."""
        if phone_number.startswith('+'):
            normalized = '+' + ''.join(filter(str.isdigit, phone_number[1:]))
        else:
            normalized = ''.join(filter(str.isdigit, phone_number))
        return normalized


class User(AbstractUser):
    """Кастомная модель пользователя, где основным идентификатором является номер телефона."""
    username = models.CharField(
        max_length=150,
        unique=False,
        blank=True,
        null=True
    )

    phone_number = models.CharField(
        max_length=15,
        unique=True,
        db_index=True,
        verbose_name="Номер телефона"
    )

    invite_code = models.CharField(
        max_length=6,
        unique=True,
        blank=True,
        verbose_name="Мой инвайт-код"
    )

    activated_invite_code = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals',
        verbose_name="Активированный инвайт-код"
    )

    is_phone_verified = models.BooleanField(
        default=False,
        verbose_name="Телефон подтвержден"
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone_number

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        indexes = [
            models.Index(fields=['invite_code']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['activated_invite_code']),
        ]

    def save(self, *args, **kwargs):
        """Переопределяем метод сохранения для автоматической генерации инвайт-кода."""
        if not self.invite_code:
            self.invite_code = self.generate_unique_invite_code()

        if not self.username:
            self.username = self.phone_number

        super().save(*args, **kwargs)

    def generate_unique_invite_code(self):
        """Генерирует уникальный 6-значный код из букв и цифр."""
        length = 6
        allowed_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

        while True:
            code = get_random_string(length=length, allowed_chars=allowed_chars)
            if not User.objects.filter(invite_code=code).exists():
                return code

    def clean(self):
        """Валидация на уровне модели."""
        if self.activated_invite_code and self.activated_invite_code == self:
            raise ValidationError("Нельзя активировать собственный инвайт-код.")
        super().clean()

    def get_referred_users(self):
        """Возвращает QuerySet пользователей, которые активировали код текущего пользователя."""
        return self.referrals.filter(is_phone_verified=True)

    def get_referred_users_count(self):
        """Возвращает количество пользователей, активировавших код текущего пользователя."""
        return self.get_referred_users().count()

    def get_referred_phones(self):
        """Возвращает список телефонов пользователей, активировавших код текущего пользователя."""
        return list(self.get_referred_users().values_list('phone_number', flat=True))

    def has_activated_invite(self):
        """Проверяет, активировал ли пользователь чей-то инвайт-код."""
        return self.activated_invite_code is not None

    def can_activate_invite(self):
        """Проверяет, может ли пользователь активировать инвайт-код."""
        return not self.has_activated_invite()

    def activate_invite_code(self, invite_code):
        """Активирует инвайт-код для пользователя."""
        from django.core.exceptions import ValidationError

        if self.has_activated_invite():
            raise ValidationError("Вы уже активировали инвайт-код")

        try:
            inviter = User.objects.get(invite_code=invite_code.upper())
        except User.DoesNotExist:
            raise ValidationError("Инвайт-код не найден")

        if inviter == self:
            raise ValidationError("Нельзя активировать собственный инвайт-код")

        self.activated_invite_code = inviter
        self.save(update_fields=['activated_invite_code'])

        return inviter

    def get_invite_info(self):
        """Возвращает информацию о реферальной системе для пользователя."""
        return {
            'my_invite_code': self.invite_code,
            'activated_invite_code': self.activated_invite_code.invite_code if self.activated_invite_code else None,
            'activated_invite_phone': self.activated_invite_code.phone_number if self.activated_invite_code else None,
            'referred_count': self.get_referred_users_count(),
            'referred_phones': self.get_referred_phones(),
            'can_activate': self.can_activate_invite(),
        }
