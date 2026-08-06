from django.contrib import messages
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.contrib.auth.decorators import (
    login_required,
)
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_http_methods,
)

from core.forms import (
    ActualizarEstadoPedidoForm,
    BuscarPedidoForm,
)
from core.models import Pedido
from core.services.flujo_pedidos import (
    cambiar_estado_pedido,
    construir_timeline,
)


# ==========================================================================
# CONFIGURACIÓN
# ==========================================================================

PEDIDOS_POR_PAGINA_CLIENTE = 8
PEDIDOS_POR_PAGINA_ADMIN = 20
PEDIDOS_VISIBLES_POR_BANDEJA = 8
MAX_PEDIDOS_AUTORIZADOS_SESION = 20


# ==========================================================================
# QUERYSET GENERAL
# ==========================================================================

def _queryset_pedidos():
    """
    Queryset optimizado para cargar pedidos con sus relaciones.

    Evita consultas adicionales al mostrar:
    - Usuario asociado.
    - Productos del pedido.
    - Historial de estados.
    - Usuarios que modificaron los estados.
    """

    return (
        Pedido.objects
        .select_related(
            "usuario",
        )
        .prefetch_related(
            "items__producto",
            "historial_estados__usuario",
        )
    )


# ==========================================================================
# FUNCIONES AUXILIARES DE SEGUIMIENTO
# ==========================================================================

def _normalizar_numero_pedido(
    numero,
) -> str:
    """
    Normaliza el número de pedido para realizar búsquedas exactas.
    """

    return (
        str(numero or "")
        .strip()
        .upper()
    )


def _pedidos_autorizados_sesion(
    request,
) -> list[str]:
    """
    Obtiene los números de pedido autorizados en la sesión actual.
    """

    autorizados = request.session.get(
        "pedidos_consultados",
        [],
    )

    if not isinstance(autorizados, list):
        return []

    return [
        _normalizar_numero_pedido(numero)
        for numero in autorizados
        if numero
    ]


def _autorizar_pedido_en_sesion(
    request,
    numero: str,
) -> None:
    """
    Autoriza temporalmente la visualización del pedido en la sesión.

    El número del pedido funciona como clave de acceso para
    clientes que realizaron la compra sin iniciar sesión.
    """

    numero = _normalizar_numero_pedido(
        numero
    )

    autorizados = (
        _pedidos_autorizados_sesion(
            request
        )
    )

    if numero not in autorizados:
        autorizados.append(numero)

    request.session[
        "pedidos_consultados"
    ] = autorizados[
        -MAX_PEDIDOS_AUTORIZADOS_SESION:
    ]

    request.session.modified = True


def _usuario_puede_ver(
    request,
    pedido: Pedido,
) -> bool:
    """
    Determina si la persona puede visualizar el pedido.

    Puede verlo cuando:
    - Es personal administrativo.
    - El pedido pertenece a su cuenta.
    - Buscó previamente el número desde el formulario público.

    No se asocian automáticamente pedidos invitados por correo.
    """

    if (
        request.user.is_authenticated
        and request.user.is_staff
    ):
        return True

    if (
        request.user.is_authenticated
        and pedido.usuario_id
        == request.user.id
    ):
        return True

    autorizados = (
        _pedidos_autorizados_sesion(
            request
        )
    )

    return (
        _normalizar_numero_pedido(
            pedido.numero
        )
        in autorizados
    )


# ==========================================================================
# HISTORIAL DE COMPRAS DEL CLIENTE
# ==========================================================================

@login_required
def mis_compras(request):
    """
    Historial de compras del usuario autenticado.

    Por defecto muestra únicamente pedidos pagados.

    Los pedidos pendientes de pago se consultan mediante:

        ?tipo=pendientes
    """

    pedidos_usuario = (
        _queryset_pedidos()
        .filter(
            usuario=request.user,
        )
    )

    # ---------------------------------------------------------
    # GRUPOS DE PEDIDOS
    # ---------------------------------------------------------

    pedidos_pagados = (
        pedidos_usuario
        .filter(
            pagado=True,
        )
        .order_by(
            "-creado",
        )
    )

    pedidos_pendientes = (
        pedidos_usuario
        .filter(
            pagado=False,
            estado="pendiente",
        )
        .order_by(
            "-creado",
        )
    )

    total_pagados = (
        pedidos_pagados.count()
    )

    total_pendientes_pago = (
        pedidos_pendientes.count()
    )

    # ---------------------------------------------------------
    # TIPO DE BANDEJA
    # ---------------------------------------------------------

    tipo_actual = (
        request.GET.get(
            "tipo",
            "pagados",
        )
        .strip()
        .lower()
    )

    tipos_validos = {
        "pagados",
        "pendientes",
    }

    if tipo_actual not in tipos_validos:
        tipo_actual = "pagados"

    # ---------------------------------------------------------
    # FILTRO POR ESTADO
    # ---------------------------------------------------------

    estado = (
        request.GET.get(
            "estado",
            "",
        )
        .strip()
        .lower()
    )

    estados_filtro = [
        (
            valor,
            etiqueta,
        )
        for valor, etiqueta in Pedido.ESTADOS
        if valor != "pendiente"
    ]

    estados_validos = {
        valor
        for valor, _ in estados_filtro
    }

    if tipo_actual == "pendientes":
        pedidos = pedidos_pendientes

        # La bandeja pendiente no necesita filtro
        # de estado porque todos están pendientes.
        estado = ""

    else:
        pedidos = pedidos_pagados

        if estado in estados_validos:
            pedidos = pedidos.filter(
                estado=estado,
            )
        else:
            estado = ""

    # ---------------------------------------------------------
    # PAGINACIÓN
    # ---------------------------------------------------------

    paginador = Paginator(
        pedidos,
        PEDIDOS_POR_PAGINA_CLIENTE,
    )

    pagina = paginador.get_page(
        request.GET.get("page")
    )

    # ---------------------------------------------------------
    # TEMPLATE
    # ---------------------------------------------------------

    return render(
        request,
        "core/mis_compras.html",
        {
            "page_obj": pagina,
            "tipo_actual": tipo_actual,
            "estado_actual": estado,
            "estados": estados_filtro,
            "total_pagados": total_pagados,
            "total_pendientes_pago": (
                total_pendientes_pago
            ),
        },
    )
# ==========================================================================
# SEGUIMIENTO PÚBLICO POR NÚMERO DE PEDIDO
# ==========================================================================

@require_http_methods([
    "GET",
    "POST",
])
def seguimiento_pedido(
    request,
    numero=None,
):
    """
    Permite consultar un pedido mediante su número exacto.

    Usuario autenticado:
    - Puede acceder directamente a sus propios pedidos.
    - También puede buscar un número desde el formulario.

    Usuario invitado:
    - Debe buscar el número exacto del pedido.
    - El número queda autorizado temporalmente en su sesión.
    """

    pedido = None

    numero_inicial = (
        _normalizar_numero_pedido(
            numero
        )
    )

    form = BuscarPedidoForm(
        request.POST or None,
        initial={
            "numero": numero_inicial,
        },
    )

    # ------------------------------------------------------------------
    # BÚSQUEDA POR FORMULARIO
    # ------------------------------------------------------------------

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        numero_buscado = (
            _normalizar_numero_pedido(
                form.cleaned_data[
                    "numero"
                ]
            )
        )

        pedido_encontrado = (
            _queryset_pedidos()
            .filter(
                numero__iexact=numero_buscado,
            )
            .first()
        )

        if pedido_encontrado is None:
            form.add_error(
                "numero",
                (
                    "No encontramos un pedido "
                    "con ese número."
                ),
            )

        else:
            _autorizar_pedido_en_sesion(
                request,
                pedido_encontrado.numero,
            )

            return redirect(
                "core:seguimiento_pedido_numero",
                numero=pedido_encontrado.numero,
            )

    # ------------------------------------------------------------------
    # VISUALIZACIÓN POR URL
    # ------------------------------------------------------------------

    if numero_inicial:
        pedido_encontrado = (
            _queryset_pedidos()
            .filter(
                numero__iexact=numero_inicial,
            )
            .first()
        )

        if pedido_encontrado is None:
            form.add_error(
                "numero",
                (
                    "No encontramos un pedido "
                    "con ese número."
                ),
            )

        elif _usuario_puede_ver(
            request,
            pedido_encontrado,
        ):
            pedido = pedido_encontrado

        else:
            form = BuscarPedidoForm(
                initial={
                    "numero": numero_inicial,
                }
            )

            form.add_error(
                "numero",
                (
                    "Para acceder al seguimiento, "
                    "ingresa el número del pedido "
                    "y presiona Buscar."
                ),
            )

    timeline = (
        construir_timeline(pedido)
        if pedido is not None
        else []
    )

    return render(
        request,
        "core/seguimiento_pedido.html",
        {
            "pedido": pedido,
            "form": form,
            "timeline": timeline,
        },
    )


# ==========================================================================
# PANEL ADMINISTRATIVO DE PEDIDOS
# ==========================================================================

@staff_member_required
def panel_pedidos(request):
    """
    Panel administrativo escalable.

    Tablero general:
    - Muestra un máximo de 8 pedidos por bandeja.
    - Conserva el contador total real.

    Bandeja completa:
    - Se abre mediante ?bandeja=nuevos, operacion, etc.
    - Muestra 20 pedidos por página.

    Los pedidos pendientes de pago se separan de las ventas
    confirmadas.
    """

    pedidos = (
        _queryset_pedidos()
        .order_by(
            "-actualizado",
        )
    )

    busqueda = (
        request.GET.get(
            "q",
            "",
        )
        .strip()
    )

    if busqueda:
        pedidos = pedidos.filter(
            Q(
                numero__icontains=busqueda
            )
            | Q(
                nombre__icontains=busqueda
            )
            | Q(
                apellido__icontains=busqueda
            )
            | Q(
                email__icontains=busqueda
            )
            | Q(
                rut__icontains=busqueda
            )
        )

    # ------------------------------------------------------------------
    # BANDEJAS
    # ------------------------------------------------------------------

    pendientes_pago = pedidos.filter(
        estado="pendiente",
        pagado=False,
    )

    nuevos = pedidos.filter(
        estado="confirmado",
        pagado=True,
    )

    operacion = pedidos.filter(
        estado__in=[
            "preparacion",
            "listo",
        ],
        pagado=True,
    )

    despacho = pedidos.filter(
        estado="enviado",
        pagado=True,
    )

    finalizados = pedidos.filter(
        estado__in=[
            "entregado",
            "cancelado",
        ],
    )

    bandejas_querysets = {
        "nuevos": nuevos,
        "operacion": operacion,
        "despacho": despacho,
        "finalizados": finalizados,
        "pendientes": pendientes_pago,
    }

    bandejas_nombres = {
        "nuevos": "Nuevos",
        "operacion": "En operación",
        "despacho": "En despacho",
        "finalizados": "Finalizados",
        "pendientes": "Pendientes de pago",
    }

    bandejas_iconos = {
        "nuevos": "bi-bag-check",
        "operacion": "bi-box-seam",
        "despacho": "bi-truck",
        "finalizados": "bi-check2-circle",
        "pendientes": "bi-clock-history",
    }

    # ------------------------------------------------------------------
    # CONTADORES
    # ------------------------------------------------------------------

    totales = {
        clave: queryset.count()
        for clave, queryset
        in bandejas_querysets.items()
    }

    # ------------------------------------------------------------------
    # BANDEJA SELECCIONADA
    # ------------------------------------------------------------------

    bandeja_actual = (
        request.GET.get(
            "bandeja",
            "",
        )
        .strip()
        .lower()
    )

    mostrar_bandeja = (
        bandeja_actual
        in bandejas_querysets
    )

    page_obj = None
    titulo_bandeja = ""

    if mostrar_bandeja:
        queryset_bandeja = (
            bandejas_querysets[
                bandeja_actual
            ]
        )

        paginador = Paginator(
            queryset_bandeja,
            PEDIDOS_POR_PAGINA_ADMIN,
        )

        page_obj = paginador.get_page(
            request.GET.get("page")
        )

        titulo_bandeja = (
            bandejas_nombres[
                bandeja_actual
            ]
        )

    # ------------------------------------------------------------------
    # TARJETAS DEL TABLERO GENERAL
    # ------------------------------------------------------------------

    bandejas = []

    claves_tablero = [
        "nuevos",
        "operacion",
        "despacho",
        "finalizados",
    ]

    for clave in claves_tablero:
        queryset = (
            bandejas_querysets[
                clave
            ]
        )

        total = totales[clave]

        bandejas.append(
            {
                "clave": clave,
                "nombre": (
                    bandejas_nombres[
                        clave
                    ]
                ),
                "icono": (
                    bandejas_iconos[
                        clave
                    ]
                ),
                "total": total,
                "pedidos": queryset[
                    :PEDIDOS_VISIBLES_POR_BANDEJA
                ],
                "hay_mas": (
                    total
                    > PEDIDOS_VISIBLES_POR_BANDEJA
                ),
            }
        )

    # ------------------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------------------

    return render(
        request,
        "core/gestion/panel_pedidos.html",
        {
            # Nuevo tablero escalable.
            "bandejas": bandejas,
            "bandeja_actual": bandeja_actual,
            "titulo_bandeja": titulo_bandeja,
            "mostrar_bandeja": mostrar_bandeja,
            "page_obj": page_obj,

            # Buscador.
            "busqueda": busqueda,

            # Contadores.
            "total_principal": (
                totales["nuevos"]
            ),
            "total_operacion": (
                totales["operacion"]
            ),
            "total_despacho": (
                totales["despacho"]
            ),
            "total_cerrados": (
                totales["finalizados"]
            ),
            "total_pendientes_pago": (
                totales["pendientes"]
            ),

            # Compatibilidad temporal con el template anterior.
            # Solo entrega un máximo de 8 pedidos por columna.
            "principal": nuevos[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ],
            "operacion": operacion[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ],
            "despacho": despacho[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ],
            "cerrados": finalizados[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ],
        },
    )


# ==========================================================================
# DETALLE Y ADMINISTRACIÓN DE UN PEDIDO
# ==========================================================================

@staff_member_required
@require_http_methods([
    "GET",
    "POST",
])
def panel_pedido_detalle(
    request,
    numero,
):
    numero = _normalizar_numero_pedido(
        numero
    )

    pedido = get_object_or_404(
        _queryset_pedidos(),
        numero__iexact=numero,
    )

    form = ActualizarEstadoPedidoForm(
        request.POST or None,
        pedido=pedido,
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        nuevo_estado = (
            form.cleaned_data[
                "nuevo_estado"
            ]
        )

        comentario = (
            form.cleaned_data.get(
                "comentario",
                "",
            )
        )

        try:
            pedido_actualizado = (
                cambiar_estado_pedido(
                    pedido=pedido,
                    nuevo_estado=nuevo_estado,
                    comentario=comentario,
                    usuario=request.user,
                )
            )

        except ValidationError as error:
            errores = getattr(
                error,
                "messages",
                [
                    str(error),
                ],
            )

            for mensaje_error in errores:
                form.add_error(
                    None,
                    mensaje_error,
                )

        else:
            messages.success(
                request,
                (
                    "El pedido "
                    f"{pedido_actualizado.numero} "
                    "fue actualizado correctamente."
                ),
            )

            return redirect(
                "core:panel_pedido_detalle",
                numero=(
                    pedido_actualizado.numero
                ),
            )

    historial = (
        pedido.historial_estados
        .select_related(
            "usuario",
        )
        .all()
    )

    return render(
        request,
        "core/gestion/panel_pedido_detalle.html",
        {
            "pedido": pedido,
            "form": form,
            "timeline": construir_timeline(
                pedido
            ),
            "historial": historial,
        },
    )