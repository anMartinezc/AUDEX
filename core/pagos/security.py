import hashlib
import hmac
import logging

from django.conf import settings


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDAR FIRMA WEBHOOK MERCADO PAGO
# =============================================================================


def validar_firma_mercado_pago(
    request,
) -> bool:
    """
    Valida la firma HMAC-SHA256 enviada por Mercado Pago.

    Mercado Pago firma utilizando:

        data.id        -> query parameter
        x-request-id   -> header
        ts             -> contenido en x-signature
        secret         -> MERCADOPAGO_WEBHOOK_SECRET

    Manifest esperado:

        id:<data.id>;
        request-id:<x-request-id>;
        ts:<timestamp>;

    IMPORTANTE:

    data.id debe obtenerse desde request.GET,
    no desde el JSON del body.
    """

    # =========================================================================
    # SECRET CONFIGURADO
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
            (
                "No está configurado "
                "MERCADOPAGO_WEBHOOK_SECRET."
            )
        )

        return False

    # =========================================================================
    # HEADERS MERCADO PAGO
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
    # MUY IMPORTANTE:
    #
    # Mercado Pago exige utilizar el data.id recibido
    # como QUERY PARAMETER.
    #
    # Ejemplo:
    #
    # ?data.id=174874615035&type=payment
    #
    # No utilizar aquí:
    #
    # request.body["data"]["id"]
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
    # VALIDAR DATOS NECESARIOS
    # =========================================================================

    if not x_signature:

        logger.warning(
            (
                "Webhook Mercado Pago sin "
                "header x-signature."
            )
        )

        return False

    if not x_request_id:

        logger.warning(
            (
                "Webhook Mercado Pago sin "
                "header x-request-id."
            )
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
    # PARSEAR X-SIGNATURE
    # =========================================================================
    #
    # Ejemplo:
    #
    # ts=1704908010,
    # v1=618c85345248dd820d...
    #
    # =========================================================================

    partes = {}

    for elemento in (
        x_signature.split(",")
    ):

        elemento = (
            elemento.strip()
        )

        if not elemento:
            continue

        if "=" not in elemento:
            continue

        clave, valor = (
            elemento.split(
                "=",
                1,
            )
        )

        clave = (
            clave
            .strip()
            .lower()
        )

        valor = (
            valor
            .strip()
        )

        if clave and valor:
            partes[
                clave
            ] = valor

    # =========================================================================
    # TIMESTAMP / FIRMA
    # =========================================================================

    timestamp = str(
        partes.get(
            "ts",
            "",
        )
        or ""
    ).strip()

    firma_recibida = str(
        partes.get(
            "v1",
            "",
        )
        or ""
    ).strip().lower()

    if not timestamp:

        logger.warning(
            (
                "Webhook Mercado Pago "
                "sin timestamp en x-signature."
            )
        )

        return False

    if not firma_recibida:

        logger.warning(
            (
                "Webhook Mercado Pago "
                "sin firma v1."
            )
        )

        return False

    # =========================================================================
    # NORMALIZAR DATA.ID
    # =========================================================================
    #
    # Mercado Pago normaliza el identificador
    # en minúsculas antes de construir el manifest.
    #
    # Para IDs numéricos no cambia absolutamente nada.
    #
    # =========================================================================

    data_id_normalizado = (
        data_id.lower()
    )

    # =========================================================================
    # MANIFEST
    # =========================================================================

    manifest = (
        f"id:{data_id_normalizado};"
        f"request-id:{x_request_id};"
        f"ts:{timestamp};"
    )

    # =========================================================================
    # CALCULAR HMAC SHA256
    # =========================================================================

    try:

        firma_calculada = (
            hmac.new(
                secret.encode(
                    "utf-8"
                ),
                manifest.encode(
                    "utf-8"
                ),
                hashlib.sha256,
            )
            .hexdigest()
            .lower()
        )

    except Exception as error:

        logger.exception(
            (
                "Error calculando firma "
                "Mercado Pago: %s"
            ),
            error,
        )

        return False

    # =========================================================================
    # COMPARACIÓN SEGURA
    # =========================================================================

    firma_valida = (
        hmac.compare_digest(
            firma_calculada,
            firma_recibida,
        )
    )

    # =========================================================================
    # LOG
    # =========================================================================
    #
    # NO mostramos:
    #
    # - secret;
    # - firma calculada;
    # - firma recibida.
    #
    # =========================================================================

    if firma_valida:

        logger.info(
            (
                "Firma webhook Mercado Pago "
                "validada correctamente. "
                "Resource ID=%s "
                "Request ID=%s."
            ),
            data_id,
            x_request_id,
        )

    else:

        logger.warning(
            (
                "Firma webhook Mercado Pago "
                "inválida. "
                "Resource ID=%s "
                "Request ID=%s."
            ),
            data_id,
            x_request_id,
        )

    return firma_valida