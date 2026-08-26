# pedidos/services/email.py

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.template.loader import render_to_string

from core.services.resend_email import (
    enviar_correo_resend,
)


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIRMACIÓN DE COMPRA - CLIENTE
# =============================================================================

def enviar_confirmacion_compra(
    pedido,
    pdf_boleta,
):
    """
    Envía al cliente la confirmación de compra
    junto con la boleta en PDF mediante Resend.

    Utiliza:
        emails/compra_confirmada.html
        emails/compra_confirmada.txt

    Remitente:
        ventas@audex.cl
    """

    # =========================================================================
    # CONTEXTO
    # =========================================================================

    contexto = {
        "pedido": pedido,
        "items": pedido.items.all(),
        "url_pedido": (
            f"{settings.SITE_URL}/mi-cuenta/pedidos/"
            f"{pedido.id_publico}/"
        ),
    }

    # =========================================================================
    # RENDERIZAR TEMPLATES
    # =========================================================================

    html = render_to_string(
        "emails/compra_confirmada.html",
        contexto,
    )

    texto = render_to_string(
        "emails/compra_confirmada.txt",
        contexto,
    )

    # =========================================================================
    # NOMBRE DE LA BOLETA
    # =========================================================================

    nombre_boleta = (
        f"boleta-{pedido.dte_folio}.pdf"
    )

    # =========================================================================
    # ENVÍO MEDIANTE RESEND
    # =========================================================================

    try:

        respuesta = enviar_correo_resend(
            destinatarios=pedido.email,
            asunto=(
                f"Compra confirmada "
                f"#{pedido.id_publico}"
            ),
            html=html,
            texto=texto,
            remitente=(
                settings.RESEND_FROM_VENTAS
            ),
            adjuntos=[
                {
                    "filename": nombre_boleta,
                    "content": pdf_boleta,
                }
            ],
        )

    except Exception as error:

        logger.exception(
            (
                "Error enviando confirmación "
                "de compra del pedido %s "
                "a %s mediante Resend: %s"
            ),
            pedido.id_publico,
            pedido.email,
            error,
        )

        raise

    logger.info(
        (
            "Confirmación de compra del pedido "
            "%s enviada correctamente a %s "
            "mediante Resend."
        ),
        pedido.id_publico,
        pedido.email,
    )

    return respuesta


# =============================================================================
# OBTENER CORREOS DE ADMINISTRADORES
# =============================================================================

def obtener_correos_administradores():
    """
    Obtiene los correos de todos los usuarios
    administradores activos del sistema.

    Considera administrador a usuarios con:

        - is_staff=True
        - is_superuser=True

    Elimina correos vacíos y duplicados.
    """

    User = get_user_model()

    correos = (
        User.objects
        .filter(
            Q(is_staff=True)
            | Q(is_superuser=True),
            is_active=True,
        )
        .exclude(
            email="",
        )
        .exclude(
            email__isnull=True,
        )
        .values_list(
            "email",
            flat=True,
        )
        .distinct()
    )

    # =========================================================================
    # NORMALIZAR Y ELIMINAR DUPLICADOS
    # =========================================================================

    resultado = []

    vistos = set()

    for correo in correos:

        correo = str(
            correo or ""
        ).strip().lower()

        if not correo:
            continue

        if correo in vistos:
            continue

        vistos.add(
            correo
        )

        resultado.append(
            correo
        )

    return resultado


# =============================================================================
# NOTIFICACIÓN DE COMPRA - ADMINISTRADORES
# =============================================================================

def enviar_notificacion_compra_administradores(
    pedido,
):
    """
    Notifica mediante Resend a todos los
    administradores cuando se confirma
    una nueva compra.

    Cada administrador recibe un correo individual.

    Esto evita:
        - Exponer direcciones entre administradores.
        - Dependencia de BCC.
        - Agrupar varios administradores en un único envío.

    Utiliza:
        emails/admin_nueva_compra.html
        emails/admin_nueva_compra.txt

    Remitente:
        ventas@audex.cl
    """

    # =========================================================================
    # OBTENER ADMINISTRADORES
    # =========================================================================

    correos_admin = (
        obtener_correos_administradores()
    )

    if not correos_admin:

        logger.warning(
            (
                "El pedido %s fue confirmado, "
                "pero no existen administradores "
                "activos con correo configurado."
            ),
            pedido.id_publico,
        )

        return 0

    # =========================================================================
    # CONTEXTO
    # =========================================================================

    contexto = {
        "pedido": pedido,
        "items": pedido.items.all(),
        "url_pedido": (
            f"{settings.SITE_URL}/gestion/pedidos/"
            f"{pedido.id_publico}/"
        ),
    }

    # =========================================================================
    # RENDERIZAR TEMPLATES
    # =========================================================================

    html = render_to_string(
        "emails/admin_nueva_compra.html",
        contexto,
    )

    texto = render_to_string(
        "emails/admin_nueva_compra.txt",
        contexto,
    )

    asunto = (
        f"Nueva compra confirmada "
        f"#{pedido.id_publico}"
    )

    # =========================================================================
    # ENVÍO INDIVIDUAL
    # =========================================================================

    enviados = 0

    errores = []

    for correo_admin in correos_admin:

        try:

            respuesta = enviar_correo_resend(
                destinatarios=correo_admin,
                asunto=asunto,
                html=html,
                texto=texto,
                remitente=(
                    settings.RESEND_FROM_VENTAS
                ),
            )

            if not respuesta:

                raise RuntimeError(
                    (
                        "Resend no devolvió una "
                        "respuesta válida."
                    )
                )

        except Exception as error:

            errores.append(
                {
                    "email": correo_admin,
                    "error": str(error),
                }
            )

            logger.exception(
                (
                    "Error enviando notificación "
                    "del pedido %s al administrador "
                    "%s mediante Resend: %s"
                ),
                pedido.id_publico,
                correo_admin,
                error,
            )

            continue

        enviados += 1

        logger.info(
            (
                "Notificación del pedido %s "
                "enviada correctamente al "
                "administrador %s mediante Resend."
            ),
            pedido.id_publico,
            correo_admin,
        )

    # =========================================================================
    # RESULTADO
    # =========================================================================

    if errores:

        logger.warning(
            (
                "La notificación administrativa "
                "del pedido %s finalizó parcialmente. "
                "Enviados: %s de %s."
            ),
            pedido.id_publico,
            enviados,
            len(correos_admin),
        )

    else:

        logger.info(
            (
                "La nueva compra %s fue notificada "
                "correctamente mediante Resend "
                "a %s administrador(es)."
            ),
            pedido.id_publico,
            enviados,
        )

    return enviados