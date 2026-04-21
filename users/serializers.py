from rest_framework import serializers
from django.core.validators import RegexValidator
from .models import User
from .utils import SMSVerificationService
from .validators import validate_invite_code


class PhoneNumberSerializer(serializers.Serializer):
    """Проверка номера телефона."""
    phone_number = serializers.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9]{10,15}$',
                message="Введите корректный номер телефона (10-15 цифр, можно с + в начале)"
            )
        ],
    )

    def validate_phone_number(self, value):
        """Убираем все нецифровые символы, кроме '+' в начале."""
        if value.startswith('+'):
            normalized = '+' + ''.join(filter(str.isdigit, value[1:]))
        else:
            normalized = ''.join(filter(str.isdigit, value))

        if len(normalized.replace('+', '')) < 10:
            raise serializers.ValidationError("Номер телефона слишком короткий")

        return normalized


class SendCodeSerializer(PhoneNumberSerializer):
    """Сериализатор для запроса отправки кода."""
    pass


class VerifyCodeSerializer(PhoneNumberSerializer):
    """Проверка кода подтверждения."""
    code = serializers.CharField(
        max_length=4,
        min_length=4,
        help_text="4-значный код подтверждения"
    )

    def validate_code(self, value):
        """Проверяет, что код состоит только из цифр."""
        if not value.isdigit():
            raise serializers.ValidationError("Код должен состоять только из цифр")
        return value

    def validate(self, attrs):
        """Проверяет соответствие кода номеру телефона."""
        phone_number = attrs['phone_number']
        code = attrs['code']

        if not SMSVerificationService.verify_code(phone_number, code):
            raise serializers.ValidationError({
                "code": "Неверный код подтверждения или срок его действия истек"
            })

        return attrs


class ActivateInviteCodeSerializer(serializers.Serializer):
    """
    Сериализатор для активации инвайт-кода.
    """
    invite_code = serializers.CharField(
        max_length=6,
        min_length=6,
        validators=[validate_invite_code],
        help_text="6-значный инвайт-код для активации"
    )

    def validate_invite_code(self, value):
        """Приводит код к верхнему регистру и проверяет существование."""
        value = value.upper()

        if not User.objects.filter(invite_code=value).exists():
            raise serializers.ValidationError("Инвайт-код не найден в системе")

        return value

    def validate(self, attrs):
        """Проверяет возможность активации кода для текущего пользователя."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Необходима авторизация")

        user = request.user
        invite_code = attrs['invite_code']

        if user.has_activated_invite():
            raise serializers.ValidationError({
                "invite_code": "Вы уже активировали инвайт-код"
            })

        try:
            inviter = User.objects.get(invite_code=invite_code)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "invite_code": "Инвайт-код не найден"
            })

        if inviter == user:
            raise serializers.ValidationError({
                "invite_code": "Нельзя активировать собственный инвайт-код"
            })

        attrs['inviter'] = inviter

        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """Расширенный сериализатор для отображения профиля пользователя."""
    referred_users = serializers.SerializerMethodField(
        help_text="Список телефонов пользователей, активировавших мой инвайт-код"
    )
    referred_count = serializers.SerializerMethodField(
        help_text="Количество пользователей, активировавших мой инвайт-код"
    )
    activated_invite_code = serializers.SerializerMethodField(
        help_text="Инвайт-код, который я активировал"
    )
    activated_invite_phone = serializers.SerializerMethodField(
        help_text="Номер телефона пользователя, чей код я активировал"
    )
    can_activate_invite = serializers.SerializerMethodField(
        help_text="Могу ли я активировать инвайт-код"
    )

    class Meta:
        model = User
        fields = [
            'id',
            'phone_number',
            'invite_code',
            'activated_invite_code',
            'activated_invite_phone',
            'referred_users',
            'referred_count',
            'can_activate_invite',
            'is_phone_verified',
            'date_joined',
            'last_login',
        ]
        read_only_fields = fields

    def get_referred_users(self, obj):
        """Возвращает список телефонов приглашенных пользователей."""
        return obj.get_referred_phones()

    def get_referred_count(self, obj):
        """Возвращает количество приглашенных пользователей."""
        return obj.get_referred_users_count()

    def get_activated_invite_code(self, obj):
        """Возвращает активированный инвайт-код."""
        if obj.activated_invite_code:
            return obj.activated_invite_code.invite_code
        return None

    def get_activated_invite_phone(self, obj):
        """Возвращает телефон пользователя, чей код активирован."""
        if obj.activated_invite_code:
            return obj.activated_invite_code.phone_number
        return None

    def get_can_activate_invite(self, obj):
        """Проверяет, может ли пользователь активировать инвайт-код."""
        return obj.can_activate_invite()


class ReferralStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики реферальной системы."""
    total_users = serializers.IntegerField()
    users_with_activated_invite = serializers.IntegerField()
    top_referrers = serializers.ListField(child=serializers.DictField())
