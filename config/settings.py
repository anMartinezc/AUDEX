"""
Django settings for config project.

Configuración de PRODUCCIÓN para:

- https://audex.cl
- https://www.audex.cl
- PostgreSQL / MySQL mediante variables de entorno.
- Mercado Pago.
- Webpay / Transbank.
- Nubox.
- Google Allauth.
- Resend API para correos transaccionales.
- WhiteNoise para archivos estáticos.
- Verificación obligatoria de correo electrónico.
"""

from pathlib import Path
from urllib.parse import urlparse
import os

from dotenv import load_dotenv
import environ
import dj_database_url


# =============================================================================
# RUTAS DEL PROYECTO
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# VARIABLES DE ENTORNO
# =============================================================================

load_dotenv(
    BASE_DIR / ".env",
    override=False,
)


env = environ.Env(
    DEBUG=(bool, True),
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
    en una lista de strings.
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
            "django-insecure-clave-temporal-solo-desarrollo-local"
        )

    else:

        raise RuntimeError(
            "DJANGO_SECRET_KEY debe estar configurada en producción."
        )


SECRET_KEY = DJANGO_SECRET_KEY


# =============================================================================
# DOMINIOS / LOCALHOST
# =============================================================================

SITE_URL = os.getenv(
    "SITE_URL",
    "https://audex.cl",
).strip().rstrip("/")


ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "audex.cl,www.audex.cl",
)


CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    (
        "https://audex.cl,"
        "https://www.audex.cl"
    ),
)


# Dominios opcionales entregados por algunos proveedores de hosting.
# Se agregan automáticamente si existen como variables de entorno.
for hosting_domain_env in (
    "RAILWAY_PUBLIC_DOMAIN",
    "RENDER_EXTERNAL_HOSTNAME",
):

    hosting_domain = os.getenv(
        hosting_domain_env,
        "",
    ).strip()

    if (
        hosting_domain
        and hosting_domain not in ALLOWED_HOSTS
    ):
        ALLOWED_HOSTS.append(
            hosting_domain
        )

    if hosting_domain:

        hosting_origin = (
            f"https://{hosting_domain}"
        )

        if (
            hosting_origin
            not in CSRF_TRUSTED_ORIGINS
        ):
            CSRF_TRUSTED_ORIGINS.append(
                hosting_origin
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

    # Correo transaccional
    "anymail",

    # Django Allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # Google OAuth
    "allauth.socialaccount.providers.google",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    # Bloquea sesiones de clientes cuyo correo aún no fue verificado.
    "core.middleware.RequireVerifiedEmailMiddleware",

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
# REVERSE PROXY / TÚNELES HTTPS
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


# -----------------------------------------------------------------------------
# POSTGRESQL
# -----------------------------------------------------------------------------

if DATABASE_URL:

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }


# -----------------------------------------------------------------------------
# MYSQL
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# SQLITE
# -----------------------------------------------------------------------------

else:

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
# STORAGE / WHITENOISE
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
            "CompressedStaticFilesStorage"
        ),
    },
}


WHITENOISE_AUTOREFRESH = DEBUG

WHITENOISE_USE_FINDERS = DEBUG

WHITENOISE_MAX_AGE = (
    0
    if DEBUG
    else 60 * 60 * 24 * 365
)


# =============================================================================
# ARCHIVOS MEDIA
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# TRANSBANK / WEBPAY
# =============================================================================

TRANSBANK_ENVIRONMENT = os.getenv(
    "TRANSBANK_ENVIRONMENT",
    "integration",
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


MERCADOPAGO_API_URL = os.getenv(
    "MERCADOPAGO_API_URL",
    "https://api.mercadopago.com",
).strip().rstrip("/")


# =============================================================================
# URL LOCAL
# =============================================================================

SITE_URL = SITE_URL.rstrip("/")


# =============================================================================
# MERCADO PAGO - WEBHOOK
# =============================================================================

MERCADOPAGO_NOTIFICATION_URL = os.getenv(
    "MERCADOPAGO_NOTIFICATION_URL",
    "",
).strip()


if not MERCADOPAGO_NOTIFICATION_URL:

    if SITE_URL:

        MERCADOPAGO_NOTIFICATION_URL = (
            f"{SITE_URL}/webhooks/mercadopago/"
        )


if MERCADOPAGO_NOTIFICATION_URL:

    MERCADOPAGO_NOTIFICATION_URL = (
        MERCADOPAGO_NOTIFICATION_URL.rstrip("/")
        + "/"
    )


# =============================================================================
# REGISTRAR HOSTS / ORÍGENES DE URLS PÚBLICAS
# =============================================================================


def registrar_url_publica_django(
    url: str,
) -> None:
    if not url:
        return

    try:
        parsed = urlparse(
            url
        )
    except ValueError:
        return

    hostname = (
        parsed.hostname
        or ""
    ).strip()

    if (
        hostname
        and hostname not in ALLOWED_HOSTS
    ):
        ALLOWED_HOSTS.append(
            hostname
        )

    if (
        parsed.scheme in {
            "http",
            "https",
        }
        and parsed.netloc
    ):
        origin = (
            f"{parsed.scheme}://{parsed.netloc}"
        )

        if (
            origin
            not in CSRF_TRUSTED_ORIGINS
        ):
            CSRF_TRUSTED_ORIGINS.append(
                origin
            )


registrar_url_publica_django(
    SITE_URL
)

registrar_url_publica_django(
    MERCADOPAGO_NOTIFICATION_URL
)


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


NUBOX_BOLETA_LEGAL_CODE = env(
    "NUBOX_BOLETA_LEGAL_CODE",
    default="39",
)


NUBOX_SALE_TYPE_ID = 1

NUBOX_PAYMENT_FORM_ID = 1


NUBOX_CLIENT_MAIN_ACTIVITY = (
    "Consumidor final"
)


NUBOX_COMUNA_CODES = {
    # Configurar los códigos reales utilizados
    # por Nubox / SII.
}


# =============================================================================
# RESEND
# =============================================================================

RESEND_API_KEY = os.getenv(
    "RESEND_API_KEY",
    "",
).strip()


RESEND_FROM_VENTAS = os.getenv(
    "RESEND_FROM_VENTAS",
    "Audex Ventas <ventas@audex.cl>",
).strip()


RESEND_FROM_SOPORTE = os.getenv(
    "RESEND_FROM_SOPORTE",
    "Audex Soporte <soporte@audex.cl>",
).strip()


RESEND_FROM_NO_REPLY = os.getenv(
    "RESEND_FROM_NO_REPLY",
    "Audex <no-reply@audex.cl>",
).strip()


RESEND_FROM_CONTACTO = os.getenv(
    "RESEND_FROM_CONTACTO",
    "Audex <contacto@audex.cl>",
).strip()


# =============================================================================
# DIRECCIONES AUDEX
# =============================================================================

EMAIL_CONTACTO = os.getenv(
    "EMAIL_CONTACTO",
    "contacto@audex.cl",
).strip()


EMAIL_VENTAS = os.getenv(
    "EMAIL_VENTAS",
    "ventas@audex.cl",
).strip()


EMAIL_SOPORTE = os.getenv(
    "EMAIL_SOPORTE",
    "soporte@audex.cl",
).strip()


EMAIL_NO_REPLY = os.getenv(
    "EMAIL_NO_REPLY",
    "no-reply@audex.cl",
).strip()


# =============================================================================
# REMITENTES POR DEFECTO
# =============================================================================

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    RESEND_FROM_NO_REPLY,
).strip()


SERVER_EMAIL = os.getenv(
    "SERVER_EMAIL",
    RESEND_FROM_NO_REPLY,
).strip()


# =============================================================================
# ANYMAIL / RESEND
# =============================================================================

ANYMAIL = {
    "RESEND_API_KEY": RESEND_API_KEY,
}


# =============================================================================
# CORREO DJANGO / ALLAUTH
# =============================================================================
#
# Por defecto utiliza Resend mediante django-anymail.
#
# Si alguna vez quieres volver temporalmente al backend de consola,
# puedes definir en .env:
#
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
#
# Para envíos reales:
#
# EMAIL_BACKEND=anymail.backends.resend.EmailBackend
# =============================================================================

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "anymail.backends.resend.EmailBackend",
).strip()


try:

    EMAIL_TIMEOUT = int(
        os.getenv(
            "EMAIL_TIMEOUT",
            "20",
        )
    )

except (TypeError, ValueError):

    EMAIL_TIMEOUT = 20


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

# Usa HTTPS automáticamente en producción y HTTP en desarrollo local.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = (
    "https"
    if SITE_URL.startswith("https://")
    else "http"
)


# El correo es obligatorio para crear una cuenta.
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]


# El inicio de sesión normal se realiza mediante correo.
ACCOUNT_LOGIN_METHODS = {
    "email",
}


# No se permiten dos cuentas con el mismo correo.
ACCOUNT_UNIQUE_EMAIL = True


# La verificación del correo es obligatoria.
#
# IMPORTANTE:
# Allauth crea el usuario en la base de datos antes de verificar el correo.
# Eso es normal. Mientras EmailAddress.verified sea False, el cliente no
# debe poder utilizar una sesión autenticada.
ACCOUNT_EMAIL_VERIFICATION = (
    "mandatory"
)


# Mantiene la confirmación mediante enlace enviado por correo.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = False


# Permite reenviar el correo de confirmación desde el flujo de Allauth.
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = True


# Los enlaces de confirmación vencen después de 3 días.
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3


# Después de confirmar el correo puede completar automáticamente
# el inicio de sesión pendiente.
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = (
    True
)


# Después de restablecer correctamente la contraseña,
# inicia sesión automáticamente.
ACCOUNT_LOGIN_ON_PASSWORD_RESET = (
    True
)


ACCOUNT_EMAIL_NOTIFICATIONS = True


# Reduce la enumeración de cuentas por dirección de correo.
ACCOUNT_PREVENT_ENUMERATION = True


# Cada usuario tendrá como máximo una dirección administrada por Allauth.
ACCOUNT_MAX_EMAIL_ADDRESSES = 1


# No permitimos cambiar el correo desde el flujo estándar de Allauth.
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


SESSION_COOKIE_AGE = (
    60 * 60 * 24 * 30
)


SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SESSION_SAVE_EVERY_REQUEST = False

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"


# =============================================================================
# SEGURIDAD PRODUCCIÓN
# =============================================================================

SECURE_SSL_REDIRECT = env_bool(
    "SECURE_SSL_REDIRECT",
    not DEBUG,
)


SESSION_COOKIE_SECURE = env_bool(
    "SESSION_COOKIE_SECURE",
    not DEBUG,
)


CSRF_COOKIE_SECURE = env_bool(
    "CSRF_COOKIE_SECURE",
    not DEBUG,
)


SECURE_HSTS_SECONDS = int(
    os.getenv(
        "SECURE_HSTS_SECONDS",
        "3600" if not DEBUG else "0",
    )
)


SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False,
)


SECURE_HSTS_PRELOAD = env_bool(
    "SECURE_HSTS_PRELOAD",
    False,
)


SECURE_CONTENT_TYPE_NOSNIFF = True


SECURE_REFERRER_POLICY = (
    "strict-origin-when-cross-origin"
)


X_FRAME_OPTIONS = "DENY"


# =============================================================================
# PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


# =============================================================================
# NUBOX - CONFIGURACIÓN
# =============================================================================

NUBOX_ENABLED = (
    os.getenv(
        "NUBOX_ENABLED",
        "False",
    ).strip().lower()
    in {
        "1",
        "true",
        "yes",
        "si",
        "sí",
    }
)


NUBOX_ENV = (
    os.getenv(
        "NUBOX_ENV",
        "uat",
    )
    .strip()
    .lower()
)


NUBOX_UAT_BASE_URL = (
    os.getenv(
        "NUBOX_UAT_BASE_URL",
        "",
    )
    .strip()
    .rstrip("/")
)


NUBOX_PRODUCTION_BASE_URL = (
    os.getenv(
        "NUBOX_PRODUCTION_BASE_URL",
        "",
    )
    .strip()
    .rstrip("/")
)


if NUBOX_ENV == "production":

    NUBOX_BASE_URL = (
        NUBOX_PRODUCTION_BASE_URL
    )

else:

    NUBOX_BASE_URL = (
        NUBOX_UAT_BASE_URL
    )


# Compatibilidad con código anterior
NUBOX_API_URL = NUBOX_BASE_URL


NUBOX_PARTNER_TOKEN = (
    os.getenv(
        "NUBOX_PARTNER_TOKEN",
        "",
    )
    .strip()
)


NUBOX_API_KEY = (
    os.getenv(
        "NUBOX_API_KEY",
        "",
    )
    .strip()
)


# Compatibilidad con nombre anterior
NUBOX_COMPANY_API_KEY = (
    os.getenv(
        "NUBOX_COMPANY_API_KEY",
        NUBOX_API_KEY,
    )
    .strip()
)


try:

    NUBOX_TIMEOUT = int(
        os.getenv(
            "NUBOX_TIMEOUT",
            "20",
        )
    )

except (TypeError, ValueError):

    NUBOX_TIMEOUT = 20