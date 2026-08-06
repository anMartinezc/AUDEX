from django.core.exceptions import ValidationError
from django.db import transaction


class StockError(Exception):
    """Error controlado al confirmar el stock de un pedido."""


@transaction.atomic
def confirmar_stock_pedido(pedido) -> None:
    """
    Descuenta el stock de todos los productos de un pedido.

    La función bloquea los productos durante la operación para evitar
    que dos compras descuenten simultáneamente la última unidad.

    El control principal de idempotencia se realiza mediante el campo
    pedido.stock_descontado.
    """

    # Evita descontar nuevamente el stock.
    if getattr(pedido, "stock_descontado", False):
        return

    items = list(
        pedido.items
        .select_related("producto")
        .all()
    )

    if not items:
        raise StockError(
            "El pedido no contiene productos."
        )

    # Obtiene dinámicamente el modelo relacionado con producto.
    campo_producto = (
        pedido.items.model
        ._meta
        .get_field("producto")
    )

    ModeloProducto = (
        campo_producto.remote_field.model
    )

    producto_ids = [
        item.producto_id
        for item in items
        if item.producto_id
    ]

    if not producto_ids:
        raise StockError(
            "Los productos del pedido no son válidos."
        )

    # Bloquea las filas de productos hasta finalizar la transacción.
    productos_bloqueados = {
        producto.pk: producto
        for producto in (
            ModeloProducto.objects
            .select_for_update()
            .filter(pk__in=producto_ids)
        )
    }

    # Primero validamos todo el stock.
    # No se descuenta nada hasta comprobar todos los productos.
    for item in items:
        producto = productos_bloqueados.get(
            item.producto_id
        )

        if producto is None:
            raise StockError(
                "No se encontró uno de los productos "
                f"del pedido {pedido.numero}."
            )

        if not hasattr(producto, "stock"):
            raise StockError(
                f"El producto {producto} no tiene "
                "un campo llamado stock."
            )

        try:
            cantidad = int(item.cantidad)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise StockError(
                f"La cantidad de {producto} no es válida."
            ) from error

        if cantidad <= 0:
            raise StockError(
                f"La cantidad de {producto} "
                "debe ser mayor que cero."
            )

        stock_actual = int(
            producto.stock
        )

        if stock_actual < cantidad:
            raise StockError(
                "Stock insuficiente para "
                f"{producto}. "
                f"Disponible: {stock_actual}; "
                f"solicitado: {cantidad}."
            )

    # Después de validar todos los productos,
    # realizamos el descuento.
    for item in items:
        producto = productos_bloqueados[
            item.producto_id
        ]

        cantidad = int(
            item.cantidad
        )

        producto.stock -= cantidad

        campos_actualizados = [
            "stock",
        ]

        # Actualiza automáticamente un campo modificado/actualizado
        # cuando existe en el modelo Producto.
        if hasattr(
            producto,
            "actualizado",
        ):
            campos_actualizados.append(
                "actualizado"
            )

        producto.save(
            update_fields=campos_actualizados
        )