"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Inicio / cierre de sesión propios del sistema.
    # login_not_required deja la página de login accesible SIN sesión
    # (de lo contrario LoginRequiredMiddleware la bloquearía y haría un bucle).
    path(
        'login/',
        login_not_required(
            auth_views.LoginView.as_view(template_name='registration/login.html')
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('', include('inventario.urls')),
]
