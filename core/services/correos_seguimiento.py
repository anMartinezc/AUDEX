
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


logger = logging.getLogger(__name__)


# =============================================================================
# UTILIDADES
# =============================================================================


def _obtener_destinatarios(
    pedido,
):
    """
    Obtiene los correos asociados al pedido.

    Utiliza la propiedad emails_confirmacion del modelo Pedido,
    que incluye:

    - correo utilizado durante el checkout;
    - correo asociado al usuario, si existe;
    - eliminación automática de duplicados.
    """

    try:
        destinatarios = list(
            pedido.emails_confirmacion
        )

    except Exception:
        destinatarios = []

    return [
        email
        for email in destinatarios
        if email
    ]


def _enviar_correo(
    *,
    asunto,
    destinatarios,
    template_html,
    template_txt,
    contexto,
):
    """
    Envía un correo multipart:

    - versión HTML;
    - versión de texto plano.

    Devuelve True si Django informa que el correo
    fue enviado correctamente.
    """

    if not destinatarios:
        return False

    texto = render_to_string(
        template_txt,
        contexto,
    )

    html = render_to_string(
        template_html,
        contexto,
    )

    correo = EmailMultiAlternatives(
        subject=asunto,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )

    correo.attach_alternative(
        html,
        "text/html",
    )

    enviados = correo.send(
        fail_silently=False,
    )

    return enviados > 0


# =============================================================================
# CORREO: PEDIDO EN DESPACHO
# =============================================================================


def enviar_correo_despacho(
    pedido,
):
    """
    Envía el correo cuando el pedido pasa al estado ENVIADO.

    El correo solo se envía si:

    - el pedido está en estado ENVIADO;
    - existen destinatarios;
    - todavía no se ha enviado anteriormente.

    Después del envío exitoso registra:

    - correo_despacho_enviado = True;
    - fecha_correo_despacho = timezone.now().
    """

    # -------------------------------------------------------------------------
    # VALIDAR PEDIDO
    # -------------------------------------------------------------------------

    if pedido is None:
        return False

    # -------------------------------------------------------------------------
    # EVITAR ENVÍOS DUPLICADOS
    # -------------------------------------------------------------------------

    if pedido.correo_despacho_enviado:
        return False

    # -------------------------------------------------------------------------
    # VALIDAR ESTADO
    # -------------------------------------------------------------------------

    if (
        pedido.estado
        != pedido.EstadoPedido.ENVIADO
    ):
        return False

    # -------------------------------------------------------------------------
    # DESTINATARIOS
    # -------------------------------------------------------------------------

    destinatarios = (
        _obtener_destinatarios(
            pedido
        )
    )

    if not destinatarios:

        logger.warning(
            "No se pudo enviar el correo de despacho "
            "del pedido %s porque no existen "
            "destinatarios.",
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # CONTEXTO
    # -------------------------------------------------------------------------

    contexto = {
        "pedido": pedido,
    }

    # -------------------------------------------------------------------------
    # ASUNTO
    # -------------------------------------------------------------------------

    asunto = (
        f"Tu pedido {pedido.numero} va en camino | Audex"
    )

    # -------------------------------------------------------------------------
    # ENVÍO
    # -------------------------------------------------------------------------

    try:

        enviado = _enviar_correo(
            asunto=asunto,
            destinatarios=destinatarios,
            template_html=(
                "emails/"
                "pedido_en_despacho.html"
            ),
            template_txt=(
                "emails/"
                "pedido_en_despacho.txt"
            ),
            contexto=contexto,
        )

    except Exception:

        logger.exception(
            "Error enviando correo de despacho "
            "para el pedido %s.",
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # VERIFICAR ENVÍO
    # -------------------------------------------------------------------------

    if not enviado:

        logger.warning(
            "Django no confirmó el envío del correo "
            "de despacho del pedido %s.",
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # REGISTRAR ENVÍO
    # -------------------------------------------------------------------------

    pedido.correo_despacho_enviado = True

    pedido.fecha_correo_despacho = (
        timezone.now()
    )

    pedido.save(
        update_fields=[
            "correo_despacho_enviado",
            "fecha_correo_despacho",
            "actualizado",
        ]
    )

    logger.info(
        "Correo de despacho enviado "
        "correctamente para el pedido %s.",
        pedido.numero,
    )

    return True


# =============================================================================
# CORREO: PEDIDO ENTREGADO
# =============================================================================


def enviar_correo_entrega(
    pedido,
):
    """
    Envía el correo cuando el pedido pasa al estado ENTREGADO.

    El correo solo se envía si:

    - el pedido está en estado ENTREGADO;
    - existen destinatarios;
    - todavía no se ha enviado anteriormente.

    Después del envío exitoso registra:

    - correo_entrega_enviado = True;
    - fecha_correo_entrega = timezone.now().
    """

    # -------------------------------------------------------------------------
    # VALIDAR PEDIDO
    # -------------------------------------------------------------------------

    if pedido is None:
        return False

    # -------------------------------------------------------------------------
    # EVITAR ENVÍOS DUPLICADOS
    # -------------------------------------------------------------------------

    if pedido.correo_entrega_enviado:
        return False

    # -------------------------------------------------------------------------
    # VALIDAR ESTADO
    # -------------------------------------------------------------------------

    if (
        pedido.estado
        != pedido.EstadoPedido.ENTREGADO
    ):
        return False

    # -------------------------------------------------------------------------
    # DESTINATARIOS
    # -------------------------------------------------------------------------

    destinatarios = (
        _obtener_destinatarios(
            pedido
        )
    )

    if not destinatarios:

        logger.warning(
            "No se pudo enviar el correo de entrega "
            "del pedido %s porque no existen "
            "destinatarios.",
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # CONTEXTO
    # -------------------------------------------------------------------------

    contexto = {
        "pedido": pedido,
    }

    # -------------------------------------------------------------------------
    # ASUNTO
    # -------------------------------------------------------------------------

    asunto = (
        f"Tu pedido {pedido.numero} fue entregado | Audex"
    )

    # -------------------------------------------------------------------------
    # ENVÍO
    # -------------------------------------------------------------------------

    try:

        enviado = _enviar_correo(
            asunto=asunto,
            destinatarios=destinatarios,
            template_html=(
                "emails/"
                "pedido_entregado.html"
            ),
            template_txt=(
                "emails/"
                "pedido_entregado.txt"
            ),
            contexto=contexto,
        )

    except Exception:

        logger.exception(
            "Error enviando correo de entrega "
            "para el pedido %s.",
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # VERIFICAR ENVÍO
    # -------------------------------------------------------------------------

    if not enviado:

        logger.warning(
            "Django no confirmó el envío del correo "
            "de entrega del pedido %s.",
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # REGISTRAR ENVÍO
    # -------------------------------------------------------------------------

    pedido.correo_entrega_enviado = True

    pedido.fecha_correo_entrega = (
        timezone.now()
    )

    pedido.save(
        update_fields=[
            "correo_entrega_enviado",
            "fecha_correo_entrega",
            "actualizado",
        ]
    )

    logger.info(
        "Correo de entrega enviado "
        "correctamente para el pedido %s.",
        pedido.numero,
    )

    return True

