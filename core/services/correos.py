# core/services/correos.py

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import CorreoPedido, Pedido


logger = logging.getLogger(__name__)


# =============================================================================
# TIPOS DE CORREO
# =============================================================================

TIPO_CONFIRMACION_PAGO = CorreoPedido.TIPO_CONFIRMACION_PAGO

# Lo dejamos independiente del correo del cliente para evitar que una dirección
# que coincida con la de un administrador bloquee el segundo correo.
TIPO_ADMIN_NUEVA_COMPRA = "admin_nueva_compra"


# =============================================================================
# DESTINATARIOS CLIENTE
# =============================================================================

def obtener_emails_confirmacion(pedido):
    """
    Obtiene el correo ingresado en checkout y el correo del usuario
    autenticado, eliminando duplicados.
    """

    return list(
        pedido.emails_confirmacion
    )


# =============================================================================
# DESTINATARIOS ADMINISTRADORES
# =============================================================================

def obtener_emails_administradores():
    """
    Obtiene los correos de todos los usuarios activos que tengan
    permisos administrativos en Django.

    Considera administrador a:
    - is_staff=True
    - is_superuser=True

    Elimina correos vacíos y duplicados.
    """

    Usuario = get_user_model()

    emails = (
        Usuario.objects
        .filter(
            Q(is_staff=True)
            | Q(is_superuser=True),
            is_active=True,
        )
        .exclude(
            email__isnull=True,
        )
        .exclude(
            email="",
        )
        .values_list(
            "email",
            flat=True,
        )
        .distinct()
    )

    resultado = []

    emails_vistos = set()

    for email in emails:
        email_normalizado = (
            Pedido.normalizar_email(email)
        )

        if not email_normalizado:
            continue

        if email_normalizado in emails_vistos:
            continue

        emails_vistos.add(
            email_normalizado
        )

        resultado.append(
            email_normalizado
        )

    return resultado


# =============================================================================
# RESERVA DE ENVÍOS
# =============================================================================

def reservar_envio(
    pedido,
    email,
    tipo=TIPO_CONFIRMACION_PAGO,
):
    """
    Reserva el envío de un correo antes de contactar al servidor SMTP.

    Evita enviar dos veces el mismo tipo de correo a la misma
    dirección para un pedido determinado.

    Devuelve:
        ID del registro si se puede enviar.
        None si ya fue enviado o está siendo enviado.
    """

    email = Pedido.normalizar_email(
        email
    )

    if not email:
        return None

    try:
        with transaction.atomic():

            registro, creado = (
                CorreoPedido.objects
                .get_or_create(
                    pedido=pedido,
                    email=email,
                    tipo=tipo,
                    defaults={
                        "estado": (
                            CorreoPedido
                            .ESTADO_PENDIENTE
                        ),
                    },
                )
            )

            if registro.estado in {
                CorreoPedido.ESTADO_ENVIADO,
                CorreoPedido.ESTADO_ENVIANDO,
            }:
                return None

            registro.estado = (
                CorreoPedido.ESTADO_ENVIANDO
            )

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
        logger.info(
            (
                "El correo %s del pedido %s "
                "tipo %s ya fue reservado "
                "por otro proceso."
            ),
            email,
            pedido.numero,
            tipo,
        )

        return None


# =============================================================================
# ACTUALIZAR RESULTADO DEL ENVÍO
# =============================================================================

def marcar_correo_error(
    registro_id,
    error,
):
    """
    Marca un registro de correo como fallido.
    """

    CorreoPedido.objects.filter(
        pk=registro_id,
    ).update(
        estado=CorreoPedido.ESTADO_ERROR,
        ultimo_error=str(error),
        actualizado_en=timezone.now(),
    )


def marcar_correo_enviado(
    registro_id,
):
    """
    Marca un registro de correo como enviado.
    """

    ahora = timezone.now()

    CorreoPedido.objects.filter(
        pk=registro_id,
    ).update(
        estado=CorreoPedido.ESTADO_ENVIADO,
        enviado_en=ahora,
        ultimo_error="",
        actualizado_en=ahora,
    )


# =============================================================================
# ENVÍO ADMINISTRADORES
# =============================================================================

def enviar_notificacion_administradores(
    pedido,
    items,
):
    """
    Envía una notificación individual a cada administrador activo
    cuando una compra ha sido confirmada.

    Usa:
        emails/admin_nueva_compra.html
        emails/admin_nueva_compra.txt
    """

    destinatarios_admin = (
        obtener_emails_administradores()
    )

    if not destinatarios_admin:
        logger.warning(
            (
                "El pedido %s fue confirmado, pero no "
                "hay administradores activos con correo."
            ),
            pedido.numero,
        )

        return True

    # -------------------------------------------------------------------------
    # URL PANEL DE PEDIDOS
    # -------------------------------------------------------------------------

    site_url = getattr(
        settings,
        "SITE_URL",
        "",
    ).rstrip("/")

    url_pedido = (
        f"{site_url}/gestion/pedidos/"
    )

    # -------------------------------------------------------------------------
    # CONTEXTO
    # -------------------------------------------------------------------------

    contexto = {
        "pedido": pedido,
        "items": items,
        "url_pedido": url_pedido,
    }

    asunto = (
        f"Nueva compra confirmada · "
        f"Pedido {pedido.numero}"
    )

    # -------------------------------------------------------------------------
    # RENDERIZAR TEMPLATES ADMIN
    # -------------------------------------------------------------------------

    try:
        contenido_texto = render_to_string(
            "emails/admin_nueva_compra.txt",
            contexto,
        )

        contenido_html = render_to_string(
            "emails/admin_nueva_compra.html",
            contexto,
        )

    except Exception as error:
        logger.exception(
            (
                "No se pudieron renderizar las "
                "plantillas administrativas del "
                "pedido %s: %s"
            ),
            pedido.numero,
            error,
        )

        return False

    # -------------------------------------------------------------------------
    # ENVIAR A CADA ADMINISTRADOR
    # -------------------------------------------------------------------------

    enviados = 0

    for email in destinatarios_admin:

        registro_id = reservar_envio(
            pedido=pedido,
            email=email,
            tipo=TIPO_ADMIN_NUEVA_COMPRA,
        )

        if registro_id is None:

            # Puede significar que ya se envió anteriormente.
            ya_enviado = (
                CorreoPedido.objects
                .filter(
                    pedido=pedido,
                    email=email,
                    tipo=TIPO_ADMIN_NUEVA_COMPRA,
                    estado=(
                        CorreoPedido
                        .ESTADO_ENVIADO
                    ),
                )
                .exists()
            )

            if ya_enviado:
                enviados += 1

            continue

        try:
            mensaje = EmailMultiAlternatives(
                subject=asunto,
                body=contenido_texto,
                from_email=(
                    settings.DEFAULT_FROM_EMAIL
                ),
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
                    (
                        "El backend SMTP no confirmó "
                        "el envío al administrador."
                    )
                )

        except Exception as error:

            marcar_correo_error(
                registro_id,
                error,
            )

            logger.exception(
                (
                    "Error enviando notificación "
                    "administrativa del pedido "
                    "%s a %s: %s"
                ),
                pedido.numero,
                email,
                error,
            )

        else:

            marcar_correo_enviado(
                registro_id,
            )

            enviados += 1

            logger.info(
                (
                    "Notificación administrativa "
                    "del pedido %s enviada a %s."
                ),
                pedido.numero,
                email,
            )

    # -------------------------------------------------------------------------
    # RESULTADO
    # -------------------------------------------------------------------------

    todos_enviados = (
        enviados
        == len(destinatarios_admin)
    )

    if todos_enviados:
        logger.info(
            (
                "La nueva compra %s fue notificada "
                "correctamente a %s administrador(es)."
            ),
            pedido.numero,
            len(destinatarios_admin),
        )

        return True

    logger.warning(
        (
            "No todos los administradores recibieron "
            "la notificación del pedido %s. "
            "Enviados: %s de %s."
        ),
        pedido.numero,
        enviados,
        len(destinatarios_admin),
    )

    return False


# =============================================================================
# ENVÍO CONFIRMACIÓN CLIENTE
# =============================================================================

def enviar_confirmacion_pago(pedido_id):
    """
    Envía:

    1. Confirmación de pago al cliente.
    2. Notificación de nueva compra a todos los administradores.

    El correo del cliente y el administrativo se gestionan como
    tipos distintos para impedir duplicados.
    """

    try:
        pedido = (
            Pedido.objects
            .select_related(
                "usuario",
            )
            .prefetch_related(
                "items__producto",
            )
            .get(
                pk=pedido_id,
            )
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
                "No se envió la confirmación "
                "del pedido %s: "
                "el pago no está aprobado."
            ),
            pedido.numero,
        )

        return False

    # -------------------------------------------------------------------------
    # ITEMS
    # -------------------------------------------------------------------------

    items = list(
        pedido.items.all()
    )

    # =========================================================================
    # 1. CORREO CLIENTE
    # =========================================================================

    destinatarios = (
        obtener_emails_confirmacion(
            pedido
        )
    )

    cliente_correcto = False

    if not destinatarios:
        logger.error(
            (
                "No se pudo enviar la confirmación "
                "del pedido %s: "
                "no tiene correos destinatarios."
            ),
            pedido.numero,
        )

    else:

        contexto_cliente = {
            "pedido": pedido,
            "items": items,
        }

        asunto_cliente = (
            f"Pago confirmado · "
            f"Pedido {pedido.numero}"
        )

        try:
            contenido_texto = render_to_string(
                "emails/pago_confirmado.txt",
                contexto_cliente,
            )

            contenido_html = render_to_string(
                "emails/pago_confirmado.html",
                contexto_cliente,
            )

        except Exception as error:
            logger.exception(
                (
                    "No se pudieron renderizar "
                    "las plantillas del correo "
                    "del pedido %s: %s"
                ),
                pedido.numero,
                error,
            )

        else:

            for email in destinatarios:

                registro_id = reservar_envio(
                    pedido=pedido,
                    email=email,
                    tipo=TIPO_CONFIRMACION_PAGO,
                )

                if registro_id is None:
                    continue

                try:
                    mensaje = EmailMultiAlternatives(
                        subject=asunto_cliente,
                        body=contenido_texto,
                        from_email=(
                            settings
                            .DEFAULT_FROM_EMAIL
                        ),
                        to=[email],
                    )

                    mensaje.attach_alternative(
                        contenido_html,
                        "text/html",
                    )

                    cantidad_enviada = (
                        mensaje.send(
                            fail_silently=False,
                        )
                    )

                    if cantidad_enviada != 1:
                        raise RuntimeError(
                            (
                                "El backend SMTP "
                                "no confirmó el envío."
                            )
                        )

                except Exception as error:

                    marcar_correo_error(
                        registro_id,
                        error,
                    )

                    logger.exception(
                        (
                            "Error enviando confirmación "
                            "del pedido %s a %s: %s"
                        ),
                        pedido.numero,
                        email,
                        error,
                    )

                else:

                    marcar_correo_enviado(
                        registro_id,
                    )

                    logger.info(
                        (
                            "Confirmación del pedido "
                            "%s enviada a %s."
                        ),
                        pedido.numero,
                        email,
                    )

            # -----------------------------------------------------------------
            # COMPROBAR CLIENTE
            # -----------------------------------------------------------------

            cantidad_enviados = (
                CorreoPedido.objects
                .filter(
                    pedido=pedido,
                    tipo=TIPO_CONFIRMACION_PAGO,
                    email__in=destinatarios,
                    estado=(
                        CorreoPedido
                        .ESTADO_ENVIADO
                    ),
                )
                .count()
            )

            cliente_correcto = (
                cantidad_enviados
                == len(destinatarios)
            )

            if cliente_correcto:

                ahora = timezone.now()

                Pedido.objects.filter(
                    pk=pedido.pk,
                ).update(
                    correo_confirmacion_enviado=True,
                    fecha_correo_confirmacion=(
                        pedido.fecha_correo_confirmacion
                        or ahora
                    ),
                )

                logger.info(
                    (
                        "Todos los correos del cliente "
                        "del pedido %s fueron enviados "
                        "correctamente."
                    ),
                    pedido.numero,
                )

            else:
                logger.warning(
                    (
                        "El pedido %s tiene correos "
                        "del cliente pendientes o "
                        "con error. Enviados: %s de %s."
                    ),
                    pedido.numero,
                    cantidad_enviados,
                    len(destinatarios),
                )

    # =========================================================================
    # 2. CORREO ADMINISTRADORES
    # =========================================================================

    admin_correcto = (
        enviar_notificacion_administradores(
            pedido=pedido,
            items=items,
        )
    )

    # =========================================================================
    # RESULTADO FINAL
    # =========================================================================

    if (
        cliente_correcto
        and admin_correcto
    ):
        logger.info(
            (
                "Proceso completo de correos "
                "del pedido %s finalizado "
                "correctamente."
            ),
            pedido.numero,
        )

        return True

    logger.warning(
        (
            "Proceso de correos del pedido %s "
            "finalizó parcialmente. "
            "Cliente OK: %s | "
            "Administradores OK: %s"
        ),
        pedido.numero,
        cliente_correcto,
        admin_correcto,
    )

    return False