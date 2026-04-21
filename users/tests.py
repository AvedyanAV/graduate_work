from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import User


class AuthenticationAPITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.phone_number = '+79991234567'
        self.send_code_url = reverse('users:send-code')
        self.verify_code_url = reverse('users:verify-code')
        self.profile_url = reverse('users:profile')

    def test_send_code_success(self):
        """Тест успешной отправки кода."""
        response = self.client.post(self.send_code_url, {
            'phone_number': self.phone_number
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['phone_number'], self.phone_number)
        self.assertIn('debug_code', response.data)  # Проверяем, что код приходит
        self.assertEqual(response.data['debug_code'], '1234')  # Проверяем тестовый код

    def test_verify_code_new_user(self):
        """Тест регистрации нового пользователя."""
        response = self.client.post(
            self.send_code_url,
            {'phone_number': self.phone_number},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        code = response.data['debug_code']

        response = self.client.post(
            self.verify_code_url,
            {
                'phone_number': self.phone_number,
                'code': code
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_new_user'])
        self.assertEqual(response.data['user']['phone_number'], self.phone_number)

        user = User.objects.get(phone_number=self.phone_number)
        self.assertTrue(user.is_phone_verified)
        self.assertIsNotNone(user.invite_code)
        self.assertEqual(len(user.invite_code), 6)

    def test_verify_code_existing_user(self):
        """Тест авторизации существующего пользователя."""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            is_phone_verified=True
        )
        original_invite_code = user.invite_code

        response = self.client.post(
            self.send_code_url,
            {'phone_number': self.phone_number},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        code = response.data['debug_code']

        response = self.client.post(
            self.verify_code_url,
            {
                'phone_number': self.phone_number,
                'code': code
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_new_user'])

        user.refresh_from_db()
        self.assertEqual(user.invite_code, original_invite_code)

    def test_profile_authenticated(self):
        """Тест получения профиля авторизованного пользователя."""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            is_phone_verified=True
        )

        response = self.client.post(
            self.send_code_url,
            {'phone_number': self.phone_number},
            format='json'
        )
        code = response.data['debug_code']

        response = self.client.post(
            self.verify_code_url,
            {
                'phone_number': self.phone_number,
                'code': code
            },
            format='json'
        )

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], self.phone_number)
        self.assertEqual(response.data['invite_code'], user.invite_code)
        self.assertIn('referred_users', response.data)


class InviteCodeTestCase(TestCase):
    """Тесты для проверки логики инвайт-кодов."""

    def setUp(self):
        self.client = APIClient()
        self.phone_number = '+79991234567'

    def test_invite_code_generation_unique(self):
        """Тест уникальности генерируемых инвайт-кодов."""
        codes = set()

        for i in range(10):
            user = User.objects.create_user(
                phone_number=f'+7999123456{i}',
                is_phone_verified=True
            )
            codes.add(user.invite_code)

        self.assertEqual(len(codes), 10)

    def test_invite_code_format(self):
        """Тест формата инвайт-кода."""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            is_phone_verified=True
        )

        code = user.invite_code

        self.assertEqual(len(code), 6)

        self.assertTrue(code.isalnum())


class ReferralSystemTestCase(TestCase):
    """Тесты для реферальной системы."""

    def setUp(self):
        self.client = APIClient()
        self.phone_number1 = '+79991234561'
        self.phone_number2 = '+79991234562'
        self.phone_number3 = '+79991234563'

        self.user1 = User.objects.create_user(
            phone_number=self.phone_number1,
            is_phone_verified=True
        )

        self.user2 = User.objects.create_user(
            phone_number=self.phone_number2,
            is_phone_verified=True
        )

        self.activate_url = reverse('users:activate-invite')
        self.profile_url = reverse('users:profile')
        self.referrals_url = reverse('users:user-referrals')

    def test_activate_invite_code_success(self):
        """Тест успешной активации инвайт-кода."""
        self.client.force_login(self.user2)

        response = self.client.post(
            self.activate_url,
            {'invite_code': self.user1.invite_code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['inviter']['phone_number'], self.user1.phone_number)

        self.user2.refresh_from_db()
        self.assertEqual(self.user2.activated_invite_code, self.user1)

    def test_activate_own_invite_code(self):
        """Тест попытки активации собственного инвайт-кода."""
        self.client.force_login(self.user1)

        response = self.client.post(
            self.activate_url,
            {'invite_code': self.user1.invite_code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invite_code', response.data)

    def test_activate_invalid_invite_code(self):
        """Тест активации несуществующего инвайт-кода."""
        self.client.force_login(self.user1)

        response = self.client.post(
            self.activate_url,
            {'invite_code': 'ZZZZZZ'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invite_code', response.data)

    def test_activate_second_invite_code(self):
        """Тест попытки активации второго инвайт-кода."""
        self.client.force_login(self.user2)

        # Активируем первый код
        self.client.post(
            self.activate_url,
            {'invite_code': self.user1.invite_code},
            format='json'
        )

        user3 = User.objects.create_user(
            phone_number=self.phone_number3,
            is_phone_verified=True
        )

        response = self.client.post(
            self.activate_url,
            {'invite_code': user3.invite_code},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invite_code', response.data)

    def test_profile_shows_referral_info(self):
        """Тест отображения реферальной информации в профиле."""
        self.user2.activated_invite_code = self.user1
        self.user2.save()

        self.client.force_login(self.user1)

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invite_code'], self.user1.invite_code)
        self.assertIsNone(response.data['activated_invite_code'])
        self.assertEqual(response.data['referred_count'], 2)
        self.assertIn(self.phone_number2, response.data['referred_users'])
        self.assertIn(self.phone_number3, response.data['referred_users'])

    def test_user_referrals_endpoint(self):
        """Тест эндпоинта со списком рефералов."""
        self.user2.activated_invite_code = self.user1
        self.user2.save()

        self.client.force_login(self.user1)

        response = self.client.get(self.referrals_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['my_invite_code'], self.user1.invite_code)
        self.assertEqual(response.data['total_referrals'], 1)
        self.assertEqual(len(response.data['referrals']), 1)
        self.assertEqual(response.data['referrals'][0]['phone_number'], self.phone_number2)

    def test_can_activate_invite_flag(self):
        """Тест флага can_activate_invite в профиле."""
        self.client.force_login(self.user1)

        response = self.client.get(self.profile_url)
        self.assertTrue(response.data['can_activate_invite'])

        self.client.post(
            self.activate_url,
            {'invite_code': self.user2.invite_code},
            format='json'
        )

        response = self.client.get(self.profile_url)
        self.assertFalse(response.data['can_activate_invite'])


class ReferralStatsTestCase(TestCase):
    """Тесты для статистики реферальной системы."""

    def setUp(self):
        User.objects.all().delete()

        self.client = APIClient()
        self.stats_url = reverse('users:referral-stats')

        self.user1 = User.objects.create_user(
            phone_number='+79991234561',
            is_phone_verified=True
        )

        for i in range(2, 6):
            User.objects.create_user(
                phone_number=f'+7999123456{i}',
                is_phone_verified=True,
                activated_invite_code=self.user1
            )

        User.objects.create_user(
            phone_number='+79991234560',
            is_phone_verified=True
        )

    def test_referral_stats_endpoint(self):
        """Тест получения статистики."""
        response = self.client.get(self.stats_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['total_users'], User.objects.count())
        self.assertEqual(
            response.data['users_with_activated_invite'],
            User.objects.filter(activated_invite_code__isnull=False).count()
        )

        top_phones = [r['phone_number'] for r in response.data['top_referrers']]
        self.assertIn(self.user1.phone_number, top_phones)

        for referrer in response.data['top_referrers']:
            if referrer['phone_number'] == self.user1.phone_number:
                self.assertEqual(referrer['referral_count'], 4)
                break
