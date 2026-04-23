from rest_framework import serializers
from .models import User
from .utils import SMSVerificationService
from .validators import validate_invite_code


class PhoneNumberSerializer(serializers.Serializer):
    """Базовый сериализатор для номера телефона."""
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Номер телефона в международном формате (например, +79991234567)"
    )

    def validate_phone_number(self, value):
        """Валидация и нормализация номера телефона."""
        if value.startswith('+'):
            normalized = '+' + ''.join(filter(str.isdigit, value[1:]))
        else:
            normalized = ''.join(filter(str.isdigit, value))

        digits_only = normalized.replace('+', '')
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise serializers.ValidationError(
                "Номер телефона должен содержать от 10 до 15 цифр"
            )

        return normalized


class SendCodeSerializer(PhoneNumberSerializer):
    """Сериализатор для запроса отправки кода."""
    pass


class VerifyCodeSerializer(PhoneNumberSerializer):
    """Сериализатор для проверки кода подтверждения."""
    code = serializers.CharField(
        max_length=4,
        min_length=4,
        help_text="4-значный код подтверждения"
    )

    def validate_code(self, value):
        """Проверка формата кода."""
        if not value.isdigit():
            raise serializers.ValidationError("Код должен состоять только из цифр")
        return value

    def validate(self, attrs):
        """Проверка кода подтверждения."""
        phone_number = attrs.get('phone_number')
        code = attrs.get('code')

        if not phone_number or not code:
            raise serializers.ValidationError("Телефон и код обязательны")

        if not SMSVerificationService.verify_code(phone_number, code):
            raise serializers.ValidationError({
                "code": "Неверный код подтверждения или срок его действия истек"
            })

        return attrs


class ActivateInviteCodeSerializer(serializers.Serializer):
    """Сериализатор для активации инвайт-кода."""
    invite_code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="6-значный инвайт-код другого пользователя (буквы и цифры)"
    )

    def validate_invite_code(self, value):
        """Приводит код к верхнему регистру и проверяет существование."""
        value = value.upper()

        # Проверяем формат
        try:
            validate_invite_code(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))

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
        help_text="Количество пользователей, активировавших инвайт-код"
    )
    activated_invite_code = serializers.SerializerMethodField(
        help_text="Инвайт-код, который активировал пользователь"
    )
    activated_invite_phone = serializers.SerializerMethodField(
        help_text="Номер телефона пользователя, чей код активирован"
    )
    can_activate_invite = serializers.SerializerMethodField(
        help_text="Может ли пользователь активировать инвайт-код"
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
        return obj.get_referred_phones()

    def get_referred_count(self, obj):
        return obj.get_referred_users_count()

    def get_activated_invite_code(self, obj):
        if obj.activated_invite_code:
            return obj.activated_invite_code.invite_code
        return None

    def get_activated_invite_phone(self, obj):
        if obj.activated_invite_code:
            return obj.activated_invite_code.phone_number
        return None

    def get_can_activate_invite(self, obj):
        return obj.can_activate_invite()


class ReferralStatsSerializer(serializers.Serializer):
    """Сериализатор для статистики реферальной системы."""
    total_users = serializers.IntegerField()
    users_with_activated_invite = serializers.IntegerField()
    activation_rate = serializers.FloatField(required=False)
    top_referrers = serializers.ListField(child=serializers.DictField())
