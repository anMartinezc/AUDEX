# core/services/nubox.py

import logging
import re
import uuid

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

import requests

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPCIONES
# =============================================================================


class NuboxError(Exception):
    """
    Error controlado durante una operación
    con la API de Nubox.
    """


# =============================================================================
# CONSTANTES
# =============================================================================


IVA = Decimal("0.19")
FACTOR_IVA = Decimal("1.19")

NUBOX_BOLETA_AFECTA = "39"

NUBOX_IVA_LEGAL_CODE = "14"

NUBOX_UNIDAD = "UNID"

NUBOX_TIPO_VENTA_NORMAL = 1

NUBOX_PAGO_CONTADO = 1


# =============================================================================
# REGIONES
# =============================================================================


REGIONES_NUBOX = {
    "tarapaca": "01",
    "i tarapaca": "01",
    "antofagasta": "02",
    "ii antofagasta": "02",
    "atacama": "03",
    "iii atacama": "03",
    "coquimbo": "04",
    "iv coquimbo": "04",
    "valparaiso": "05",
    "v valparaiso": "05",
    "ohiggins": "06",
    "o'higgins": "06",
    "libertador general bernardo ohiggins": "06",
    "libertador general bernardo o'higgins": "06",
    "maule": "07",
    "biobio": "08",
    "biobío": "08",
    "la araucania": "09",
    "la araucanía": "09",
    "los lagos": "10",
    "aysen": "11",
    "aysén": "11",
    "magallanes": "12",
    "metropolitana": "13",
    "region metropolitana": "13",
    "región metropolitana": "13",
    "metropolitana de santiago": "13",
    "los rios": "14",
    "los ríos": "14",
    "arica y parinacota": "15",
    "nuble": "16",
    "ñuble": "16",
}


# =============================================================================
# UTILIDADES
# =============================================================================


def _texto(
    valor,
    *,
    max_length=None,
):
    texto = str(
        valor
        or ""
    ).strip()

    if (
        max_length
        and len(texto) > max_length
    ):
        texto = texto[:max_length]

    return texto


def _normalizar_texto(
    valor,
):
    texto = _texto(
        valor
    ).lower()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(
            origen,
            destino,
        )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    return texto


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
        raise NuboxError(
            f"Monto inválido: {valor}"
        ) from error


def _redondear_peso(
    valor,
):
    """
    Nubox trabaja con montos CLP.

    Los dejamos expresados como enteros,
    redondeados al peso.
    """

    return int(
        _decimal(
            valor
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _precio_neto_desde_bruto(
    precio_bruto,
):
    precio_bruto = _decimal(
        precio_bruto
    )

    if precio_bruto < 0:
        raise NuboxError(
            (
                "No se pueden enviar "
                "montos negativos a Nubox."
            )
        )

    return (
        precio_bruto
        / FACTOR_IVA
    )


def _separar_neto_iva(
    precio_bruto,
):
    """
    Recibe un monto final IVA incluido
    y devuelve:

    (neto, iva)

    ambos redondeados al peso.

    Se fuerza que:

        neto + iva == bruto

    para evitar diferencias de redondeo.
    """

    bruto = _redondear_peso(
        precio_bruto
    )

    neto = _redondear_peso(
        _precio_neto_desde_bruto(
            bruto
        )
    )

    iva = (
        bruto
        - neto
    )

    return (
        neto,
        iva,
    )


# =============================================================================
# CONFIGURACIÓN
# =============================================================================


def _configuracion():
    base_url = (
        getattr(
            settings,
            "NUBOX_API_URL",
            "",
        )
        or ""
    ).strip().rstrip("/")

    partner_token = (
        getattr(
            settings,
            "NUBOX_PARTNER_TOKEN",
            "",
        )
        or ""
    ).strip()

    company_api_key = (
        getattr(
            settings,
            "NUBOX_COMPANY_API_KEY",
            "",
        )
        or ""
    ).strip()

    if not base_url:
        raise NuboxError(
            "NUBOX_API_URL no está configurado."
        )

    if not partner_token:
        raise NuboxError(
            (
                "NUBOX_PARTNER_TOKEN "
                "no está configurado."
            )
        )

    if not company_api_key:
        raise NuboxError(
            (
                "NUBOX_COMPANY_API_KEY "
                "no está configurado."
            )
        )

    return {
        "base_url": base_url,
        "partner_token": (
            partner_token
        ),
        "company_api_key": (
            company_api_key
        ),
    }


# =============================================================================
# HEADERS
# =============================================================================


def _headers(
    *,
    idempotence_id=None,
    accept="application/json",
):
    config = _configuracion()

    headers = {
        "Authorization": (
            f"Bearer "
            f"{config['partner_token']}"
        ),
        "X-Api-Key": (
            config[
                "company_api_key"
            ]
        ),
        "Content-Type": (
            "application/json"
        ),
        "Accept": accept,
    }

    if idempotence_id:
        headers[
            "X-Idempotence-id"
        ] = str(
            idempotence_id
        )

    return headers


# =============================================================================
# MANEJO DE ERRORES HTTP
# =============================================================================


def _extraer_mensaje_error(
    response,
):
    try:
        data = response.json()

    except ValueError:
        texto = (
            response.text
            or ""
        ).strip()

        return (
            texto[:2000]
            or "Respuesta inválida de Nubox."
        )

    if isinstance(
        data,
        dict,
    ):
        mensaje = (
            data.get(
                "message"
            )
            or data.get(
                "error"
            )
            or data.get(
                "code"
            )
        )

        errores = (
            data.get(
                "errors"
            )
            or []
        )

        mensajes_errores = []

        if isinstance(
            errores,
            list,
        ):
            for error in errores:

                if not isinstance(
                    error,
                    dict,
                ):
                    continue

                campo = (
                    error.get(
                        "field"
                    )
                    or ""
                )

                detalle = (
                    error.get(
                        "message"
                    )
                    or ""
                )

                if campo and detalle:
                    mensajes_errores.append(
                        f"{campo}: {detalle}"
                    )

                elif detalle:
                    mensajes_errores.append(
                        detalle
                    )

        partes = []

        if mensaje:
            partes.append(
                str(mensaje)
            )

        partes.extend(
            mensajes_errores
        )

        if partes:
            return " | ".join(
                partes
            )[:2000]

    return str(
        data
    )[:2000]


# =============================================================================
# GET
# =============================================================================


def _get(
    endpoint,
    *,
    params=None,
    accept="application/json",
    devolver_bytes=False,
):
    config = _configuracion()

    url = (
        f"{config['base_url']}/"
        f"{endpoint.lstrip('/')}"
    )

    try:
        response = requests.get(
            url,
            headers=_headers(
                accept=accept,
            ),
            params=(
                params
                or {}
            ),
            timeout=30,
        )

    except requests.RequestException as error:
        raise NuboxError(
            (
                "No fue posible conectar "
                f"con Nubox: {error}"
            )
        ) from error

    if not response.ok:
        raise NuboxError(
            (
                f"Nubox HTTP "
                f"{response.status_code}: "
                f"{_extraer_mensaje_error(response)}"
            )
        )

    if devolver_bytes:
        return response.content

    try:
        return response.json()

    except ValueError as error:
        raise NuboxError(
            (
                "Nubox respondió con "
                "contenido JSON no válido."
            )
        ) from error


# =============================================================================
# POST
# =============================================================================


def _post(
    endpoint,
    payload,
    *,
    idempotence_id,
):
    config = _configuracion()

    url = (
        f"{config['base_url']}/"
        f"{endpoint.lstrip('/')}"
    )

    try:
        response = requests.post(
            url,
            headers=_headers(
                idempotence_id=(
                    idempotence_id
                ),
            ),
            json=payload,
            timeout=30,
        )

    except requests.RequestException as error:
        raise NuboxError(
            (
                "No fue posible conectar "
                f"con Nubox: {error}"
            )
        ) from error

    try:
        data = response.json()

    except ValueError as error:
        raise NuboxError(
            (
                "Nubox respondió con "
                "contenido no válido."
            )
        ) from error

    # Nubox utiliza 207 Multi-Status
    # como respuesta válida del endpoint
    # de emisión.
    if not (
        response.ok
        or response.status_code == 207
    ):
        raise NuboxError(
            (
                f"Nubox HTTP "
                f"{response.status_code}: "
                f"{_extraer_mensaje_error(response)}"
            )
        )

    return data


# =============================================================================
# CÓDIGO REGIÓN
# =============================================================================


def _codigo_region_nubox(
    pedido,
):
    """
    Nubox requiere territorialDivisionLegalCode.

    Prioridad:

    1. pedido.nubox_region_codigo
    2. pedido.region_codigo
    3. NUBOX_REGION_CODES en settings
    4. mapping interno de regiones chilenas
    """

    for atributo in (
        "nubox_region_codigo",
        "region_codigo",
        "codigo_region",
    ):
        valor = getattr(
            pedido,
            atributo,
            None,
        )

        if valor:
            return str(
                valor
            ).zfill(2)

    region = _texto(
        getattr(
            pedido,
            "region",
            "",
        )
    )

    if not region:
        raise NuboxError(
            (
                "El pedido no contiene "
                "región."
            )
        )

    mappings = getattr(
        settings,
        "NUBOX_REGION_CODES",
        {},
    )

    if isinstance(
        mappings,
        dict,
    ):
        for nombre, codigo in mappings.items():

            if (
                _normalizar_texto(nombre)
                == _normalizar_texto(region)
            ):
                return str(
                    codigo
                ).zfill(2)

    normalizada = (
        _normalizar_texto(
            region
        )
    )

    codigo = (
        REGIONES_NUBOX.get(
            normalizada
        )
    )

    if codigo:
        return codigo

    raise NuboxError(
        (
            "No fue posible determinar "
            "el código Nubox/SII de la región "
            f"'{region}'."
        )
    )


# =============================================================================
# CÓDIGO COMUNA
# =============================================================================


def _codigo_comuna_nubox(
    pedido,
):
    """
    Nubox requiere el código legal SII
    de la comuna.

    Ejemplo:

        Santiago -> 13101

    No se intenta inventar el código.

    Puede venir:

    1. directamente desde Pedido;
    2. desde NUBOX_COMUNA_CODES en settings.
    """

    for atributo in (
        "nubox_comuna_codigo",
        "comuna_codigo",
        "codigo_comuna",
    ):
        valor = getattr(
            pedido,
            atributo,
            None,
        )

        if valor:
            return str(
                valor
            ).zfill(5)

    comuna = _texto(
        getattr(
            pedido,
            "comuna",
            "",
        )
    )

    if not comuna:
        raise NuboxError(
            (
                "El pedido no contiene "
                "comuna."
            )
        )

    mappings = getattr(
        settings,
        "NUBOX_COMUNA_CODES",
        {},
    )

    if isinstance(
        mappings,
        dict,
    ):
        normalizada = (
            _normalizar_texto(
                comuna
            )
        )

        for nombre, codigo in mappings.items():

            if (
                _normalizar_texto(nombre)
                == normalizada
            ):
                return str(
                    codigo
                ).zfill(5)

    # También aceptamos que pedido.comuna
    # ya venga directamente con el código SII.
    if re.fullmatch(
        r"\d{5}",
        comuna,
    ):
        return comuna

    raise NuboxError(
        (
            "No existe código Nubox/SII "
            f"configurado para la comuna "
            f"'{comuna}'. "
            "Configura NUBOX_COMUNA_CODES "
            "o guarda el código en el Pedido."
        )
    )


# =============================================================================
# CLIENTE
# =============================================================================


def _crear_cliente_nubox(
    pedido,
):
    rut = (
        _texto(
            getattr(
                pedido,
                "rut",
                "",
            )
        )
        .upper()
        .replace(
            ".",
            "",
        )
    )

    nombre = _texto(
        getattr(
            pedido,
            "nombre",
            "",
        ),
        max_length=50,
    )

    apellido = _texto(
        getattr(
            pedido,
            "apellido",
            "",
        ),
        max_length=50,
    )

    nombre_completo = (
        f"{nombre} {apellido}"
    ).strip()

    email = _texto(
        getattr(
            pedido,
            "email",
            "",
        ),
        max_length=100,
    ).lower()

    telefono = _texto(
        getattr(
            pedido,
            "telefono",
            "",
        ),
        max_length=30,
    )

    direccion = _texto(
        getattr(
            pedido,
            "direccion_completa",
            "",
        ),
        max_length=200,
    )

    comuna = _texto(
        getattr(
            pedido,
            "comuna",
            "",
        ),
        max_length=50,
    )

    if not rut:
        raise NuboxError(
            (
                "El pedido no tiene RUT "
                "para emitir la boleta."
            )
        )

    if not nombre_completo:
        raise NuboxError(
            (
                "El pedido no tiene "
                "nombre del cliente."
            )
        )

    if not email:
        raise NuboxError(
            (
                "El pedido no tiene "
                "correo electrónico."
            )
        )

    actividad = _texto(
        getattr(
            settings,
            "NUBOX_CLIENT_MAIN_ACTIVITY",
            "Consumidor final",
        ),
        max_length=40,
    )

    cliente = {
        "tradeName": (
            nombre_completo[:100]
        ),

        "identification": {
            "type": 1,
            "value": rut,
        },

        "mainActivity": (
            actividad
        ),

        "email": email,

        "contactName": (
            nombre_completo[:100]
        ),

        "address": direccion,

        "city": comuna,

        "territorialDivisionLegalCode": (
            _codigo_region_nubox(
                pedido
            )
        ),

        "territorialDivisionL2LegalCode": (
            _codigo_comuna_nubox(
                pedido
            )
        ),
    }

    if telefono:
        cliente[
            "phone"
        ] = telefono

    return cliente


# =============================================================================
# PRODUCT CODE
# =============================================================================


def _codigo_producto_nubox(
    item,
    *,
    indice,
):
    """
    Nubox limita productCode a determinados
    caracteres y máximo 35 caracteres.
    """

    producto = getattr(
        item,
        "producto",
        None,
    )

    posibles = [
        getattr(
            producto,
            "sku",
            None,
        ),
        getattr(
            producto,
            "codigo",
            None,
        ),
        getattr(
            producto,
            "id",
            None,
        ),
        getattr(
            item,
            "producto_id",
            None,
        ),
    ]

    codigo = ""

    for valor in posibles:

        if valor:
            codigo = str(
                valor
            )
            break

    if not codigo:
        codigo = (
            f"AUDEX-{indice}"
        )

    codigo = re.sub(
        r"[^A-Za-z0-9\-_\.#@\[\]\(\)\{\}]",
        "-",
        codigo,
    )

    return codigo[:35]


# =============================================================================
# DETALLES
# =============================================================================


def _crear_detalles_nubox(
    pedido,
):
    """
    Genera los detalles para Nubox desde
    PedidoItem.

    En la integración Nubox,
    usamos total_final porque contempla:

    - precio/oferta;
    - cantidad;
    - descuento por código.

    Cada PedidoItem se envía como una línea
    económica completa quantity=1 para que
    el total emitido coincida exactamente
    con el pedido.
    """

    detalles = []

    items = list(
        pedido.items.all()
    )

    if not items:
        raise NuboxError(
            (
                "El pedido no contiene "
                "productos."
            )
        )

    total_productos = Decimal(
        "0"
    )

    orden = 1

    for item in items:

        cantidad_real = int(
            getattr(
                item,
                "cantidad",
                0,
            )
            or 0
        )

        if cantidad_real <= 0:
            raise NuboxError(
                (
                    "Existe un ítem con "
                    "cantidad inválida."
                )
            )

        total_final = _decimal(
            getattr(
                item,
                "total_final",
                0,
            )
        )

        # Compatibilidad con pedidos
        # históricos.
        if total_final <= 0:

            total_original = _decimal(
                getattr(
                    item,
                    "total",
                    0,
                )
            )

            descuento_codigo = _decimal(
                getattr(
                    item,
                    "descuento_codigo",
                    0,
                )
            )

            if total_original > 0:
                total_final = max(
                    (
                        total_original
                        - descuento_codigo
                    ),
                    Decimal("0"),
                )

        if total_final <= 0:
            continue

        total_productos += (
            total_final
        )

        (
            neto,
            iva,
        ) = _separar_neto_iva(
            total_final
        )

        nombre_producto = _texto(
            getattr(
                item,
                "nombre_producto",
                "",
            )
            or "Producto Audex",
            max_length=80,
        )

        descripcion_extendida = (
            f"{nombre_producto} "
            f"x {cantidad_real}"
        )

        detalles.append(
            {
                "order": orden,

                "productCode": (
                    _codigo_producto_nubox(
                        item,
                        indice=orden,
                    )
                ),

                # Se envía como línea
                # económica completa.
                "quantity": 1,

                "productDescription": (
                    nombre_producto
                ),

                "productDescriptionExtended": (
                    descripcion_extendida[:1000]
                ),

                "subjectToTax": True,

                "uom": {
                    "code": (
                        NUBOX_UNIDAD
                    )
                },

                # Precio NETO.
                "price": neto,

                "taxes": [
                    {
                        "legalCode": (
                            NUBOX_IVA_LEGAL_CODE
                        ),
                        "amount": iva,
                    }
                ],

                "discountsAndSurcharges": [],
            }
        )

        orden += 1

    if not detalles:
        raise NuboxError(
            (
                "No existen productos "
                "válidos para emitir."
            )
        )

    return (
        detalles,
        total_productos,
    )


# =============================================================================
# DESPACHO
# =============================================================================


def _agregar_despacho_nubox(
    *,
    pedido,
    detalles,
):
    despacho = _decimal(
        getattr(
            pedido,
            "despacho",
            0,
        )
    )

    if despacho <= 0:
        return Decimal(
            "0"
        )

    (
        neto,
        iva,
    ) = _separar_neto_iva(
        despacho
    )

    detalles.append(
        {
            "order": (
                len(detalles)
                + 1
            ),

            "productCode": (
                "DESPACHO"
            ),

            "quantity": 1,

            "productDescription": (
                "Despacho Blue Express"
            ),

            "productDescriptionExtended": (
                "Servicio de despacho "
                "pedido Audex"
            ),

            "subjectToTax": True,

            "uom": {
                "code": (
                    NUBOX_UNIDAD
                )
            },

            "price": neto,

            "taxes": [
                {
                    "legalCode": (
                        NUBOX_IVA_LEGAL_CODE
                    ),
                    "amount": iva,
                }
            ],

            "discountsAndSurcharges": [],
        }
    )

    return despacho


# =============================================================================
# PAYLOAD
# =============================================================================


def _crear_payload_nubox(
    pedido,
):
    cliente = (
        _crear_cliente_nubox(
            pedido
        )
    )

    (
        detalles,
        total_productos,
    ) = (
        _crear_detalles_nubox(
            pedido
        )
    )

    despacho = (
        _agregar_despacho_nubox(
            pedido=pedido,
            detalles=detalles,
        )
    )

    total_esperado = (
        total_productos
        + despacho
    )

    total_pedido = _decimal(
        getattr(
            pedido,
            "total",
            0,
        )
    )

    if (
        _redondear_peso(
            total_esperado
        )
        !=
        _redondear_peso(
            total_pedido
        )
    ):
        raise NuboxError(
            (
                "El total que se enviará "
                "a Nubox no coincide con "
                "el pedido. "
                f"Productos+despacho="
                f"{total_esperado}, "
                f"Pedido={total_pedido}, "
                f"Número={pedido.numero}."
            )
        )

    fecha_pago = (
        timezone.localdate()
        .isoformat()
    )

    documento = {
        "sequence": 1,

        "type": {
            "legalCode": (
                str(
                    getattr(
                        settings,
                        "NUBOX_BOLETA_LEGAL_CODE",
                        NUBOX_BOLETA_AFECTA,
                    )
                )
            )
        },

        "client": cliente,

        "saleType": {
            "id": (
                int(
                    getattr(
                        settings,
                        "NUBOX_SALE_TYPE_ID",
                        NUBOX_TIPO_VENTA_NORMAL,
                    )
                )
            )
        },

        "paymentForm": {
            "id": (
                int(
                    getattr(
                        settings,
                        "NUBOX_PAYMENT_FORM_ID",
                        NUBOX_PAGO_CONTADO,
                    )
                )
            )
        },

        "paymentDate": (
            fecha_pago
        ),

        "comment": (
            f"Pedido Audex "
            f"{pedido.numero}"
        )[:500],

        "details": detalles,

        "references": [],
    }

    # La API de emisión recibe un ARRAY
    # incluso cuando se envía una sola boleta.
    return [
        documento
    ]


# =============================================================================
# VALIDAR RESPUESTA EMISIÓN
# =============================================================================


def _procesar_respuesta_emision(
    data,
):
    if not isinstance(
        data,
        list,
    ):
        raise NuboxError(
            (
                "Nubox respondió con un "
                "formato inesperado al emitir."
            )
        )

    if not data:
        raise NuboxError(
            (
                "Nubox respondió sin "
                "documentos."
            )
        )

    resultado = data[0]

    if not isinstance(
        resultado,
        dict,
    ):
        raise NuboxError(
            (
                "Respuesta de emisión "
                "Nubox inválida."
            )
        )

    errores = (
        resultado.get(
            "errors"
        )
        or []
    )

    if errores:

        mensajes = []

        for error in errores:

            if not isinstance(
                error,
                dict,
            ):
                mensajes.append(
                    str(error)
                )
                continue

            campo = (
                error.get(
                    "field"
                )
                or ""
            )

            mensaje = (
                error.get(
                    "message"
                )
                or "Error de validación."
            )

            if campo:
                mensajes.append(
                    f"{campo}: {mensaje}"
                )

            else:
                mensajes.append(
                    mensaje
                )

        raise NuboxError(
            (
                "Nubox rechazó la boleta: "
                + " | ".join(
                    mensajes
                )
            )
        )

    document_id = (
        resultado.get(
            "id"
        )
    )

    if not document_id:
        raise NuboxError(
            (
                "Nubox aceptó la solicitud "
                "pero respondió sin ID "
                "de documento."
            )
        )

    return resultado


# =============================================================================
# EMITIR BOLETA
# =============================================================================


def emitir_boleta_nubox(
    pedido,
):
    """
    Envía la boleta a la cola de emisión
    de Nubox.

    IMPORTANTE:

    Esta función NO significa que la boleta
    ya haya sido aceptada por el SII.

    La API Nubox es asíncrona.

    Después se debe consultar:

        GET /v1/sales/{document_id}
    """

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not (
        pedido.pagado
        and pedido.estado_pago
        == pedido.EstadoPago.APROBADO
    ):
        raise NuboxError(
            (
                "No se puede emitir una "
                "boleta para un pedido "
                "no pagado."
            )
        )

    # =========================================================================
    # IDEMPOTENCIA LOCAL
    # =========================================================================

    document_id_existente = (
        getattr(
            pedido,
            "nubox_document_id",
            None,
        )
    )

    if document_id_existente:
        return {
            "id": (
                document_id_existente
            ),
            "already_created": True,
        }

    # =========================================================================
    # X-IDEMPOTENCE-ID
    # =========================================================================

    idempotence_id = (
        getattr(
            pedido,
            "nubox_idempotence_id",
            None,
        )
    )

    if not idempotence_id:
        idempotence_id = (
            str(
                uuid.uuid4()
            )
        )

        # Solo guardamos si el modelo
        # ya posee el campo.
        if hasattr(
            pedido,
            "nubox_idempotence_id",
        ):
            pedido.nubox_idempotence_id = (
                idempotence_id
            )

            pedido.save(
                update_fields=[
                    "nubox_idempotence_id",
                    "actualizado",
                ]
            )

    # =========================================================================
    # PAYLOAD
    # =========================================================================

    payload = (
        _crear_payload_nubox(
            pedido
        )
    )

    logger.info(
        (
            "Enviando boleta Nubox "
            "para pedido %s. "
            "Idempotence=%s"
        ),
        pedido.numero,
        idempotence_id,
    )

    # =========================================================================
    # EMITIR
    # =========================================================================

    data = _post(
        "v1/sales/issuance",
        payload,
        idempotence_id=(
            idempotence_id
        ),
    )

    resultado = (
        _procesar_respuesta_emision(
            data
        )
    )

    document_id = (
        resultado.get(
            "id"
        )
    )

    # =========================================================================
    # GUARDAR
    # =========================================================================

    campos_update = []

    if hasattr(
        pedido,
        "nubox_document_id",
    ):
        pedido.nubox_document_id = (
            document_id
        )

        campos_update.append(
            "nubox_document_id"
        )

    if hasattr(
        pedido,
        "nubox_estado",
    ):
        pedido.nubox_estado = (
            "PENDIENTE"
        )

        campos_update.append(
            "nubox_estado"
        )

    if hasattr(
        pedido,
        "nubox_emitido",
    ):
        # Todavía NO está emitido.
        pedido.nubox_emitido = False

        campos_update.append(
            "nubox_emitido"
        )

    if hasattr(
        pedido,
        "nubox_ultimo_error",
    ):
        pedido.nubox_ultimo_error = ""

        campos_update.append(
            "nubox_ultimo_error"
        )

    if campos_update:

        campos_update.append(
            "actualizado"
        )

        pedido.save(
            update_fields=(
                campos_update
            )
        )

    logger.info(
        (
            "Solicitud de emisión Nubox "
            "recibida. Pedido=%s "
            "documentId=%s."
        ),
        pedido.numero,
        document_id,
    )

    return resultado


# =============================================================================
# CONSULTAR DOCUMENTO
# =============================================================================


def consultar_documento_nubox(
    document_id,
):
    if not document_id:
        raise NuboxError(
            (
                "document_id es obligatorio "
                "para consultar Nubox."
            )
        )

    return _get(
        (
            f"v1/sales/"
            f"{document_id}"
        )
    )


# =============================================================================
# SINCRONIZAR ESTADO
# =============================================================================


def sincronizar_estado_nubox(
    pedido,
):
    document_id = (
        getattr(
            pedido,
            "nubox_document_id",
            None,
        )
    )

    if not document_id:
        raise NuboxError(
            (
                "El pedido no posee "
                "nubox_document_id."
            )
        )

    data = (
        consultar_documento_nubox(
            document_id
        )
    )

    # Nubox puede devolver la estructura
    # del estado con campos adicionales.
    #
    # Dejamos extracción tolerante para
    # no romper la integración si cambia
    # la representación secundaria.

    estado = (
        data.get(
            "status"
        )
        or data.get(
            "state"
        )
        or data.get(
            "emissionStatus"
        )
        or {}
    )

    if isinstance(
        estado,
        dict,
    ):
        estado_nombre = (
            estado.get(
                "name"
            )
            or estado.get(
                "description"
            )
            or estado.get(
                "code"
            )
            or ""
        )

    else:
        estado_nombre = str(
            estado
            or ""
        )

    folio = (
        data.get(
            "number"
        )
        or data.get(
            "folio"
        )
        or ""
    )

    campos_update = []

    if hasattr(
        pedido,
        "nubox_folio",
    ) and folio:

        pedido.nubox_folio = (
            str(
                folio
            )
        )

        campos_update.append(
            "nubox_folio"
        )

    if hasattr(
        pedido,
        "nubox_estado",
    ):

        pedido.nubox_estado = (
            estado_nombre[:100]
            or "PROCESANDO"
        )

        campos_update.append(
            "nubox_estado"
        )

    estado_normalizado = (
        _normalizar_texto(
            estado_nombre
        )
    )

    emitido = (
        estado_normalizado
        in {
            "emitido",
            "aceptado",
            "accepted",
            "issued",
        }
    )

    if (
        emitido
        and hasattr(
            pedido,
            "nubox_emitido",
        )
    ):
        pedido.nubox_emitido = True

        campos_update.append(
            "nubox_emitido"
        )

        if hasattr(
            pedido,
            "nubox_emitido_en",
        ):
            if not (
                pedido.nubox_emitido_en
            ):
                pedido.nubox_emitido_en = (
                    timezone.now()
                )

                campos_update.append(
                    "nubox_emitido_en"
                )

    if campos_update:

        campos_update.append(
            "actualizado"
        )

        pedido.save(
            update_fields=list(
                dict.fromkeys(
                    campos_update
                )
            )
        )

    return data


# =============================================================================
# PDF
# =============================================================================


def obtener_pdf_nubox(
    document_id,
    *,
    formato="A4",
):
    """
    Retorna los bytes del PDF.

    formato:
        A4
        80MM
    """

    formato = (
        str(
            formato
            or "A4"
        )
        .strip()
        .upper()
    )

    templates = {
        "A4": "TEMPLATE_A4",
        "80MM": "TEMPLATE_80MM",
    }

    template = (
        templates.get(
            formato
        )
    )

    if not template:
        raise NuboxError(
            (
                "Formato PDF Nubox "
                "no válido."
            )
        )

    return _get(
        (
            f"v1/sales/"
            f"{document_id}/pdf"
        ),
        params={
            "template": template,
        },
        accept="application/pdf",
        devolver_bytes=True,
    )


# =============================================================================
# XML
# =============================================================================


def obtener_xml_nubox(
    document_id,
):
    """
    Retorna los bytes del XML tributario.
    """

    return _get(
        (
            f"v1/sales/"
            f"{document_id}/xml"
        ),
        accept="application/xml",
        devolver_bytes=True,
    )


# =============================================================================
# PUNTO DE ENTRADA POR PEDIDO
# =============================================================================


def emitir_boleta_nubox_por_pedido(
    *,
    pedido_id,
):
    """
    Carga nuevamente el Pedido desde
    base de datos después del commit.

    Este es el punto de entrada utilizado
    desde core/services/pagos.py para emitir
    la boleta Nubox después del commit.
    """

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
                "para emitir Nubox."
            ),
            pedido_id,
        )

        return None

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not pedido.pago_aprobado:

        logger.warning(
            (
                "Pedido %s no tiene "
                "pago aprobado. "
                "No se emitirá Nubox."
            ),
            pedido.numero,
        )

        return None

    # =========================================================================
    # YA ENVIADO
    # =========================================================================

    document_id = (
        getattr(
            pedido,
            "nubox_document_id",
            None,
        )
    )

    if document_id:

        logger.info(
            (
                "Pedido %s ya posee "
                "documento Nubox %s."
            ),
            pedido.numero,
            document_id,
        )

        return {
            "id": document_id,
            "already_created": True,
        }

    # =========================================================================
    # EMITIR
    # =========================================================================

    try:

        return emitir_boleta_nubox(
            pedido
        )

    except NuboxError as error:

        logger.exception(
            (
                "Error Nubox en pedido "
                "%s: %s"
            ),
            pedido.numero,
            error,
        )

        if hasattr(
            pedido,
            "nubox_ultimo_error",
        ):
            Pedido.objects.filter(
                pk=pedido.pk
            ).update(
                nubox_ultimo_error=(
                    str(error)[:2000]
                )
            )

        return None

    except Exception as error:

        logger.exception(
            (
                "Error inesperado Nubox "
                "en pedido %s: %s"
            ),
            pedido.numero,
            error,
        )

        if hasattr(
            pedido,
            "nubox_ultimo_error",
        ):
            Pedido.objects.filter(
                pk=pedido.pk
            ).update(
                nubox_ultimo_error=(
                    str(error)[:2000]
                )
            )

        return None