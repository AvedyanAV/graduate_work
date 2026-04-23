from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login, logout
from django.db import transaction, models
from django.core.exceptions import ValidationError

from .models import User
from .serializers import (
    SendCodeSerializer,
    VerifyCodeSerializer,
    UserProfileSerializer,
    ActivateInviteCodeSerializer,
    ReferralStatsSerializer
)
from .utils import SMSVerificationService
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


class LoginPageView(TemplateView):
    """Страница входа в систему."""
    template_name = 'users/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('users:profile_page')
        return super().dispatch(request, *args, **kwargs)


class ProfilePageView(LoginRequiredMixin, TemplateView):
    """Страница профиля пользователя."""
    template_name = 'users/profile.html'
    login_url = '/login/'


class StatsPageView(TemplateView):
    """Страница статистики."""
    template_name = 'users/stats.html'


class HomePageView(TemplateView):
    """Главная страница."""
    template_name = 'users/home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('users:profile_page')
        return redirect('users:login_page')


def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('users:login_page')


@extend_schema_view(
    post=extend_schema(
        tags=['auth'],
        summary='Отправка кода подтверждения',
        description='''Отправляет 4-значный код подтверждения на указанный номер телефона.''',
        request=SendCodeSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Код успешно отправлен',
                examples=[
                    OpenApiExample(
                        'Успешный ответ',
                        value={
                            'status': 'success',
                            'message': 'Код подтверждения отправлен',
                            'phone_number': '+79991234567',
                            'delay_seconds': 1.23,
                            'debug_code': '1234'  # Только в DEBUG режиме
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Ошибка валидации номера телефона'),
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                value={'phone_number': '+79991234567'},
                request_only=True
            )
        ]
    )
)
class SendVerificationCodeView(APIView):
    """Отправка кода подтверждения на номер телефона."""
    permission_classes = [AllowAny]
    serializer_class = SendCodeSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = serializer.validated_data['phone_number']

        delay = SMSVerificationService.simulate_sms_delay()

        code = SMSVerificationService.generate_verification_code()

        SMSVerificationService.save_code(phone_number, code)

        response_data = {
            "status": "success",
            "message": "Код подтверждения отправлен",
            "phone_number": phone_number,
            "delay_seconds": round(delay, 2)
        }

        from django.conf import settings
        if settings.DEBUG or getattr(settings, 'TESTING', False):
            response_data["debug_code"] = code

        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        tags=['auth'],
        summary='Подтверждение кода и авторизация',
        description='''Проверяет код подтверждения и авторизует пользователя.''',
        request=VerifyCodeSerializer,
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer,
                description='Успешная авторизация',
                examples=[
                    OpenApiExample(
                        'Новый пользователь',
                        value={
                            'status': 'success',
                            'message': 'Авторизация успешна',
                            'is_new_user': True,
                            'user': {
                                'phone_number': '+79991234567',
                                'invite_code': 'A1B2C3',
                                'activated_invite_code': None,
                                'referred_users': [],
                                'referred_count': 0,
                                'can_activate_invite': True
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Неверный код подтверждения'),
        }
    )
)
class VerifyCodeView(APIView):
    """Подтверждение кода и авторизация пользователя."""
    permission_classes = [AllowAny]
    serializer_class = VerifyCodeSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = serializer.validated_data['phone_number']

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'is_phone_verified': True,
                }
            )

            if not created:
                user.is_phone_verified = True
                user.save(update_fields=['is_phone_verified'])

        login(request, user)

        profile_serializer = UserProfileSerializer(user)

        response_data = {
            "status": "success",
            "message": "Авторизация успешна",
            "is_new_user": created,
            "user": profile_serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        tags=['auth'],
        summary='Выход из системы',
        description='Завершает сессию текущего пользователя.',
        responses={
            200: OpenApiResponse(
                description='Успешный выход',
                examples=[
                    OpenApiExample(
                        'Успешный ответ',
                        value={
                            'status': 'success',
                            'message': 'Вы успешно вышли из системы'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Не авторизован'),
        }
    )
)
class LogoutView(APIView):
    """Выход из системы."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({
            "status": "success",
            "message": "Вы успешно вышли из системы"
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получение профиля пользователя',
        description='Возвращает информацию о текущем пользователе, включая реферальную статистику.',
        responses={
            200: UserProfileSerializer,
            401: OpenApiResponse(description='Не авторизован'),
        }
    )
)
class UserProfileView(APIView):
    """Получение профиля текущего пользователя."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get(self, request):
        """Возвращает полную информацию о профиле пользователя."""
        serializer = self.serializer_class(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        tags=['referral'],
        summary='Активация инвайт-кода',
        description='''Активирует инвайт-код другого пользователя.''',
        request=ActivateInviteCodeSerializer,
        responses={
            200: OpenApiResponse(
                description='Код успешно активирован',
                examples=[
                    OpenApiExample(
                        'Успешная активация',
                        value={
                            'status': 'success',
                            'message': 'Инвайт-код A1B2C3 успешно активирован',
                            'inviter': {
                                'phone_number': '+79991234567',
                                'invite_code': 'A1B2C3'
                            },
                            'user': {
                                'phone_number': '+79998765432',
                                'activated_invite_code': 'A1B2C3',
                                'can_activate_invite': False
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Ошибка активации (код не найден, уже активирован и т.д.)'),
            401: OpenApiResponse(description='Не авторизован'),
        }
    )
)
class ActivateInviteCodeView(APIView):
    """Активация инвайт-кода."""
    permission_classes = [IsAuthenticated]
    serializer_class = ActivateInviteCodeSerializer

    def post(self, request):
        """Активирует инвайт-код для текущего пользователя."""
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        invite_code = serializer.validated_data['invite_code']
        inviter = serializer.validated_data['inviter']

        try:
            request.user.activate_invite_code(invite_code)

            profile_serializer = UserProfileSerializer(request.user)

            return Response({
                "status": "success",
                "message": f"Инвайт-код {invite_code} успешно активирован",
                "inviter": {
                    "phone_number": inviter.phone_number,
                    "invite_code": inviter.invite_code
                },
                "user": profile_serializer.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    get=extend_schema(
        tags=['stats'],
        summary='Статистика реферальной системы',
        description='Возвращает общую статистику по всем пользователям и топ рефереров.',
        responses={
            200: OpenApiResponse(
                description='Статистика',
                examples=[
                    OpenApiExample(
                        'Успешный ответ',
                        value={
                            'total_users': 100,
                            'users_with_activated_invite': 75,
                            'activation_rate': 75.0,
                            'top_referrers': [
                                {
                                    'phone_number': '+79991234567',
                                    'invite_code': 'A1B2C3',
                                    'referral_count': 10
                                }
                            ]
                        }
                    )
                ]
            ),
        }
    )
)
class ReferralStatsView(APIView):
    """Статистика реферальной системы."""
    permission_classes = [AllowAny]  # Или IsAdminUser для production

    def get(self, request):
        """Возвращает общую статистику по реферальной системе."""
        total_users = User.objects.count()

        users_with_invite = User.objects.filter(
            activated_invite_code__isnull=False
        ).count()

        top_referrers = User.objects.annotate(
            referral_count=models.Count('referrals')
        ).filter(
            referral_count__gt=0
        ).order_by('-referral_count')[:10]

        top_referrers_data = [
            {
                'phone_number': user.phone_number,
                'invite_code': user.invite_code,
                'referral_count': user.referral_count
            }
            for user in top_referrers
        ]

        data = {
            'total_users': total_users,
            'users_with_activated_invite': users_with_invite,
            'activation_rate': round(users_with_invite / total_users * 100, 2) if total_users > 0 else 0,
            'top_referrers': top_referrers_data
        }

        serializer = ReferralStatsSerializer(data=data)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=['referral'],
        summary='Список рефералов',
        description='Возвращает детальный список пользователей, активировавших инвайт-код текущего пользователя.',
        responses={
            200: OpenApiResponse(
                description='Список рефералов',
                examples=[
                    OpenApiExample(
                        'Успешный ответ',
                        value={
                            'my_invite_code': 'A1B2C3',
                            'total_referrals': 2,
                            'referrals': [
                                {
                                    'phone_number': '+79991234567',
                                    'date_joined': '2026-04-21T10:00:00Z',
                                    'has_activated_invite': True,
                                    'referral_count': 1
                                }
                            ]
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Не авторизован'),
        }
    )
)
class UserReferralsView(APIView):
    """Получение списка рефералов текущего пользователя."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Возвращает детальную информацию о рефералах пользователя."""
        referrals = request.user.get_referred_users()

        referrals_data = [
            {
                'phone_number': referral.phone_number,
                'date_joined': referral.date_joined,
                'has_activated_invite': referral.has_activated_invite(),
                'referral_count': referral.get_referred_users_count()
            }
            for referral in referrals
        ]

        return Response({
            'my_invite_code': request.user.invite_code,
            'total_referrals': len(referrals_data),
            'referrals': referrals_data
        }, status=status.HTTP_200_OK)
