from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.dateparse import parse_datetime

from core.models import ComprobantePago


def _decimal_seguro(valor):
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _fecha_segura(valor):
    if not valor:
        return None

    if hasattr(valor, "isoformat"):
        return valor

    try:
        return parse_datetime(str(valor))
    except (TypeError, ValueError):
        return None


def _ultimos_cuatro(valor):
    if not valor:
        return ""

    valor = str(valor).strip()

    return valor[-4:]


# ============================================================
# WEBPAY
# ============================================================
@transaction.atomic
def guardar_comprobante_webpay(
    pedido,
    respuesta,
):
    """
    Guarda o actualiza el comprobante de un pago
    Webpay confirmado correctamente por Transbank.

    Reglas:

    - solo acepta pagos autorizados;
    - response_code debe ser 0;
    - status debe ser AUTHORIZED;
    - guarda únicamente información necesaria;
    - conserva solo los últimos 4 dígitos de la tarjeta;
    - evita guardar objetos datetime directamente en JSONField;
    - es idempotente mediante update_or_create().
    """

    # =========================================================================
    # VALIDACIONES INICIALES
    # =========================================================================

    if pedido is None:
        return None

    if not isinstance(
        respuesta,
        dict,
    ):
        return None

    # =========================================================================
    # RESPONSE CODE
    # =========================================================================

    response_code_raw = (
        respuesta.get(
            "response_code"
        )
    )

    try:

        response_code = int(
            response_code_raw
        )

    except (
        TypeError,
        ValueError,
    ):

        response_code = None

    # =========================================================================
    # STATUS
    # =========================================================================

    status = str(
        respuesta.get(
            "status",
            "",
        )
        or ""
    ).strip().upper()

    # =========================================================================
    # VALIDAR APROBACIÓN
    # =========================================================================

    aprobado = bool(
        response_code == 0
        and status == "AUTHORIZED"
    )

    if not aprobado:
        return None

    # =========================================================================
    # BUY ORDER
    # =========================================================================

    buy_order = str(
        respuesta.get(
            "buy_order",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # CÓDIGO DE AUTORIZACIÓN
    # =========================================================================

    authorization_code = str(
        respuesta.get(
            "authorization_code",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # TIPO DE PAGO
    # =========================================================================

    payment_type_code = str(
        respuesta.get(
            "payment_type_code",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # TARJETA
    # =========================================================================

    card_detail = (
        respuesta.get(
            "card_detail"
        )
        or {}
    )

    if not isinstance(
        card_detail,
        dict,
    ):
        card_detail = {}

    ultimos_4 = (
        _ultimos_cuatro(
            card_detail.get(
                "card_number"
            )
        )
    )

    # =========================================================================
    # MONTO
    # =========================================================================

    monto = (
        _decimal_seguro(
            respuesta.get(
                "amount"
            )
        )
    )

    if monto <= 0:
        return None

    # =========================================================================
    # FECHA DE PAGO
    # =========================================================================

    transaction_date_raw = (
        respuesta.get(
            "transaction_date"
        )
    )

    fecha_pago = (
        _fecha_segura(
            transaction_date_raw
        )
    )

    # =========================================================================
    # FECHA SEGURA PARA JSON
    # =========================================================================
    #
    # JSONField no debe recibir directamente un datetime.
    #
    # Guardamos la fecha como ISO 8601.
    # =========================================================================

    if transaction_date_raw:

        if hasattr(
            transaction_date_raw,
            "isoformat",
        ):

            transaction_date_json = (
                transaction_date_raw
                .isoformat()
            )

        else:

            transaction_date_json = str(
                transaction_date_raw
            )

    else:

        transaction_date_json = None

    # =========================================================================
    # CUOTAS
    # =========================================================================

    cuotas_raw = (
        respuesta.get(
            "installments_number"
        )
    )

    try:

        cuotas = int(
            cuotas_raw
            or 0
        )

        if cuotas < 0:
            cuotas = 0

    except (
        TypeError,
        ValueError,
    ):

        cuotas = 0

    # =========================================================================
    # IDENTIFICADOR DE TRANSACCIÓN
    # =========================================================================
    #
    # Priorizamos el código de autorización entregado por Transbank.
    #
    # Como respaldo utilizamos buy_order.
    # =========================================================================

    id_transaccion = (
        authorization_code
        or buy_order
    )

    # =========================================================================
    # DATOS SEGUROS DE RESPALDO
    # =========================================================================
    #
    # No almacenamos:
    #
    # - número completo de tarjeta;
    # - secretos;
    # - API Keys;
    # - respuesta completa de Transbank.
    #
    # =========================================================================

    datos_seguros = {
        "response_code": (
            response_code
        ),

        "status": (
            status
        ),

        "buy_order": (
            buy_order
        ),

        "authorization_code": (
            authorization_code
        ),

        "payment_type_code": (
            payment_type_code
        ),

        "transaction_date": (
            transaction_date_json
        ),

        "amount": str(
            monto
        ),

        "installments_number": (
            cuotas
        ),

        "card_last4": (
            ultimos_4
        ),
    }

    # =========================================================================
    # CREAR / ACTUALIZAR COMPROBANTE
    # =========================================================================
    #
    # Pedido -> OneToOneField
    #
    # Si el retorno se procesa nuevamente:
    #
    # - no crea otro comprobante;
    # - actualiza el existente.
    #
    # =========================================================================

    comprobante, _ = (
        ComprobantePago.objects
        .update_or_create(
            pedido=pedido,

            defaults={
                "proveedor": (
                    ComprobantePago
                    .Proveedor
                    .WEBPAY
                ),

                "estado": (
                    ComprobantePago
                    .Estado
                    .APROBADO
                ),

                "estado_proveedor": (
                    status
                ),

                "id_transaccion": (
                    id_transaccion
                ),

                "referencia": (
                    buy_order
                ),

                "codigo_autorizacion": (
                    authorization_code
                ),

                "monto": (
                    monto
                ),

                "moneda": (
                    "CLP"
                ),

                "fecha_pago": (
                    fecha_pago
                ),

                "metodo_pago": (
                    "Webpay"
                ),

                "tipo_pago": (
                    payment_type_code
                ),

                "ultimos_4": (
                    ultimos_4
                ),

                "cuotas": (
                    cuotas
                ),

                "datos_respaldo": (
                    datos_seguros
                ),
            },
        )
    )

    return comprobante
# ============================================================
# MERCADO PAGO
# ============================================================



@transaction.atomic
def guardar_comprobante_mercadopago(
    pedido,
    pago,
):
    """
    Guarda o actualiza el comprobante de un pago
    aprobado por Mercado Pago.

    Reglas:

    - solo acepta pagos approved;
    - valida el payload;
    - guarda únicamente información necesaria;
    - conserva solo los últimos 4 dígitos;
    - evita objetos datetime dentro de JSONField;
    - es idempotente mediante update_or_create().
    """

    # =========================================================================
    # VALIDACIONES INICIALES
    # =========================================================================

    if pedido is None:
        return None

    if not isinstance(
        pago,
        dict,
    ):
        return None

    # =========================================================================
    # STATUS
    # =========================================================================

    status = str(
        pago.get(
            "status",
            "",
        )
        or ""
    ).strip().lower()

    if status != "approved":
        return None

    # =========================================================================
    # PAYMENT ID
    # =========================================================================

    payment_id = str(
        pago.get(
            "id",
            "",
        )
        or ""
    ).strip()

    if not payment_id:
        return None

    # =========================================================================
    # EXTERNAL REFERENCE
    # =========================================================================

    referencia = str(
        pago.get(
            "external_reference",
            "",
        )
        or ""
    ).strip()

    if not referencia:
        return None

    # =========================================================================
    # MONTO
    # =========================================================================

    monto = _decimal_seguro(
        pago.get(
            "transaction_amount"
        )
    )

    if monto <= 0:
        return None

    # =========================================================================
    # MONEDA
    # =========================================================================

    moneda = str(
        pago.get(
            "currency_id",
            "CLP",
        )
        or "CLP"
    ).strip().upper()

    # La validación principal de CLP ya se realiza
    # antes de llamar esta función.
    #
    # Aquí mantenemos igualmente un valor normalizado.
    if not moneda:
        moneda = "CLP"

    # =========================================================================
    # TARJETA
    # =========================================================================

    card = (
        pago.get(
            "card"
        )
        or {}
    )

    if not isinstance(
        card,
        dict,
    ):
        card = {}

    ultimos_4 = _ultimos_cuatro(
        card.get(
            "last_four_digits"
        )
    )

    # =========================================================================
    # FECHA DEL PAGO
    # =========================================================================

    date_approved_raw = (
        pago.get(
            "date_approved"
        )
    )

    fecha_pago = _fecha_segura(
        date_approved_raw
    )

    # =========================================================================
    # FECHA SEGURA PARA JSONFIELD
    # =========================================================================

    if date_approved_raw:

        if hasattr(
            date_approved_raw,
            "isoformat",
        ):

            date_approved_json = (
                date_approved_raw
                .isoformat()
            )

        else:

            date_approved_json = str(
                date_approved_raw
            )

    else:

        date_approved_json = None

    # =========================================================================
    # CUOTAS
    # =========================================================================

    cuotas_raw = (
        pago.get(
            "installments"
        )
    )

    try:

        cuotas = int(
            cuotas_raw
            or 0
        )

        if cuotas < 0:
            cuotas = 0

    except (
        TypeError,
        ValueError,
    ):

        cuotas = 0

    # =========================================================================
    # MÉTODO DE PAGO
    # =========================================================================

    payment_method_id = str(
        pago.get(
            "payment_method_id",
            "",
        )
        or ""
    ).strip()

    payment_type_id = str(
        pago.get(
            "payment_type_id",
            "",
        )
        or ""
    ).strip()

    status_detail = str(
        pago.get(
            "status_detail",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # DATOS SEGUROS DE RESPALDO
    # =========================================================================
    #
    # No almacenamos la respuesta completa de Mercado Pago.
    #
    # Solo conservamos la información necesaria para
    # identificar y respaldar el pago.
    # =========================================================================

    datos_seguros = {
        "id": (
            payment_id
        ),

        "status": (
            status
        ),

        "status_detail": (
            status_detail
        ),

        "external_reference": (
            referencia
        ),

        "transaction_amount": str(
            monto
        ),

        "currency_id": (
            moneda
        ),

        "date_approved": (
            date_approved_json
        ),

        "payment_method_id": (
            payment_method_id
        ),

        "payment_type_id": (
            payment_type_id
        ),

        "installments": (
            cuotas
        ),

        "card_last4": (
            ultimos_4
        ),
    }

    # =========================================================================
    # CREAR / ACTUALIZAR COMPROBANTE
    # =========================================================================

    comprobante, _ = (
        ComprobantePago.objects
        .update_or_create(
            pedido=pedido,

            defaults={
                "proveedor": (
                    ComprobantePago
                    .Proveedor
                    .MERCADO_PAGO
                ),

                "estado": (
                    ComprobantePago
                    .Estado
                    .APROBADO
                ),

                "estado_proveedor": (
                    status
                ),

                "id_transaccion": (
                    payment_id
                ),

                "referencia": (
                    referencia
                ),

                "codigo_autorizacion": (
                    ""
                ),

                "monto": (
                    monto
                ),

                "moneda": (
                    moneda
                ),

                "fecha_pago": (
                    fecha_pago
                ),

                "metodo_pago": (
                    payment_method_id
                    or "Mercado Pago"
                ),

                "tipo_pago": (
                    payment_type_id
                ),

                "ultimos_4": (
                    ultimos_4
                ),

                "cuotas": (
                    cuotas
                ),

                "datos_respaldo": (
                    datos_seguros
                ),
            },
        )
    )

    return comprobante
