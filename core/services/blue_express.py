from dataclasses import dataclass

from django.db.models import Q

from core.models import (
    Producto,
    ReglaEnvioProducto,
    TarifaBlueExpress,
)


# =============================================================================
# BLUE EXPRESS
# =============================================================================
#
# ORIGEN:
# Todos los pedidos salen desde Santiago.
#
# ENTREGA:
# A domicilio.
#
# ---------------------------------------------------------------------------
# CÁLCULO AUTOMÁTICO GENERAL
# ---------------------------------------------------------------------------
#
# Se calcula utilizando la cantidad TOTAL de unidades del carrito:
#
# 1 - 2 unidades   -> XS
# 3 - 5 unidades   -> S
# 6 - 10 unidades  -> M
# 11 - 20 unidades -> L
#
# ---------------------------------------------------------------------------
# REGLAS ESPECIALES POR PRODUCTO
# ---------------------------------------------------------------------------
#
# Algunos productos pueden necesitar una talla superior debido
# a sus dimensiones.
#
# Ejemplo:
#
# Parlante grande:
#
# 1 - 2 unidades -> M
# 3 - 5 unidades -> L
#
# Si el carrito contiene:
#
# 1 parlante
#
# automático general -> XS
# regla especial      -> M
#
# resultado final     -> M
#
# IMPORTANTE:
#
# La regla especial NUNCA puede reducir la talla automática.
# Siempre se utiliza la talla más grande.
#
# =============================================================================


# =============================================================================
# ORDEN DE TALLAS
# =============================================================================

ORDEN_TALLAS_BLUE_EXPRESS = {
    "XS": 1,
    "S": 2,
    "M": 3,
    "L": 4,
}


# =============================================================================
# TIEMPOS BLUE EXPRESS
# =============================================================================

TIEMPOS_BLUE_EXPRESS = {
    "SANTIAGO": 48,
    "CENTRO": 72,
    "EXTREMO": 72,
}


# =============================================================================
# REGIONES POR ZONA
# =============================================================================

REGIONES_SANTIAGO = {
    "Metropolitana",
}


REGIONES_CENTRO = {
    "Coquimbo",
    "Valparaíso",
    "O’Higgins",
    "Maule",
    "Ñuble",
    "Biobío",
    "La Araucanía",
    "Los Ríos",
    "Los Lagos",
}


REGIONES_EXTREMO = {
    "Arica y Parinacota",
    "Tarapacá",
    "Antofagasta",
    "Atacama",
    "Aysén",
    "Magallanes",
}


# =============================================================================
# RESULTADO DE COTIZACIÓN
# =============================================================================

@dataclass(frozen=True)
class CotizacionBlueExpress:
    cantidad_productos: int
    talla: str
    zona: str
    costo: int


# =============================================================================
# NORMALIZAR TALLA
# =============================================================================

def normalizar_talla_blue_express(
    talla,
):
    talla = str(
        talla or ""
    ).strip().upper()

    if not talla:
        return ""

    if talla not in ORDEN_TALLAS_BLUE_EXPRESS:
        raise ValueError(
            (
                "La talla Blue Express "
                f"'{talla}' no es válida."
            )
        )

    return talla


# =============================================================================
# TALLA AUTOMÁTICA SEGÚN CANTIDAD TOTAL
# =============================================================================

def obtener_talla_blue_express(
    cantidad_productos,
):
    try:

        cantidad_productos = int(
            cantidad_productos
        )

    except (
        TypeError,
        ValueError,
    ):

        cantidad_productos = 0

    if cantidad_productos <= 0:
        raise ValueError(
            (
                "No es posible calcular el envío "
                "para un carrito vacío."
            )
        )

    if cantidad_productos <= 2:
        return "XS"

    if cantidad_productos <= 5:
        return "S"

    if cantidad_productos <= 10:
        return "M"

    if cantidad_productos <= 20:
        return "L"

    raise ValueError(
        (
            "Los pedidos superiores a 20 unidades "
            "requieren cotización manual."
        )
    )


# =============================================================================
# COMPARAR DOS TALLAS
# =============================================================================

def obtener_talla_mayor_blue_express(
    *,
    talla_actual,
    talla_minima,
):
    talla_actual = (
        normalizar_talla_blue_express(
            talla_actual
        )
    )

    talla_minima = (
        normalizar_talla_blue_express(
            talla_minima
        )
    )

    if not talla_actual:
        return talla_minima

    if not talla_minima:
        return talla_actual

    nivel_actual = (
        ORDEN_TALLAS_BLUE_EXPRESS[
            talla_actual
        ]
    )

    nivel_minimo = (
        ORDEN_TALLAS_BLUE_EXPRESS[
            talla_minima
        ]
    )

    if nivel_minimo > nivel_actual:
        return talla_minima

    return talla_actual


# =============================================================================
# OBTENER ZONA SEGÚN REGIÓN
# =============================================================================

def obtener_zona_blue_express(
    region,
):
    region = str(
        region or ""
    ).strip()

    if not region:
        raise ValueError(
            (
                "Debes seleccionar una región "
                "para calcular el despacho."
            )
        )

    if region in REGIONES_SANTIAGO:
        return "SANTIAGO"

    if region in REGIONES_CENTRO:
        return "CENTRO"

    if region in REGIONES_EXTREMO:
        return "EXTREMO"

    raise ValueError(
        (
            "La región seleccionada no tiene "
            "una zona Blue Express configurada: "
            f"{region}."
        )
    )


# =============================================================================
# OBTENER LÍNEAS DEL CARRITO
# =============================================================================

def obtener_lineas_carrito(
    carrito_serializado,
):
    if not isinstance(
        carrito_serializado,
        dict,
    ):
        return []

    for clave in (
        "items",
        "productos",
        "lineas",
        "detalle",
    ):

        elementos = (
            carrito_serializado.get(
                clave,
                []
            )
            or []
        )

        if (
            isinstance(
                elementos,
                list,
            )
            and elementos
        ):
            return elementos

    return []


# =============================================================================
# CANTIDAD TOTAL DEL CARRITO
# =============================================================================

def obtener_cantidad_total_carrito(
    carrito_serializado,
):
    if not isinstance(
        carrito_serializado,
        dict,
    ):
        return 0

    # -------------------------------------------------------------------------
    # PRIMER INTENTO
    #
    # Utilizar cantidad_total ya calculada.
    # -------------------------------------------------------------------------

    for clave in (
        "cantidad_total",
        "total_unidades",
        "cantidad_productos",
    ):

        valor = (
            carrito_serializado.get(
                clave
            )
        )

        if valor in (
            None,
            "",
        ):
            continue

        try:

            cantidad = int(
                valor
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if cantidad > 0:
            return cantidad

    # -------------------------------------------------------------------------
    # SEGUNDO INTENTO
    #
    # Sumar cantidades de todas las líneas.
    # -------------------------------------------------------------------------

    elementos = (
        obtener_lineas_carrito(
            carrito_serializado
        )
    )

    cantidad_total = 0

    for item in elementos:

        if not isinstance(
            item,
            dict,
        ):
            continue

        try:

            cantidad = int(
                item.get(
                    "cantidad",
                    0,
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            cantidad = 0

        if cantidad > 0:
            cantidad_total += (
                cantidad
            )

    return cantidad_total


# =============================================================================
# EXTRAER ID DE UN ITEM
# =============================================================================

def obtener_producto_id_item(
    item,
):
    if not isinstance(
        item,
        dict,
    ):
        return None

    # -------------------------------------------------------------------------
    # ID DIRECTO
    # -------------------------------------------------------------------------

    for clave in (
        "producto_id",
        "product_id",
        "id_producto",
        "id",
        "pk",
    ):

        valor = item.get(
            clave
        )

        if valor in (
            None,
            "",
        ):
            continue

        try:

            return int(
                valor
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

    # -------------------------------------------------------------------------
    # PRODUCTO ANIDADO
    # -------------------------------------------------------------------------

    producto_data = (
        item.get(
            "producto"
        )
    )

    if isinstance(
        producto_data,
        dict,
    ):

        for clave in (
            "producto_id",
            "id",
            "pk",
        ):

            valor = (
                producto_data.get(
                    clave
                )
            )

            if valor in (
                None,
                "",
            ):
                continue

            try:

                return int(
                    valor
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

    elif producto_data not in (
        None,
        "",
    ):

        try:

            return int(
                producto_data
            )

        except (
            TypeError,
            ValueError,
        ):

            pass

    return None


# =============================================================================
# EXTRAER SLUG DE UN ITEM
# =============================================================================

def obtener_producto_slug_item(
    item,
):
    if not isinstance(
        item,
        dict,
    ):
        return ""

    # -------------------------------------------------------------------------
    # SLUG DIRECTO
    # -------------------------------------------------------------------------

    for clave in (
        "producto_slug",
        "product_slug",
        "slug",
    ):

        valor = str(
            item.get(
                clave,
                "",
            )
            or ""
        ).strip()

        if valor:
            return valor

    # -------------------------------------------------------------------------
    # PRODUCTO ANIDADO
    # -------------------------------------------------------------------------

    producto_data = (
        item.get(
            "producto"
        )
    )

    if isinstance(
        producto_data,
        dict,
    ):

        valor = str(
            producto_data.get(
                "slug",
                "",
            )
            or ""
        ).strip()

        if valor:
            return valor

    return ""


# =============================================================================
# CANTIDAD DE CADA PRODUCTO
# =============================================================================

def obtener_cantidades_productos_carrito(
    carrito_serializado,
):
    """
    Obtiene la cantidad comprada de cada producto.

    Retorna:

        cantidades_por_id
        cantidades_por_slug

    Ejemplo:

        {
            8: 2,
            10: 1,
        }

    Esto es diferente de cantidad_total.

    Las reglas especiales se aplican según la cantidad
    específica de cada producto.
    """

    elementos = (
        obtener_lineas_carrito(
            carrito_serializado
        )
    )

    cantidades_por_id = {}
    cantidades_por_slug = {}

    for item in elementos:

        if not isinstance(
            item,
            dict,
        ):
            continue

        # ---------------------------------------------------------------------
        # CANTIDAD
        # ---------------------------------------------------------------------

        try:

            cantidad = int(
                item.get(
                    "cantidad",
                    0,
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            cantidad = 0

        if cantidad <= 0:
            continue

        # ---------------------------------------------------------------------
        # PRODUCTO
        # ---------------------------------------------------------------------

        producto_id = (
            obtener_producto_id_item(
                item
            )
        )

        slug = (
            obtener_producto_slug_item(
                item
            )
        )

        # ---------------------------------------------------------------------
        # PREFERIR ID
        # ---------------------------------------------------------------------

        if producto_id is not None:

            cantidades_por_id[
                producto_id
            ] = (
                cantidades_por_id.get(
                    producto_id,
                    0,
                )
                + cantidad
            )

            continue

        # ---------------------------------------------------------------------
        # FALLBACK POR SLUG
        # ---------------------------------------------------------------------

        if slug:

            cantidades_por_slug[
                slug
            ] = (
                cantidades_por_slug.get(
                    slug,
                    0,
                )
                + cantidad
            )

    return (
        cantidades_por_id,
        cantidades_por_slug,
    )


# =============================================================================
# OBTENER PRODUCTOS DEL CARRITO
# =============================================================================

def obtener_productos_carrito(
    carrito_serializado,
):
    (
        cantidades_por_id,
        cantidades_por_slug,
    ) = (
        obtener_cantidades_productos_carrito(
            carrito_serializado
        )
    )

    ids_productos = set(
        cantidades_por_id.keys()
    )

    slugs_productos = set(
        cantidades_por_slug.keys()
    )

    if (
        not ids_productos
        and not slugs_productos
    ):
        return (
            [],
            cantidades_por_id,
            cantidades_por_slug,
        )

    consulta = Q()

    if ids_productos:

        consulta |= Q(
            pk__in=ids_productos
        )

    if slugs_productos:

        consulta |= Q(
            slug__in=slugs_productos
        )

    productos = list(
        Producto.objects
        .filter(
            consulta,
            activo=True,
        )
    )

    return (
        productos,
        cantidades_por_id,
        cantidades_por_slug,
    )


# =============================================================================
# TALLA ESPECIAL POR REGLAS DE PRODUCTO
# =============================================================================

def obtener_talla_especial_productos_carrito(
    carrito_serializado,
):
    """
    Busca las reglas especiales activas de todos
    los productos presentes en el carrito.

    Ejemplo:

        Parlante:
            cantidad carrito = 1

        regla:
            desde = 1
            hasta = 2
            talla = M

        resultado especial:
            M

    Si varios productos tienen reglas especiales,
    se utiliza la talla más grande entre ellas.
    """

    (
        productos,
        cantidades_por_id,
        cantidades_por_slug,
    ) = (
        obtener_productos_carrito(
            carrito_serializado
        )
    )

    if not productos:
        return ""

    productos_por_id = {
        producto.id: producto
        for producto in productos
    }

    # =========================================================================
    # CANTIDADES DEFINITIVAS POR PRODUCTO
    # =========================================================================

    cantidades_definitivas = {}

    for producto in productos:

        cantidad = (
            cantidades_por_id.get(
                producto.id,
                0,
            )
        )

        # ---------------------------------------------------------------------
        # Si el item llegó solamente identificado por slug.
        # ---------------------------------------------------------------------

        cantidad += (
            cantidades_por_slug.get(
                producto.slug,
                0,
            )
        )

        if cantidad > 0:

            cantidades_definitivas[
                producto.id
            ] = cantidad

    if not cantidades_definitivas:
        return ""

    # =========================================================================
    # CONSULTAR TODAS LAS REGLAS ACTIVAS EN UNA SOLA CONSULTA
    # =========================================================================

    reglas = (
        ReglaEnvioProducto.objects
        .filter(
            producto_id__in=(
                cantidades_definitivas.keys()
            ),
            activa=True,
        )
        .order_by(
            "producto_id",
            "cantidad_desde",
            "cantidad_hasta",
            "pk",
        )
    )

    # =========================================================================
    # TALLA ESPECIAL MAYOR
    # =========================================================================

    talla_especial_mayor = ""

    for regla in reglas:

        cantidad_producto = (
            cantidades_definitivas.get(
                regla.producto_id,
                0,
            )
        )

        if cantidad_producto <= 0:
            continue

        # ---------------------------------------------------------------------
        # COMPROBAR RANGO
        # ---------------------------------------------------------------------

        aplica = (
            regla.cantidad_desde
            <= cantidad_producto
            <= regla.cantidad_hasta
        )

        if not aplica:
            continue

        talla_regla = (
            normalizar_talla_blue_express(
                regla.talla
            )
        )

        if not talla_regla:
            continue

        # ---------------------------------------------------------------------
        # PRIMERA REGLA
        # ---------------------------------------------------------------------

        if not talla_especial_mayor:

            talla_especial_mayor = (
                talla_regla
            )

            continue

        # ---------------------------------------------------------------------
        # VARIAS REGLAS / VARIOS PRODUCTOS
        #
        # Por seguridad utilizamos siempre la más grande.
        # ---------------------------------------------------------------------

        talla_especial_mayor = (
            obtener_talla_mayor_blue_express(
                talla_actual=(
                    talla_especial_mayor
                ),
                talla_minima=(
                    talla_regla
                ),
            )
        )

    return talla_especial_mayor


# =============================================================================
# TALLA FINAL DEL CARRITO
# =============================================================================

def obtener_talla_final_blue_express(
    *,
    carrito_serializado,
    cantidad_productos,
):
    """
    Calcula la talla final.

    PASO 1:
        calcula la talla automática por cantidad TOTAL.

    PASO 2:
        busca reglas especiales según la cantidad
        de cada producto.

    PASO 3:
        compara ambas.

    PASO 4:
        devuelve siempre la talla mayor.
    """

    # =========================================================================
    # TALLA AUTOMÁTICA GENERAL
    # =========================================================================

    talla_automatica = (
        obtener_talla_blue_express(
            cantidad_productos
        )
    )

    # =========================================================================
    # TALLA ESPECIAL DE PRODUCTOS
    # =========================================================================

    talla_especial = (
        obtener_talla_especial_productos_carrito(
            carrito_serializado
        )
    )

    # =========================================================================
    # SIN REGLAS ESPECIALES
    # =========================================================================

    if not talla_especial:
        return talla_automatica

    # =========================================================================
    # COMPARAR
    # =========================================================================

    return (
        obtener_talla_mayor_blue_express(
            talla_actual=(
                talla_automatica
            ),
            talla_minima=(
                talla_especial
            ),
        )
    )


# =============================================================================
# TARIFA BLUE EXPRESS
# =============================================================================

def obtener_tarifa_blue_express(
    *,
    zona,
    talla,
):
    zona = str(
        zona or ""
    ).strip().upper()

    talla = (
        normalizar_talla_blue_express(
            talla
        )
    )

    if not zona:
        raise ValueError(
            (
                "Debes indicar una zona "
                "para obtener la tarifa."
            )
        )

    if not talla:
        raise ValueError(
            (
                "Debes indicar una talla "
                "para obtener la tarifa."
            )
        )

    tarifa = (
        TarifaBlueExpress.objects
        .filter(
            zona=zona,
            talla=talla,
            activa=True,
        )
        .first()
    )

    if tarifa is None:
        raise ValueError(
            (
                "No existe una tarifa Blue Express "
                f"activa para {zona} / {talla}."
            )
        )

    try:

        costo = int(
            tarifa.precio
        )

    except (
        TypeError,
        ValueError,
    ) as error:

        raise ValueError(
            (
                "La tarifa Blue Express "
                f"{zona} / {talla} "
                "tiene un valor inválido."
            )
        ) from error

    if costo <= 0:
        raise ValueError(
            (
                "La tarifa Blue Express "
                f"{zona} / {talla} "
                "debe ser mayor que $0."
            )
        )

    return costo


# =============================================================================
# COTIZAR BLUE EXPRESS
# =============================================================================

def cotizar_blue_express(
    *,
    carrito_serializado,
    region,
):
    """
    Cotización definitiva de Blue Express.

    Flujo:

        carrito
            ↓
        cantidad total
            ↓
        talla automática
            ↓
        reglas especiales por producto
            ↓
        talla mayor
            ↓
        zona
            ↓
        tarifa
            ↓
        costo final
    """

    # =========================================================================
    # CANTIDAD TOTAL
    # =========================================================================

    cantidad = (
        obtener_cantidad_total_carrito(
            carrito_serializado
        )
    )

    if cantidad <= 0:
        raise ValueError(
            (
                "No fue posible determinar "
                "la cantidad de productos "
                "del carrito."
            )
        )

    # =========================================================================
    # TALLA FINAL
    # =========================================================================

    talla = (
        obtener_talla_final_blue_express(
            carrito_serializado=(
                carrito_serializado
            ),
            cantidad_productos=(
                cantidad
            ),
        )
    )

    # =========================================================================
    # ZONA
    # =========================================================================

    zona = (
        obtener_zona_blue_express(
            region
        )
    )

    # =========================================================================
    # COSTO
    # =========================================================================

    costo = (
        obtener_tarifa_blue_express(
            zona=zona,
            talla=talla,
        )
    )

    # =========================================================================
    # RESULTADO
    # =========================================================================

    return CotizacionBlueExpress(
        cantidad_productos=(
            cantidad
        ),
        talla=(
            talla
        ),
        zona=(
            zona
        ),
        costo=(
            costo
        ),
    )


# =============================================================================
# TIEMPO ESTIMADO
# =============================================================================

def obtener_tiempo_estimado_blue_express(
    *,
    zona,
):
    zona = str(
        zona or ""
    ).strip().upper()

    tiempo = (
        TIEMPOS_BLUE_EXPRESS.get(
            zona
        )
    )

    if tiempo is None:
        raise ValueError(
            (
                "No existe un tiempo estimado "
                "configurado para la zona "
                f"{zona}."
            )
        )

    try:

        tiempo = int(
            tiempo
        )

    except (
        TypeError,
        ValueError,
    ) as error:

        raise ValueError(
            (
                "El tiempo estimado configurado "
                f"para {zona} no es válido."
            )
        ) from error

    if tiempo <= 0:
        raise ValueError(
            (
                "El tiempo estimado configurado "
                f"para {zona} debe ser mayor a 0."
            )
        )

    return tiempo