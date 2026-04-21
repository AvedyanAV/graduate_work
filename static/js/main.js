// Общие функции для всего приложения
(function() {
    'use strict';

    // Настройка CSRF токена для всех AJAX запросов
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie('csrftoken');

    // Функция для AJAX запросов с автоматическим CSRF
    window.apiRequest = function(url, method, data) {
        return $.ajax({
            url: url,
            method: method,
            contentType: 'application/json',
            data: data ? JSON.stringify(data) : undefined,
            headers: {
                'X-CSRFToken': csrftoken
            }
        });
    };

    // Функция для показа уведомлений
    window.showNotification = function(message, type = 'info') {
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show position-fixed"
                 style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        $('body').append(alertHtml);

        setTimeout(function() {
            $('.alert').alert('close');
        }, 5000);
    };

    // Форматирование номера телефона
    window.formatPhoneNumber = function(phone) {
        if (!phone) return '';

        // Убираем всё кроме цифр
        let cleaned = phone.replace(/\D/g, '');

        // Форматируем как +7 (XXX) XXX-XX-XX
        if (cleaned.length === 11) {
            return `+7 (${cleaned.slice(1, 4)}) ${cleaned.slice(4, 7)}-${cleaned.slice(7, 9)}-${cleaned.slice(9, 11)}`;
        }

        return phone;
    };

    // Проверка авторизации
    window.checkAuth = function() {
        const isAuthPage = window.location.pathname === '/login/';

        if (!isAuthPage) {
            $.ajax({
                url: '/api/profile/',
                method: 'GET',
                error: function(xhr) {
                    if (xhr.status === 401 || xhr.status === 403) {
                        window.location.href = '/login/';
                    }
                }
            });
        }
    };

    // Валидация инвайт-кода
    window.validateInviteCode = function(code) {
        if (!code) return false;
        if (code.length !== 6) return false;
        if (!/^[A-Z0-9]+$/.test(code)) return false;
        return true;
    };

    // Копирование в буфер обмена
    window.copyToClipboard = function(text) {
        if (navigator.clipboard) {
            return navigator.clipboard.writeText(text);
        } else {
            // Fallback
            const input = document.createElement('input');
            input.value = text;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            return Promise.resolve();
        }
    };

    // Запускаем проверку авторизации
    checkAuth();

})();