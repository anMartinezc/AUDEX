from django.contrib import messages
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.contrib.auth.decorators import (
    login_required,
)
from datetime import timedelta
from django.utils import timezone
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
from django.db.models import Sum

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
    Historial de compras confirmadas del usuario.

    Solo muestra pedidos cuyo pago fue aprobado.

    Permite filtrar por estado operativo:

    - confirmado
    - preparacion
    - listo
    - enviado
    - entregado
    - cancelado

    Los intentos de pago pendientes, rechazados
    o cancelados antes de pagar no aparecen aquí.
    """

    # =========================================================================
    # QUERYSET BASE
    # =========================================================================

    pedidos_base = (
        _queryset_pedidos()
        .filter(
            usuario=request.user,
            pagado=True,
            estado_pago=Pedido.EstadoPago.APROBADO,
        )
        .annotate(
            total_unidades=Sum(
                "items__cantidad"
            ),
        )
        .order_by(
            "-creado",
        )
    )

    # =========================================================================
    # TOTAL REAL DE COMPRAS
    # =========================================================================

    total_compras = (
        pedidos_base.count()
    )

    # =========================================================================
    # FILTROS DISPONIBLES
    # =========================================================================

    estados_filtro = [
        (
            valor,
            etiqueta,
        )
        for valor, etiqueta
        in Pedido.EstadoPedido.choices
        if (
            valor
            != Pedido.EstadoPedido.PENDIENTE
        )
    ]

    estados_validos = {
        valor
        for valor, _ in estados_filtro
    }

    # =========================================================================
    # ESTADO SOLICITADO
    # =========================================================================

    estado_actual = (
        request.GET.get(
            "estado",
            "",
        )
        .strip()
        .lower()
    )

    if (
        estado_actual
        not in estados_validos
    ):
        estado_actual = ""

    # =========================================================================
    # FILTRAR
    # =========================================================================

    pedidos = pedidos_base

    if estado_actual:

        pedidos = pedidos.filter(
            estado=estado_actual,
        )

    # =========================================================================
    # INFORMACIÓN DEL FILTRO
    # =========================================================================

    etiquetas_estado = dict(
        estados_filtro
    )

    etiqueta_estado_actual = (
        etiquetas_estado.get(
            estado_actual,
            "",
        )
    )

    total_filtrados = (
        pedidos.count()
    )

    # =========================================================================
    # ESTADOS VACÍOS
    # =========================================================================

    estados_vacios = {

        Pedido.EstadoPedido.CONFIRMADO: {
            "icono": "bi-check-circle",
            "titulo": (
                "No tienes compras recién confirmadas"
            ),
            "mensaje": (
                "Tus compras confirmadas que avancen "
                "a preparación dejarán de aparecer "
                "en este filtro."
            ),
        },

        Pedido.EstadoPedido.PREPARACION: {
            "icono": "bi-box-seam",
            "titulo": (
                "No tienes pedidos en preparación"
            ),
            "mensaje": (
                "Cuando comencemos a preparar una "
                "de tus compras, aparecerá aquí."
            ),
        },

        Pedido.EstadoPedido.LISTO: {
            "icono": "bi-box-seam",
            "titulo": (
                "No tienes pedidos listos para despacho"
            ),
            "mensaje": (
                "Cuando uno de tus pedidos esté listo "
                "para ser entregado al transportista, "
                "aparecerá en esta sección."
            ),
        },

        Pedido.EstadoPedido.ENVIADO: {
            "icono": "bi-truck",
            "titulo": (
                "No tienes pedidos enviados"
            ),
            "mensaje": (
                "Cuando un pedido salga a despacho, "
                "podrás consultarlo desde este filtro."
            ),
        },

        Pedido.EstadoPedido.ENTREGADO: {
            "icono": "bi-house-check",
            "titulo": (
                "No tienes pedidos entregados"
            ),
            "mensaje": (
                "Tus compras entregadas aparecerán "
                "aquí una vez finalice el despacho."
            ),
        },

        Pedido.EstadoPedido.CANCELADO: {
            "icono": "bi-x-circle",
            "titulo": (
                "No tienes compras canceladas"
            ),
            "mensaje": (
                "No existen compras confirmadas "
                "que hayan sido canceladas."
            ),
        },
    }

    # =========================================================================
    # VACÍO GENERAL
    # =========================================================================

    if estado_actual:

        vacio = estados_vacios.get(
            estado_actual,
            {
                "icono": "bi-bag-x",
                "titulo": (
                    "No hay compras en este estado"
                ),
                "mensaje": (
                    "No encontramos compras que "
                    "coincidan con este filtro."
                ),
            },
        )

    else:

        vacio = {
            "icono": "bi-bag-x",
            "titulo": (
                "Aún no tienes compras"
            ),
            "mensaje": (
                "Cuando completes una compra "
                "y su pago sea confirmado, "
                "aparecerá aquí."
            ),
        }

    # =========================================================================
    # PAGINACIÓN
    # =========================================================================

    paginador = Paginator(
        pedidos,
        PEDIDOS_POR_PAGINA_CLIENTE,
    )

    pagina = paginador.get_page(
        request.GET.get(
            "page",
            1,
        )
    )

    # =========================================================================
    # RENDER
    # =========================================================================

    return render(
        request,
        "core/mis_compras.html",
        {
            "page_obj": pagina,

            "estado_actual": (
                estado_actual
            ),

            "etiqueta_estado_actual": (
                etiqueta_estado_actual
            ),

            "estados": (
                estados_filtro
            ),

            "total_compras": (
                total_compras
            ),

            "total_filtrados": (
                total_filtrados
            ),

            "vacio": vacio,
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
    Seguimiento público de pedidos.

    Flujo:

    1. Si la URL contiene un número de pedido:
       /seguimiento/AUD-XXXXXXXX/

       Se busca y muestra directamente el pedido.

    2. Si no existe número en la URL:
       /seguimiento/

       Se muestra el formulario para buscar el pedido.

    3. El formulario puede buscar por número de pedido.

    No es necesario iniciar sesión ni ingresar nuevamente
    datos cuando el número del pedido ya viene en la URL.
    """

    # =========================================================================
    # VARIABLES
    # =========================================================================

    pedido = None
    timeline = []

    # =========================================================================
    # ACCESO DIRECTO POR URL
    # =========================================================================

    if numero:

        numero_normalizado = (
            _normalizar_numero_pedido(
                numero
            )
        )

        pedido = (
            _queryset_pedidos()
            .filter(
                numero__iexact=(
                    numero_normalizado
                )
            )
            .first()
        )

        # =====================================================================
        # PEDIDO NO ENCONTRADO
        # =====================================================================

        if pedido is None:

            messages.warning(
                request,
                (
                    "No encontramos el pedido indicado. "
                    "Verifica el número e intenta nuevamente."
                ),
            )

            form = BuscarPedidoForm(
                initial={
                    "numero": (
                        numero_normalizado
                    ),
                }
            )

        else:

            # =================================================================
            # CONSTRUIR TIMELINE
            # =================================================================

            timeline = construir_timeline(
                pedido
            )

            # =================================================================
            # NO NECESITAMOS FORMULARIO
            # =================================================================

            form = BuscarPedidoForm()

            # =================================================================
            # RENDER DIRECTO
            # =================================================================

            return render(
                request,
                "core/seguimiento_pedido.html",
                {
                    "pedido": pedido,
                    "form": form,
                    "timeline": timeline,
                },
            )

    # =========================================================================
    # SIN NÚMERO EN URL
    # =========================================================================
    #
    # /seguimiento/
    #
    # Se utiliza únicamente para buscar manualmente.
    # =========================================================================

    else:

        form = BuscarPedidoForm(
            request.POST or None
        )

    # =========================================================================
    # BÚSQUEDA MANUAL
    # =========================================================================

    if (
        request.method == "POST"
        and form.is_valid()
    ):

        # =====================================================================
        # NÚMERO
        # =====================================================================

        numero_form = (
            form.cleaned_data.get(
                "numero"
            )
            or ""
        )

        numero_form = (
            str(
                numero_form
            )
            .strip()
        )

        # =====================================================================
        # VALIDAR
        # =====================================================================

        if not numero_form:

            if "numero" in form.fields:

                form.add_error(
                    "numero",
                    (
                        "Ingresa el número "
                        "del pedido."
                    ),
                )

            else:

                form.add_error(
                    None,
                    (
                        "No fue posible obtener "
                        "el número del pedido."
                    ),
                )

        else:

            # =================================================================
            # NORMALIZAR
            # =================================================================

            numero_normalizado = (
                _normalizar_numero_pedido(
                    numero_form
                )
            )

            # =================================================================
            # BUSCAR
            # =================================================================

            pedido = (
                _queryset_pedidos()
                .filter(
                    numero__iexact=(
                        numero_normalizado
                    )
                )
                .first()
            )

            # =================================================================
            # NO ENCONTRADO
            # =================================================================

            if pedido is None:

                form.add_error(
                    "numero",
                    (
                        "No encontramos un pedido "
                        "con ese número."
                    ),
                )

            # =================================================================
            # ENCONTRADO
            # =================================================================

            else:

                return redirect(
                    "core:seguimiento_pedido_numero",
                    numero=pedido.numero,
                )

    # =========================================================================
    # TIMELINE
    # =========================================================================

    if pedido:

        timeline = construir_timeline(
            pedido
        )

    # =========================================================================
    # RENDER
    # =========================================================================

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
    Panel administrativo de pedidos.

    El tablero principal muestra exclusivamente ventas
    cuyo pago fue confirmado.

    Organización:

    - Nuevos:
        pedidos pagados y confirmados.

    - En operación:
        preparación / listo para despacho.

    - En despacho:
        pedidos enviados.

    - Finalizados:
        entregados o cancelados después de una venta válida.

    Pagos pendientes:

    - No forman parte del tablero operativo.
    - Solo se muestran durante las primeras 48 horas
      desde su última actualización.
    - Después de 48 horas dejan de mostrarse como alerta
      y desaparecen de la bandeja administrativa.
    - Los registros antiguos NO se eliminan de la base
      de datos; simplemente dejan de mostrarse aquí.

    Bsale:

    - Se contabilizan boletas pendientes de emisión.
    - El template puede acceder directamente a:
        pedido.bsale_url_pdf
        pedido.bsale_url_publica
        pedido.bsale_folio
        pedido.bsale_emitido
    """

    # =========================================================================
    # QUERYSET BASE
    # =========================================================================

    pedidos = (
        _queryset_pedidos()
        .annotate(
            total_unidades=Sum(
                "items__cantidad"
            ),
        )
        .order_by(
            "-actualizado",
        )
    )

    # =========================================================================
    # BUSCADOR
    # =========================================================================

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

    # =========================================================================
    # VENTAS CONFIRMADAS
    # =========================================================================
    #
    # Solo los pedidos cuyo pago realmente fue aprobado
    # forman parte de la operación logística.
    # =========================================================================

    ventas_confirmadas = pedidos.filter(
        pagado=True,
        estado_pago=Pedido.EstadoPago.APROBADO,
    )

    # =========================================================================
    # TODOS LOS PAGOS PENDIENTES
    # =========================================================================
    #
    # Este queryset puede contener intentos antiguos.
    #
    # Se conserva únicamente como referencia interna.
    # NO se utiliza directamente para mostrar la bandeja.
    # =========================================================================

    pendientes_pago_todos = pedidos.filter(
        pagado=False,
        estado_pago__in=[
            Pedido.EstadoPago.PENDIENTE,
            Pedido.EstadoPago.INICIADO,
        ],
    )

    # =========================================================================
    # LÍMITE DE VISIBILIDAD DE PAGOS PENDIENTES
    # =========================================================================
    #
    # Un intento pendiente solo merece atención administrativa
    # durante 48 horas desde su última actualización.
    #
    # Después de ese plazo:
    #
    # - No aparece como alerta.
    # - No aparece en la bandeja de pagos pendientes.
    # - No se incluye en el contador visible.
    # - NO se elimina de la base de datos.
    # =========================================================================

    limite_pendientes_visibles = (
        timezone.now()
        - timedelta(
            hours=48
        )
    )

    # =========================================================================
    # PAGOS PENDIENTES VISIBLES
    # =========================================================================

    pendientes_pago = (
        pendientes_pago_todos
        .filter(
            actualizado__gte=(
                limite_pendientes_visibles
            ),
        )
        .order_by(
            "-actualizado",
        )
    )

    # =========================================================================
    # PAGOS PENDIENTES EXPIRADOS
    # =========================================================================
    #
    # Solo se calcula por si posteriormente quieres
    # utilizarlo para estadísticas o mantenimiento.
    #
    # No se muestra en el panel.
    # =========================================================================

    pendientes_pago_expirados = (
        pendientes_pago_todos
        .filter(
            actualizado__lt=(
                limite_pendientes_visibles
            ),
        )
    )

    # =========================================================================
    # BANDEJAS OPERATIVAS
    # =========================================================================

    nuevos = ventas_confirmadas.filter(
        estado=Pedido.EstadoPedido.CONFIRMADO,
    )

    operacion = ventas_confirmadas.filter(
        estado__in=[
            Pedido.EstadoPedido.PREPARACION,
            Pedido.EstadoPedido.LISTO,
        ],
    )

    despacho = ventas_confirmadas.filter(
        estado=Pedido.EstadoPedido.ENVIADO,
    )

    finalizados = ventas_confirmadas.filter(
        estado__in=[
            Pedido.EstadoPedido.ENTREGADO,
            Pedido.EstadoPedido.CANCELADO,
        ],
    )

    # =========================================================================
    # BSALE
    # =========================================================================
    #
    # Venta pagada que todavía no registra
    # una boleta electrónica emitida.
    # =========================================================================

    boletas_pendientes = ventas_confirmadas.filter(
        bsale_emitido=False,
    )

    # =========================================================================
    # QUERYSETS DISPONIBLES
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # "pendientes" utiliza únicamente los intentos
    # correspondientes a las últimas 48 horas.
    #
    # Nunca se entrega aquí el histórico completo.
    # =========================================================================

    bandejas_querysets = {
        "nuevos": nuevos,
        "operacion": operacion,
        "despacho": despacho,
        "finalizados": finalizados,

        "pendientes": pendientes_pago,

        "boletas": boletas_pendientes,
    }

    # =========================================================================
    # NOMBRES
    # =========================================================================

    bandejas_nombres = {
        "nuevos": "Nuevos",
        "operacion": "En operación",
        "despacho": "En despacho",
        "finalizados": "Finalizados",
        "pendientes": "Pagos pendientes",
        "boletas": "Boletas pendientes",
    }

    # =========================================================================
    # ICONOS
    # =========================================================================

    bandejas_iconos = {
        "nuevos": "bi-bag-check",
        "operacion": "bi-box-seam",
        "despacho": "bi-truck",
        "finalizados": "bi-check2-circle",
        "pendientes": "bi-clock-history",
        "boletas": "bi-receipt-cutoff",
    }

    # =========================================================================
    # CONTADORES
    # =========================================================================

    totales = {
        clave: queryset.count()
        for clave, queryset
        in bandejas_querysets.items()
    }

    # =========================================================================
    # PAGOS PENDIENTES
    # =========================================================================
    #
    # Este es ahora el único contador que debería
    # utilizarse para mostrar la alerta.
    #
    # Si es 0, la alerta debe desaparecer.
    # =========================================================================

    total_pendientes_pago = (
        pendientes_pago.count()
    )

    # =========================================================================
    # HISTÓRICOS EXPIRADOS
    # =========================================================================
    #
    # No se muestran.
    #
    # Se conserva la variable únicamente por si quieres
    # usarla posteriormente en estadísticas o limpieza.
    # =========================================================================

    total_pendientes_expirados = (
        pendientes_pago_expirados.count()
    )

    # =========================================================================
    # BSALE
    # =========================================================================

    total_boletas_pendientes = (
        boletas_pendientes.count()
    )

    # =========================================================================
    # BANDEJA SOLICITADA
    # =========================================================================

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
            request.GET.get(
                "page",
                1,
            )
        )

        titulo_bandeja = (
            bandejas_nombres[
                bandeja_actual
            ]
        )

    # =========================================================================
    # TARJETAS DEL TABLERO
    # =========================================================================
    #
    # Pagos pendientes y Bsale continúan siendo
    # incidencias administrativas, no estados logísticos.
    # =========================================================================

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

        total = (
            totales[
                clave
            ]
        )

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

    # =========================================================================
    # CONTEXTO
    # =========================================================================

    return render(
        request,
        "core/gestion/panel_pedidos.html",
        {
            # =============================================================
            # TABLERO
            # =============================================================

            "bandejas": bandejas,

            # =============================================================
            # BANDEJA COMPLETA
            # =============================================================

            "bandeja_actual": (
                bandeja_actual
            ),

            "titulo_bandeja": (
                titulo_bandeja
            ),

            "mostrar_bandeja": (
                mostrar_bandeja
            ),

            "page_obj": (
                page_obj
            ),

            # =============================================================
            # BUSCADOR
            # =============================================================

            "busqueda": (
                busqueda
            ),

            # =============================================================
            # CONTADORES OPERATIVOS
            # =============================================================

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

            # =============================================================
            # PAGOS PENDIENTES
            # =============================================================
            #
            # Ambos nombres se mantienen para que tu HTML
            # actual siga funcionando aunque utilice uno
            # u otro.
            #
            # Los dos representan SOLO las últimas 48 horas.
            # =============================================================

            "total_pendientes_pago": (
                total_pendientes_pago
            ),

            "total_pendientes_recientes": (
                total_pendientes_pago
            ),

            # =============================================================
            # HISTÓRICO EXPIRADO
            # =============================================================
            #
            # No debería mostrarse como alerta.
            # =============================================================

            "total_pendientes_expirados": (
                total_pendientes_expirados
            ),

            # =============================================================
            # BSALE
            # =============================================================

            "total_boletas_pendientes": (
                total_boletas_pendientes
            ),

            # =============================================================
            # COMPATIBILIDAD
            # =============================================================

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
    """
    Detalle administrativo de un pedido.

    Permite:

    - revisar productos;
    - consultar cliente y despacho;
    - revisar información del pago;
    - consultar/descargar la boleta Bsale;
    - revisar historial;
    - avanzar el estado operativo.
    """

    # =========================================================================
    # NORMALIZAR NÚMERO
    # =========================================================================

    numero = _normalizar_numero_pedido(
        numero
    )

    # =========================================================================
    # PEDIDO
    # =========================================================================

    pedido = get_object_or_404(
        _queryset_pedidos(),
        numero__iexact=numero,
    )

    # =========================================================================
    # FORMULARIO
    # =========================================================================

    form = ActualizarEstadoPedidoForm(
        request.POST or None,
        pedido=pedido,
    )

    # =========================================================================
    # ACTUALIZAR ESTADO
    # =========================================================================

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

    # =========================================================================
    # HISTORIAL
    # =========================================================================

    historial = (
        pedido.historial_estados
        .select_related(
            "usuario",
        )
        .all()
    )

    # =========================================================================
    # RENDER
    # =========================================================================

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
