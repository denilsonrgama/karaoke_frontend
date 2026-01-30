#accounts/urls.py
from django import views
from django.urls import path
from .views import register_view, logout_view


urlpatterns = [    
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    
]   