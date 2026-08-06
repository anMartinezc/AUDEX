from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from core.models import Pedido
from core.services.stock import confirmar_stock_pedido

from core.models import *

class ConfirmacionPagoError(Exception):
    """Error controlado al confirmar un pago."""


@transaction.atomic
def confirmar_pago_mercadopago(
    pago: dict,
) -> tuple[Pedido, bool]:
    """
    Confirma un pago aprobado de Mercado Pago.

    La función es idempotente:
    - No confirma dos veces el mismo pedido.
    - No descuenta stock dos veces.
    - No inicia la postventa dos veces.

    Retorna:
        tuple[Pedido, bool]:
            - Pedido confirmado.
            - True si se actualizó en esta ejecución.
            - False si ya estaba aprobado.
    """

    payment_id = str(
        pago.get("id") or ""
    ).strip()

    estado_mp = str(
        pago.get("status") or ""
    ).strip().lower()

    referencia = str(
        pago.get("external_reference") or ""
    ).strip()

    status_detail = str(
        pago.get("status_detail") or ""
    ).strip()

    payment_type = str(
        pago.get("payment_type_id") or ""
    ).strip()

    moneda = str(
        pago.get("currency_id") or ""
    ).strip().upper()

    # ------------------------------------------------------------------
    # VALIDACIONES BÁSICAS
    # ------------------------------------------------------------------

    if not payment_id:
        raise ConfirmacionPagoError(
            "El pago no contiene identificador."
        )

    if estado_mp != "approved":
        raise ConfirmacionPagoError(
            "El pago todavía no está aprobado. "
            f"Estado recibido: {estado_mp or 'desconocido'}."
        )

    if not referencia:
        raise ConfirmacionPagoError(
            "El pago no contiene external_reference."
        )

    if moneda != "CLP":
        raise ConfirmacionPagoError(
            "La moneda recibida no corresponde a CLP. "
            f"Moneda recibida: {moneda or 'desconocida'}."
        )

    # ------------------------------------------------------------------
    # BLOQUEO DEL PEDIDO
    # ------------------------------------------------------------------

    try:
        pedido = (
            Pedido.objects
            .select_for_update()
            .get(numero=referencia)
        )

    except Pedido.DoesNotExist as error:
        raise ConfirmacionPagoError(
            f"No existe el pedido {referencia}."
        ) from error

    # ------------------------------------------------------------------
    # IDEMPOTENCIA
    # ------------------------------------------------------------------

    if (
        pedido.estado_pago
        == Pedido.EstadoPago.APROBADO
    ):
        if (
            pedido.mercadopago_payment_id
            and pedido.mercadopago_payment_id
            != payment_id
        ):
            raise ConfirmacionPagoError(
                "El pedido ya está aprobado con otro "
                "identificador de Mercado Pago."
            )

        return pedido, False

    # Evita asociar un mismo pago a dos pedidos diferentes.
    pago_duplicado = (
        Pedido.objects
        .filter(
            mercadopago_payment_id=payment_id,
        )
        .exclude(pk=pedido.pk)
        .exists()
    )

    if pago_duplicado:
        raise ConfirmacionPagoError(
            "El pago de Mercado Pago ya está asociado "
            "a otro pedido."
        )

    # ------------------------------------------------------------------
    # VALIDACIÓN DEL MONTO
    # ------------------------------------------------------------------

    try:
        monto_pagado = Decimal(
            str(
                pago.get(
                    "transaction_amount"
                )
            )
        )

        monto_pedido = Decimal(
            str(pedido.total)
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as error:
        raise ConfirmacionPagoError(
            "No fue posible validar el monto pagado."
        ) from error

    if monto_pagado != monto_pedido:
        raise ConfirmacionPagoError(
            "El monto pagado no coincide con el pedido. "
            f"Monto Mercado Pago: ${monto_pagado}; "
            f"total del pedido: ${monto_pedido}."
        )

    # ------------------------------------------------------------------
    # DESCUENTO DE STOCK
    # ------------------------------------------------------------------

    if not pedido.stock_descontado:
        confirmar_stock_pedido(
            pedido
        )

        pedido.stock_descontado = True

    # ------------------------------------------------------------------
    # ACTUALIZACIÓN DEL PEDIDO
    # ------------------------------------------------------------------

    pedido.estado_pago = (
        Pedido.EstadoPago.APROBADO
    )

    pedido.pagado = True

    # Tu lista ESTADOS no contiene "pagado".
    # El estado general correcto después del pago es "confirmado".
    estado_anterior = pedido.estado
    pedido.estado = "confirmado"

    pedido.fecha_pago = (
        pedido.fecha_pago
        or timezone.now()
    )

    pedido.mercadopago_payment_id = (
        payment_id
    )

    pedido.mercadopago_status = (
        estado_mp
    )

    pedido.mercadopago_status_detail = (
        status_detail
    )

    pedido.mercadopago_payment_type = (
        payment_type
    )

    pedido.mercadopago_transaction_amount = (
        monto_pagado
    )

    pedido.save(
        update_fields=[
            "estado_pago",
            "pagado",
            "estado",
            "fecha_pago",
            "mercadopago_payment_id",
            "mercadopago_status",
            "mercadopago_status_detail",
            "mercadopago_payment_type",
            "mercadopago_transaction_amount",
            "stock_descontado",
            "actualizado",
        ]
    )


    


    if estado_anterior != "confirmado":
        PedidoHistorialEstado.objects.create(
            pedido=pedido,
            estado_anterior=estado_anterior,
            estado_nuevo="confirmado",
            comentario=(
                "Pago confirmado automáticamente "
                "por Mercado Pago."
            ),
        )





    # El correo y la boleta se ejecutan únicamente
    # cuando la transacción se confirmó correctamente.
    transaction.on_commit(
        lambda pedido_id=pedido.pk: (
            iniciar_postventa(
                pedido_id
            )
        )
    )

    return pedido, True

def iniciar_postventa(pedido_id):
    """
    Ejecuta correo y boleta después del commit.
    """

    try:
        from core.services.postventa import (
            emitir_boleta_y_enviar_correo,
        )

        emitir_boleta_y_enviar_correo(
            pedido_id
        )

    except Exception as error:
        # Durante el desarrollo deja evidencia en consola.
        # En producción debería ejecutarse con Celery.
        print(
            "ERROR EN POSTVENTA:",
            repr(error),
        )