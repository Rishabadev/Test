"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from core.views import (
    login_view,
    signup_view,
    dashboard_view,
    portal_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),

    # Frontend Application Routes
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('dashboard/', dashboard_view, name='dashboard-frontend'),
    path('portal/', portal_view, name='portal-frontend'),
]
