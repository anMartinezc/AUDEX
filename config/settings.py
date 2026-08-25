"""
Django settings for config project.

Configuración preparada para:

- Desarrollo local.
- Railway.
- Producción con HTTPS.
- MySQL.
- Mercado Pago.
- Webpay / Transbank.
- Nubox.
- Google Allauth.
- WhiteNoise para archivos estáticos.
"""

from pathlib import Path
import os

from dotenv import load_dotenv
import environ


# =============================================================================
# RUTAS DEL PROYECTO
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# En desarrollo permite seguir utilizando .env.
# En Railway las variables se obtienen directamente
# desde el entorno del servicio.
load_dotenv(BASE_DIR / ".env")


# =============================================================================
# ENVIRONMENT
# =============================================================================

env = environ.Env(
    DEBUG=(bool, False),
)


def env_bool(
    nombre: str,
    valor_por_defecto: bool = False,
) -> bool:
    """
    Convierte:
    true, 1, yes, on
    en True.
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
    Convierte una variable separada por comas
    en una lista.
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
    False,
)


# =============================================================================
# SECRET KEY
# =============================================================================

DJANGO_SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "",
).strip()

if not DJANGO_SECRET_KEY:

    if DEBUG:
        DJANGO_SECRET_KEY = (
            "django-insecure-clave-temporal-solo-desarrollo"
        )

    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY no está configurada."
        )

SECRET_KEY = DJANGO_SECRET_KEY


# =============================================================================
# DOMINIOS
# =============================================================================

RAILWAY_PUBLIC_DOMAIN = os.getenv(
    "RAILWAY_PUBLIC_DOMAIN",
    "",
).strip()

SITE_URL = os.getenv(
    "SITE_URL",
    "",
).strip().rstrip("/")


# -------------------------------------------------------------------------
# ALLOWED HOSTS
# -------------------------------------------------------------------------

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost",
)

if RAILWAY_PUBLIC_DOMAIN:
    if RAILWAY_PUBLIC_DOMAIN not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(
            RAILWAY_PUBLIC_DOMAIN
        )


# -------------------------------------------------------------------------
# CSRF TRUSTED ORIGINS
# -------------------------------------------------------------------------

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "",
)

if SITE_URL.startswith("https://"):
    if SITE_URL not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(
            SITE_URL
        )

if RAILWAY_PUBLIC_DOMAIN:

    railway_origin = (
        f"https://{RAILWAY_PUBLIC_DOMAIN}"
    )

    if railway_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(
            railway_origin
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

    # Proyecto
    "core.apps.CoreConfig",

    # Django Allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # Google
    "allauth.socialaccount.providers.google",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise debe ir inmediatamente
    # después de SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",

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
# URLS / WSGI
# =============================================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"


# =============================================================================
# RAILWAY / REVERSE PROXY / HTTPS
# =============================================================================

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
#
# PRODUCCIÓN:
#
# Railway puede entregar DATABASE_URL.
#
# También soportamos directamente las variables:
#
# MYSQLHOST
# MYSQLPORT
# MYSQLDATABASE
# MYSQLUSER
# MYSQLPASSWORD
#
# DESARROLLO:
#
# Si no existe ninguna configuración MySQL,
# utilizamos SQLite.
# =============================================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
).strip()

MYSQLHOST = os.getenv(
    "MYSQLHOST",
    "",
).strip()

MYSQLPORT = os.getenv(
    "MYSQLPORT",
    "3306",
).strip()

MYSQLDATABASE = os.getenv(
    "MYSQLDATABASE",
    "",
).strip()

MYSQLUSER = os.getenv(
    "MYSQLUSER",
    "",
).strip()

MYSQLPASSWORD = os.getenv(
    "MYSQLPASSWORD",
    "",
)


if DATABASE_URL:

    DATABASES = {
        "default": env.db_url(
            "DATABASE_URL",
            conn_max_age=600,
        )
    }


elif (
    MYSQLHOST
    and MYSQLDATABASE
    and MYSQLUSER
):

    DATABASES = {
        "default": {
            "ENGINE": (
                "django.db.backends.mysql"
            ),

            "NAME": MYSQLDATABASE,

            "USER": MYSQLUSER,

            "PASSWORD": MYSQLPASSWORD,

            "HOST": MYSQLHOST,

            "PORT": MYSQLPORT,

            "CONN_MAX_AGE": 600,

            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }


else:

    if not DEBUG:
        raise RuntimeError(
            (
                "No existe una base de datos configurada. "
                "Configura DATABASE_URL o las variables "
                "MYSQLHOST, MYSQLDATABASE, MYSQLUSER y "
                "MYSQLPASSWORD."
            )
        )

    DATABASES = {
        "default": {

            "ENGINE": (
                "django.db.backends.sqlite3"
            ),

            "NAME": (
                BASE_DIR / "db.sqlite3"
            ),

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
# IDIOMA / ZONA HORARIA
# =============================================================================

LANGUAGE_CODE = "es-cl"

TIME_ZONE = "America/Santiago"

USE_I18N = True

USE_TZ = True


# =============================================================================
# FORMATO DE NÚMEROS
# =============================================================================

USE_THOUSAND_SEPARATOR = True

THOUSAND_SEPARATOR = "."

DECIMAL_SEPARATOR = ","

NUMBER_GROUPING = 3

FORMAT_MODULE_PATH = [
    "config.formats",
]


# =============================================================================
# ARCHIVOS ESTÁTICOS
# =============================================================================

STATIC_URL = "/static/"

STATIC_ROOT = (
    BASE_DIR / "staticfiles"
)

STATICFILES_DIRS = (
    [
        BASE_DIR / "static",
    ]
    if (BASE_DIR / "static").exists()
    else []
)


# =============================================================================
# WHITENOISE
# =============================================================================
#
# Permite que Gunicorn/Django sirvan correctamente
# CSS, JS e imágenes estáticas en Railway.
# =============================================================================

STORAGES = {

    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },

    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# =============================================================================
# ARCHIVOS SUBIDOS
# =============================================================================
#
# IMPORTANTE:
#
# El disco normal de Railway es efímero.
#
# Para imágenes subidas desde el panel de administración
# deberás posteriormente utilizar:
#
# - Railway Volume;
# - Cloudinary;
# - S3;
# - otro almacenamiento persistente.
#
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# TRANSBANK / WEBPAY
# =============================================================================

TRANSBANK_ENVIRONMENT = os.getenv(
    "TRANSBANK_ENVIRONMENT",
    (
        "integration"
        if DEBUG
        else "production"
    ),
).strip().lower()

TRANSBANK_COMMERCE_CODE = os.getenv(
    "TRANSBANK_COMMERCE_CODE",
    "",
).strip()

TRANSBANK_API_KEY = os.getenv(
    "TRANSBANK_API_KEY",
    "",
).strip()


# =============================================================================
# MERCADO PAGO
# =============================================================================

MERCADOPAGO_ACCESS_TOKEN = os.getenv(
    "MERCADOPAGO_ACCESS_TOKEN",
    "",
).strip()

MERCADOPAGO_PUBLIC_KEY = os.getenv(
    "MERCADOPAGO_PUBLIC_KEY",
    "",
).strip()

MERCADOPAGO_WEBHOOK_SECRET = os.getenv(
    "MERCADOPAGO_WEBHOOK_SECRET",
    "",
).strip()


# -------------------------------------------------------------------------
# URL PÚBLICA
# -------------------------------------------------------------------------

if not SITE_URL:

    if RAILWAY_PUBLIC_DOMAIN:

        SITE_URL = (
            f"https://{RAILWAY_PUBLIC_DOMAIN}"
        )

    elif DEBUG:

        SITE_URL = (
            "http://127.0.0.1:8000"
        )


SITE_URL = SITE_URL.rstrip("/")


# -------------------------------------------------------------------------
# WEBHOOK MERCADO PAGO
# -------------------------------------------------------------------------
#
# ESTE ES EL WEBHOOK ACTUAL:
#
# /webhooks/mercadopago/
#
# El webhook antiguo /mercadopago/webhook/
# ya fue eliminado.
# -------------------------------------------------------------------------

MERCADOPAGO_NOTIFICATION_URL = os.getenv(
    "MERCADOPAGO_NOTIFICATION_URL",
    (
        f"{SITE_URL}/webhooks/mercadopago/"
        if SITE_URL
        else ""
    ),
).strip()


MERCADOPAGO_API_URL = os.getenv(
    "MERCADOPAGO_API_URL",
    "https://api.mercadopago.com",
).rstrip("/")


# =============================================================================
# NUBOX
# =============================================================================

NUBOX_API_URL = env(
    "NUBOX_API_URL",
    default="",
)

NUBOX_PARTNER_TOKEN = env(
    "NUBOX_PARTNER_TOKEN",
    default="",
)

NUBOX_COMPANY_API_KEY = env(
    "NUBOX_COMPANY_API_KEY",
    default="",
)


# Boleta electrónica afecta.
NUBOX_BOLETA_LEGAL_CODE = env(
    "NUBOX_BOLETA_LEGAL_CODE",
    default="39",
)


# Venta normal.
NUBOX_SALE_TYPE_ID = 1


# Contado.
NUBOX_PAYMENT_FORM_ID = 1


NUBOX_CLIENT_MAIN_ACTIVITY = (
    "Consumidor final"
)


NUBOX_COMUNA_CODES = {

    # Ejemplo:
    #
    # "Santiago": "13101",
    # "Providencia": "13123",
}


# =============================================================================
# CORREO
# =============================================================================

if DEBUG:

    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND",
        (
            "django.core.mail.backends."
            "console.EmailBackend"
        ),
    )

else:

    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND",
        (
            "django.core.mail.backends."
            "smtp.EmailBackend"
        ),
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


DEFAULT_FROM_EMAIL = (
    os.getenv(
        "DEFAULT_FROM_EMAIL",
        "",
    ).strip()
    or EMAIL_HOST_USER
)


SERVER_EMAIL = os.getenv(
    "SERVER_EMAIL",
    DEFAULT_FROM_EMAIL,
)


# =============================================================================
# DTE
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
# AUTENTICACIÓN
# =============================================================================

LOGIN_URL = "core:login"

LOGIN_REDIRECT_URL = "core:inicio"

LOGOUT_REDIRECT_URL = "core:inicio"


# =============================================================================
# ALLAUTH
# =============================================================================

ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]


ACCOUNT_LOGIN_METHODS = {
    "email",
}


ACCOUNT_UNIQUE_EMAIL = True


ACCOUNT_EMAIL_VERIFICATION = (
    "mandatory"
)


ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = (
    True
)


ACCOUNT_LOGIN_ON_PASSWORD_RESET = (
    True
)


ACCOUNT_EMAIL_NOTIFICATIONS = True


ACCOUNT_PREVENT_ENUMERATION = True


ACCOUNT_MAX_EMAIL_ADDRESSES = 1


ACCOUNT_CHANGE_EMAIL = False


# =============================================================================
# GOOGLE ALLAUTH
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

        "APP": {

            "client_id": (
                GOOGLE_CLIENT_ID
            ),

            "secret": (
                GOOGLE_CLIENT_SECRET
            ),

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


SOCIALACCOUNT_LOGIN_ON_GET = False


# =============================================================================
# SESIONES
# =============================================================================

SESSION_ENGINE = (
    "django.contrib.sessions.backends.db"
)


# 30 días.
SESSION_COOKIE_AGE = (
    60 * 60 * 24 * 30
)


SESSION_EXPIRE_AT_BROWSER_CLOSE = False


SESSION_SAVE_EVERY_REQUEST = False


SESSION_COOKIE_HTTPONLY = True


SESSION_COOKIE_SAMESITE = "Lax"


# =============================================================================
# SEGURIDAD DE PRODUCCIÓN
# =============================================================================

if not DEBUG:

    # ---------------------------------------------------------------------
    # HTTPS
    # ---------------------------------------------------------------------

    SECURE_SSL_REDIRECT = env_bool(
        "SECURE_SSL_REDIRECT",
        True,
    )


    # ---------------------------------------------------------------------
    # COOKIES
    # ---------------------------------------------------------------------

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True


    # ---------------------------------------------------------------------
    # HSTS
    # ---------------------------------------------------------------------

    SECURE_HSTS_SECONDS = int(
        os.getenv(
            "SECURE_HSTS_SECONDS",
            "3600",
        )
    )

    SECURE_HSTS_INCLUDE_SUBDOMAINS = (
        env_bool(
            "SECURE_HSTS_INCLUDE_SUBDOMAINS",
            False,
        )
    )

    SECURE_HSTS_PRELOAD = False


    # ---------------------------------------------------------------------
    # SECURITY HEADERS
    # ---------------------------------------------------------------------

    SECURE_CONTENT_TYPE_NOSNIFF = True

    SECURE_REFERRER_POLICY = (
        "strict-origin-when-cross-origin"
    )

    X_FRAME_OPTIONS = "DENY"


else:

    SECURE_SSL_REDIRECT = False

    SESSION_COOKIE_SECURE = False

    CSRF_COOKIE_SECURE = False

    SECURE_HSTS_SECONDS = 0


# =============================================================================
# PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)