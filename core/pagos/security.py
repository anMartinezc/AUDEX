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


def validar_firma_mercado_pago(
    request,
) -> bool:
    """
    Valida la autenticidad del Webhook utilizando
    el validador oficial de Mercado Pago.

    Mercado Pago utiliza:

        x-signature
        x-request-id
        data.id
        MERCADOPAGO_WEBHOOK_SECRET
    """

    # =========================================================================
    # SECRET
    # =========================================================================

    secret = str(
        getattr(
            settings,
            "MERCADOPAGO_WEBHOOK_SECRET",
            "",
        )
        or ""
    ).strip()

    if not secret:

        logger.error(
            "MERCADOPAGO_WEBHOOK_SECRET no está configurado."
        )

        return False

    # =========================================================================
    # HEADERS
    # =========================================================================

    x_signature = str(
        request.headers.get(
            "x-signature",
            "",
        )
        or ""
    ).strip()

    x_request_id = str(
        request.headers.get(
            "x-request-id",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # DATA.ID
    # =========================================================================
    #
    # Debe salir del query parameter firmado por Mercado Pago.
    #
    # Ejemplo:
    #
    # /webhooks/mercadopago/?data.id=123456&type=payment
    #
    # =========================================================================

    data_id = str(
        request.GET.get(
            "data.id",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # DIAGNÓSTICO SEGURO
    # =========================================================================

    logger.info(
        (
            "Validando firma Mercado Pago. "
            "data_id=%s "
            "x_signature=%s "
            "x_request_id=%s "
            "secret_configurado=%s."
        ),
        data_id or "vacío",
        bool(x_signature),
        bool(x_request_id),
        bool(secret),
    )

    # =========================================================================
    # DATOS OBLIGATORIOS
    # =========================================================================

    if not x_signature:

        logger.warning(
            "Webhook Mercado Pago sin x-signature."
        )

        return False

    if not x_request_id:

        logger.warning(
            "Webhook Mercado Pago sin x-request-id."
        )

        return False

    if not data_id:

        logger.warning(
            (
                "Webhook Mercado Pago sin "
                "query parameter data.id."
            )
        )

        return False

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

    except InvalidWebhookSignatureError:

        logger.warning(
            (
                "Firma Mercado Pago inválida. "
                "Resource ID=%s "
                "Request ID=%s."
            ),
            data_id,
            x_request_id,
        )

        return False

    except Exception as error:

        logger.exception(
            (
                "Error inesperado validando "
                "firma Mercado Pago. "
                "Resource ID=%s. Error=%s"
            ),
            data_id,
            error,
        )

        return False

    # =========================================================================
    # CORRECTO
    # =========================================================================

    logger.info(
        (
            "Firma Mercado Pago validada "
            "correctamente. "
            "Resource ID=%s "
            "Request ID=%s."
        ),
        data_id,
        x_request_id,
    )

    return True