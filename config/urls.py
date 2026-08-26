"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

Examples:

Function views
    1. Add an import:
       from my_app import views

    2. Add a URL to urlpatterns:
       path('', views.home, name='home')

Class-based views
    1. Add an import:
       from other_app.views import Home

    2. Add a URL to urlpatterns:
       path('', Home.as_view(), name='home')

Including another URLconf
    1. Import the include() function:
       from django.urls import include, path

    2. Add a URL to urlpatterns:
       path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic.base import RedirectView


# =============================================================================
# BLOQUEO DE PANTALLAS DE GESTIÓN DE ALLAUTH
# =============================================================================

def bloquear_gestion_correo(request):
    """
    Impide que el usuario acceda a la pantalla de administración
    de correos de django-allauth.

    La cuenta utiliza un único correo y su administración no se
    expone al cliente.
    """
    return redirect("/mi-cuenta/perfil/")


def bloquear_conexiones_sociales(request):
    """
    Impide que el usuario acceda a la pantalla de administración
    de conexiones sociales de django-allauth.

    Esto NO desactiva el inicio de sesión con Google.
    Solo bloquea la interfaz donde el usuario podría administrar
    o desconectar las cuentas sociales vinculadas.
    """
    return redirect("/mi-cuenta/perfil/")


# =============================================================================
# URLS
# =============================================================================

urlpatterns = [

    # =========================================================================
    # ADMINISTRACIÓN
    # =========================================================================

    path(
        "admin/",
        admin.site.urls,
    ),


    # =========================================================================
    # APLICACIÓN PRINCIPAL
    # =========================================================================

    path(
        "",
        include("core.urls"),
    ),


 





    # =========================================================================
    # BLOQUEOS DE ALLAUTH
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # Estas rutas deben estar ANTES de:
    #
    #     path("accounts/", include("allauth.urls"))
    #
    # De esta forma Django encuentra primero nuestros bloqueos.
    #
    # =========================================================================


    # -------------------------------------------------------------------------
    # BLOQUEAR ADMINISTRACIÓN DE CORREOS
    # -------------------------------------------------------------------------

    path(
        "accounts/email/",
        bloquear_gestion_correo,
        name="bloquear_gestion_correo",
    ),


    # -------------------------------------------------------------------------
    # BLOQUEAR ADMINISTRACIÓN DE CONEXIONES SOCIALES
    # -------------------------------------------------------------------------

    path(
        "accounts/3rdparty/",
        bloquear_conexiones_sociales,
        name="bloquear_conexiones_sociales",
    ),


    # =========================================================================
    # DJANGO ALLAUTH
    # =========================================================================
    #
    # Se mantienen disponibles las funciones necesarias:
    #
    # - Registro.
    # - Confirmación de correo.
    # - Login social con Google.
    # - Recuperación de contraseña.
    # - Crear contraseña.
    # - Cambiar contraseña.
    # - Cerrar sesión.
    #
    # =========================================================================

    path(
        "accounts/",
        include("allauth.urls"),
    ),
]


# =============================================================================
# ARCHIVOS MEDIA EN DESARROLLO
# =============================================================================

if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )