from dataclasses import dataclass
from typing import Any
from functools import partial
from django.db import transaction
from ..models import *
from .correos import enviar_confirmacion_pago
from core.services.descuentos import *

class ErrorInicioPago(Exception):
    """Error controlado al iniciar un medio de pago."""


@dataclass
class ResultadoInicioPago:
    url_redireccion: str | None = None
    nombre_url: str = "core:pedido_confirmacion"
    parametros_url: dict[str, Any] | None = None
    identificador_externo: str = ""
    estado: str = "pendiente"

    def __post_init__(self):
        if self.parametros_url is None:
            self.parametros_url = {}


def iniciar_pago_pedido(
    *,
    request,
    pedido,
) -> ResultadoInicioPago:
    metodo = pedido.metodo_pago

    if metodo == "transferencia":
        return ResultadoInicioPago(
            nombre_url="core:pedido_confirmacion",
            parametros_url={
                "numero": pedido.numero,
            },
            estado="pendiente",
        )

    if metodo == "mercadopago":
        return iniciar_pago_mercadopago(
            request=request,
            pedido=pedido,
        )

    if metodo == "webpay":
        raise ErrorInicioPago(
            "Webpay todavía no está disponible."
        )

    raise ErrorInicioPago(
        "El método de pago seleccionado no está disponible."
    )



def iniciar_pago_mercadopago(
    *,
    request,
    pedido,
) -> ResultadoInicioPago:
    try:
        from .mercadopago import (
            MercadoPagoError,
            crear_preferencia,
        )
    except ImportError as error:
        raise ErrorInicioPago(
            "La integración de Mercado Pago "
            "no está configurada."
        ) from error

    try:
        preferencia = crear_preferencia(
            request=request,
            pedido=pedido,
        )
    except MercadoPagoError as error:
        raise ErrorInicioPago(
            "No fue posible iniciar el pago "
            "con Mercado Pago. "
            f"Detalle: {error}"
        ) from error

    preference_id = str(
        preferencia.get("preference_id")
        or preferencia.get("id")
        or ""
    ).strip()

    checkout_url = str(
        preferencia.get("checkout_url")
        or preferencia.get("init_point")
        or preferencia.get("sandbox_init_point")
        or ""
    ).strip()

    if not preference_id:
        raise ErrorInicioPago(
            "Mercado Pago no entregó un identificador."
        )

    if not checkout_url:
        raise ErrorInicioPago(
            "Mercado Pago no entregó la URL de pago."
        )

    pedido.mercadopago_preference_id = preference_id

    campos_actualizados = [
        "mercadopago_preference_id",
    ]

    if hasattr(pedido, "estado_pago"):
        pedido.estado_pago = "iniciado"
        campos_actualizados.append(
            "estado_pago"
        )

    pedido.save(
        update_fields=campos_actualizados,
    )

    return ResultadoInicioPago(
        url_redireccion=checkout_url,
        identificador_externo=preference_id,
        estado="iniciado",
    )



from functools import partial

from django.db import transaction
from django.utils import timezone

from core.models import Pedido
from core.services.correos import enviar_confirmacion_pago
def marcar_pedido_como_pagado(
    pedido_id,
    datos_pago=None,
):
    """
    Marca un pedido como pagado de forma idempotente.

    También:

    - Cambia el estado general a confirmado.
    - Cambia estado_pago a aprobado.
    - Registra la fecha del pago.
    - Guarda la información del proveedor.
    - Valida el monto reportado cuando está disponible.
    - Marca como utilizado el código personal reservado.
    - Acumula la compra en el programa de fidelidad.
    - Genera premios de fidelidad cuando corresponde.
    - Registra el cambio en el historial del pedido.
    - Programa el correo después de confirmar la transacción.
    """

    datos_pago = datos_pago or {}

    # -------------------------------------------------------------------------
    # UTILIDADES INTERNAS
    # -------------------------------------------------------------------------

    def primer_valor(*claves):
        """
        Devuelve el primer valor informado en datos_pago.

        Mantiene valores válidos como 0 y False.
        """

        for clave in claves:
            if clave not in datos_pago:
                continue

            valor = datos_pago.get(clave)

            if valor is None:
                continue

            if isinstance(valor, str):
                valor = valor.strip()

                if not valor:
                    continue

            return valor

        return None

    def convertir_decimal(
        valor,
        nombre_campo,
    ):
        if valor is None:
            return None

        try:
            return Decimal(
                str(valor)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                (
                    f"El valor de {nombre_campo} "
                    "no es un número válido."
                )
            ) from error

    def convertir_entero(
        valor,
        nombre_campo,
    ):
        if valor is None:
            return None

        try:
            return int(valor)

        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                (
                    f"El valor de {nombre_campo} "
                    "no es un número entero válido."
                )
            ) from error

    def convertir_fecha(
        valor,
        nombre_campo,
    ):
        if valor is None:
            return None

        if isinstance(
            valor,
            datetime,
        ):
            fecha = valor

        else:
            texto = str(valor).strip()

            fecha = parse_datetime(
                texto
            )

            if fecha is None:
                try:
                    fecha = datetime.fromisoformat(
                        texto.replace(
                            "Z",
                            "+00:00",
                        )
                    )

                except ValueError as error:
                    raise ValueError(
                        (
                            f"El valor de {nombre_campo} "
                            "no contiene una fecha válida."
                        )
                    ) from error

        if timezone.is_naive(fecha):
            fecha = timezone.make_aware(
                fecha,
                timezone.get_current_timezone(),
            )

        return fecha

    # -------------------------------------------------------------------------
    # TRANSACCIÓN PRINCIPAL
    # -------------------------------------------------------------------------

    with transaction.atomic():
        pedido = (
            Pedido.objects
            .select_for_update()
            .select_related(
                "usuario",
            )
            .get(
                pk=pedido_id,
            )
        )

        pago_ya_estaba_aprobado = (
            pedido.pago_aprobado
        )

        estado_anterior = pedido.estado

        campos_actualizados = set()

        def asignar(
            campo,
            valor,
        ):
            """
            Asigna únicamente valores informados y diferentes.

            No ignora valores válidos como:
            - False
            - 0
            - Decimal("0")
            """

            if valor is None:
                return

            if isinstance(valor, str):
                valor = valor.strip()

                if not valor:
                    return

            if getattr(
                pedido,
                campo,
            ) != valor:
                setattr(
                    pedido,
                    campo,
                    valor,
                )

                campos_actualizados.add(
                    campo
                )

        # ---------------------------------------------------------------------
        # MÉTODO DE PAGO
        # ---------------------------------------------------------------------

        metodo = str(
            primer_valor(
                "metodo",
                "metodo_pago",
            )
            or pedido.metodo_pago
            or ""
        ).strip().lower()

        if not metodo:
            raise ValueError(
                "No se indicó el método de pago."
            )

        if metodo not in Pedido.MetodoPago.values:
            raise ValueError(
                (
                    "Método de pago no válido: "
                    f"{metodo}"
                )
            )

        asignar(
            "metodo_pago",
            metodo,
        )

        # ---------------------------------------------------------------------
        # VALIDAR MONTO REPORTADO
        # ---------------------------------------------------------------------

        monto_reportado_bruto = primer_valor(
            "mercadopago_transaction_amount",
            "transaction_amount",
            "amount",
            "monto",
        )

        monto_reportado = convertir_decimal(
            monto_reportado_bruto,
            "monto pagado",
        )

        if (
            monto_reportado is not None
            and monto_reportado != pedido.total
        ):
            raise ValueError(
                (
                    "El monto reportado por el proveedor "
                    "no coincide con el total del pedido. "
                    f"Pedido: {pedido.total}. "
                    f"Proveedor: {monto_reportado}."
                )
            )

        # ---------------------------------------------------------------------
        # ESTADO GENERAL
        # ---------------------------------------------------------------------

        asignar(
            "estado",
            Pedido.EstadoPedido.CONFIRMADO,
        )

        asignar(
            "estado_pago",
            Pedido.EstadoPago.APROBADO,
        )

        asignar(
            "pagado",
            True,
        )

        if not pedido.fecha_pago:
            pedido.fecha_pago = (
                timezone.now()
            )

            campos_actualizados.add(
                "fecha_pago"
            )

        # ---------------------------------------------------------------------
        # MERCADO PAGO
        # ---------------------------------------------------------------------

        if (
            metodo
            == Pedido.MetodoPago.MERCADOPAGO
        ):
            payment_id = primer_valor(
                "mercadopago_payment_id",
                "payment_id",
                "id",
            )

            asignar(
                "mercadopago_payment_id",
                (
                    str(payment_id).strip()
                    if payment_id is not None
                    else None
                ),
            )

            asignar(
                "mercadopago_status",
                (
                    primer_valor(
                        "mercadopago_status",
                        "status",
                    )
                    or "approved"
                ),
            )

            asignar(
                "mercadopago_status_detail",
                primer_valor(
                    "mercadopago_status_detail",
                    "status_detail",
                ),
            )

            asignar(
                "mercadopago_payment_type",
                primer_valor(
                    "mercadopago_payment_type",
                    "payment_type",
                    "payment_type_id",
                ),
            )

            asignar(
                "mercadopago_transaction_amount",
                monto_reportado,
            )

        # ---------------------------------------------------------------------
        # WEBPAY
        # ---------------------------------------------------------------------

        elif (
            metodo
            == Pedido.MetodoPago.WEBPAY
        ):
            buy_order = primer_valor(
                "webpay_buy_order",
                "buy_order",
                "payment_id",
            )

            asignar(
                "webpay_buy_order",
                (
                    str(buy_order).strip()
                    if buy_order is not None
                    else None
                ),
            )

            asignar(
                "webpay_token",
                primer_valor(
                    "webpay_token",
                    "token",
                    "token_ws",
                ),
            )

            asignar(
                "webpay_authorization_code",
                primer_valor(
                    "webpay_authorization_code",
                    "authorization_code",
                ),
            )

            codigo_respuesta = (
                convertir_entero(
                    primer_valor(
                        "webpay_response_code",
                        "response_code",
                    ),
                    "código de respuesta Webpay",
                )
            )

            asignar(
                "webpay_response_code",
                codigo_respuesta,
            )

            asignar(
                "webpay_payment_type_code",
                primer_valor(
                    "webpay_payment_type_code",
                    "payment_type_code",
                ),
            )

            numero_cuotas = (
                convertir_entero(
                    primer_valor(
                        "webpay_installments_number",
                        "installments_number",
                    ),
                    "número de cuotas Webpay",
                )
            )

            asignar(
                "webpay_installments_number",
                numero_cuotas,
            )

            fecha_transaccion = (
                convertir_fecha(
                    primer_valor(
                        "webpay_transaction_date",
                        "transaction_date",
                    ),
                    "fecha de transacción Webpay",
                )
            )

            asignar(
                "webpay_transaction_date",
                fecha_transaccion,
            )

        # ---------------------------------------------------------------------
        # GUARDAR PEDIDO
        # ---------------------------------------------------------------------

        if campos_actualizados:
            campos_actualizados.add(
                "actualizado"
            )

            pedido.save(
                update_fields=sorted(
                    campos_actualizados
                )
            )

        # ---------------------------------------------------------------------
        # HISTORIAL
        # ---------------------------------------------------------------------

        if (
            estado_anterior
            != pedido.estado
        ):
            PedidoHistorialEstado.objects.create(
                pedido=pedido,
                estado_anterior=estado_anterior,
                estado_nuevo=pedido.estado,
                comentario=(
                    "Pago aprobado y confirmado "
                    f"mediante {pedido.get_metodo_pago_display()}."
                ),
                usuario=None,
            )

        # ---------------------------------------------------------------------
        # CÓDIGO PERSONAL DE FIDELIDAD
        # ---------------------------------------------------------------------
        #
        # Si el pedido reservó un código personal durante el checkout,
        # queda marcado como utilizado al aprobarse el pago.
        #
        # La función debe ser idempotente:
        # si el código ya está usado, no hace nada.
        # ---------------------------------------------------------------------

        confirmar_codigo_fidelidad_pedido(
            pedido
        )

        # ---------------------------------------------------------------------
        # ACUMULAR COMPRA Y GENERAR PREMIOS
        # ---------------------------------------------------------------------
        #
        # registrar_compra_fidelidad() utiliza la bandera
        # pedido.fidelidad_contabilizada para impedir que un webhook repetido
        # acumule la misma compra varias veces.
        # ---------------------------------------------------------------------

        registrar_compra_fidelidad(
            pedido.pk
        )

        # ---------------------------------------------------------------------
        # CORREO
        # ---------------------------------------------------------------------

        debe_enviar_correo = (
            not pago_ya_estaba_aprobado
            or not pedido.correo_confirmacion_enviado
        )

        if debe_enviar_correo:
            pedido_pk = pedido.pk

            def enviar_correo_despues_commit():
                enviar_confirmacion_pago(
                    pedido_id=pedido_pk,
                )

            transaction.on_commit(
                enviar_correo_despues_commit,
                robust=True,
            )

    # Refresca cambios hechos por fidelidad y por el callback del correo.
    pedido.refresh_from_db()

    return pedido