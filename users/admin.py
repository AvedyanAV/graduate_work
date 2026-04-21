from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'phone_number',
        'invite_code',
        'activated_invite_code',
        'referral_count',
        'is_phone_verified',
        'is_staff',
        'date_joined'
    )
    list_filter = ('is_phone_verified', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('phone_number', 'invite_code')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Реферальная система', {
            'fields': (
                'invite_code',
                'activated_invite_code',
                'get_referral_info'
            )
        }),
        ('Разрешения', {
            'fields': (
                'is_phone_verified',
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    readonly_fields = ('invite_code', 'get_referral_info', 'last_login', 'date_joined')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2'),
        }),
    )

    def referral_count(self, obj):
        """Отображает количество рефералов."""
        count = obj.get_referred_users_count()
        if count > 0:
            return format_html(
                '<a href="?activated_invite_code__id={}">{}</a>',
                obj.id,
                count
            )
        return '0'

    referral_count.short_description = 'Рефералы'
    referral_count.admin_order_field = 'referral_count'

    def get_referral_info(self, obj):
        """Отображает информацию о реферальной системе."""
        if obj.pk:
            info = obj.get_invite_info()
            return format_html(
                '<div>'
                '<strong>Мой код:</strong> {}<br>'
                '<strong>Активирован:</strong> {}<br>'
                '<strong>Рефералов:</strong> {}'
                '</div>',
                info['my_invite_code'],
                info['activated_invite_code'] or 'Нет',
                info['referred_count']
            )
        return '-'

    get_referral_info.short_description = 'Информация о рефералах'

    def get_queryset(self, request):
        """Оптимизируем запросы."""
        return super().get_queryset(request).prefetch_related('referrals')
