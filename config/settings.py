"""
Django settings for config project.
"""

from pathlib import Path
import os

from dotenv import load_dotenv


# =============================================================================
# RUTAS DEL PROYECTO
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga el archivo .env ubicado en la misma carpeta que manage.py.
load_dotenv(BASE_DIR / ".env")


def env_bool(
    nombre: str,
    valor_por_defecto: bool = False,
) -> bool:
    """
    Convierte variables de entorno como True, true, 1, yes u on
    en valores booleanos de Python.
    """
    valor = os.getenv(nombre)

    if valor is None:
        return valor_por_defecto

    return valor.strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def env_list(
    nombre: str,
    valor_por_defecto: str = "",
) -> list[str]:
    """
    Convierte una variable de entorno separada por comas
    en una lista sin valores vacíos.
    """
    return [
        elemento.strip()
        for elemento in os.getenv(
            nombre,
            valor_por_defecto,
        ).split(",")
        if elemento.strip()
    ]


# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================

DEBUG = env_bool(
    "DEBUG",
    True,
)

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-clave-temporal-solo-desarrollo",
)

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost",
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "",
)


# =============================================================================
# APLICACIONES
# =============================================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # Aplicaciones propias
    "core.apps.CoreConfig",

    # Django Allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # Proveedor Google
    "allauth.socialaccount.providers.google",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =============================================================================
# BACKENDS DE AUTENTICACIÓN
# =============================================================================

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]


# =============================================================================
# URLS Y SERVIDOR
# =============================================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"



# =============================================================================
# PROXY HTTPS / NGROK
# =============================================================================

# Ngrok termina HTTPS y reenvía la solicitud a Django.
# Estas opciones permiten que Django reconstruya URLs externas con HTTPS.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

USE_X_FORWARDED_HOST = True


# =============================================================================
# PLANTILLAS
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth.context_processors."
                    "auth"
                ),
                (
                    "django.contrib.messages.context_processors."
                    "messages"
                ),
            ],
        },
    },
]


# =============================================================================
# BASE DE DATOS
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    }
}

# =============================================================================
# VALIDACIÓN DE CONTRASEÑAS
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =============================================================================
# IDIOMA Y ZONA HORARIA
# =============================================================================

LANGUAGE_CODE = "es-cl"

TIME_ZONE = "America/Santiago"

USE_I18N = True

USE_TZ = True


# =============================================================================
# ARCHIVOS ESTÁTICOS
# =============================================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = (
    [
        BASE_DIR / "static",
    ]
    if (BASE_DIR / "static").exists()
    else []
)


# =============================================================================
# ARCHIVOS SUBIDOS POR USUARIOS
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# MERCADO PAGO
# =============================================================================

MERCADOPAGO_ACCESS_TOKEN = os.getenv(
    "MERCADOPAGO_ACCESS_TOKEN",
    "",
)

MERCADOPAGO_PUBLIC_KEY = os.getenv(
    "MERCADOPAGO_PUBLIC_KEY",
    "",
)

MERCADOPAGO_WEBHOOK_SECRET = os.getenv(
    "MERCADOPAGO_WEBHOOK_SECRET",
    "",
)

SITE_URL = os.getenv(
    "SITE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

MERCADOPAGO_NOTIFICATION_URL = os.getenv(
    "MERCADOPAGO_NOTIFICATION_URL",
    f"{SITE_URL}/pagos/mercadopago/webhook/",
)

MERCADOPAGO_API_URL = os.getenv(
    "MERCADOPAGO_API_URL",
    "https://api.mercadopago.com",
).rstrip("/")

# =============================================================================
# CORREO ELECTRÓNICO
# =============================================================================

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    "",
).strip()

EMAIL_PORT = int(
    os.getenv(
        "EMAIL_PORT",
        "587",
    )
)

EMAIL_HOST_USER = os.getenv(
    "EMAIL_HOST_USER",
    "",
).strip()

EMAIL_HOST_PASSWORD = os.getenv(
    "EMAIL_HOST_PASSWORD",
    "",
).strip()

EMAIL_USE_TLS = env_bool(
    "EMAIL_USE_TLS",
    True,
)

EMAIL_USE_SSL = env_bool(
    "EMAIL_USE_SSL",
    False,
)

EMAIL_TIMEOUT = int(
    os.getenv(
        "EMAIL_TIMEOUT",
        "20",
    )
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "",
).strip() or EMAIL_HOST_USER


# =============================================================================
# BOLETA ELECTRÓNICA / PROVEEDOR DTE
# =============================================================================

DTE_MODE = os.getenv(
    "DTE_MODE",
    "provider",
)

DTE_PROVIDER_URL = os.getenv(
    "DTE_PROVIDER_URL",
    "",
).rstrip("/")

DTE_PROVIDER_TOKEN = os.getenv(
    "DTE_PROVIDER_TOKEN",
    "",
)


# =============================================================================
# AUTENTICACIÓN Y REDIRECCIONES
# =============================================================================

# Conserva el inicio de sesión personalizado de Audex.
LOGIN_URL = "core:login"

LOGIN_REDIRECT_URL = "core:mis_compras"

LOGOUT_REDIRECT_URL = "core:inicio"


# =============================================================================
# DJANGO ALLAUTH: CUENTAS LOCALES
# =============================================================================

# Registro e inicio de sesión mediante correo electrónico.
# Se omite ACCOUNT_USER_MODEL_USERNAME_FIELD porque el proyecto
# utiliza el modelo User estándar de Django.
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]

ACCOUNT_LOGIN_METHODS = {
    "email",
}

ACCOUNT_UNIQUE_EMAIL = True

# Exige confirmar el correo antes de utilizar plenamente la cuenta.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

ACCOUNT_LOGIN_ON_PASSWORD_RESET = True

ACCOUNT_EMAIL_NOTIFICATIONS = True

ACCOUNT_PREVENT_ENUMERATION = True


# =============================================================================
# DJANGO ALLAUTH: GOOGLE
# =============================================================================

GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "",
).strip()

GOOGLE_CLIENT_SECRET = os.getenv(
    "GOOGLE_CLIENT_SECRET",
    "",
).strip()


SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # Credenciales cargadas desde el archivo .env.
        # No crees además un SocialApp de Google en el administrador.
        "APP": {
            "client_id": GOOGLE_CLIENT_ID,
            "secret": GOOGLE_CLIENT_SECRET,
            "key": "",
        },

        "SCOPE": [
            "profile",
            "email",
        ],

        "AUTH_PARAMS": {
            "access_type": "online",
        },

        "OAUTH_PKCE_ENABLED": True,
    },
}

# El inicio del flujo social se mantiene mediante POST.
SOCIALACCOUNT_LOGIN_ON_GET = False


# =============================================================================
# CONFIGURACIÓN DE PRODUCCIÓN
# =============================================================================

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_SSL_REDIRECT = env_bool(
        "SECURE_SSL_REDIRECT",
        True,
    )

    SECURE_HSTS_SECONDS = int(
        os.getenv(
            "SECURE_HSTS_SECONDS",
            "3600",
        )
    )

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False


# =============================================================================
# CLAVE PRIMARIA
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"




# =============================================================================
# SESIÓN Y CARRITO ANÓNIMO
# =============================================================================

SESSION_ENGINE = (
    "django.contrib.sessions.backends.db"
)

# 30 días.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30

# No borrar al cerrar el navegador.
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Renueva la duración durante la navegación.
SESSION_SAVE_EVERY_REQUEST = False

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"