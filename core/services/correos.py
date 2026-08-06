# core/services/correos.py

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import CorreoPedido, Pedido


logger = logging.getLogger(__name__)


def obtener_emails_confirmacion(pedido):
    """
    Obtiene el correo ingresado en checkout y el correo del usuario
    autenticado, eliminando duplicados.
    """

    return list(pedido.emails_confirmacion)


def reservar_envio(pedido, email):
    """
    Reserva el envío del correo antes de contactar al servidor SMTP.

    Devuelve el ID del registro cuando se puede enviar.
    Devuelve None si ya fue enviado o existe otro proceso enviándolo.
    """

    email = Pedido.normalizar_email(email)

    if not email:
        return None

    try:
        with transaction.atomic():
            registro, creado = CorreoPedido.objects.get_or_create(
                pedido=pedido,
                email=email,
                tipo=CorreoPedido.TIPO_CONFIRMACION_PAGO,
                defaults={
                    "estado": CorreoPedido.ESTADO_PENDIENTE,
                },
            )

            if registro.estado in {
                CorreoPedido.ESTADO_ENVIADO,
                CorreoPedido.ESTADO_ENVIANDO,
            }:
                return None

            registro.estado = CorreoPedido.ESTADO_ENVIANDO
            registro.ultimo_error = ""

            registro.save(
                update_fields=[
                    "estado",
                    "ultimo_error",
                    "actualizado_en",
                ]
            )

            return registro.pk

    except IntegrityError:
        # Otra ejecución pudo crear el mismo registro simultáneamente.
        logger.info(
            (
                "El correo %s del pedido %s ya fue reservado "
                "por otro proceso."
            ),
            email,
            pedido.numero,
        )

        return None


def enviar_confirmacion_pago(pedido_id):
    """
    Envía la confirmación de pago al correo del checkout y al correo
    del usuario autenticado cuando sean diferentes.

    No repite el envío a una dirección que ya esté registrada como enviada.
    """

    try:
        pedido = (
            Pedido.objects
            .select_related("usuario")
            .prefetch_related("items__producto")
            .get(pk=pedido_id)
        )

    except Pedido.DoesNotExist:
        logger.error(
            "No existe el pedido con ID %s.",
            pedido_id,
        )

        return False

    # -------------------------------------------------------------------------
    # VALIDAR PAGO
    # -------------------------------------------------------------------------

    if not pedido.pago_aprobado:
        logger.warning(
            (
                "No se envió la confirmación del pedido %s: "
                "el pago no está aprobado."
            ),
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # DESTINATARIOS
    # -------------------------------------------------------------------------

    destinatarios = obtener_emails_confirmacion(
        pedido
    )

    if not destinatarios:
        logger.error(
            (
                "No se pudo enviar la confirmación del pedido %s: "
                "no tiene correos destinatarios."
            ),
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    items = list(
        pedido.items.all()
    )

    contexto = {
        "pedido": pedido,
        "items": items,
    }

    asunto = (
        f"Pago confirmado · Pedido {pedido.numero}"
    )

    try:
        contenido_texto = render_to_string(
            "emails/pago_confirmado.txt",
            contexto,
        )

        contenido_html = render_to_string(
            "emails/pago_confirmado.html",
            contexto,
        )

    except Exception as error:
        logger.exception(
            (
                "No se pudieron renderizar las plantillas "
                "del correo del pedido %s: %s"
            ),
            pedido.numero,
            error,
        )

        return False

    # -------------------------------------------------------------------------
    # ENVIAR CORREOS
    # -------------------------------------------------------------------------

    for email in destinatarios:
        registro_id = reservar_envio(
            pedido,
            email,
        )

        if registro_id is None:
            continue

        try:
            mensaje = EmailMultiAlternatives(
                subject=asunto,
                body=contenido_texto,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )

            mensaje.attach_alternative(
                contenido_html,
                "text/html",
            )

            cantidad_enviada = mensaje.send(
                fail_silently=False,
            )

            if cantidad_enviada != 1:
                raise RuntimeError(
                    "El backend SMTP no confirmó el envío."
                )

        except Exception as error:
            CorreoPedido.objects.filter(
                pk=registro_id,
            ).update(
                estado=CorreoPedido.ESTADO_ERROR,
                ultimo_error=str(error),
                actualizado_en=timezone.now(),
            )

            logger.exception(
                (
                    "Error enviando confirmación del pedido "
                    "%s a %s: %s"
                ),
                pedido.numero,
                email,
                error,
            )

        else:
            CorreoPedido.objects.filter(
                pk=registro_id,
            ).update(
                estado=CorreoPedido.ESTADO_ENVIADO,
                enviado_en=timezone.now(),
                ultimo_error="",
                actualizado_en=timezone.now(),
            )

            logger.info(
                (
                    "Confirmación del pedido %s "
                    "enviada a %s."
                ),
                pedido.numero,
                email,
            )

    # -------------------------------------------------------------------------
    # COMPROBAR SI TODOS FUERON ENVIADOS
    # -------------------------------------------------------------------------

    cantidad_enviados = (
        CorreoPedido.objects
        .filter(
            pedido=pedido,
            tipo=CorreoPedido.TIPO_CONFIRMACION_PAGO,
            email__in=destinatarios,
            estado=CorreoPedido.ESTADO_ENVIADO,
        )
        .count()
    )

    todos_enviados = (
        cantidad_enviados == len(destinatarios)
    )

    if todos_enviados:
        Pedido.objects.filter(
            pk=pedido.pk,
        ).update(
            correo_confirmacion_enviado=True,
            fecha_correo_confirmacion=(
                pedido.fecha_correo_confirmacion
                or timezone.now()
            ),
        )

        logger.info(
            (
                "Todos los correos del pedido %s "
                "fueron enviados correctamente."
            ),
            pedido.numero,
        )

        return True

    logger.warning(
        (
            "El pedido %s tiene correos pendientes o con error. "
            "Enviados: %s de %s."
        ),
        pedido.numero,
        cantidad_enviados,
        len(destinatarios),
    )

    return False