from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from django.db import transaction

from core.models import (
    Pedido,
    PedidoHistorialEstado,
    PedidoItem,
    Producto,
)

from core.services.descuentos import (
    DescuentoError,
    reservar_codigo_descuento,
    resolver_descuento,
)
import logging


logger = logging.getLogger(__name__)


META_DESPACHO_GRATIS = Decimal(
    "50000"
)

COSTO_DESPACHO = Decimal(
    "4990"
)


@transaction.atomic
def procesar_pedido_checkout(
    request,
    form,
    carrito,
):
    """
    Crea el pedido definitivo a partir del carrito.

    También:

    - Valida productos y cantidades.
    - Bloquea los productos durante la transacción.
    - Comprueba el stock disponible.
    - Valida el código general o personal.
    - Impide que un RUT repita un código.
    - Reserva el código hasta confirmar el pago.
    - Guarda el detalle histórico del descuento.
    - Guarda explícitamente el email ingresado en checkout.
    """

    # =========================================================================
    # VALIDAR CARRITO
    # =========================================================================

    if not carrito:
        raise ValueError(
            "El carrito está vacío."
        )

    # =========================================================================
    # IDS DE PRODUCTOS
    # =========================================================================

    ids_productos = []

    for producto_id in carrito:
        try:
            ids_productos.append(
                int(producto_id)
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

    if not ids_productos:
        raise ValueError(
            (
                "El carrito no contiene "
                "productos válidos."
            )
        )

    # =========================================================================
    # PRODUCTOS BLOQUEADOS
    # =========================================================================

    productos = {
        producto.id: producto
        for producto in (
            Producto.objects
            .select_for_update()
            .filter(
                id__in=ids_productos,
                activo=True,
            )
        )
    }

    # =========================================================================
    # VALIDAR ITEMS Y CALCULAR SUBTOTAL
    # =========================================================================

    items_para_crear = []
    subtotal = Decimal("0")

    for (
        producto_id_texto,
        datos,
    ) in carrito.items():

        try:
            producto_id = int(
                producto_id_texto
            )

            cantidad = int(
                datos.get(
                    "cantidad",
                    1,
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:
            raise ValueError(
                (
                    "El carrito contiene "
                    "datos inválidos."
                )
            ) from error

        # ---------------------------------------------------------------------
        # VALIDAR CANTIDAD
        # ---------------------------------------------------------------------

        if cantidad <= 0:
            raise ValueError(
                (
                    "La cantidad de un producto "
                    "no es válida."
                )
            )

        # ---------------------------------------------------------------------
        # VALIDAR PRODUCTO
        # ---------------------------------------------------------------------

        producto = productos.get(
            producto_id
        )

        if producto is None:
            raise ValueError(
                (
                    "Uno de los productos ya no "
                    "está disponible."
                )
            )

        # ---------------------------------------------------------------------
        # STOCK DISPONIBLE
        # ---------------------------------------------------------------------

        stock_disponible = max(
            producto.stock
            - producto.stock_reservado,
            0,
        )

        if stock_disponible < cantidad:
            raise ValueError(
                (
                    f"No existe stock suficiente de "
                    f"{producto.nombre}. "
                    f"Disponibles: {stock_disponible}."
                )
            )

        # ---------------------------------------------------------------------
        # PRECIOS
        # ---------------------------------------------------------------------

        precio_lista = Decimal(
            str(
                producto.precio
            )
        )

        precio_venta = Decimal(
            str(
                producto.precio_actual
            )
        )

        descuento_producto_unitario = max(
            precio_lista
            - precio_venta,
            Decimal("0"),
        )

        total_linea = (
            precio_venta
            * cantidad
        )

        subtotal += (
            total_linea
        )

        items_para_crear.append(
            {
                "producto": producto,

                "cantidad": cantidad,

                "precio_lista": (
                    precio_lista
                ),

                "precio_venta": (
                    precio_venta
                ),

                "descuento_producto_unitario": (
                    descuento_producto_unitario
                ),

                "total": (
                    total_linea
                ),
            }
        )

    # =========================================================================
    # VALIDAR ITEMS
    # =========================================================================

    if not items_para_crear:
        raise ValueError(
            (
                "No fue posible crear los "
                "productos del pedido."
            )
        )

    # =========================================================================
    # DATOS DEL CHECKOUT
    # =========================================================================

    codigo = (
        form.cleaned_data.get(
            "codigo_descuento",
            "",
        )
        or ""
    ).strip().upper()

    rut = (
        form.cleaned_data.get(
            "rut",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # EMAIL DEL CHECKOUT
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # Este debe ser el correo ingresado por el cliente
    # en el formulario de checkout.
    #
    # No utilizamos request.user.email aquí.
    # =========================================================================

    email_checkout = (
        form.cleaned_data.get(
            "email",
            "",
        )
        or ""
    ).strip().lower()

    if not email_checkout:
        raise ValueError(
            (
                "Debes ingresar un correo electrónico "
                "válido para recibir la confirmación."
            )
        )

    # =========================================================================
    # DATOS PERSONALES
    # =========================================================================

    nombre_checkout = (
        form.cleaned_data.get(
            "nombre",
            "",
        )
        or ""
    ).strip()

    apellido_checkout = (
        form.cleaned_data.get(
            "apellido",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # RESOLVER DESCUENTO
    # =========================================================================

    try:
        resultado_descuento = (
            resolver_descuento(
                usuario=request.user,
                rut=rut,
                subtotal=subtotal,
                codigo=codigo,
                bloquear=True,
            )
        )

    except DescuentoError as error:
        raise ValueError(
            str(
                error
            )
        ) from error

    # =========================================================================
    # MONTO DESCUENTO
    # =========================================================================

    descuento = Decimal(
        str(
            resultado_descuento.descuento
            or 0
        )
    )

    # =========================================================================
    # BASE DESPACHO
    # =========================================================================

    base_despacho = max(
        subtotal - descuento,
        Decimal("0"),
    )

    despacho = (
        Decimal("0")
        if base_despacho
        >= META_DESPACHO_GRATIS
        else COSTO_DESPACHO
    )

    # =========================================================================
    # TOTAL
    # =========================================================================

    total = (
        base_despacho
        + despacho
    )

    if total <= Decimal("0"):
        raise ValueError(
            (
                "El total calculado del pedido "
                "no es válido."
            )
        )

    # =========================================================================
    # CREAR PEDIDO DESDE FORM
    # =========================================================================

    pedido = form.save(
        commit=False
    )

    # =========================================================================
    # USUARIO
    # =========================================================================

    pedido.usuario = (
        request.user
        if request.user.is_authenticated
        else None
    )

    # =========================================================================
    # DATOS DEL CHECKOUT
    # =========================================================================
    #
    # Los asignamos explícitamente para garantizar
    # que el Pedido use los datos escritos en checkout.
    # =========================================================================

    pedido.email = (
        email_checkout
    )

    if hasattr(
        pedido,
        "nombre",
    ):
        pedido.nombre = (
            nombre_checkout
        )

    if hasattr(
        pedido,
        "apellido",
    ):
        pedido.apellido = (
            apellido_checkout
        )

    if hasattr(
        pedido,
        "rut",
    ):
        pedido.rut = (
            rut
        )

    # =========================================================================
    # DESCUENTO
    # =========================================================================

    pedido.codigo_descuento_obj = (
        resultado_descuento.codigo_objeto
    )

    pedido.codigo_descuento = (
        resultado_descuento.codigo
        or ""
    )

    pedido.tipo_descuento = (
        resultado_descuento.tipo
    )

    pedido.porcentaje_descuento = (
        resultado_descuento.porcentaje
    )

    # =========================================================================
    # MONTOS
    # =========================================================================

    pedido.subtotal = (
        subtotal
    )

    pedido.descuento = (
        descuento
    )

    pedido.despacho = (
        despacho
    )

    pedido.total = (
        total
    )

    # =========================================================================
    # ESTADOS INICIALES
    # =========================================================================

    pedido.estado = (
        Pedido.EstadoPedido.PENDIENTE
    )

    pedido.estado_pago = (
        Pedido.EstadoPago.PENDIENTE
    )

    pedido.pagado = False

    pedido.stock_descontado = False

    pedido.correo_confirmacion_enviado = (
        False
    )

    pedido.fidelidad_contabilizada = (
        False
    )

    # =========================================================================
    # GUARDAR PEDIDO
    # =========================================================================

    pedido.save()

    # =========================================================================
    # LOG DE DIAGNÓSTICO
    # =========================================================================
    #
    # Esto te permitirá comprobar en terminal
    # qué correo quedó realmente guardado.
    # =========================================================================

    logger.info(
        (
            "Pedido creado desde checkout. "
            "Pedido=%s "
            "metodo_pago=%s "
            "email_checkout=%s "
            "email_usuario=%s "
            "email_guardado=%s"
        ),
        pedido.numero,
        pedido.metodo_pago,
        email_checkout,
        (
            request.user.email
            if request.user.is_authenticated
            else ""
        ),
        pedido.email,
    )

    # =========================================================================
    # RESERVAR CÓDIGO
    # =========================================================================

    reservar_codigo_descuento(
        resultado=resultado_descuento,
        pedido=pedido,
        usuario=request.user,
        rut=rut,
    )

    # =========================================================================
    # DISTRIBUIR DESCUENTO ENTRE ITEMS
    # =========================================================================

    descuento_pendiente = (
        descuento
    )

    items_pedido = []

    for (
        indice,
        datos_item,
    ) in enumerate(
        items_para_crear
    ):

        es_ultimo_item = (
            indice
            == len(
                items_para_crear
            )
            - 1
        )

        if (
            subtotal > Decimal("0")
            and not es_ultimo_item
        ):

            proporcion = (
                datos_item["total"]
                / subtotal
            )

            descuento_linea = (
                descuento
                * proporcion
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )

            descuento_linea = min(
                descuento_linea,
                descuento_pendiente,
            )

        else:

            descuento_linea = (
                descuento_pendiente
            )

        descuento_pendiente -= (
            descuento_linea
        )

        total_final_linea = max(
            datos_item["total"]
            - descuento_linea,
            Decimal("0"),
        )

        producto = (
            datos_item[
                "producto"
            ]
        )

        items_pedido.append(
            PedidoItem(
                pedido=pedido,

                producto=(
                    producto
                ),

                nombre_producto=(
                    producto.nombre
                ),

                precio_lista_unitario=(
                    datos_item[
                        "precio_lista"
                    ]
                ),

                precio_unitario=(
                    datos_item[
                        "precio_venta"
                    ]
                ),

                descuento_producto_unitario=(
                    datos_item[
                        "descuento_producto_unitario"
                    ]
                ),

                cantidad=(
                    datos_item[
                        "cantidad"
                    ]
                ),

                total=(
                    datos_item[
                        "total"
                    ]
                ),

                descuento_codigo=(
                    descuento_linea
                ),

                total_final=(
                    total_final_linea
                ),
            )
        )

    # =========================================================================
    # CREAR ITEMS
    # =========================================================================

    PedidoItem.objects.bulk_create(
        items_pedido
    )

    # =========================================================================
    # HISTORIAL
    # =========================================================================

    PedidoHistorialEstado.objects.create(
        pedido=pedido,

        estado_anterior="",

        estado_nuevo=(
            Pedido.EstadoPedido.PENDIENTE
        ),

        comentario=(
            "Pedido creado desde el checkout."
        ),

        usuario=(
            request.user
            if request.user.is_authenticated
            else None
        ),
    )

    # =========================================================================
    # RETORNAR
    # =========================================================================

    return pedido