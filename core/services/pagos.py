from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..models import *
from .correos import enviar_confirmacion_pago
from core.services.descuentos import *


# =============================================================================
# EXCEPCIONES
# =============================================================================


class ErrorInicioPago(Exception):
    """
    Error controlado al iniciar un medio de pago.
    """


# =============================================================================
# RESULTADO DE INICIO DE PAGO
# =============================================================================


@dataclass
class ResultadoInicioPago:
    """
    Resultado normalizado utilizado por todos
    los proveedores de pago.

    Puede representar:

    - redirección externa GET;
    - redirección externa POST;
    - redirección interna de Django.
    """

    # =========================================================================
    # REDIRECCIÓN EXTERNA GET
    # =========================================================================
    #
    # Ejemplo:
    # Mercado Pago.
    # =========================================================================

    url_redireccion: str | None = None

    # =========================================================================
    # REDIRECCIÓN EXTERNA POST
    # =========================================================================
    #
    # Ejemplo:
    # Webpay.
    #
    # Webpay requiere enviar:
    #
    # token_ws=<token>
    #
    # mediante POST hacia la URL entregada
    # por Transbank.
    # =========================================================================

    url_post: str | None = None

    datos_post: (
        dict[str, Any]
        | None
    ) = None

    # =========================================================================
    # REDIRECCIÓN INTERNA DJANGO
    # =========================================================================
    #
    # Ejemplo:
    # transferencia bancaria.
    # =========================================================================

    nombre_url: str = (
        "core:pedido_confirmacion"
    )

    parametros_url: (
        dict[str, Any]
        | None
    ) = None

    # =========================================================================
    # INFORMACIÓN ADICIONAL
    # =========================================================================

    identificador_externo: str = ""

    estado: str = "pendiente"

    # =========================================================================
    # NORMALIZACIÓN
    # =========================================================================

    def __post_init__(
        self,
    ):
        if self.parametros_url is None:
            self.parametros_url = {}

        if self.datos_post is None:
            self.datos_post = {}


# =============================================================================
# INICIAR PAGO DE PEDIDO
# =============================================================================


def iniciar_pago_pedido(
    *,
    request,
    pedido,
) -> ResultadoInicioPago:
    """
    Inicia el flujo correspondiente al método
    de pago seleccionado en el Pedido.

    Importante:

    El Pedido debe llegar aquí con sus montos
    definitivos ya guardados:

        subtotal
        descuento
        despacho
        total

    pedido.total debe ser exactamente el monto
    que utilizará el proveedor de pago.
    """

    # =========================================================================
    # VALIDAR PEDIDO
    # =========================================================================

    if pedido is None:
        raise ErrorInicioPago(
            (
                "No existe un pedido "
                "para iniciar el pago."
            )
        )

    # =========================================================================
    # VALIDAR TOTAL
    # =========================================================================

    try:
        total_pedido = Decimal(
            str(
                pedido.total
                or 0
            )
        )

    except Exception as error:
        raise ErrorInicioPago(
            (
                "El total del pedido "
                "no es válido."
            )
        ) from error

    if total_pedido <= 0:
        raise ErrorInicioPago(
            (
                "El total del pedido "
                "debe ser mayor que $0."
            )
        )

    # =========================================================================
    # MÉTODO
    # =========================================================================

    metodo = str(
        pedido.metodo_pago
        or ""
    ).strip().lower()

    # =========================================================================
    # TRANSFERENCIA
    # =========================================================================

    if metodo == "transferencia":

        campos_actualizados = []

        # ---------------------------------------------------------------------
        # Estado del pago
        # ---------------------------------------------------------------------

        if hasattr(
            pedido,
            "estado_pago",
        ):
            try:
                pedido.estado_pago = (
                    Pedido.EstadoPago.PENDIENTE
                )

            except AttributeError:
                pedido.estado_pago = (
                    "pendiente"
                )

            campos_actualizados.append(
                "estado_pago"
            )

        # ---------------------------------------------------------------------
        # Guardar
        # ---------------------------------------------------------------------

        if campos_actualizados:
            pedido.save(
                update_fields=(
                    campos_actualizados
                )
            )

        # ---------------------------------------------------------------------
        # Transferencia redirige internamente
        # ---------------------------------------------------------------------

        return ResultadoInicioPago(
            nombre_url=(
                "core:pedido_confirmacion"
            ),

            parametros_url={
                "numero": (
                    pedido.numero
                ),
            },

            estado=(
                "pendiente"
            ),
        )

    # =========================================================================
    # MERCADO PAGO
    # =========================================================================

    if metodo == "mercadopago":

        return iniciar_pago_mercadopago(
            request=request,
            pedido=pedido,
        )

    # =========================================================================
    # WEBPAY
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # La importación es LOCAL intencionalmente.
    #
    # No debemos hacer arriba:
    #
    # from core.services.webpay import *
    #
    # porque webpay.py necesita:
    #
    # ErrorInicioPago
    # ResultadoInicioPago
    #
    # definidos precisamente en este archivo.
    #
    # Si ambos archivos se importan mutuamente durante
    # el arranque, Python genera un import circular.
    # =========================================================================

    if metodo == "webpay":

        try:
            from core.services.webpay import (
                iniciar_pago_webpay,
            )

        except ImportError as error:
            raise ErrorInicioPago(
                (
                    "La integración de Webpay "
                    "no está configurada correctamente."
                )
            ) from error

        return iniciar_pago_webpay(
            request=request,
            pedido=pedido,
        )

    # =========================================================================
    # MÉTODO DESCONOCIDO
    # =========================================================================

    raise ErrorInicioPago(
        (
            "El método de pago seleccionado "
            "no está disponible."
        )
    )


# =============================================================================
# DESCONTAR STOCK
# =============================================================================


def descontar_stock_pedido(
    pedido,
):
    """
    Descuenta físicamente el stock
    de los productos del pedido.

    Esta función debe ejecutarse una
    sola vez por pedido aprobado.

    La protección principal es:

        pedido.stock_descontado
    """

    # =========================================================================
    # OBTENER ITEMS CON BLOQUEO
    # =========================================================================

    items = (
        pedido.items
        .select_related(
            "producto"
        )
        .select_for_update()
        .all()
    )

    # =========================================================================
    # RECORRER ITEMS
    # =========================================================================

    for item in items:

        producto = (
            item.producto
        )

        if producto is None:
            continue

        cantidad = int(
            item.cantidad
            or 0
        )

        if cantidad <= 0:
            continue

        # =====================================================================
        # BLOQUEAR PRODUCTO
        # =====================================================================

        producto = (
            Producto.objects
            .select_for_update()
            .get(
                pk=producto.pk
            )
        )

        # =====================================================================
        # VALIDAR STOCK
        # =====================================================================

        if producto.stock < cantidad:
            raise ValueError(
                (
                    f"No existe stock suficiente para "
                    f"{item.nombre_producto}. "
                    f"Stock actual: {producto.stock}. "
                    f"Cantidad vendida: {cantidad}."
                )
            )

        # =====================================================================
        # DESCONTAR STOCK
        # =====================================================================

        producto.stock = (
            producto.stock
            - cantidad
        )

        # =====================================================================
        # STOCK RESERVADO
        # =====================================================================

        if hasattr(
            producto,
            "stock_reservado",
        ):

            producto.stock_reservado = max(
                (
                    int(
                        producto.stock_reservado
                        or 0
                    )
                    - cantidad
                ),
                0,
            )

            producto.save(
                update_fields=[
                    "stock",
                    "stock_reservado",
                    "actualizado",
                ]
            )

        else:

            producto.save(
                update_fields=[
                    "stock",
                    "actualizado",
                ]
            )


# =============================================================================
# CONFIRMAR CÓDIGO UTILIZADO
# =============================================================================


def confirmar_codigo_descuento_pedido(
    *,
    pedido,
):
    """
    Confirma el UsoCodigoDescuento
    reservado para el pedido.

    Es idempotente:

    si ya estaba confirmado,
    no vuelve a consumir el código.
    """

    # =========================================================================
    # OBTENER RESERVA
    # =========================================================================

    try:
        uso = (
            UsoCodigoDescuento.objects
            .select_for_update()
            .select_related(
                "codigo"
            )
            .get(
                pedido=pedido
            )
        )

    except UsoCodigoDescuento.DoesNotExist:
        return None

    # =========================================================================
    # YA CONFIRMADO
    # =========================================================================

    if (
        uso.estado
        == UsoCodigoDescuento.Estado.CONFIRMADO
    ):
        return uso

    # =========================================================================
    # SOLO CONFIRMAR RESERVADOS
    # =========================================================================

    if (
        uso.estado
        != UsoCodigoDescuento.Estado.RESERVADO
    ):
        return uso

    # =========================================================================
    # FECHA
    # =========================================================================

    ahora = timezone.now()

    # =========================================================================
    # CONFIRMAR USO
    # =========================================================================

    uso.estado = (
        UsoCodigoDescuento.Estado.CONFIRMADO
    )

    campos_uso = [
        "estado",
    ]

    # -------------------------------------------------------------------------
    # Fecha confirmación
    # -------------------------------------------------------------------------

    if hasattr(
        uso,
        "confirmado_en",
    ):

        uso.confirmado_en = (
            ahora
        )

        campos_uso.append(
            "confirmado_en"
        )

    # -------------------------------------------------------------------------
    # Limpiar fecha de liberación
    # -------------------------------------------------------------------------

    if hasattr(
        uso,
        "liberado_en",
    ):

        uso.liberado_en = None

        campos_uso.append(
            "liberado_en"
        )

    # -------------------------------------------------------------------------
    # Guardar
    # -------------------------------------------------------------------------

    uso.save(
        update_fields=(
            campos_uso
        ),
    )

    # =========================================================================
    # CÓDIGO PERSONAL / FIDELIDAD
    # =========================================================================

    codigo = (
        uso.codigo
    )

    if (
        codigo
        and codigo.tipo
        == CodigoDescuento.Tipo.FIDELIDAD
    ):

        if not codigo.consumido:

            codigo.consumido = True

            campos_codigo = [
                "consumido",
            ]

            if hasattr(
                codigo,
                "consumido_en",
            ):

                codigo.consumido_en = (
                    ahora
                )

                campos_codigo.append(
                    "consumido_en"
                )

            codigo.save(
                update_fields=(
                    campos_codigo
                ),
            )

    return uso


# =============================================================================
# MARCAR PEDIDO COMO PAGADO
# =============================================================================


def marcar_pedido_como_pagado(
    *,
    pedido_id,
    datos_pago=None,
):
    """
    Función central para confirmar un pago.

    Puede ser utilizada por:

    - webhook de Mercado Pago;
    - retorno confirmado de Mercado Pago;
    - retorno confirmado de Webpay;
    - futuros proveedores.

    Se encarga de:

    - bloquear el pedido;
    - validar idempotencia;
    - validar el monto;
    - registrar información del proveedor;
    - descontar stock una sola vez;
    - confirmar el código reservado;
    - marcar el pedido como pagado;
    - enviar el correo después del commit.

    IMPORTANTE:

    Esta función solamente debe llamarse cuando
    el proveedor de pago ya confirmó efectivamente
    que la transacción fue aprobada.
    """

    # =========================================================================
    # NORMALIZAR DATOS
    # =========================================================================

    datos_pago = (
        datos_pago
        or {}
    )

    # =========================================================================
    # TRANSACCIÓN
    # =========================================================================

    with transaction.atomic():

        # =====================================================================
        # BLOQUEAR PEDIDO
        # =====================================================================

        try:
            pedido = (
                Pedido.objects
                .select_for_update()
                .select_related(
                    "usuario"
                )
                .get(
                    pk=pedido_id
                )
            )

        except Pedido.DoesNotExist as error:
            raise ValueError(
                (
                    "No existe el pedido que "
                    "se intenta confirmar."
                )
            ) from error

        # =====================================================================
        # MÉTODO DE PAGO
        # =====================================================================

        metodo = str(
            datos_pago.get(
                "metodo"
            )
            or pedido.metodo_pago
            or ""
        ).strip().lower()

        # =====================================================================
        # IDENTIFICADOR DEL PAGO
        # =====================================================================

        payment_id = str(
            datos_pago.get(
                "payment_id"
            )
            or datos_pago.get(
                "transaction_id"
            )
            or ""
        ).strip()

        # =====================================================================
        # ESTADO MERCADO PAGO
        # =====================================================================

        status = str(
            datos_pago.get(
                "mercadopago_status"
            )
            or datos_pago.get(
                "status"
            )
            or ""
        ).strip().lower()

        status_detail = str(
            datos_pago.get(
                "mercadopago_status_detail"
            )
            or datos_pago.get(
                "status_detail"
            )
            or ""
        ).strip()

        payment_type = str(
            datos_pago.get(
                "payment_type"
            )
            or ""
        ).strip()

        # =====================================================================
        # MONTO PAGADO
        # =====================================================================

        transaction_amount_raw = (
            datos_pago.get(
                "transaction_amount"
            )
        )

        transaction_amount = None

        if (
            transaction_amount_raw
            is not None
        ):

            try:
                transaction_amount = Decimal(
                    str(
                        transaction_amount_raw
                    )
                )

            except Exception as error:
                raise ValueError(
                    (
                        "El monto recibido desde "
                        "el proveedor de pago no es válido."
                    )
                ) from error

        # =====================================================================
        # IDEMPOTENCIA
        # =====================================================================

        pago_ya_aprobado = bool(
            pedido.pagado
            and pedido.estado_pago
            == Pedido.EstadoPago.APROBADO
        )

        if pago_ya_aprobado:

            # -----------------------------------------------------------------
            # Para Mercado Pago podemos comparar
            # el payment_id almacenado.
            # -----------------------------------------------------------------

            if (
                metodo
                == str(
                    Pedido.MetodoPago.MERCADOPAGO
                )
            ):

                payment_id_actual = str(
                    getattr(
                        pedido,
                        "mercadopago_payment_id",
                        "",
                    )
                    or ""
                ).strip()

                if (
                    payment_id
                    and payment_id_actual
                    and payment_id
                    != payment_id_actual
                ):
                    raise ValueError(
                        (
                            "El pedido ya fue confirmado "
                            "con otro pago."
                        )
                    )

            # -----------------------------------------------------------------
            # Ya estaba aprobado.
            # No ejecutar nuevamente stock,
            # descuentos ni correo.
            # -----------------------------------------------------------------

            return pedido

        # =====================================================================
        # VALIDAR MONTO
        # =====================================================================

        if transaction_amount is not None:

            total_pedido = Decimal(
                str(
                    pedido.total
                    or 0
                )
            )

            if (
                transaction_amount
                != total_pedido
            ):

                # =============================================================
                # REGISTRAR DATOS DE MP SI CORRESPONDE
                # =============================================================

                campos_revision = []

                if (
                    metodo
                    == str(
                        Pedido.MetodoPago.MERCADOPAGO
                    )
                ):

                    if hasattr(
                        pedido,
                        "mercadopago_payment_id",
                    ):
                        pedido.mercadopago_payment_id = (
                            payment_id
                        )

                        campos_revision.append(
                            "mercadopago_payment_id"
                        )

                    if hasattr(
                        pedido,
                        "mercadopago_status",
                    ):
                        pedido.mercadopago_status = (
                            status
                        )

                        campos_revision.append(
                            "mercadopago_status"
                        )

                    if hasattr(
                        pedido,
                        "mercadopago_status_detail",
                    ):
                        pedido.mercadopago_status_detail = (
                            status_detail
                        )

                        campos_revision.append(
                            "mercadopago_status_detail"
                        )

                    if hasattr(
                        pedido,
                        "mercadopago_payment_type",
                    ):
                        pedido.mercadopago_payment_type = (
                            payment_type
                        )

                        campos_revision.append(
                            "mercadopago_payment_type"
                        )

                    if hasattr(
                        pedido,
                        "mercadopago_transaction_amount",
                    ):
                        pedido.mercadopago_transaction_amount = (
                            transaction_amount
                        )

                        campos_revision.append(
                            "mercadopago_transaction_amount"
                        )

                # =============================================================
                # MARCAR REVISIÓN
                # =============================================================

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.PENDIENTE
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.REVISION
                )

                campos_revision.extend(
                    [
                        "pagado",
                        "estado",
                        "estado_pago",
                        "actualizado",
                    ]
                )

                campos_revision = list(
                    dict.fromkeys(
                        campos_revision
                    )
                )

                pedido.save(
                    update_fields=(
                        campos_revision
                    )
                )

                raise ValueError(
                    (
                        "El monto pagado no coincide "
                        "con el total del pedido. "
                        f"Pedido={total_pedido}. "
                        f"Pago={transaction_amount}."
                    )
                )

        # =====================================================================
        # REGISTRAR MERCADO PAGO
        # =====================================================================

        campos_proveedor = []

        if (
            metodo
            == str(
                Pedido.MetodoPago.MERCADOPAGO
            )
        ):

            if hasattr(
                pedido,
                "mercadopago_payment_id",
            ):
                pedido.mercadopago_payment_id = (
                    payment_id
                )

                campos_proveedor.append(
                    "mercadopago_payment_id"
                )

            if hasattr(
                pedido,
                "mercadopago_status",
            ):
                pedido.mercadopago_status = (
                    status
                )

                campos_proveedor.append(
                    "mercadopago_status"
                )

            if hasattr(
                pedido,
                "mercadopago_status_detail",
            ):
                pedido.mercadopago_status_detail = (
                    status_detail
                )

                campos_proveedor.append(
                    "mercadopago_status_detail"
                )

            if hasattr(
                pedido,
                "mercadopago_payment_type",
            ):
                pedido.mercadopago_payment_type = (
                    payment_type
                )

                campos_proveedor.append(
                    "mercadopago_payment_type"
                )

            if hasattr(
                pedido,
                "mercadopago_transaction_amount",
            ):
                pedido.mercadopago_transaction_amount = (
                    transaction_amount
                )

                campos_proveedor.append(
                    "mercadopago_transaction_amount"
                )

        # =====================================================================
        # DESCONTAR STOCK
        # =====================================================================

        if not pedido.stock_descontado:

            descontar_stock_pedido(
                pedido
            )

            pedido.stock_descontado = True

        # =====================================================================
        # CONFIRMAR CÓDIGO DE DESCUENTO
        # =====================================================================

        confirmar_codigo_descuento_pedido(
            pedido=pedido
        )

        # =====================================================================
        # MARCAR PEDIDO COMO PAGADO
        # =====================================================================

        pedido.pagado = True

        pedido.estado = (
            Pedido.EstadoPedido.CONFIRMADO
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.APROBADO
        )

        if not pedido.fecha_pago:
            pedido.fecha_pago = (
                timezone.now()
            )

        # =====================================================================
        # CAMPOS A GUARDAR
        # =====================================================================

        campos_actualizar = [
            "pagado",
            "estado",
            "estado_pago",
            "fecha_pago",
            "stock_descontado",
            "actualizado",
        ]

        campos_actualizar.extend(
            campos_proveedor
        )

        campos_actualizar = list(
            dict.fromkeys(
                campos_actualizar
            )
        )

        # =====================================================================
        # GUARDAR PEDIDO
        # =====================================================================

        pedido.save(
            update_fields=(
                campos_actualizar
            ),
        )

        # =====================================================================
        # CORREO DE CONFIRMACIÓN
        # =====================================================================
        #
        # Solo se ejecutará después de que la
        # transacción de base de datos confirme.
        # =====================================================================

        if not pedido.correo_confirmacion_enviado:

            transaction.on_commit(
                partial(
                    enviar_confirmacion_pago,
                    pedido_id=pedido.pk,
                )
            )

        # =====================================================================
        # RESULTADO
        # =====================================================================

        return pedido


# =============================================================================
# MERCADO PAGO
# =============================================================================


def iniciar_pago_mercadopago(
    *,
    request,
    pedido,
) -> ResultadoInicioPago:
    """
    Crea una preferencia en Mercado Pago
    y devuelve la URL de Checkout Pro.

    pedido.total ya debe contener el monto
    definitivo del pedido.
    """

    # =========================================================================
    # IMPORTAR INTEGRACIÓN
    # =========================================================================
    #
    # La importación local mantiene desacoplados
    # los servicios de pago.
    # =========================================================================

    try:
        from .mercadopago import (
            MercadoPagoError,
            crear_preferencia,
        )

    except ImportError as error:
        raise ErrorInicioPago(
            (
                "La integración de Mercado Pago "
                "no está configurada."
            )
        ) from error

    # =========================================================================
    # VALIDAR PEDIDO
    # =========================================================================

    if pedido is None:
        raise ErrorInicioPago(
            (
                "No existe un pedido para "
                "iniciar Mercado Pago."
            )
        )

    # =========================================================================
    # VALIDAR TOTAL DEFINITIVO
    # =========================================================================

    try:
        total_pedido = Decimal(
            str(
                pedido.total
                or 0
            )
        )

    except Exception as error:
        raise ErrorInicioPago(
            (
                "El total del pedido "
                "no es válido."
            )
        ) from error

    if total_pedido <= 0:
        raise ErrorInicioPago(
            (
                "El total del pedido "
                "debe ser mayor que $0."
            )
        )

    # =========================================================================
    # CREAR PREFERENCIA
    # =========================================================================

    try:
        preferencia = crear_preferencia(
            request=request,
            pedido=pedido,
        )

    except MercadoPagoError as error:
        raise ErrorInicioPago(
            (
                "No fue posible iniciar el pago "
                "con Mercado Pago. "
                f"Detalle: {error}"
            )
        ) from error

    # =========================================================================
    # VALIDAR RESPUESTA
    # =========================================================================

    if not isinstance(
        preferencia,
        dict,
    ):
        raise ErrorInicioPago(
            (
                "Mercado Pago devolvió "
                "una respuesta inválida."
            )
        )

    # =========================================================================
    # PREFERENCE ID
    # =========================================================================

    preference_id = str(
        preferencia.get(
            "preference_id"
        )
        or preferencia.get(
            "id"
        )
        or ""
    ).strip()

    # =========================================================================
    # URL CHECKOUT
    # =========================================================================

    checkout_url = str(
        preferencia.get(
            "checkout_url"
        )
        or preferencia.get(
            "init_point"
        )
        or preferencia.get(
            "sandbox_init_point"
        )
        or ""
    ).strip()

    # =========================================================================
    # VALIDAR PREFERENCE
    # =========================================================================

    if not preference_id:
        raise ErrorInicioPago(
            (
                "Mercado Pago no entregó "
                "un identificador de preferencia."
            )
        )

    if not checkout_url:
        raise ErrorInicioPago(
            (
                "Mercado Pago no entregó "
                "la URL de pago."
            )
        )

    # =========================================================================
    # GUARDAR DATOS DE MERCADO PAGO
    # =========================================================================

    campos_actualizados = []

    # -------------------------------------------------------------------------
    # Preference ID
    # -------------------------------------------------------------------------

    if hasattr(
        pedido,
        "mercadopago_preference_id",
    ):

        pedido.mercadopago_preference_id = (
            preference_id
        )

        campos_actualizados.append(
            "mercadopago_preference_id"
        )

    # -------------------------------------------------------------------------
    # Estado de pago
    # -------------------------------------------------------------------------

    if hasattr(
        pedido,
        "estado_pago",
    ):

        try:
            pedido.estado_pago = (
                Pedido.EstadoPago.INICIADO
            )

        except AttributeError:
            pedido.estado_pago = (
                "iniciado"
            )

        campos_actualizados.append(
            "estado_pago"
        )

    # -------------------------------------------------------------------------
    # Estado textual Mercado Pago
    # -------------------------------------------------------------------------

    if hasattr(
        pedido,
        "mercadopago_status",
    ):

        pedido.mercadopago_status = (
            "iniciado"
        )

        campos_actualizados.append(
            "mercadopago_status"
        )

    # =========================================================================
    # EVITAR DUPLICADOS
    # =========================================================================

    campos_actualizados = list(
        dict.fromkeys(
            campos_actualizados
        )
    )

    # =========================================================================
    # GUARDAR
    # =========================================================================

    if campos_actualizados:
        pedido.save(
            update_fields=(
                campos_actualizados
            )
        )

    # =========================================================================
    # RESULTADO
    # =========================================================================
    #
    # Mercado Pago sí utiliza una redirección
    # externa convencional.
    # =========================================================================

    return ResultadoInicioPago(
        url_redireccion=(
            checkout_url
        ),

        identificador_externo=(
            preference_id
        ),

        estado=(
            "iniciado"
        ),
    )