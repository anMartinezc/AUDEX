from datetime import timedelta
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.urls import reverse


from core.services.nubox import (
    NuboxError,
    obtener_pdf_nubox,
    sincronizar_estado_nubox,
)

from django.contrib.auth.decorators import (
    login_required,
)
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
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


logger = logging.getLogger(__name__)


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

    if not isinstance(
        autorizados,
        list,
    ):
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
        autorizados.append(
            numero
        )

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
            estado_pago=(
                Pedido.EstadoPago.APROBADO
            ),
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
            # AUTORIZAR PEDIDO EN LA SESIÓN
            # =================================================================

            _autorizar_pedido_en_sesion(
                request,
                pedido.numero,
            )

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

                _autorizar_pedido_en_sesion(
                    request,
                    pedido.numero,
                )

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

    Además:

    - sincroniza automáticamente una cantidad limitada
      de documentos Nubox pendientes;
    - evita mantener boletas marcadas como pendientes
      cuando Nubox ya terminó su emisión;
    - no vuelve a emitir documentos;
    - solamente consulta documentos que ya poseen
      nubox_document_id.
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

    ventas_confirmadas = (
        pedidos.filter(
            pagado=True,
            estado_pago=(
                Pedido.EstadoPago.APROBADO
            ),
        )
    )

    # =========================================================================
    # SINCRONIZACIÓN AUTOMÁTICA NUBOX
    # =========================================================================
    #
    # Importante:
    #
    # - Solo consultamos documentos que Nubox ya recibió.
    # - No volvemos a emitir ninguna boleta.
    # - Procesamos una cantidad limitada para no hacer
    #   lenta la carga del panel.
    # - Evitamos volver a consultar documentos recién
    #   sincronizados.
    # =========================================================================

    limite_sincronizacion_nubox = (
        timezone.now()
        - timedelta(
            seconds=15
        )
    )

    documentos_nubox_pendientes = (
        Pedido.objects
        .filter(
            pagado=True,
            estado_pago=(
                Pedido.EstadoPago.APROBADO
            ),
            nubox_emitido=False,
            nubox_document_id__isnull=False,
            actualizado__lt=(
                limite_sincronizacion_nubox
            ),
        )
        .exclude(
            nubox_document_id=""
        )
        .order_by(
            "actualizado",
        )[:10]
    )

    for pedido_nubox in (
        documentos_nubox_pendientes
    ):

        try:

            sincronizar_estado_nubox(
                pedido_nubox
            )

        except NuboxError:

            # El panel administrativo no debe
            # dejar de cargar si Nubox está
            # temporalmente no disponible.
            pass

        except Exception:

            # Mismo criterio:
            # un problema externo de Nubox no
            # debe romper el panel completo.
            pass

    # =========================================================================
    # TODOS LOS PAGOS PENDIENTES
    # =========================================================================

    pendientes_pago_todos = (
        pedidos.filter(
            pagado=False,
            estado_pago__in=[
                Pedido.EstadoPago.PENDIENTE,
                Pedido.EstadoPago.INICIADO,
            ],
        )
    )

    # =========================================================================
    # LÍMITE DE VISIBILIDAD
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

    nuevos = (
        ventas_confirmadas.filter(
            estado=(
                Pedido.EstadoPedido.CONFIRMADO
            ),
        )
    )

    operacion = (
        ventas_confirmadas.filter(
            estado__in=[
                Pedido.EstadoPedido.PREPARACION,
                Pedido.EstadoPedido.LISTO,
            ],
        )
    )

    despacho = (
        ventas_confirmadas.filter(
            estado=(
                Pedido.EstadoPedido.ENVIADO
            ),
        )
    )

    finalizados = (
        ventas_confirmadas.filter(
            estado__in=[
                Pedido.EstadoPedido.ENTREGADO,
                Pedido.EstadoPedido.CANCELADO,
            ],
        )
    )

    # =========================================================================
    # NUBOX
    # =========================================================================

    boletas_pendientes = (
        ventas_confirmadas
        .filter(
            nubox_emitido=False,
            nubox_document_id__isnull=False,
        )
        .exclude(
            nubox_document_id=""
        )
        .order_by(
            "-actualizado",
        )
    )

    # =========================================================================
    # QUERYSETS DISPONIBLES
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

    total_pendientes_pago = (
        pendientes_pago.count()
    )

    # =========================================================================
    # HISTÓRICOS EXPIRADOS
    # =========================================================================

    total_pendientes_expirados = (
        pendientes_pago_expirados.count()
    )

    # =========================================================================
    # NUBOX
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
            # CONTADORES
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

            "total_pendientes_pago": (
                total_pendientes_pago
            ),

            "total_pendientes_recientes": (
                total_pendientes_pago
            ),

            "total_pendientes_expirados": (
                total_pendientes_expirados
            ),

            # =============================================================
            # NUBOX
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
    - consultar automáticamente el estado Nubox;
    - consultar el folio Nubox;
    - revisar errores de emisión;
    - revisar historial;
    - avanzar el estado operativo.

    Nubox:

    Si el pedido ya posee nubox_document_id
    pero todavía no está marcado como emitido,
    al abrir el detalle administrativo se consulta
    nuevamente el estado directamente en Nubox.

    Esta consulta NO vuelve a emitir la boleta.
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
    # SINCRONIZAR NUBOX
    # =========================================================================
    #
    # Solo consultamos:
    #
    # - pedidos pagados;
    # - que ya poseen document_id;
    # - que todavía no aparecen como emitidos.
    #
    # IMPORTANTE:
    #
    # sincronizar_estado_nubox() únicamente consulta
    # el documento existente.
    #
    # NO vuelve a emitir la boleta.
    # =========================================================================

    if (
        request.method == "GET"
        and pedido.pago_aprobado
        and pedido.nubox_document_id
        and not pedido.nubox_emitido
    ):

        try:

            sincronizar_estado_nubox(
                pedido
            )

        except NuboxError as error:

            # No bloqueamos el panel administrativo
            # si Nubox está temporalmente caído.
            #
            # El error puede quedar registrado en logs,
            # pero el administrador igualmente podrá
            # revisar y gestionar el pedido.
            logger.warning(
                (
                    "No fue posible sincronizar "
                    "Nubox desde detalle admin. "
                    "Pedido=%s Error=%s"
                ),
                pedido.numero,
                error,
            )

        except Exception as error:

            logger.exception(
                (
                    "Error inesperado sincronizando "
                    "Nubox desde detalle admin. "
                    "Pedido=%s Error=%s"
                ),
                pedido.numero,
                error,
            )

        # Volvemos a cargar el pedido porque
        # sincronizar_estado_nubox() puede haber
        # actualizado:
        #
        # - nubox_estado
        # - nubox_folio
        # - nubox_emitido
        # - nubox_emitido_en
        # - actualizado

        pedido.refresh_from_db()

    # =========================================================================
    # FORMULARIO
    # =========================================================================

    form = ActualizarEstadoPedidoForm(
        request.POST or None,
        pedido=pedido,
    )

    # =========================================================================
    # ACTUALIZAR ESTADO OPERATIVO
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






@require_http_methods(["GET"])
def estado_boleta_nubox(
    request,
    numero,
):
    """
    Consulta el estado más reciente de la boleta en Nubox.

    Está pensado para el polling AJAX de la página de confirmación.
    Si Nubox todavía está procesando el documento, devuelve el estado
    actual sin bloquear la compra ni volver a emitir la boleta.

    IMPORTANTE:

    - Nunca crea una segunda boleta.
    - Nunca cambia el X-Idempotence-id.
    - Solo sincroniza un documento Nubox ya existente.
    - No expone credenciales ni mensajes internos de Nubox al navegador.
    """

    # =========================================================================
    # NORMALIZAR Y OBTENER PEDIDO
    # =========================================================================

    numero = _normalizar_numero_pedido(
        numero
    )

    pedido = get_object_or_404(
        Pedido.objects.select_related(
            "usuario",
        ),
        numero__iexact=numero,
    )

    # =========================================================================
    # AUTORIZACIÓN
    # =========================================================================

    if not _usuario_puede_ver(
        request,
        pedido,
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "No autorizado.",
            },
            status=403,
        )

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not pedido.pago_aprobado:
        return JsonResponse(
            {
                "ok": False,
                "emitido": False,
                "estado": "PAGO_NO_APROBADO",
                "folio": None,
                "descarga_url": None,
            },
            status=409,
        )

    # =========================================================================
    # TODAVÍA NO EXISTE DOCUMENT ID
    # =========================================================================

    if not pedido.nubox_document_id:
        response = JsonResponse(
            {
                "ok": True,
                "emitido": False,
                "estado": (
                    pedido.nubox_estado
                    or "PREPARANDO"
                ),
                "folio": None,
                "descarga_url": None,
                "error_temporal": bool(
                    pedido.nubox_ultimo_error
                ),
            }
        )

        response[
            "Cache-Control"
        ] = "no-store"

        return response

    # =========================================================================
    # SINCRONIZAR ESTADO REAL CON NUBOX
    # =========================================================================

    if not pedido.nubox_emitido:

        try:
            sincronizar_estado_nubox(
                pedido
            )

        except NuboxError as error:

            logger.warning(
                (
                    "No fue posible sincronizar "
                    "Nubox para pedido %s: %s"
                ),
                pedido.numero,
                error,
            )

        except Exception:

            logger.exception(
                (
                    "Error inesperado al sincronizar "
                    "Nubox para pedido %s."
                ),
                pedido.numero,
            )

        pedido.refresh_from_db()

    # =========================================================================
    # URL DE DESCARGA
    # =========================================================================

    descarga_url = None

    if pedido.nubox_emitido:
        descarga_url = reverse(
            "core:descargar_boleta_nubox",
            kwargs={
                "numero": pedido.numero,
            },
        )

    # =========================================================================
    # RESPUESTA JSON
    # =========================================================================

    response = JsonResponse(
        {
            "ok": True,
            "document_id": (
                pedido.nubox_document_id
            ),
            "emitido": bool(
                pedido.nubox_emitido
            ),
            "estado": (
                pedido.nubox_estado
                or "PROCESANDO"
            ),
            "folio": (
                pedido.nubox_folio
                or None
            ),
            "descarga_url": descarga_url,
            "error_temporal": bool(
                pedido.nubox_ultimo_error
            ),
        }
    )

    response[
        "Cache-Control"
    ] = "no-store"

    return response


# ==========================================================================
# DESCARGAR BOLETA NUBOX
# ==========================================================================


@require_http_methods(["GET"])
def descargar_boleta_nubox(
    request,
    numero,
):
    """
    Obtiene la boleta electrónica directamente
    desde Nubox y la entrega al navegador.

    Las credenciales de Nubox permanecen
    exclusivamente en el backend.

    Antes de solicitar el PDF se comprueba el estado
    más reciente del documento para evitar pedir a Nubox
    un PDF que todavía no ha terminado de emitirse.
    """

    # =========================================================================
    # NORMALIZAR PEDIDO
    # =========================================================================

    numero = _normalizar_numero_pedido(
        numero
    )

    # =========================================================================
    # OBTENER PEDIDO
    # =========================================================================

    pedido = get_object_or_404(
        _queryset_pedidos(),
        numero__iexact=numero,
    )

    # =========================================================================
    # AUTORIZACIÓN
    # =========================================================================

    if not _usuario_puede_ver(
        request,
        pedido,
    ):
        return HttpResponse(
            "No tienes permiso para acceder a esta boleta.",
            status=403,
        )

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not pedido.pago_aprobado:
        return HttpResponse(
            "La boleta no está disponible.",
            status=404,
        )

    # =========================================================================
    # VALIDAR DOCUMENTO NUBOX
    # =========================================================================

    if not pedido.nubox_document_id:
        return HttpResponse(
            "La boleta todavía no ha sido generada.",
            status=404,
        )

    # =========================================================================
    # SINCRONIZAR ANTES DE DESCARGAR
    # =========================================================================

    if not pedido.nubox_emitido:

        try:
            sincronizar_estado_nubox(
                pedido
            )

        except NuboxError as error:

            logger.warning(
                (
                    "No fue posible sincronizar "
                    "Nubox antes de descargar. "
                    "Pedido=%s error=%s"
                ),
                pedido.numero,
                error,
            )

        except Exception:

            logger.exception(
                (
                    "Error inesperado sincronizando "
                    "Nubox antes de descargar. "
                    "Pedido=%s"
                ),
                pedido.numero,
            )

        pedido.refresh_from_db()

    if not pedido.nubox_emitido:
        return HttpResponse(
            (
                "La boleta todavía está "
                "en procesamiento."
            ),
            status=409,
        )

    # =========================================================================
    # OBTENER PDF DESDE NUBOX
    # =========================================================================

    try:
        pdf = obtener_pdf_nubox(
            pedido.nubox_document_id,
            formato="A4",
        )

    except NuboxError as error:

        logger.warning(
            (
                "No fue posible obtener PDF Nubox. "
                "Pedido=%s document_id=%s error=%s"
            ),
            pedido.numero,
            pedido.nubox_document_id,
            error,
        )

        return HttpResponse(
            (
                "No fue posible obtener la boleta "
                "en este momento. Intenta nuevamente."
            ),
            status=502,
        )

    except Exception:

        logger.exception(
            (
                "Error inesperado obteniendo PDF Nubox. "
                "Pedido=%s document_id=%s"
            ),
            pedido.numero,
            pedido.nubox_document_id,
        )

        return HttpResponse(
            (
                "No fue posible obtener la boleta "
                "en este momento. Intenta nuevamente."
            ),
            status=502,
        )

    # =========================================================================
    # RESPUESTA
    # =========================================================================

    response = HttpResponse(
        pdf,
        content_type="application/pdf",
    )

    nombre_archivo = (
        f"boleta-{pedido.numero}.pdf"
    )

    response[
        "Content-Disposition"
    ] = (
        f'attachment; filename="{nombre_archivo}"'
    )

    response[
        "Cache-Control"
    ] = "private, no-store"

    response[
        "X-Content-Type-Options"
    ] = "nosniff"

    return response
