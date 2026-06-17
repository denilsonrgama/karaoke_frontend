#accounts/urls.py
from django import views
from django.urls import path
from .views import register_view, logout_view, welcome_view


urlpatterns = [    
    path("register/", register_view, name="register"),
    path("welcome/", welcome_view, name="welcome"),
    path("logout/", logout_view, name="logout"),
    
]   
