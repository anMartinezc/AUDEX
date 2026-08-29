import logging

from django.conf import settings

from mercadopago.webhook import (
    InvalidWebhookSignatureError,
    WebhookSignatureValidator,
)


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDAR FIRMA WEBHOOK MERCADO PAGO
# =============================================================================


def validar_firma_mercado_pago(request) -> bool:
    """
    Valida la autenticidad de un Webhook de Mercado Pago utilizando
    el validador oficial del SDK.

    Mercado Pago puede utilizar para construir la firma:

        x-signature
        x-request-id
        data.id
        MERCADOPAGO_WEBHOOK_SECRET

    IMPORTANTE:

    - x-signature sí es obligatorio para validar la firma.
    - x-request-id puede no estar presente.
    - data.id puede no estar presente en determinados casos.
    - No debemos obtener data.id desde el JSON para validar la firma.
      Se utiliza el query parameter recibido en la URL.
    """

    # =========================================================================
    # SECRET
    # =========================================================================

    secret = getattr(
        settings,
        "MERCADOPAGO_WEBHOOK_SECRET",
        None,
    )

    if secret is not None:
        secret = str(secret).strip()

    if not secret:
        logger.error(
            "MERCADOPAGO_WEBHOOK_SECRET no está configurado."
        )
        return False

    # =========================================================================
    # HEADERS
    # =========================================================================
    #
    # Django trata los headers sin distinguir mayúsculas/minúsculas.
    #
    # Ejemplo Mercado Pago:
    #
    # X-Signature: ts=1234567890,v1=...
    # X-Request-Id: abc-def-123
    #
    # =========================================================================

    x_signature = request.headers.get(
        "x-signature"
    )

    x_request_id = request.headers.get(
        "x-request-id"
    )

    if x_signature is not None:
        x_signature = str(x_signature).strip() or None

    if x_request_id is not None:
        x_request_id = str(x_request_id).strip() or None

    # =========================================================================
    # DATA.ID
    # =========================================================================
    #
    # Mercado Pago normalmente envía:
    #
    # /webhooks/mercadopago/?data.id=123456&type=payment
    #
    # Para compatibilidad también comprobamos "data_id", aunque "data.id"
    # es el nombre utilizado actualmente en la documentación para Python.
    #
    # IMPORTANTE:
    # NO utilizar request.body["data"]["id"] para validar la firma.
    #
    # =========================================================================

    data_id = request.GET.get("data.id")

    if data_id is None:
        data_id = request.GET.get("data_id")

    if data_id is not None:
        data_id = str(data_id).strip() or None

    # =========================================================================
    # DIAGNÓSTICO SEGURO
    # =========================================================================
    #
    # No registramos:
    #
    # - secret completo
    # - firma completa
    #
    # Solo indicamos si existen.
    #
    # =========================================================================

    logger.info(
        (
            "Validando firma Mercado Pago. "
            "path=%s "
            "data_id=%s "
            "x_signature_presente=%s "
            "x_request_id_presente=%s "
            "secret_configurado=%s."
        ),
        request.path,
        data_id or "vacío",
        bool(x_signature),
        bool(x_request_id),
        bool(secret),
    )

    # =========================================================================
    # X-SIGNATURE
    # =========================================================================
    #
    # Este sí es indispensable.
    #
    # Aunque el SDK también detecta su ausencia, dejamos este control
    # explícito para obtener un log más claro.
    #
    # =========================================================================

    if not x_signature:
        logger.warning(
            (
                "Webhook Mercado Pago rechazado: "
                "no contiene x-signature. "
                "Path=%s."
            ),
            request.path,
        )
        return False

    # =========================================================================
    # ADVERTENCIAS
    # =========================================================================
    #
    # NO rechazamos inmediatamente si faltan estos valores.
    #
    # El SDK oficial permite x_request_id=None y data_id=None y construye
    # el manifest omitiendo esas partes cuando corresponda.
    #
    # =========================================================================

    if not x_request_id:
        logger.warning(
            (
                "Webhook Mercado Pago sin x-request-id. "
                "Se intentará validar igualmente."
            )
        )

    if not data_id:
        logger.warning(
            (
                "Webhook Mercado Pago sin data.id en query string. "
                "Se intentará validar igualmente."
            )
        )

    # =========================================================================
    # VALIDACIÓN OFICIAL
    # =========================================================================

    try:
        WebhookSignatureValidator.validate(
            x_signature,
            x_request_id,
            data_id,
            secret,
        )

    except InvalidWebhookSignatureError as error:
        # ---------------------------------------------------------------------
        # Las versiones actuales del SDK incluyen información del motivo:
        #
        # MissingSignatureHeader
        # MalformedSignatureHeader
        # MissingTimestamp
        # MissingHash
        # SignatureMismatch
        # TimestampOutOfTolerance
        #
        # Utilizamos getattr para mantener compatibilidad con versiones
        # anteriores del SDK.
        # ---------------------------------------------------------------------

        reason = getattr(
            error,
            "reason",
            None,
        )

        reason_value = getattr(
            reason,
            "value",
            None,
        )

        if not reason_value:
            reason_value = str(reason or "desconocido")

        timestamp = getattr(
            error,
            "timestamp",
            None,
        )

        logger.warning(
            (
                "Firma Mercado Pago inválida. "
                "motivo=%s "
                "resource_id=%s "
                "request_id=%s "
                "timestamp=%s."
            ),
            reason_value,
            data_id or "vacío",
            x_request_id or "vacío",
            timestamp or "vacío",
        )

        return False

    except (TypeError, ValueError) as error:
        logger.exception(
            (
                "Error de configuración o parámetros "
                "validando firma Mercado Pago. "
                "resource_id=%s "
                "request_id=%s "
                "error=%s"
            ),
            data_id or "vacío",
            x_request_id or "vacío",
            error,
        )

        return False

    except Exception as error:
        logger.exception(
            (
                "Error inesperado validando firma Mercado Pago. "
                "resource_id=%s "
                "request_id=%s "
                "error=%s"
            ),
            data_id or "vacío",
            x_request_id or "vacío",
            error,
        )

        return False

    # =========================================================================
    # CORRECTO
    # =========================================================================

    logger.info(
        (
            "Firma Mercado Pago validada correctamente. "
            "resource_id=%s "
            "request_id=%s."
        ),
        data_id or "vacío",
        x_request_id or "vacío",
    )

    return True