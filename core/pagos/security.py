import hashlib
import hmac
import logging

from importlib.metadata import (
    PackageNotFoundError,
    version,
)

from django.conf import settings

from mercadopago.webhook import (
    InvalidWebhookSignatureError,
    WebhookSignatureValidator,
)


logger = logging.getLogger(__name__)


# =============================================================================
# VERSIÓN SDK MERCADO PAGO
# =============================================================================

try:
    MERCADOPAGO_SDK_VERSION = version(
        "mercadopago"
    )

except PackageNotFoundError:
    MERCADOPAGO_SDK_VERSION = "desconocida"


# =============================================================================
# EXTRAER X-SIGNATURE
# =============================================================================


def _extraer_componentes_firma(
    x_signature,
):
    """
    Extrae de:

        ts=1234567890,v1=abcdef...

    los valores:

        timestamp
        firma v1

    No realiza ninguna validación criptográfica.
    """

    if not x_signature:
        return None, None

    componentes = {}

    for parte in str(
        x_signature
    ).split(","):

        clave, separador, valor = (
            parte.partition("=")
        )

        if not separador:
            continue

        clave = clave.strip().lower()
        valor = valor.strip()

        if not clave or not valor:
            continue

        componentes[clave] = valor

    return (
        componentes.get("ts"),
        componentes.get("v1"),
    )


# =============================================================================
# VALIDACIÓN HMAC MANUAL DE DIAGNÓSTICO
# =============================================================================


def _validar_hmac_manual(
    *,
    x_signature,
    x_request_id,
    data_id,
    secret,
):
    """
    Reproduce manualmente el HMAC utilizado por Mercado Pago.

    IMPORTANTE:

    Esta función se utiliza solamente como diagnóstico.

    La validación oficial continúa siendo realizada mediante
    WebhookSignatureValidator.

    Nunca registra:

    - secret;
    - firma esperada;
    - firma calculada.
    """

    timestamp, firma_v1 = (
        _extraer_componentes_firma(
            x_signature
        )
    )

    if not timestamp:
        return False, "missing_timestamp"

    if not firma_v1:
        return False, "missing_v1"

    # =========================================================================
    # MANIFEST
    # =========================================================================
    #
    # Mercado Pago firma:
    #
    # id:<data.id>;
    # request-id:<x-request-id>;
    # ts:<timestamp>;
    #
    # Si data.id o x-request-id no existen,
    # sus segmentos se omiten.
    # =========================================================================

    partes_manifest = []

    if data_id:
        partes_manifest.append(
            f"id:{data_id}"
        )

    if x_request_id:
        partes_manifest.append(
            f"request-id:{x_request_id}"
        )

    partes_manifest.append(
        f"ts:{timestamp}"
    )

    manifest = (
        ";".join(
            partes_manifest
        )
        + ";"
    )

    # =========================================================================
    # HMAC SHA256
    # =========================================================================

    firma_calculada = hmac.new(
        secret.encode(
            "utf-8"
        ),
        manifest.encode(
            "utf-8"
        ),
        hashlib.sha256,
    ).hexdigest()

    coincide = hmac.compare_digest(
        firma_calculada,
        firma_v1,
    )

    return coincide, "ok"


# =============================================================================
# VALIDAR FIRMA WEBHOOK MERCADO PAGO
# =============================================================================


def validar_firma_mercado_pago(
    request,
) -> bool:
    """
    Valida la autenticidad de un Webhook de Mercado Pago
    utilizando el SDK oficial.

    Valores utilizados:

        x-signature
        x-request-id
        data.id
        MERCADOPAGO_WEBHOOK_SECRET

    La comprobación HMAC manual se utiliza únicamente
    como diagnóstico cuando el SDK rechaza una firma.

    Nunca se procesa una notificación cuya firma
    no haya sido aceptada por el SDK oficial.
    """

    # =========================================================================
    # SECRET
    # =========================================================================

    secret = getattr(
        settings,
        "MERCADOPAGO_WEBHOOK_SECRET",
        "",
    )

    secret = str(
        secret
        or ""
    ).strip()

    if not secret:

        logger.error(
            (
                "MERCADOPAGO_WEBHOOK_SECRET "
                "no está configurado."
            )
        )

        return False

    # =========================================================================
    # HEADERS
    # =========================================================================

    x_signature = request.headers.get(
        "x-signature"
    )

    x_request_id = request.headers.get(
        "x-request-id"
    )

    if x_signature is not None:

        x_signature = (
            str(
                x_signature
            ).strip()
            or None
        )

    if x_request_id is not None:

        x_request_id = (
            str(
                x_request_id
            ).strip()
            or None
        )

    # =========================================================================
    # DATA.ID
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # Utilizamos EXCLUSIVAMENTE:
    #
    #     ?data.id=...
    #
    # No:
    #
    #     data_id
    #
    # No:
    #
    #     request.body["data"]["id"]
    #
    # Esto replica exactamente el ejemplo oficial de Mercado Pago.
    # =========================================================================

    data_id = request.GET.get(
        "data.id"
    )

    if data_id is not None:

        data_id = (
            str(
                data_id
            ).strip()
            or None
        )

    # =========================================================================
    # COMPONENTES X-SIGNATURE
    # =========================================================================

    timestamp, firma_v1 = (
        _extraer_componentes_firma(
            x_signature
        )
    )

    # =========================================================================
    # DIAGNÓSTICO SEGURO
    # =========================================================================
    #
    # NO registramos:
    #
    # - secret;
    # - x-signature completa;
    # - v1;
    # - HMAC calculado.
    #
    # =========================================================================

    logger.info(
        (
            "Validando firma Mercado Pago. "
            "path=%s "
            "data_id=%s "
            "x_signature_presente=%s "
            "x_request_id_presente=%s "
            "timestamp_presente=%s "
            "v1_presente=%s "
            "secret_configurado=%s "
            "secret_largo=%s "
            "sdk_version=%s."
        ),
        request.path,
        data_id or "vacío",
        bool(
            x_signature
        ),
        bool(
            x_request_id
        ),
        bool(
            timestamp
        ),
        bool(
            firma_v1
        ),
        bool(
            secret
        ),
        len(
            secret
        ),
        MERCADOPAGO_SDK_VERSION,
    )

    # =========================================================================
    # X-SIGNATURE OBLIGATORIO
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

    if not x_request_id:

        logger.warning(
            (
                "Webhook Mercado Pago "
                "sin x-request-id. "
                "El SDK intentará validar "
                "igualmente."
            )
        )

    if not data_id:

        logger.warning(
            (
                "Webhook Mercado Pago "
                "sin data.id en query string. "
                "El SDK intentará validar "
                "igualmente."
            )
        )

    # =========================================================================
    # VALIDACIÓN OFICIAL SDK
    # =========================================================================

    try:

        WebhookSignatureValidator.validate(
            x_signature,
            x_request_id,
            data_id,
            secret,
        )

    # =========================================================================
    # FIRMA RECHAZADA POR SDK
    # =========================================================================

    except InvalidWebhookSignatureError as error:

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

            reason_value = str(
                reason
                or "desconocido"
            )

        timestamp_error = getattr(
            error,
            "timestamp",
            None,
        )

        # =====================================================================
        # DIAGNÓSTICO HMAC MANUAL
        # =====================================================================
        #
        # Esto NO autoriza la petición.
        #
        # Solo sirve para determinar si:
        #
        # SDK falla + HMAC manual falla
        #     -> probablemente Secret/configuración.
        #
        # SDK falla + HMAC manual coincide
        #     -> investigar SDK/versión.
        #
        # =====================================================================

        manual_coincide = False
        manual_motivo = "no_ejecutado"

        try:

            (
                manual_coincide,
                manual_motivo,
            ) = _validar_hmac_manual(
                x_signature=x_signature,
                x_request_id=x_request_id,
                data_id=data_id,
                secret=secret,
            )

        except Exception:

            logger.exception(
                (
                    "Error realizando diagnóstico "
                    "HMAC Mercado Pago. "
                    "resource_id=%s."
                ),
                data_id or "vacío",
            )

            manual_coincide = False
            manual_motivo = (
                "diagnostico_error"
            )

        logger.warning(
            (
                "Firma Mercado Pago inválida. "
                "motivo_sdk=%s "
                "resource_id=%s "
                "request_id=%s "
                "timestamp=%s "
                "hmac_manual_coincide=%s "
                "hmac_manual_motivo=%s "
                "sdk_version=%s."
            ),
            reason_value,
            data_id or "vacío",
            x_request_id or "vacío",
            (
                timestamp_error
                or timestamp
                or "vacío"
            ),
            manual_coincide,
            manual_motivo,
            MERCADOPAGO_SDK_VERSION,
        )

        return False

    # =========================================================================
    # ERROR DE PARÁMETROS
    # =========================================================================

    except (
        TypeError,
        ValueError,
    ) as error:

        logger.exception(
            (
                "Error de configuración o parámetros "
                "validando firma Mercado Pago. "
                "resource_id=%s "
                "request_id=%s "
                "sdk_version=%s "
                "error=%s."
            ),
            data_id or "vacío",
            x_request_id or "vacío",
            MERCADOPAGO_SDK_VERSION,
            error,
        )

        return False

    # =========================================================================
    # ERROR INESPERADO
    # =========================================================================

    except Exception as error:

        logger.exception(
            (
                "Error inesperado validando "
                "firma Mercado Pago. "
                "resource_id=%s "
                "request_id=%s "
                "sdk_version=%s "
                "error=%s."
            ),
            data_id or "vacío",
            x_request_id or "vacío",
            MERCADOPAGO_SDK_VERSION,
            error,
        )

        return False

    # =========================================================================
    # FIRMA CORRECTA
    # =========================================================================

    logger.info(
        (
            "Firma Mercado Pago validada "
            "correctamente. "
            "resource_id=%s "
            "request_id=%s "
            "sdk_version=%s."
        ),
        data_id or "vacío",
        x_request_id or "vacío",
        MERCADOPAGO_SDK_VERSION,
    )

    return True