from django.db import transaction

from core.models import (
    Favorito,
    Producto,
)


CLAVE_FAVORITOS = "favoritos_audex"

CLAVE_USUARIO_SINCRONIZADO = (
    "favoritos_audex_usuario_id"
)


def normalizar_ids_favoritos(valor):
    """
    Convierte el contenido de sesión en una lista
    de IDs de productos activos y válidos.
    """

    if isinstance(valor, dict):
        valor = list(
            valor.keys()
        )

    if not isinstance(
        valor,
        (
            list,
            tuple,
            set,
        ),
    ):
        return []

    ids = []

    for elemento in valor:
        try:
            producto_id = int(
                elemento
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if producto_id <= 0:
            continue

        if producto_id not in ids:
            ids.append(
                producto_id
            )

    if not ids:
        return []

    productos_validos = set(
        Producto.objects.filter(
            id__in=ids,
            activo=True,
        ).values_list(
            "id",
            flat=True,
        )
    )

    return [
        producto_id
        for producto_id in ids
        if producto_id in productos_validos
    ]


def _guardar_en_sesion(
    request,
    ids_favoritos,
):
    request.session[
        CLAVE_FAVORITOS
    ] = list(
        ids_favoritos
    )

    request.session.modified = True


def _marcar_usuario_sincronizado(
    request,
):
    if not request.user.is_authenticated:
        return

    request.session[
        CLAVE_USUARIO_SINCRONIZADO
    ] = request.user.pk

    request.session.modified = True


@transaction.atomic
def obtener_ids_favoritos(request):
    """
    Invitado:
        carga favoritos desde la sesión.

    Usuario autenticado:
        carga desde la base de datos.

    En el primer acceso después del login:
        combina favoritos anónimos y favoritos
        guardados en la cuenta.
    """

    favoritos_sesion = (
        normalizar_ids_favoritos(
            request.session.get(
                CLAVE_FAVORITOS,
                [],
            )
        )
    )

    if not request.user.is_authenticated:
        request.session.pop(
            CLAVE_USUARIO_SINCRONIZADO,
            None,
        )

        _guardar_en_sesion(
            request,
            favoritos_sesion,
        )

        return favoritos_sesion

    favoritos_usuario = list(
        Favorito.objects.filter(
            usuario=request.user,
            producto__activo=True,
        ).values_list(
            "producto_id",
            flat=True,
        )
    )

    favoritos_usuario = (
        normalizar_ids_favoritos(
            favoritos_usuario
        )
    )

    usuario_sincronizado = (
        request.session.get(
            CLAVE_USUARIO_SINCRONIZADO
        )
    )

    if (
        usuario_sincronizado
        != request.user.pk
    ):
        favoritos_combinados = list(
            dict.fromkeys(
                favoritos_usuario
                + favoritos_sesion
            )
        )

        productos = (
            Producto.objects.filter(
                id__in=favoritos_combinados,
                activo=True,
            )
        )

        Favorito.objects.bulk_create(
            [
                Favorito(
                    usuario=request.user,
                    producto=producto,
                )
                for producto in productos
            ],
            ignore_conflicts=True,
        )

        favoritos_usuario = list(
            Favorito.objects.filter(
                usuario=request.user,
                producto__activo=True,
            ).values_list(
                "producto_id",
                flat=True,
            )
        )

    _guardar_en_sesion(
        request,
        favoritos_usuario,
    )

    _marcar_usuario_sincronizado(
        request
    )

    return favoritos_usuario


def guardar_favoritos_en_sesion(
    request,
    ids_favoritos,
):
    """
    Guarda favoritos para un visitante anónimo.

    Se utiliza también después de cerrar sesión.
    """

    ids_favoritos = (
        normalizar_ids_favoritos(
            ids_favoritos
        )
    )

    request.session.pop(
        CLAVE_USUARIO_SINCRONIZADO,
        None,
    )

    _guardar_en_sesion(
        request,
        ids_favoritos,
    )

    return ids_favoritos


@transaction.atomic
def alternar_favorito(
    request,
    producto,
):
    """
    Agrega o elimina un producto de favoritos.
    """

    if request.user.is_authenticated:
        favorito, creado = (
            Favorito.objects.get_or_create(
                usuario=request.user,
                producto=producto,
            )
        )

        if creado:
            activo = True
        else:
            favorito.delete()
            activo = False

        ids_favoritos = list(
            Favorito.objects.filter(
                usuario=request.user,
                producto__activo=True,
            ).values_list(
                "producto_id",
                flat=True,
            )
        )

        _guardar_en_sesion(
            request,
            ids_favoritos,
        )

        _marcar_usuario_sincronizado(
            request
        )

        return {
            "activo": activo,
            "ids": ids_favoritos,
            "total": len(
                ids_favoritos
            ),
        }

    ids_favoritos = set(
        obtener_ids_favoritos(
            request
        )
    )

    if producto.id in ids_favoritos:
        ids_favoritos.remove(
            producto.id
        )

        activo = False
    else:
        ids_favoritos.add(
            producto.id
        )

        activo = True

    ids_ordenados = sorted(
        ids_favoritos
    )

    _guardar_en_sesion(
        request,
        ids_ordenados,
    )

    return {
        "activo": activo,
        "ids": ids_ordenados,
        "total": len(
            ids_ordenados
        ),
    }