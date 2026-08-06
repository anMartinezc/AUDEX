
import hashlib
import hmac

from django.conf import settings


def validar_firma_mercado_pago(request, data_id):
    x_signature = request.headers.get("X-Signature", "")
    x_request_id = request.headers.get("X-Request-Id", "")

    if not x_signature or not x_request_id or not data_id:
        return False

    partes = {}

    for elemento in x_signature.split(","):
        if "=" in elemento:
            clave, valor = elemento.split("=", 1)
            partes[clave.strip()] = valor.strip()

    timestamp = partes.get("ts")
    firma_recibida = partes.get("v1")

    if not timestamp or not firma_recibida:
        return False

    manifest = (
        f"id:{str(data_id).lower()};"
        f"request-id:{x_request_id};"
        f"ts:{timestamp};"
    )

    firma_calculada = hmac.new(
        settings.MERCADOPAGO_WEBHOOK_SECRET.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        firma_calculada,
        firma_recibida,
    )