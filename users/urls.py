from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('api/auth/send-code/', views.SendVerificationCodeView.as_view(), name='send-code'),
    path('api/auth/verify-code/', views.VerifyCodeView.as_view(), name='verify-code'),
    path('api/auth/logout/', views.LogoutView.as_view(), name='logout-api'),
    path('api/profile/', views.UserProfileView.as_view(), name='profile-api'),
    path('api/profile/activate-invite/', views.ActivateInviteCodeView.as_view(), name='activate-invite-api'),
    path('api/profile/referrals/', views.UserReferralsView.as_view(), name='user-referrals-api'),
    path('api/stats/referrals/', views.ReferralStatsView.as_view(), name='referral-stats-api'),

    path('', views.HomePageView.as_view(), name='home'),
    path('login/', views.LoginPageView.as_view(), name='login_page'),
    path('profile/', views.ProfilePageView.as_view(), name='profile_page'),
    path('stats/', views.StatsPageView.as_view(), name='stats_page'),
    path('logout/', views.logout_view, name='logout'),
]
