from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import requests

from django.conf import settings
from django.urls import NoReverseMatch, reverse


class MercadoPagoError(Exception):
    """Error controlado de la integración con Mercado Pago."""


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
            "No está configurado MERCADOPAGO_ACCESS_TOKEN."
        )

    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _precio_entero(valor: Decimal | int | float | str) -> int:
    try:
        return int(
            Decimal(str(valor)).quantize(Decimal("1"))
        )
    except Exception as error:
        raise MercadoPagoError(
            f"Precio inválido: {valor}."
        ) from error


def _es_url_publica_https(base_url: str) -> bool:
    url = urlparse(base_url)
    hostname = (url.hostname or "").lower()

    return (
        url.scheme == "https"
        and bool(hostname)
        and hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
    )


def crear_preferencia(
    *,
    request,
    pedido,
) -> dict[str, Any]:
    """
    Crea una preferencia de Checkout Pro.
    """

    base_url = (
        getattr(settings, "SITE_URL", "")
        or request.build_absolute_uri("/")
    ).strip().rstrip("/")

    items: list[dict[str, Any]] = []

    for item in pedido.items.select_related("producto").all():
        cantidad = int(item.cantidad)
        precio_unitario = _precio_entero(
            item.precio_unitario
        )

        if cantidad <= 0:
            raise MercadoPagoError(
                f"La cantidad de {item.nombre_producto} "
                "debe ser mayor que cero."
            )

        if precio_unitario <= 0:
            raise MercadoPagoError(
                f"El precio de {item.nombre_producto} "
                "debe ser mayor que cero."
            )

        descripcion = str(
            item.nombre_producto
        ).strip()

        producto = item.producto

        if producto:
            descripcion_corta = getattr(
                producto,
                "descripcion_corta",
                "",
            )

            if descripcion_corta:
                descripcion = str(
                    descripcion_corta
                ).strip()

        datos_item: dict[str, Any] = {
            "id": str(
                item.producto_id or item.id
            ),
            "title": str(
                item.nombre_producto
            ).strip()[:120],
            "description": descripcion[:250],
            "currency_id": "CLP",
            "quantity": cantidad,
            "unit_price": precio_unitario,
        }

        # Mercado Pago debe poder acceder públicamente a la imagen.
        if producto:
            imagen = str(
                getattr(
                    producto,
                    "imagen_mostrable",
                    "",
                )
                or ""
            ).strip()

            if imagen.startswith("https://"):
                datos_item["picture_url"] = imagen

        items.append(datos_item)

    if not items:
        raise MercadoPagoError(
            "El pedido no contiene productos."
        )

    despacho = _precio_entero(
        getattr(pedido, "despacho", 0)
    )

    if despacho > 0:
        items.append({
            "id": "despacho",
            "title": "Despacho",
            "description": "Costo de despacho del pedido",
            "currency_id": "CLP",
            "quantity": 1,
            "unit_price": despacho,
        })

    preference_data: dict[str, Any] = {
        "items": items,
        "payer": {
            "name": str(
                pedido.nombre
            ).strip(),
            "surname": str(
                pedido.apellido
            ).strip(),
            "email": str(
                pedido.email
            ).strip(),
            "phone": {
                "number": str(
                    pedido.telefono
                ).strip(),
            },
        },
        "external_reference": str(
            pedido.numero
        ),
        "statement_descriptor": "AUDEX",
        "metadata": {
            "pedido_id": str(pedido.id),
            "pedido_numero": str(
                pedido.numero
            ),
        },
    }

    # En localhost Mercado Pago no puede llamar al webhook.
    if _es_url_publica_https(base_url):
        try:
            success_path = reverse(
                "core:mercadopago_retorno_exitoso",
                kwargs={
                    "numero": pedido.numero,
                },
            )

            pending_path = reverse(
                "core:mercadopago_retorno_pendiente",
                kwargs={
                    "numero": pedido.numero,
                },
            )

            failure_path = reverse(
                "core:mercadopago_retorno_fallido",
                kwargs={
                    "numero": pedido.numero,
                },
            )

            webhook_path = reverse(
                "core:mercadopago_webhook",
            )

        except NoReverseMatch as error:
            raise MercadoPagoError(
                "No se encontraron las URLs de retorno "
                "o webhook de Mercado Pago."
            ) from error

        preference_data["back_urls"] = {
            "success": f"{base_url}{success_path}",
            "pending": f"{base_url}{pending_path}",
            "failure": f"{base_url}{failure_path}",
        }

        preference_data["auto_return"] = "approved"

        preference_data["notification_url"] = (
            f"{base_url}{webhook_path}"
        )

    try:
        respuesta = requests.post(
            f"{_api_url()}/checkout/preferences",
            headers=_headers(),
            json=preference_data,
            timeout=20,
        )

    except requests.Timeout as error:
        raise MercadoPagoError(
            "Mercado Pago demoró demasiado en responder."
        ) from error

    except requests.RequestException as error:
        raise MercadoPagoError(
            "No fue posible conectar con Mercado Pago."
        ) from error

    if not respuesta.ok:
        raise MercadoPagoError(
            "Mercado Pago rechazó la preferencia. "
            f"HTTP {respuesta.status_code}. "
            f"Respuesta: {respuesta.text[:1000]}"
        )

    try:
        datos = respuesta.json()
    except ValueError as error:
        raise MercadoPagoError(
            "Mercado Pago devolvió una respuesta inválida."
        ) from error

    checkout_url = (
        datos.get("init_point")
        or datos.get("sandbox_init_point")
    )

    if not checkout_url:
        raise MercadoPagoError(
            "Mercado Pago no devolvió una URL de pago."
        )

    # Guarda la preferencia solo cuando el campo existe.
    if hasattr(pedido, "preference_id"):
        pedido.preference_id = datos.get("id", "")
        pedido.save(
            update_fields=["preference_id"]
        )

    return {
        "preference_id": datos.get("id", ""),
        "checkout_url": checkout_url,
        "sandbox_url": datos.get(
            "sandbox_init_point"
        ),
        "respuesta": datos,
    }


def obtener_pago(
    payment_id: str,
) -> dict[str, Any]:
    """
    Consulta un pago directamente en Mercado Pago.
    """

    payment_id = str(payment_id).strip()

    if not payment_id:
        raise MercadoPagoError(
            "El identificador del pago está vacío."
        )

    try:
        respuesta = requests.get(
            f"{_api_url()}/v1/payments/{payment_id}",
            headers=_headers(),
            timeout=20,
        )

    except requests.Timeout as error:
        raise MercadoPagoError(
            "Mercado Pago demoró demasiado en responder."
        ) from error

    except requests.RequestException as error:
        raise MercadoPagoError(
            "No fue posible consultar el pago."
        ) from error

    if not respuesta.ok:
        raise MercadoPagoError(
            "Mercado Pago no devolvió el pago. "
            f"HTTP {respuesta.status_code}. "
            f"Respuesta: {respuesta.text[:1000]}"
        )

    try:
        return respuesta.json()
    except ValueError as error:
        raise MercadoPagoError(
            "Mercado Pago devolvió un pago inválido."
        ) from error







def obtener_orden_comercial(
    merchant_order_id: str,
) -> dict[str, Any]:
    """
    Consulta una merchant order de Mercado Pago.
    """

    merchant_order_id = str(
        merchant_order_id
    ).strip()

    if not merchant_order_id:
        raise MercadoPagoError(
            "El identificador de la orden comercial está vacío."
        )

    try:
        respuesta = requests.get(
            (
                f"{_api_url()}/merchant_orders/"
                f"{merchant_order_id}"
            ),
            headers=_headers(),
            timeout=20,
        )

    except requests.Timeout as error:
        raise MercadoPagoError(
            "Mercado Pago demoró demasiado "
            "en consultar la orden."
        ) from error

    except requests.RequestException as error:
        raise MercadoPagoError(
            "No fue posible consultar "
            "la orden de Mercado Pago."
        ) from error

    if not respuesta.ok:
        raise MercadoPagoError(
            "Mercado Pago no devolvió la orden comercial. "
            f"HTTP {respuesta.status_code}. "
            f"Respuesta: {respuesta.text[:1000]}"
        )

    try:
        return respuesta.json()
    except ValueError as error:
        raise MercadoPagoError(
            "Mercado Pago devolvió una orden inválida."
        ) from error