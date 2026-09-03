"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views.

For more information:
https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""


# =============================================================================
# IMPORTS
# =============================================================================

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import (
    include,
    path,
    re_path,
)
from django.views.static import serve


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

    return redirect(
        "/mi-cuenta/perfil/"
    )


def bloquear_conexiones_sociales(request):
    """
    Impide que el usuario acceda a la pantalla de administración
    de conexiones sociales de django-allauth.

    Esto NO desactiva el inicio de sesión con Google.

    Solo bloquea la interfaz donde el usuario podría administrar
    o desconectar las cuentas sociales vinculadas.
    """

    return redirect(
        "/mi-cuenta/perfil/"
    )


# =============================================================================
# URLS
# =============================================================================

urlpatterns = [

    # =========================================================================
    # ADMINISTRACIÓN DJANGO
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
        include(
            "core.urls"
        ),
    ),


    # =========================================================================
    # BLOQUEOS DE DJANGO ALLAUTH
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # Estas rutas deben estar ANTES de:
    #
    #     path(
    #         "accounts/",
    #         include("allauth.urls"),
    #     )
    #
    # De esta forma Django encuentra primero nuestras rutas
    # personalizadas y evita mostrar las pantallas de gestión
    # que no queremos exponer al cliente.
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
    # Se mantienen disponibles:
    #
    # - Registro.
    # - Inicio de sesión.
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
        include(
            "allauth.urls"
        ),
    ),

]


# =============================================================================
# HANDLERS DE ERRORES PERSONALIZADOS
# =============================================================================
#
# IMPORTANTE:
#
# Django utiliza estos handlers cuando:
#
#     DEBUG = False
#
# Con DEBUG = True Django muestra sus páginas técnicas de error
# y no utiliza normalmente estas páginas personalizadas.
#
# Las vistas correspondientes deben existir en:
#
#     core/views.py
#
# =============================================================================


handler404 = (
    "core.views.error_404"
)


handler500 = (
    "core.views.error_500"
)


# =============================================================================
# ARCHIVOS MEDIA EN DESARROLLO
# =============================================================================
#
# Durante desarrollo Django puede servir directamente los archivos MEDIA.
#
# =============================================================================

if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )


# =============================================================================
# ARCHIVOS MEDIA
# =============================================================================
#
# Se conserva esta ruta porque ya formaba parte de la configuración
# actual del proyecto.
#
# Permite resolver URLs bajo /media/.
#
# Si posteriormente el hosting/CDN se encarga directamente de MEDIA,
# este bloque puede eliminarse.
#
# =============================================================================

urlpatterns += [

    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {
            "document_root":
                settings.MEDIA_ROOT,
        },
    ),

]