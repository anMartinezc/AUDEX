from dataclasses import dataclass


# =============================================================================
# TARIFAS BLUE EXPRESS
# =============================================================================
#
# ORIGEN FIJO:
# Todos los pedidos salen desde Santiago.
#
# ENTREGA:
# A domicilio.
#
# Tallas:
# 1 - 2 productos   -> XS
# 3 - 5 productos   -> S
# 6 - 10 productos  -> M
# 11 - 20 productos -> L
#
# =============================================================================


TARIFAS_BLUE_EXPRESS = {
    "SANTIAGO": {
        "XS": 3100,
        "S": 4200,
        "M": 4800,
        "L": 5400,
    },

    "CENTRO": {
        "XS": 4300,
        "S": 5600,
        "M": 7300,
        "L": 9200,
    },

    "EXTREMO": {
        "XS": 5200,
        "S": 9500,
        "M": 14500,
        "L": 17000,
    },
}



TIEMPOS_BLUE_EXPRESS = {
    "SANTIAGO": 48,
    "CENTRO": 72,
    "EXTREMO": 72,
}


# =============================================================================
# REGIONES POR ZONA
# =============================================================================
#
# Como el origen siempre es Santiago:
#
# Metropolitana -> SANTIAGO
#
# Zona central -> CENTRO
#
# Norte/extremo sur -> EXTREMO
#
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
# RESULTADO
# =============================================================================


@dataclass(frozen=True)
class CotizacionBlueExpress:
    cantidad_productos: int
    talla: str
    zona: str
    costo: int


# =============================================================================
# TALLA
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
# ZONA
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
# CANTIDAD TOTAL
# =============================================================================


def obtener_cantidad_total_carrito(
    carrito_serializado,
):
    if not carrito_serializado:
        return 0

    # -------------------------------------------------------------------------
    # PRIMER INTENTO:
    # buscar cantidad total ya calculada.
    # -------------------------------------------------------------------------

    for clave in (
        "cantidad_total",
        "total_unidades",
        "cantidad_productos",
    ):
        valor = carrito_serializado.get(
            clave
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
    # SEGUNDO INTENTO:
    # buscar líneas del carrito.
    # -------------------------------------------------------------------------

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

        if not isinstance(
            elementos,
            list,
        ):
            continue

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
                cantidad_total += cantidad

        if cantidad_total > 0:
            return cantidad_total

    return 0


# =============================================================================
# TARIFA
# =============================================================================

def obtener_tarifa_blue_express(
    *,
    zona,
    talla,
):
    tarifas_zona = (
        TARIFAS_BLUE_EXPRESS.get(
            zona
        )
    )

    if not tarifas_zona:
        raise ValueError(
            (
                "No existen tarifas Blue Express "
                f"configuradas para {zona}."
            )
        )

    costo = tarifas_zona.get(
        talla
    )

    if costo is None:
        raise ValueError(
            (
                "No existe tarifa Blue Express "
                f"para {zona} / {talla}."
            )
        )

    try:
        costo = int(
            costo
        )

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            (
                "La tarifa Blue Express "
                f"{zona} / {talla} "
                "tiene un valor inválido."
            )
        )

    # =========================================================================
    # EXCEPCIÓN CONTROLADA PARA TEST TRANSBANK
    # =========================================================================
    #
    # Permitimos despacho $0 únicamente para:
    #
    # SANTIAGO / XS
    #
    # Esto sirve para realizar las pruebas exigidas
    # por Transbank con productos de valor $0.
    #
    # Todas las demás combinaciones siguen exigiendo
    # una tarifa mayor a $0.
    # =========================================================================

    if (
        zona == "SANTIAGO"
        and talla == "XS"
        and costo == 0
    ):
        return 0

    # =========================================================================
    # VALIDACIÓN NORMAL
    # =========================================================================

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
# COTIZAR
# =============================================================================


def cotizar_blue_express(
    *,
    carrito_serializado,
    region,
):
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

    talla = (
        obtener_talla_blue_express(
            cantidad
        )
    )

    zona = (
        obtener_zona_blue_express(
            region
        )
    )

    costo = (
        obtener_tarifa_blue_express(
            zona=zona,
            talla=talla,
        )
    )

    return CotizacionBlueExpress(
        cantidad_productos=cantidad,
        talla=talla,
        zona=zona,
        costo=costo,
    )





def obtener_tiempo_estimado_blue_express(
    *,
    zona,
):
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
    ):
        raise ValueError(
            (
                "El tiempo estimado configurado "
                f"para {zona} no es válido."
            )
        )

    if tiempo <= 0:
        raise ValueError(
            (
                "El tiempo estimado configurado "
                f"para {zona} debe ser mayor a 0."
            )
        )

    return tiempo