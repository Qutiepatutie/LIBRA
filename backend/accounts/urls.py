from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns =[
    path('login/', views.login_user, name='login_user'),
    path('google/', views.google_login, name='google_login'),
    path('register/', views.register_user, name='register_users'),
    path('changePass/', views.change_password, name='change_pass'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh')
]
