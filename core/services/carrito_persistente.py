from copy import deepcopy

from core.models import (
    CarritoUsuario,
    Producto,
)


CLAVE_CARRITO = "carrito_audex"

CLAVE_USUARIO_SINCRONIZADO = (
    "carrito_audex_usuario_id"
)


def _es_diccionario(valor):
    return (
        valor
        if isinstance(valor, dict)
        else {}
    )


def normalizar_carrito(carrito):
    """
    Limpia productos inválidos y limita cada cantidad
    al stock disponible.
    """

    carrito = _es_diccionario(
        carrito
    )

    cantidades = {}

    for producto_id_texto, datos in carrito.items():
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
        ):
            continue

        if cantidad <= 0:
            continue

        cantidades[
            producto_id
        ] = cantidad


    if not cantidades:
        return {}


    productos = {
        producto.id: producto
        for producto in (
            Producto.objects
            .filter(
                id__in=cantidades.keys(),
                activo=True,
            )
            .only(
                "id",
                "stock",
            )
        )
    }


    carrito_limpio = {}

    for producto_id, cantidad in cantidades.items():
        producto = productos.get(
            producto_id
        )

        if producto is None:
            continue

        if producto.stock <= 0:
            continue

        cantidad = min(
            cantidad,
            producto.stock,
        )

        carrito_limpio[
            str(producto_id)
        ] = {
            "cantidad": cantidad,
        }


    return carrito_limpio


def fusionar_carritos(
    carrito_invitado,
    carrito_usuario,
):
    """
    Combina ambos carritos.

    Si un producto se encuentra en los dos,
    suma sus cantidades sin superar el stock.
    """

    resultado = {}

    for carrito in (
        carrito_usuario,
        carrito_invitado,
    ):
        carrito = _es_diccionario(
            carrito
        )

        for producto_id_texto, datos in carrito.items():
            try:
                producto_id = str(
                    int(
                        producto_id_texto
                    )
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
            ):
                continue

            if cantidad <= 0:
                continue

            cantidad_actual = int(
                resultado.get(
                    producto_id,
                    {},
                ).get(
                    "cantidad",
                    0,
                )
            )

            resultado[
                producto_id
            ] = {
                "cantidad": (
                    cantidad_actual
                    + cantidad
                ),
            }


    return normalizar_carrito(
        resultado
    )


def _guardar_en_sesion(
    request,
    carrito,
):
    request.session[
        CLAVE_CARRITO
    ] = deepcopy(
        carrito
    )

    request.session.modified = True


def _marcar_usuario_sincronizado(
    request,
):
    if request.user.is_authenticated:
        request.session[
            CLAVE_USUARIO_SINCRONIZADO
        ] = request.user.pk

        request.session.modified = True


def obtener_carrito(request):
    """
    Invitado:
        carga desde request.session.

    Usuario autenticado:
        carga desde CarritoUsuario y mantiene
        una copia sincronizada en la sesión.

    En el primer acceso después del login,
    fusiona el carrito invitado con el carrito
    guardado en la cuenta.
    """

    carrito_sesion = normalizar_carrito(
        request.session.get(
            CLAVE_CARRITO,
            {},
        )
    )


    if not request.user.is_authenticated:
        request.session.pop(
            CLAVE_USUARIO_SINCRONIZADO,
            None,
        )

        _guardar_en_sesion(
            request,
            carrito_sesion,
        )

        return deepcopy(
            carrito_sesion
        )


    registro, _ = (
        CarritoUsuario.objects
        .get_or_create(
            usuario=request.user,
        )
    )

    carrito_usuario = normalizar_carrito(
        registro.contenido
    )


    usuario_sincronizado = (
        request.session.get(
            CLAVE_USUARIO_SINCRONIZADO
        )
    )
























    if usuario_sincronizado != request.user.pk:
        carrito_final = fusionar_carritos(
            carrito_invitado=carrito_sesion,
            carrito_usuario=carrito_usuario,
        )

        registro.contenido = (
            carrito_final
        )

        registro.save(
            update_fields=[
                "contenido",
                "actualizado",
            ]
        )

        _guardar_en_sesion(
            request,
            carrito_final,
        )

        _marcar_usuario_sincronizado(
            request
        )

        return deepcopy(
            carrito_final
        )


    if carrito_usuario != registro.contenido:
        registro.contenido = (
            carrito_usuario
        )

        registro.save(
            update_fields=[
                "contenido",
                "actualizado",
            ]
        )


    if carrito_sesion != carrito_usuario:
        _guardar_en_sesion(
            request,
            carrito_usuario,
        )


    _marcar_usuario_sincronizado(
        request
    )

    return deepcopy(
        carrito_usuario
    )


def guardar_carrito(
    request,
    carrito,
):
    """
    Guarda el carrito en la sesión.

    Para usuarios autenticados, también guarda
    una copia persistente en la base de datos.
    """

    carrito = normalizar_carrito(
        carrito
    )

    _guardar_en_sesion(
        request,
        carrito,
    )


    if request.user.is_authenticated:
        CarritoUsuario.objects.update_or_create(
            usuario=request.user,
            defaults={
                "contenido": carrito,
            },
        )

        _marcar_usuario_sincronizado(
            request
        )


    return deepcopy(
        carrito
    )

