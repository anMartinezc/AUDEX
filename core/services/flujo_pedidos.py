from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import (
    Pedido,
    PedidoHistorialEstado,
)


TRANSICIONES_PEDIDO = {
    "pendiente": (
        "confirmado",
        "cancelado",
    ),
    "confirmado": (
        "preparacion",
        "cancelado",
    ),
    "preparacion": (
        "listo",
        "cancelado",
    ),
    "listo": (
        "enviado",
        "cancelado",
    ),
    "enviado": (
        "entregado",
    ),
    "entregado": (),
    "cancelado": (),
}


FLUJO_CLIENTE = [
    {
        "clave": "pendiente",
        "titulo": "Pedido recibido",
        "descripcion": (
            "Registramos correctamente tu pedido."
        ),
        "icono": "bi-receipt",
    },
    {
        "clave": "confirmado",
        "titulo": "Pago confirmado",
        "descripcion": (
            "El pago fue confirmado correctamente."
        ),
        "icono": "bi-credit-card-2-front",
    },
    {
        "clave": "preparacion",
        "titulo": "En preparación",
        "descripcion": (
            "Estamos preparando tus productos."
        ),
        "icono": "bi-box-seam",
    },
    {
        "clave": "listo",
        "titulo": "Listo para despacho",
        "descripcion": (
            "Tu pedido está listo para ser enviado."
        ),
        "icono": "bi-check2-circle",
    },
    {
        "clave": "enviado",
        "titulo": "Pedido enviado",
        "descripcion": (
            "Tu pedido está en camino."
        ),
        "icono": "bi-truck",
    },
    {
        "clave": "entregado",
        "titulo": "Pedido entregado",
        "descripcion": (
            "El pedido fue entregado."
        ),
        "icono": "bi-house-check",
    },
]


BANDEJAS_PEDIDOS = {
    "principal": (
        "pendiente",
        "confirmado",
    ),
    "operacion": (
        "preparacion",
        "listo",
    ),
    "despacho": (
        "enviado",
    ),
    "cerrados": (
        "entregado",
        "cancelado",
    ),
}


def estados_permitidos(
    pedido: Pedido,
) -> tuple[str, ...]:
    return TRANSICIONES_PEDIDO.get(
        pedido.estado,
        (),
    )


@transaction.atomic
def cambiar_estado_pedido(
    *,
    pedido: Pedido,
    nuevo_estado: str,
    usuario=None,
    comentario: str = "",
) -> Pedido:
    """
    Cambia el estado y registra el movimiento.

    No permite retroceder ni saltar fases.
    """

    pedido_bloqueado = (
        Pedido.objects
        .select_for_update()
        .get(pk=pedido.pk)
    )

    estado_anterior = pedido_bloqueado.estado
    nuevo_estado = str(nuevo_estado).strip()

    if nuevo_estado == estado_anterior:
        return pedido_bloqueado

    permitidos = estados_permitidos(
        pedido_bloqueado
    )

    if nuevo_estado not in permitidos:
        raise ValidationError(
            "No se puede cambiar el pedido desde "
            f"'{pedido_bloqueado.get_estado_display()}' "
            f"hacia '{nuevo_estado}'."
        )

    pedido_bloqueado.estado = nuevo_estado
    pedido_bloqueado.save(
        update_fields=[
            "estado",
            "actualizado",
        ]
    )

    PedidoHistorialEstado.objects.create(
        pedido=pedido_bloqueado,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
        comentario=str(comentario).strip(),
        usuario=usuario,
    )

    return pedido_bloqueado


def construir_timeline(
    pedido: Pedido,
) -> list[dict]:
    """
    Construye los pasos que se mostrarán al cliente.
    """

    if pedido.estado == "cancelado":
        return [
            {
                "clave": "cancelado",
                "titulo": "Pedido cancelado",
                "descripcion": (
                    "El pedido fue cancelado."
                ),
                "icono": "bi-x-circle",
                "completado": True,
                "activo": True,
                "fecha": pedido.actualizado,
            }
        ]

    claves = [
        paso["clave"]
        for paso in FLUJO_CLIENTE
    ]

    try:
        indice_actual = claves.index(
            pedido.estado
        )
    except ValueError:
        indice_actual = 0

    fechas = {
        "pendiente": pedido.creado,
    }

    for movimiento in (
        pedido.historial_estados.all()
    ):
        fechas[movimiento.estado_nuevo] = (
            movimiento.creado
        )

    timeline = []

    for indice, paso in enumerate(
        FLUJO_CLIENTE
    ):
        timeline.append({
            **paso,
            "completado": (
                indice <= indice_actual
            ),
            "activo": (
                indice == indice_actual
            ),
            "fecha": fechas.get(
                paso["clave"]
            ),
        })

    return timeline