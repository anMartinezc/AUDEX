from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import requests

from django.conf import settings
from django.urls import NoReverseMatch, reverse


# =============================================================================
# EXCEPCIÓN
# =============================================================================


class MercadoPagoError(Exception):
    """
    Error controlado de la integración
    con Mercado Pago.
    """


# =============================================================================
# CONFIGURACIÓN
# =============================================================================


def _api_url() -> str:
    return getattr(
        settings,
        "MERCADOPAGO_API_URL",
        "https://api.mercadopago.com",
    ).rstrip("/")


def _headers() -> dict[str, str]:
    access_token = getattr(
        settings,
        "MERCADOPAGO_ACCESS_TOKEN",
        "",
    ).strip()

    if not access_token:
        raise MercadoPagoError(
            (
                "No está configurado "
                "MERCADOPAGO_ACCESS_TOKEN."
            )
        )

    return {
        "Authorization": (
            f"Bearer {access_token}"
        ),
        "Content-Type": (
            "application/json"
        ),
        "Accept": (
            "application/json"
        ),
    }


# =============================================================================
# UTILIDADES
# =============================================================================


def _precio_entero(
    valor: Decimal | int | float | str,
) -> int:
    try:
        return int(
            Decimal(
                str(valor)
            ).quantize(
                Decimal("1")
            )
        )

    except Exception as error:
        raise MercadoPagoError(
            f"Precio inválido: {valor}."
        ) from error


def _decimal_seguro(
    valor,
) -> Decimal:
    try:
        return Decimal(
            str(
                valor
                or 0
            )
        )

    except Exception:
        return Decimal(
            "0"
        )


def _es_url_publica_https(
    base_url: str,
) -> bool:
    url = urlparse(
        base_url
    )

    hostname = (
        url.hostname
        or ""
    ).lower()

    return (
        url.scheme == "https"
        and bool(
            hostname
        )
        and hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
    )


def _obtener_notification_url(
    *,
    base_url: str,
    webhook_path: str,
) -> str:
    """
    Obtiene la URL pública que Mercado Pago utilizará
    para enviar notificaciones Webhook.

    Prioridad:

    1. MERCADOPAGO_NOTIFICATION_URL configurada en settings / Railway.
    2. SITE_URL + reverse("core:mercadopago_webhook").

    En producción debe ser una URL HTTPS pública.
    """

    notification_url = str(
        getattr(
            settings,
            "MERCADOPAGO_NOTIFICATION_URL",
            "",
        )
        or ""
    ).strip()

    if not notification_url:
        notification_url = (
            f"{base_url}"
            f"{webhook_path}"
        )

    if not _es_url_publica_https(
        notification_url
    ):
        raise MercadoPagoError(
            (
                "MERCADOPAGO_NOTIFICATION_URL debe ser "
                "una URL pública HTTPS válida."
            )
        )

    return notification_url


# =============================================================================
# CALCULAR TOTAL DEL PEDIDO
# =============================================================================


def _obtener_total_final_pedido(
    pedido,
) -> int:
    """
    Obtiene el TOTAL FINAL que debe enviarse
    al método de pago.

    La fuente de verdad debe ser pedido.total.

    Ese total ya debe contener:

        subtotal productos
        - descuento adicional
        + despacho
        = total final

    Nunca reconstruimos el importe en Mercado Pago
    sumando nuevamente los productos.
    """

    total = _decimal_seguro(
        getattr(
            pedido,
            "total",
            0,
        )
    )

    if total <= 0:
        raise MercadoPagoError(
            (
                "El pedido no tiene un total "
                "válido para iniciar el pago."
            )
        )

    total_entero = (
        _precio_entero(
            total
        )
    )

    if total_entero <= 0:
        raise MercadoPagoError(
            (
                "El total final del pedido "
                "debe ser mayor que cero."
            )
        )

    return total_entero


# =============================================================================
# DESCRIPCIÓN DEL PEDIDO
# =============================================================================


def _crear_descripcion_pedido(
    pedido,
) -> str:
    """
    Crea una descripción corta para Mercado Pago
    sin usarla para recalcular el precio.
    """

    partes = []

    items = (
        pedido.items
        .select_related(
            "producto"
        )
        .all()
    )

    for item in items:
        cantidad = int(
            item.cantidad
            or 0
        )

        if cantidad <= 0:
            continue

        nombre = str(
            item.nombre_producto
            or "Producto"
        ).strip()

        if cantidad > 1:
            partes.append(
                f"{nombre} x{cantidad}"
            )

        else:
            partes.append(
                nombre
            )

    descripcion = ", ".join(
        partes
    )

    if not descripcion:
        descripcion = (
            f"Pedido {pedido.numero}"
        )

    return descripcion[:250]


# =============================================================================
# CREAR PREFERENCIA
# =============================================================================


def crear_preferencia(
    *,
    request,
    pedido,
) -> dict[str, Any]:
    """
    Crea una preferencia de Checkout Pro.

    IMPORTANTE:

    Mercado Pago recibe exactamente pedido.total.

    No reconstruimos el total utilizando los
    PedidoItem porque eso puede ignorar:

    - códigos de descuento;
    - descuentos fijos;
    - descuentos porcentuales;
    - despacho;
    - promociones;
    - redondeos.

    pedido.total es la fuente definitiva.
    """

    # =========================================================================
    # URL BASE
    # =========================================================================

    base_url = (
        getattr(
            settings,
            "SITE_URL",
            "",
        )
        or request.build_absolute_uri(
            "/"
        )
    ).strip().rstrip("/")

    # =========================================================================
    # TOTAL FINAL
    # =========================================================================

    total_final = (
        _obtener_total_final_pedido(
            pedido
        )
    )

    # =========================================================================
    # DATOS ECONÓMICOS PARA METADATA
    # =========================================================================

    subtotal = _precio_entero(
        getattr(
            pedido,
            "subtotal",
            0,
        )
        or 0
    )

    descuento = _precio_entero(
        getattr(
            pedido,
            "descuento",
            0,
        )
        or 0
    )

    despacho = _precio_entero(
        getattr(
            pedido,
            "despacho",
            0,
        )
        or 0
    )

    # =========================================================================
    # VALIDACIÓN DE SEGURIDAD
    # =========================================================================
    #
    # Verificamos:
    #
    # subtotal
    # - descuento
    # + despacho
    #
    # contra pedido.total.
    #
    # No usamos este cálculo para cobrar.
    # Solo permite detectar inconsistencias.
    # =========================================================================

    total_calculado = (
        subtotal
        - descuento
        + despacho
    )

    if total_calculado < 0:
        raise MercadoPagoError(
            (
                "El cálculo económico del pedido "
                "es inválido."
            )
        )

    # =========================================================================
    # DESCRIPCIÓN
    # =========================================================================

    descripcion = (
        _crear_descripcion_pedido(
            pedido
        )
    )

    # =========================================================================
    # ITEM DE MERCADO PAGO
    # =========================================================================
    #
    # Utilizamos UN SOLO ITEM.
    #
    # Esto garantiza que Mercado Pago cobre exactamente
    # el mismo total mostrado en tu checkout.
    #
    # =========================================================================

    items: list[
        dict[str, Any]
    ] = [
        {
            "id": (
                f"pedido-{pedido.numero}"
            ),

            "title": (
                f"Pedido AUDEX {pedido.numero}"
            )[:120],

            "description": (
                descripcion
            ),

            "currency_id": (
                "CLP"
            ),

            "quantity": 1,

            "unit_price": (
                total_final
            ),
        }
    ]

    # =========================================================================
    # PREFERENCIA
    # =========================================================================

    preference_data: dict[
        str,
        Any,
    ] = {
        "items": items,

        "payer": {
            "name": str(
                pedido.nombre
                or ""
            ).strip(),

            "surname": str(
                pedido.apellido
                or ""
            ).strip(),

            "email": str(
                pedido.email
                or ""
            ).strip(),

            "phone": {
                "number": str(
                    pedido.telefono
                    or ""
                ).strip(),
            },
        },

        "external_reference": str(
            pedido.numero
        ),

        "statement_descriptor": (
            "AUDEX"
        ),

        # =====================================================================
        # METADATA
        # =====================================================================
        #
        # Guardamos el desglose para poder revisar
        # posteriormente qué se cobró.
        #
        # =====================================================================

        "metadata": {
            "pedido_id": str(
                pedido.id
            ),

            "pedido_numero": str(
                pedido.numero
            ),

            "subtotal": (
                subtotal
            ),

            "descuento": (
                descuento
            ),

            "despacho": (
                despacho
            ),

            "total": (
                total_final
            ),
        },
    }

    # =========================================================================
    # URLS DE RETORNO / WEBHOOK
    # =========================================================================

    if _es_url_publica_https(
        base_url
    ):
        try:
            success_path = reverse(
                "core:mercadopago_retorno_exitoso",
                kwargs={
                    "numero": (
                        pedido.numero
                    ),
                },
            )

            pending_path = reverse(
                "core:mercadopago_retorno_pendiente",
                kwargs={
                    "numero": (
                        pedido.numero
                    ),
                },
            )

            failure_path = reverse(
                "core:mercadopago_retorno_fallido",
                kwargs={
                    "numero": (
                        pedido.numero
                    ),
                },
            )

            webhook_path = reverse(
                "core:mercadopago_webhook",
            )

        except NoReverseMatch as error:
            raise MercadoPagoError(
                (
                    "No se encontraron las URLs "
                    "de retorno o webhook "
                    "de Mercado Pago."
                )
            ) from error

        preference_data[
            "back_urls"
        ] = {
            "success": (
                f"{base_url}"
                f"{success_path}"
            ),

            "pending": (
                f"{base_url}"
                f"{pending_path}"
            ),

            "failure": (
                f"{base_url}"
                f"{failure_path}"
            ),
        }

        preference_data[
            "auto_return"
        ] = "approved"

        preference_data[
            "notification_url"
        ] = (
            _obtener_notification_url(
                base_url=base_url,
                webhook_path=webhook_path,
            )
        )

    # =========================================================================
    # CREAR PREFERENCIA EN MERCADO PAGO
    # =========================================================================

    try:
        respuesta = requests.post(
            (
                f"{_api_url()}"
                "/checkout/preferences"
            ),

            headers=(
                _headers()
            ),

            json=(
                preference_data
            ),

            timeout=20,
        )

    except requests.Timeout as error:
        raise MercadoPagoError(
            (
                "Mercado Pago demoró demasiado "
                "en responder."
            )
        ) from error

    except requests.RequestException as error:
        raise MercadoPagoError(
            (
                "No fue posible conectar "
                "con Mercado Pago."
            )
        ) from error

    # =========================================================================
    # ERROR HTTP
    # =========================================================================

    if not respuesta.ok:
        raise MercadoPagoError(
            (
                "Mercado Pago rechazó "
                "la preferencia. "
                f"HTTP {respuesta.status_code}. "
                f"Respuesta: "
                f"{respuesta.text[:1000]}"
            )
        )

    # =========================================================================
    # JSON
    # =========================================================================

    try:
        datos = (
            respuesta.json()
        )

    except ValueError as error:
        raise MercadoPagoError(
            (
                "Mercado Pago devolvió "
                "una respuesta inválida."
            )
        ) from error

    # =========================================================================
    # CHECKOUT URL
    # =========================================================================

    checkout_url = (
        datos.get(
            "init_point"
        )
        or datos.get(
            "sandbox_init_point"
        )
    )

    if not checkout_url:
        raise MercadoPagoError(
            (
                "Mercado Pago no devolvió "
                "una URL de pago."
            )
        )

    # =========================================================================
    # GUARDAR PREFERENCE ID
    # =========================================================================

    if hasattr(
        pedido,
        "preference_id",
    ):
        pedido.preference_id = (
            datos.get(
                "id",
                "",
            )
            or ""
        )

        pedido.save(
            update_fields=[
                "preference_id",
            ]
        )

    # =========================================================================
    # RESULTADO
    # =========================================================================

    return {
        "preference_id": (
            datos.get(
                "id",
                "",
            )
        ),

        "checkout_url": (
            checkout_url
        ),

        "sandbox_url": (
            datos.get(
                "sandbox_init_point"
            )
        ),

        "respuesta": (
            datos
        ),
    }


# =============================================================================
# CONSULTAR PAGO
# =============================================================================


def obtener_pago(
    payment_id: str,
) -> dict[str, Any]:
    """
    Consulta un pago directamente
    en Mercado Pago.
    """

    payment_id = str(
        payment_id
    ).strip()

    if not payment_id:
        raise MercadoPagoError(
            (
                "El identificador del pago "
                "está vacío."
            )
        )

    try:
        respuesta = requests.get(
            (
                f"{_api_url()}"
                f"/v1/payments/{payment_id}"
            ),

            headers=(
                _headers()
            ),

            timeout=20,
        )

    except requests.Timeout as error:
        raise MercadoPagoError(
            (
                "Mercado Pago demoró demasiado "
                "en responder."
            )
        ) from error

    except requests.RequestException as error:
        raise MercadoPagoError(
            (
                "No fue posible consultar "
                "el pago."
            )
        ) from error

    if not respuesta.ok:
        raise MercadoPagoError(
            (
                "Mercado Pago no devolvió "
                "el pago. "
                f"HTTP {respuesta.status_code}. "
                f"Respuesta: "
                f"{respuesta.text[:1000]}"
            )
        )

    try:
        return respuesta.json()

    except ValueError as error:
        raise MercadoPagoError(
            (
                "Mercado Pago devolvió "
                "un pago inválido."
            )
        ) from error


# =============================================================================
# CONSULTAR MERCHANT ORDER
# =============================================================================


def obtener_orden_comercial(
    merchant_order_id: str,
) -> dict[str, Any]:
    """
    Consulta una merchant order
    de Mercado Pago.
    """

    merchant_order_id = str(
        merchant_order_id
    ).strip()

    if not merchant_order_id:
        raise MercadoPagoError(
            (
                "El identificador de la "
                "orden comercial está vacío."
            )
        )

    try:
        respuesta = requests.get(
            (
                f"{_api_url()}"
                "/merchant_orders/"
                f"{merchant_order_id}"
            ),

            headers=(
                _headers()
            ),

            timeout=20,
        )

    except requests.Timeout as error:
        raise MercadoPagoError(
            (
                "Mercado Pago demoró demasiado "
                "en consultar la orden."
            )
        ) from error

    except requests.RequestException as error:
        raise MercadoPagoError(
            (
                "No fue posible consultar "
                "la orden de Mercado Pago."
            )
        ) from error

    if not respuesta.ok:
        raise MercadoPagoError(
            (
                "Mercado Pago no devolvió "
                "la orden comercial. "
                f"HTTP {respuesta.status_code}. "
                f"Respuesta: "
                f"{respuesta.text[:1000]}"
            )
        )

    try:
        return respuesta.json()

    except ValueError as error:
        raise MercadoPagoError(
            (
                "Mercado Pago devolvió "
                "una orden inválida."
            )
        ) from error