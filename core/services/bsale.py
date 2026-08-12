# core/services/bsale.py

import logging

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

import requests

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


class BsaleError(Exception):
    """
    Error controlado durante una operación con Bsale.
    """


# ============================================================================
# HEADERS
# ============================================================================


def _headers():
    token = (
        getattr(
            settings,
            "BSALE_ACCESS_TOKEN",
            "",
        )
        or ""
    ).strip()

    if not token:
        raise BsaleError(
            "BSALE_ACCESS_TOKEN no está configurado."
        )

    return {
        "access_token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ============================================================================
# POST
# ============================================================================


def _post(
    endpoint,
    payload,
):
    base_url = (
        getattr(
            settings,
            "BSALE_API_URL",
            "https://api.bsale.io/v1",
        )
        or "https://api.bsale.io/v1"
    ).rstrip("/")

    url = (
        f"{base_url}/"
        f"{endpoint.lstrip('/')}"
    )

    try:
        response = requests.post(
            url,
            headers=_headers(),
            json=payload,
            timeout=25,
        )

    except requests.RequestException as error:
        raise BsaleError(
            (
                "No fue posible conectar "
                f"con Bsale: {error}"
            )
        ) from error

    try:
        data = response.json()

    except ValueError as error:
        raise BsaleError(
            (
                "Bsale respondió con "
                "contenido no válido."
            )
        ) from error

    if not response.ok:

        mensaje = (
            data.get(
                "error",
                "Bsale rechazó la solicitud.",
            )
            if isinstance(
                data,
                dict,
            )
            else "Bsale rechazó la solicitud."
        )

        raise BsaleError(
            (
                f"Bsale HTTP "
                f"{response.status_code}: "
                f"{mensaje}"
            )
        )

    if (
        isinstance(
            data,
            dict,
        )
        and data.get(
            "error"
        )
    ):
        raise BsaleError(
            str(
                data["error"]
            )
        )

    return data


# ============================================================================
# DECIMALES
# ============================================================================


def _decimal(
    valor,
):
    try:
        return Decimal(
            str(
                valor
                or 0
            )
        )

    except Exception as error:
        raise BsaleError(
            f"Monto inválido: {valor}"
        ) from error


def _precio_neto_desde_bruto(
    precio_bruto,
):
    """
    Convierte precio final IVA incluido
    a precio neto.
    """

    precio_bruto = _decimal(
        precio_bruto
    )

    if precio_bruto < 0:
        raise BsaleError(
            (
                "No se pueden enviar "
                "montos negativos a Bsale."
            )
        )

    return (
        precio_bruto
        / Decimal("1.19")
    ).quantize(
        Decimal("0.000001"),
        rounding=ROUND_HALF_UP,
    )


def _numero_json(
    valor,
):
    return float(
        Decimal(
            str(valor)
        )
    )


# ============================================================================
# CLIENTE
# ============================================================================


def _crear_cliente_bsale(
    pedido,
):
    rut = (
        str(
            pedido.rut
            or ""
        )
        .strip()
        .upper()
    )

    nombre = (
        str(
            pedido.nombre
            or ""
        )
        .strip()
    )

    apellido = (
        str(
            pedido.apellido
            or ""
        )
        .strip()
    )

    email = (
        str(
            pedido.email
            or ""
        )
        .strip()
        .lower()
    )

    comuna = (
        str(
            pedido.comuna
            or ""
        )
        .strip()
    )

    region = (
        str(
            pedido.region
            or ""
        )
        .strip()
    )

    direccion = (
        str(
            pedido.direccion_completa
            or ""
        )
        .strip()
    )

    if not rut:
        raise BsaleError(
            (
                "El pedido no tiene "
                "RUT para emitir la boleta."
            )
        )

    if not email:
        raise BsaleError(
            (
                "El pedido no tiene "
                "correo electrónico."
            )
        )

    return {
        "code": rut,
        "firstName": nombre,
        "lastName": apellido,
        "company": (
            f"{nombre} {apellido}"
        ).strip(),
        "email": email,
        "address": direccion,
        "municipality": comuna,
        "city": region,
        "companyOrPerson": 0,
    }


# ============================================================================
# DETALLES
# ============================================================================


def _crear_detalles_bsale(
    pedido,
):
    """
    Genera los detalles desde PedidoItem.

    Usa total_final porque ya contempla:

    - oferta del producto;
    - cantidad;
    - descuento por código.
    """

    detalles = []

    items = list(
        pedido.items.all()
    )

    if not items:
        raise BsaleError(
            (
                "El pedido no contiene "
                "productos."
            )
        )

    total_productos = Decimal(
        "0"
    )

    for item in items:

        cantidad = int(
            item.cantidad
            or 0
        )

        if cantidad <= 0:
            raise BsaleError(
                (
                    "Existe un ítem con "
                    "cantidad inválida."
                )
            )

        total_final = _decimal(
            item.total_final
        )

        # Compatibilidad por si algún pedido
        # histórico no tiene total_final.
        if (
            total_final <= 0
            and _decimal(
                item.total
            ) > 0
        ):
            total_final = max(
                (
                    _decimal(
                        item.total
                    )
                    - _decimal(
                        item.descuento_codigo
                    )
                ),
                Decimal("0"),
            )

        if total_final <= 0:
            continue

        total_productos += (
            total_final
        )

        nombre_producto = (
            str(
                item.nombre_producto
                or "Producto Audex"
            )
            .strip()
        )

        detalles.append(
            {
                "netUnitValue": (
                    _numero_json(
                        _precio_neto_desde_bruto(
                            total_final
                        )
                    )
                ),

                # Se envía como una línea económica
                # completa para respetar descuentos.
                "quantity": 1,

                "taxes": [
                    {
                        "code": 14,
                        "percentage": 19,
                    }
                ],

                "comment": (
                    f"{nombre_producto} "
                    f"x {cantidad}"
                ),
            }
        )

    if not detalles:
        raise BsaleError(
            (
                "No existen productos "
                "válidos para emitir."
            )
        )

    return (
        detalles,
        total_productos,
    )


# ============================================================================
# DESPACHO
# ============================================================================


def _agregar_despacho_bsale(
    *,
    pedido,
    detalles,
):
    despacho = _decimal(
        pedido.despacho
    )

    if despacho <= 0:
        return Decimal(
            "0"
        )

    detalles.append(
        {
            "netUnitValue": (
                _numero_json(
                    _precio_neto_desde_bruto(
                        despacho
                    )
                )
            ),

            "quantity": 1,

            "taxes": [
                {
                    "code": 14,
                    "percentage": 19,
                }
            ],

            "comment": (
                "Despacho Blue Express"
            ),
        }
    )

    return despacho


# ============================================================================
# PAYLOAD
# ============================================================================


def _crear_payload_bsale(
    pedido,
):
    cliente = (
        _crear_cliente_bsale(
            pedido
        )
    )

    (
        detalles,
        total_productos,
    ) = (
        _crear_detalles_bsale(
            pedido
        )
    )

    despacho = (
        _agregar_despacho_bsale(
            pedido=pedido,
            detalles=detalles,
        )
    )

    total_esperado = (
        total_productos
        + despacho
    )

    total_pedido = _decimal(
        pedido.total
    )

    if (
        total_esperado
        != total_pedido
    ):
        raise BsaleError(
            (
                "El total que se enviará a Bsale "
                "no coincide con el pedido. "
                f"Productos+despacho="
                f"{total_esperado}, "
                f"Pedido={total_pedido}, "
                f"Número={pedido.numero}."
            )
        )

    return {
        "codeSii": int(
            getattr(
                settings,
                "BSALE_CODE_SII",
                39,
            )
        ),

        "officeId": int(
            getattr(
                settings,
                "BSALE_OFFICE_ID",
                1,
            )
        ),

        "declareSii": int(
            getattr(
                settings,
                "BSALE_DECLARE_SII",
                0,
            )
        ),

        "salesId": (
            pedido.numero
        ),

        "client": cliente,

        "sendEmail": int(
            getattr(
                settings,
                "BSALE_SEND_EMAIL",
                1,
            )
        ),

        "details": detalles,

        "observation": (
            f"Pedido Audex {pedido.numero}"
        ),
    }


# ============================================================================
# EMITIR BOLETA
# ============================================================================


def emitir_boleta_bsale(
    pedido,
):
    """
    Emite una boleta electrónica Bsale
    para un Pedido aprobado.
    """

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not (
        pedido.pagado
        and pedido.estado_pago
        == pedido.EstadoPago.APROBADO
    ):
        raise BsaleError(
            (
                "No se puede emitir una "
                "boleta para un pedido "
                "no pagado."
            )
        )

    # =========================================================================
    # IDEMPOTENCIA
    # =========================================================================

    if getattr(
        pedido,
        "bsale_document_id",
        None,
    ):
        return {
            "id": (
                pedido.bsale_document_id
            ),

            "number": (
                pedido.bsale_folio
            ),

            "urlPdf": (
                pedido.bsale_url_pdf
            ),

            "urlPublicView": (
                pedido.bsale_url_publica
            ),

            "already_created": True,
        }

    # =========================================================================
    # PAYLOAD
    # =========================================================================

    payload = (
        _crear_payload_bsale(
            pedido
        )
    )

    logger.info(
        (
            "Emitiendo boleta Bsale "
            "para pedido %s."
        ),
        pedido.numero,
    )

    # =========================================================================
    # CREAR DOCUMENTO
    # =========================================================================

    data = _post(
        "documents.json",
        payload,
    )

    document_id = (
        data.get(
            "id"
        )
    )

    folio = (
        data.get(
            "number"
        )
    )

    if not document_id:
        raise BsaleError(
            (
                "Bsale respondió sin "
                "ID de documento."
            )
        )

    # =========================================================================
    # CLIENTE
    # =========================================================================

    cliente_data = (
        data.get(
            "client"
        )
        or {}
    )

    cliente_id = (
        cliente_data.get(
            "id"
        )
    )

    # =========================================================================
    # GUARDAR RESPUESTA
    # =========================================================================

    pedido.bsale_document_id = (
        document_id
    )

    pedido.bsale_folio = (
        folio
    )

    pedido.bsale_client_id = (
        cliente_id
    )

    pedido.bsale_url_pdf = (
        data.get(
            "urlPdf"
        )
        or ""
    )

    pedido.bsale_url_publica = (
        data.get(
            "urlPublicView"
        )
        or ""
    )

    pedido.bsale_url_xml = (
        data.get(
            "urlXml"
        )
        or ""
    )

    pedido.bsale_token_documento = (
        data.get(
            "token"
        )
        or ""
    )

    pedido.bsale_emitido = True

    pedido.bsale_emitido_en = (
        timezone.now()
    )

    pedido.bsale_ultimo_error = ""

    pedido.save(
        update_fields=[
            "bsale_document_id",
            "bsale_folio",
            "bsale_client_id",
            "bsale_url_pdf",
            "bsale_url_publica",
            "bsale_url_xml",
            "bsale_token_documento",
            "bsale_emitido",
            "bsale_emitido_en",
            "bsale_ultimo_error",
            "actualizado",
        ]
    )

    logger.info(
        (
            "Boleta Bsale emitida. "
            "Pedido=%s "
            "documento=%s "
            "folio=%s "
            "total=%s."
        ),
        pedido.numero,
        document_id,
        folio,
        data.get(
            "totalAmount"
        ),
    )

    return data


# ============================================================================
# PUNTO DE ENTRADA DESDE transaction.on_commit()
# ============================================================================


def emitir_boleta_bsale_por_pedido(
    *,
    pedido_id,
):
    """
    Carga el Pedido nuevamente desde
    base de datos después del commit
    y emite la boleta.

    Esta es la función que importa
    core/services/pagos.py.
    """

    # Import local para evitar
    # dependencias circulares.
    from core.models import Pedido

    # =========================================================================
    # OBTENER PEDIDO
    # =========================================================================

    try:
        pedido = (
            Pedido.objects
            .select_related(
                "usuario",
            )
            .prefetch_related(
                "items__producto",
            )
            .get(
                pk=pedido_id,
            )
        )

    except Pedido.DoesNotExist:

        logger.error(
            (
                "No existe pedido_id=%s "
                "para emitir Bsale."
            ),
            pedido_id,
        )

        return None

    # =========================================================================
    # VALIDAR QUE ESTÉ PAGADO
    # =========================================================================

    if not pedido.pago_aprobado:

        logger.warning(
            (
                "Pedido %s no tiene "
                "pago aprobado. "
                "No se emitirá Bsale."
            ),
            pedido.numero,
        )

        return None

    # =========================================================================
    # YA EMITIDO
    # =========================================================================

    if (
        pedido.bsale_emitido
        or pedido.bsale_document_id
    ):

        logger.info(
            (
                "Pedido %s ya posee "
                "boleta Bsale %s."
            ),
            pedido.numero,
            pedido.bsale_document_id,
        )

        return {
            "id": (
                pedido.bsale_document_id
            ),
            "number": (
                pedido.bsale_folio
            ),
            "already_created": True,
        }

    # =========================================================================
    # EMITIR
    # =========================================================================

    try:

        return emitir_boleta_bsale(
            pedido
        )

    except BsaleError as error:

        logger.exception(
            (
                "Error Bsale en pedido "
                "%s: %s"
            ),
            pedido.numero,
            error,
        )

        Pedido.objects.filter(
            pk=pedido.pk
        ).update(
            bsale_ultimo_error=(
                str(error)[:2000]
            )
        )

        return None

    except Exception as error:

        logger.exception(
            (
                "Error inesperado Bsale "
                "en pedido %s: %s"
            ),
            pedido.numero,
            error,
        )

        Pedido.objects.filter(
            pk=pedido.pk
        ).update(
            bsale_ultimo_error=(
                str(error)[:2000]
            )
        )

        return None