"""
Middleware de seguridad para Audex.

Impide que una cuenta local con correo no verificado mantenga una sesión
autenticada, incluso si una vista personalizada de login llama directamente
a django.contrib.auth.login() y evita el flujo estándar de django-allauth.
"""

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from allauth.account.models import EmailAddress


class RequireVerifiedEmailMiddleware:
    """
    Bloquea el uso de cuentas de clientes cuyo correo no está verificado.

    - Los administradores y superusuarios no se bloquean.
    - Los usuarios anónimos no se bloquean.
    - Las rutas necesarias para confirmar el correo y cerrar sesión
      permanecen accesibles.
    """

    ALLOWED_URL_NAMES = {
        "account_confirm_email",
        "account_email_verification_sent",
        "account_logout",
        "logout",
    }

    SESSION_CACHE_KEY = "_audex_email_verified"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        user = getattr(
            request,
            "user",
            None,
        )

        if (
            not user
            or not user.is_authenticated
            or user.is_staff
            or user.is_superuser
        ):
            return self.get_response(
                request
            )

        # ---------------------------------------------------------
        # Permitir las rutas imprescindibles del proceso de
        # confirmación / cierre de sesión.
        # ---------------------------------------------------------

        try:
            match = resolve(
                request.path_info
            )

            url_name = (
                match.url_name
                or ""
            )

        except Resolver404:
            url_name = ""

        if (
            url_name
            in self.ALLOWED_URL_NAMES
        ):
            return self.get_response(
                request
            )

        # ---------------------------------------------------------
        # Evitar una consulta extra a la BD en cada request una vez
        # comprobada la verificación durante esta sesión.
        # ---------------------------------------------------------

        if request.session.get(
            self.SESSION_CACHE_KEY
        ) is True:
            return self.get_response(
                request
            )

        email = (
            getattr(
                user,
                "email",
                "",
            )
            or ""
        ).strip()

        correo_verificado = (
            bool(email)
            and EmailAddress.objects.filter(
                user=user,
                email__iexact=email,
                verified=True,
            ).exists()
        )

        if correo_verificado:

            request.session[
                self.SESSION_CACHE_KEY
            ] = True

            return self.get_response(
                request
            )

        # ---------------------------------------------------------
        # La cuenta existe, pero el correo todavía no fue confirmado.
        # Se destruye la sesión para impedir cualquier bypass desde
        # vistas de login personalizadas.
        # ---------------------------------------------------------

        logout(
            request
        )

        messages.warning(
            request,
            (
                "Debes confirmar tu correo electrónico "
                "antes de iniciar sesión."
            ),
        )

        return redirect(
            "account_email_verification_sent"
        )
