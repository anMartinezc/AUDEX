from decimal import Decimal

from django.conf import settings
from django.urls import reverse

from transbank.common.integration_api_keys import (
    IntegrationApiKeys,
)
from transbank.common.integration_commerce_codes import (
    IntegrationCommerceCodes,
)
from transbank.common.integration_type import (
    IntegrationType,
)
from transbank.common.options import (
    WebpayOptions,
)
from transbank.webpay.webpay_plus.transaction import (
    Transaction,
)

from core.services.pagos import *

def obtener_transaccion_webpay():
    """
    Construye una transacción Webpay Plus.

    En integración utiliza las credenciales
    de prueba incluidas por Transbank.

    En producción utiliza las credenciales
    configuradas en settings / .env.
    """

    environment = str(
        getattr(
            settings,
            "TRANSBANK_ENVIRONMENT",
            "integration",
        )
        or "integration"
    ).strip().lower()

    # =========================================================================
    # AMBIENTE DE INTEGRACIÓN
    # =========================================================================

    if environment == "integration":

        return Transaction(
            WebpayOptions(
                IntegrationCommerceCodes.WEBPAY_PLUS,
                IntegrationApiKeys.WEBPAY,
                IntegrationType.TEST,
            )
        )

    # =========================================================================
    # AMBIENTE DE PRODUCCIÓN
    # =========================================================================

    if environment == "production":

        commerce_code = str(
            getattr(
                settings,
                "TRANSBANK_COMMERCE_CODE",
                "",
            )
            or ""
        ).strip()

        api_key = str(
            getattr(
                settings,
                "TRANSBANK_API_KEY",
                "",
            )
            or ""
        ).strip()

        if not commerce_code:
            raise ErrorInicioPago(
                (
                    "No está configurado el código "
                    "de comercio de Webpay."
                )
            )

        if not api_key:
            raise ErrorInicioPago(
                (
                    "No está configurada la API Key "
                    "de Webpay."
                )
            )

        return Transaction.build_for_production(
            commerce_code,
            api_key,
        )

    # =========================================================================
    # AMBIENTE DESCONOCIDO
    # =========================================================================

    raise ErrorInicioPago(
        (
            "El ambiente configurado para Webpay "
            "no es válido."
        )
    )


def iniciar_pago_webpay(
    *,
    request,
    pedido,
) -> ResultadoInicioPago:
    """
    Crea una transacción Webpay Plus
    para el pedido indicado.

    El pedido debe llegar con su total
    definitivo ya calculado y persistido.
    """

    # =========================================================================
    # VALIDAR PEDIDO
    # =========================================================================

    if pedido is None:
        raise ErrorInicioPago(
            (
                "No existe un pedido "
                "para iniciar Webpay."
            )
        )

    # =========================================================================
    # VALIDAR MONTO
    # =========================================================================

    try:
        monto_decimal = Decimal(
            str(
                pedido.total
                or 0
            )
        )

    except Exception as error:
        raise ErrorInicioPago(
            (
                "El monto enviado a Webpay "
                "no es válido."
            )
        ) from error

    if monto_decimal <= 0:
        raise ErrorInicioPago(
            (
                "El monto enviado a Webpay "
                "debe ser mayor que $0."
            )
        )

    # =========================================================================
    # CLP: VALIDAR QUE SEA ENTERO
    # =========================================================================

    if (
        monto_decimal
        != monto_decimal.to_integral_value()
    ):
        raise ErrorInicioPago(
            (
                "El monto enviado a Webpay "
                "debe ser un valor entero en pesos."
            )
        )

    monto = int(
        monto_decimal
    )

    # =========================================================================
    # SESIÓN DJANGO
    # =========================================================================

    if not request.session.session_key:
        request.session.create()

    session_id = str(
        request.session.session_key
    )

    if not session_id:
        raise ErrorInicioPago(
            (
                "No fue posible obtener "
                "una sesión válida para Webpay."
            )
        )

    # =========================================================================
    # ORDEN DE COMPRA
    # =========================================================================

    buy_order = str(
        pedido.numero
        or ""
    ).strip()

    if not buy_order:
        raise ErrorInicioPago(
            (
                "El pedido no posee un "
                "número de orden válido."
            )
        )

    # =========================================================================
    # URL DE RETORNO
    # =========================================================================

    try:
        return_url = (
            request.build_absolute_uri(
                reverse(
                    "core:webpay_retorno"
                )
            )
        )

    except Exception as error:
        raise ErrorInicioPago(
            (
                "No fue posible construir "
                "la URL de retorno de Webpay."
            )
        ) from error

    # =========================================================================
    # CREAR TRANSACCIÓN WEBPAY
    # =========================================================================
    #
    # Transbank recibe:
    #
    # buy_order
    # session_id
    # amount
    # return_url
    #
    # y entrega:
    #
    # token
    # url
    #
    # =========================================================================

    try:

        transaccion = (
            obtener_transaccion_webpay()
        )

        respuesta = (
            transaccion.create(
                buy_order=buy_order,
                session_id=session_id,
                amount=monto,
                return_url=return_url,
            )
        )

    except ErrorInicioPago:
        raise

    except Exception as error:
        raise ErrorInicioPago(
            (
                "No fue posible iniciar "
                "el pago mediante Webpay."
            )
        ) from error

    # =========================================================================
    # OBTENER TOKEN
    # =========================================================================

    if isinstance(
        respuesta,
        dict,
    ):

        token = (
            respuesta.get(
                "token"
            )
        )

        url = (
            respuesta.get(
                "url"
            )
        )

    else:

        token = getattr(
            respuesta,
            "token",
            None,
        )

        url = getattr(
            respuesta,
            "url",
            None,
        )

    # =========================================================================
    # NORMALIZAR RESPUESTA
    # =========================================================================

    token = str(
        token
        or ""
    ).strip()

    url = str(
        url
        or ""
    ).strip()

    # =========================================================================
    # VALIDAR RESPUESTA WEBPAY
    # =========================================================================

    if not token:
        raise ErrorInicioPago(
            (
                "Webpay no entregó "
                "el token de la transacción."
            )
        )

    if not url:
        raise ErrorInicioPago(
            (
                "Webpay no entregó "
                "la URL necesaria "
                "para continuar el pago."
            )
        )

    # =========================================================================
    # GUARDAR INFORMACIÓN EN SESIÓN
    # =========================================================================
    #
    # Esto permite identificar el pedido cuando
    # el cliente regrese desde Transbank.
    #
    # NO significa que el pedido esté pagado.
    # =========================================================================

    request.session[
        "webpay_token"
    ] = token

    request.session[
        "webpay_pedido"
    ] = str(
        pedido.numero
    )

    request.session.modified = True

    # =========================================================================
    # RESULTADO
    # =========================================================================
    #
    # Webpay no utiliza una redirección GET normal.
    #
    # Debemos enviar:
    #
    # POST
    # token_ws=<token>
    #
    # hacia la URL entregada por Transbank.
    #
    # checkout() renderizará redireccion_pago.html
    # para realizar este POST automáticamente.
    # =========================================================================

    return ResultadoInicioPago(
        url_post=url,

        datos_post={
            "token_ws": token,
        },

        estado=(
            "pendiente"
        ),
    )