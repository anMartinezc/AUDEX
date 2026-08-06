# tributario/provider.py

import base64

import requests
from django.conf import settings

from .base import EmisorDTE, ResultadoDTE


class ProveedorDTE(EmisorDTE):
    def emitir_boleta(self, pedido):
        payload = {
            "documento": "boleta",
            "referencia_interna": str(pedido.id_publico),
            "receptor": {
                "nombre": pedido.nombre_cliente,
                "rut": pedido.rut_cliente or None,
                "email": pedido.email,
            },
            "items": [
                {
                    "codigo": item.sku,
                    "nombre": item.nombre,
                    "cantidad": item.cantidad,
                    "precio_unitario": int(item.precio_unitario),
                    "total": int(item.subtotal),
                }
                for item in pedido.items.all()
            ],
            "total": int(pedido.total),
            "medio_pago": "mercado_pago",
        }

        response = requests.post(
            f"{settings.DTE_PROVIDER_URL}/boletas",
            headers={
                "Authorization": (
                    f"Bearer {settings.DTE_PROVIDER_TOKEN}"
                ),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        return ResultadoDTE(
            folio=str(data["folio"]),
            tipo=str(data.get("tipo", "boleta")),
            estado=data["estado"],
            pdf=base64.b64decode(data["pdf_base64"]),
            xml=(
                base64.b64decode(data["xml_base64"])
                if data.get("xml_base64")
                else None
            ),
        )