from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_invite_code(value):
    """Валидатор для проверки формата инвайт-кода."""
    if not value:
        raise ValidationError(
            _('Инвайт-код не может быть пустым'),
            code='invalid'
        )

    if len(value) != 6:
        raise ValidationError(
            _('Инвайт-код должен состоять из 6 символов'),
            code='invalid_length'
        )

    if not value.isalnum():
        raise ValidationError(
            _('Инвайт-код должен содержать только буквы и цифры'),
            code='invalid_chars'
        )

    return value.upper()
