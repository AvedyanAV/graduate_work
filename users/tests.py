from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from .models import User
from .utils import SMSVerificationService


class UserModelTestCase(TestCase):
    """Тесты для модели User."""

    def setUp(self):
        User.objects.all().delete()
        self.phone_number = '+79991234567'
        self.user = User.objects.create_user(
            phone_number=self.phone_number,
            is_phone_verified=True
        )

    def test_create_user(self):
        """Тест создания пользователя."""
        self.assertEqual(self.user.phone_number, self.phone_number)
        self.assertTrue(self.user.is_phone_verified)
        self.assertFalse(self.user.is_staff)

    def test_invite_code_generated_on_create(self):
        """Тест генерации инвайт-кода."""
        self.assertIsNotNone(self.user.invite_code)
        self.assertEqual(len(self.user.invite_code), 6)
        self.assertTrue(self.user.invite_code.isalnum())

    def test_invite_code_unique(self):
        """Тест уникальности инвайт-кода."""
        codes = set()
        codes.add(self.user.invite_code)

        for i in range(10):
            user = User.objects.create_user(
                phone_number=f'+799912345{str(i).zfill(2)}',
                is_phone_verified=True
            )
            codes.add(user.invite_code)

        self.assertEqual(len(codes), 11)

    def test_has_activated_invite(self):
        """Тест проверки активированного кода."""
        self.assertFalse(self.user.has_activated_invite())

    def test_can_activate_invite(self):
        """Тест возможности активации."""
        self.assertTrue(self.user.can_activate_invite())

    def test_activate_invite_code_success(self):
        """Тест успешной активации."""
        user2 = User.objects.create_user(
            phone_number='+79992222222',
            is_phone_verified=True
        )

        inviter = self.user.activate_invite_code(user2.invite_code)
        self.assertEqual(inviter, user2)
        self.assertEqual(self.user.activated_invite_code, user2)

    def test_activate_own_invite_code(self):
        """Тест попытки активации собственного кода."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.user.activate_invite_code(self.user.invite_code)

    def test_get_referred_users(self):
        """Тест получения рефералов."""
        user2 = User.objects.create_user(
            phone_number='+79992222222',
            is_phone_verified=True,
            activated_invite_code=self.user
        )

        referrals = self.user.get_referred_users()
        self.assertEqual(referrals.count(), 1)
        self.assertIn(user2, referrals)


class ReferralModelTestCase(TestCase):
    """Тесты реферальной логики в модели User."""

    def setUp(self):
        """Создаем тестовых пользователей."""
        self.user1 = User.objects.create_user(
            phone_number='+79991111111',
            is_phone_verified=True
        )
        self.user2 = User.objects.create_user(
            phone_number='+79992222222',
            is_phone_verified=True
        )
        self.user3 = User.objects.create_user(
            phone_number='+79993333333',
            is_phone_verified=True
        )

    def test_has_activated_invite(self):
        """Тест проверки наличия активированного инвайт-кода."""
        self.assertFalse(self.user1.has_activated_invite())

        self.user1.activated_invite_code = self.user2
        self.user1.save()

        self.assertTrue(self.user1.has_activated_invite())

    def test_can_activate_invite(self):
        """Тест возможности активации инвайт-кода."""
        self.assertTrue(self.user1.can_activate_invite())

        self.user1.activated_invite_code = self.user2
        self.user1.save()

        self.assertFalse(self.user1.can_activate_invite())

    def test_activate_invite_code_success(self):
        """Тест успешной активации инвайт-кода."""
        inviter = self.user1.activate_invite_code(self.user2.invite_code)

        self.assertEqual(inviter, self.user2)
        self.assertEqual(self.user1.activated_invite_code, self.user2)
        self.assertTrue(self.user1.has_activated_invite())

    def test_activate_own_invite_code(self):
        """Тест попытки активации собственного кода."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.user1.activate_invite_code(self.user1.invite_code)

        self.assertIn('Нельзя активировать собственный инвайт-код', str(context.exception))

    def test_activate_nonexistent_invite_code(self):
        """Тест активации несуществующего кода."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.user1.activate_invite_code('ZZZZZZ')

        self.assertIn('Инвайт-код не найден', str(context.exception))

    def test_activate_second_invite_code(self):
        """Тест попытки активации второго кода."""
        from django.core.exceptions import ValidationError

        self.user1.activate_invite_code(self.user2.invite_code)

        with self.assertRaises(ValidationError) as context:
            self.user1.activate_invite_code(self.user3.invite_code)

        self.assertIn('Вы уже активировали инвайт-код', str(context.exception))

    def test_get_referred_users(self):
        """Тест получения списка рефералов."""
        self.user2.activated_invite_code = self.user1
        self.user2.save()

        self.user3.activated_invite_code = self.user1
        self.user3.save()

        referrals = self.user1.get_referred_users()

        self.assertEqual(referrals.count(), 2)
        self.assertIn(self.user2, referrals)
        self.assertIn(self.user3, referrals)

    def test_get_referred_users_count(self):
        """Тест подсчета количества рефералов."""
        self.assertEqual(self.user1.get_referred_users_count(), 0)

        self.user2.activated_invite_code = self.user1
        self.user2.save()

        self.assertEqual(self.user1.get_referred_users_count(), 1)

        self.user3.activated_invite_code = self.user1
        self.user3.save()

        self.assertEqual(self.user1.get_referred_users_count(), 2)

    def test_get_referred_phones(self):
        """Тест получения списка телефонов рефералов."""
        self.user2.activated_invite_code = self.user1
        self.user2.save()
        self.user3.activated_invite_code = self.user1
        self.user3.save()

        phones = self.user1.get_referred_phones()

        self.assertEqual(len(phones), 2)
        self.assertIn(self.user2.phone_number, phones)
        self.assertIn(self.user3.phone_number, phones)

    def test_get_invite_info(self):
        """Тест получения полной информации о реферальной системе."""
        info = self.user1.get_invite_info()

        self.assertEqual(info['my_invite_code'], self.user1.invite_code)
        self.assertIsNone(info['activated_invite_code'])
        self.assertEqual(info['referred_count'], 0)
        self.assertTrue(info['can_activate'])

        self.user1.activated_invite_code = self.user2
        self.user1.save()

        info = self.user1.get_invite_info()

        self.assertEqual(info['activated_invite_code'], self.user2.invite_code)
        self.assertFalse(info['can_activate'])


class SMSVerificationServiceTestCase(TestCase):
    """Тесты сервиса SMS."""

    def setUp(self):
        cache.clear()
        self.phone_number = '+79991234567'

    def test_generate_verification_code(self):
        """Тест генерации кода."""
        code = SMSVerificationService.generate_verification_code()
        self.assertEqual(code, '1234')

    def test_save_and_verify_code(self):
        """Тест сохранения и проверки кода."""
        code = '1234'
        SMSVerificationService.save_code(self.phone_number, code)

        self.assertTrue(SMSVerificationService.verify_code(self.phone_number, code))
        self.assertFalse(SMSVerificationService.verify_code(self.phone_number, '0000'))

    def test_verify_code_removes_from_cache(self):
        """Тест удаления кода после проверки."""
        code = '1234'
        SMSVerificationService.save_code(self.phone_number, code)

        self.assertTrue(SMSVerificationService.verify_code(self.phone_number, code))
        self.assertFalse(SMSVerificationService.verify_code(self.phone_number, code))

    def test_simulate_sms_delay(self):
        """Тест задержки."""
        delay = SMSVerificationService.simulate_sms_delay()
        self.assertEqual(delay, 0)


class SerializerTestCase(TestCase):
    """Тесты сериализаторов."""

    def setUp(self):
        from .serializers import PhoneNumberSerializer
        self.PhoneNumberSerializer = PhoneNumberSerializer

    def test_phone_number_serializer_valid(self):
        """Тест валидного номера."""
        data = {'phone_number': '+79991234567'}
        serializer = self.PhoneNumberSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['phone_number'], '+79991234567')

    def test_phone_number_serializer_normalization(self):
        """Тест нормализации."""
        from users.serializers import PhoneNumberSerializer

        data = {'phone_number': '+7 999 123-45-67'}
        serializer = PhoneNumberSerializer(data=data)

        is_valid = serializer.is_valid()
        if not is_valid:
            print(f"Validation errors: {serializer.errors}")

        self.assertTrue(is_valid, f"Serializer should be valid, errors: {serializer.errors}")
        self.assertEqual(serializer.validated_data['phone_number'], '+79991234567')

    def test_phone_number_serializer_invalid_short(self):
        """Тест короткого номера."""
        data = {'phone_number': '123'}
        serializer = self.PhoneNumberSerializer(data=data)

        self.assertFalse(serializer.is_valid())


class AuthenticationAPITestCase(APITestCase):
    """Тесты API авторизации."""

    def setUp(self):
        User.objects.all().delete()
        cache.clear()
        self.client = APIClient()
        self.phone_number = '+79991234567'
        self.send_code_url = reverse('users:send-code')
        self.verify_code_url = reverse('users:verify-code')
        self.profile_url = reverse('users:profile-api')
        self.logout_url = reverse('users:logout-api')

    def test_send_code_success(self):
        """Тест отправки кода."""
        response = self.client.post(
            self.send_code_url,
            {'phone_number': self.phone_number},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('debug_code', response.data)

    def test_verify_code_new_user(self):
        """Тест регистрации нового пользователя."""
        response = self.client.post(
            self.send_code_url,
            {'phone_number': self.phone_number},
            format='json'
        )
        code = response.data['debug_code']

        response = self.client.post(
            self.verify_code_url,
            {'phone_number': self.phone_number, 'code': code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_new_user'])
        self.assertEqual(response.data['user']['phone_number'], self.phone_number)

    def test_verify_code_existing_user(self):
        """Тест авторизации существующего пользователя."""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            is_phone_verified=True
        )
        original_code = user.invite_code

        response = self.client.post(
            self.send_code_url,
            {'phone_number': self.phone_number},
            format='json'
        )
        code = response.data['debug_code']

        response = self.client.post(
            self.verify_code_url,
            {'phone_number': self.phone_number, 'code': code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_new_user'])

        user.refresh_from_db()
        self.assertEqual(user.invite_code, original_code)

    def test_profile_requires_auth(self):
        """Тест доступа к профилю без авторизации."""
        response = self.client.get(self.profile_url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_profile_authenticated(self):
        """Тест профиля с авторизацией."""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            is_phone_verified=True
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], self.phone_number)


class ReferralAPITestCase(APITestCase):
    """Тесты API реферальной системы."""

    def setUp(self):
        User.objects.all().delete()
        cache.clear()
        self.client = APIClient()

        self.user1 = User.objects.create_user(
            phone_number='+79991111111',
            is_phone_verified=True
        )
        self.user2 = User.objects.create_user(
            phone_number='+79992222222',
            is_phone_verified=True
        )

        self.activate_url = reverse('users:activate-invite-api')
        self.referrals_url = reverse('users:user-referrals-api')

    def test_activate_invite_code_success(self):
        """Тест активации инвайт-кода."""
        self.client.force_authenticate(user=self.user2)

        response = self.client.post(
            self.activate_url,
            {'invite_code': self.user1.invite_code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_activate_own_invite_code(self):
        """Тест активации своего кода."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            self.activate_url,
            {'invite_code': self.user1.invite_code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_referrals_empty(self):
        """Тест пустого списка рефералов."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(self.referrals_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_referrals'], 0)

    def test_user_referrals_with_data(self):
        """Тест списка рефералов с данными."""
        self.user2.activated_invite_code = self.user1
        self.user2.save()

        self.client.force_authenticate(user=self.user1)

        response = self.client.get(self.referrals_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_referrals'], 1)


class ValidatorTestCase(TestCase):
    """Тесты валидаторов."""

    def test_validate_invite_code_valid(self):
        """Тест валидных кодов."""
        from .validators import validate_invite_code

        valid_codes = ['A1B2C3', '123456', 'ABCDEF']
        for code in valid_codes:
            result = validate_invite_code(code)
            self.assertEqual(result, code.upper())

    def test_validate_invite_code_invalid_length(self):
        """Тест невалидной длины."""
        from .validators import validate_invite_code
        from django.core.exceptions import ValidationError

        invalid_codes = ['', 'A1B2C', 'A1B2C3D']
        for code in invalid_codes:
            with self.assertRaises(ValidationError):
                validate_invite_code(code)


class IntegrationTestCase(TransactionTestCase):
    """Интеграционные тесты."""
    reset_sequences = True

    def setUp(self):
        User.objects.all().delete()
        cache.clear()
        self.client = APIClient()

    def test_full_registration_flow(self):
        """Тест полного цикла регистрации."""
        phone = '+79991234567'

        response = self.client.post(
            reverse('users:send-code'),
            {'phone_number': phone},
            format='json'
        )
        self.assertEqual(response.status_code, 200)
        code = response.data['debug_code']

        response = self.client.post(
            reverse('users:verify-code'),
            {'phone_number': phone, 'code': code},
            format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_new_user'])

        response = self.client.get(reverse('users:profile-api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['phone_number'], phone)
