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

from django.db import transaction

from core.services.correos_seguimiento import (
    enviar_correo_despacho,
    enviar_correo_entrega,
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




def _queryset_panel_pedidos():
    """
    Queryset liviano para el panel administrativo.

    Solo carga lo necesario para dibujar las tarjetas:

    - pedido;
    - usuario;
    - items;
    - producto de cada item.

    No precarga historial porque el tablero general
    no lo utiliza.
    """

    return (
        Pedido.objects
        .select_related(
            "usuario",
        )
        .prefetch_related(
            "items__producto",
        )
    )


def _queryset_detalle_pedido():
    """
    Queryset optimizado para el detalle administrativo.

    Carga:

    - usuario;
    - items y productos;
    - historial y usuario asociado a cada cambio.

    No realiza llamadas externas.
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
    Seguimiento seguro de pedidos.

    MODOS DE ACCESO:

    1. USUARIO LOGUEADO
       - Puede acceder directamente a sus propios pedidos.
       - No necesita ingresar RUT nuevamente.

    2. USUARIO NO LOGUEADO / INVITADO
       - Debe ingresar número de pedido + RUT.
       - Una vez validados ambos datos, el pedido queda
         autorizado temporalmente en la sesión.

    3. ADMINISTRADOR
       - Puede consultar cualquier pedido.

    SEGURIDAD:

    - Conocer solamente el número del pedido no autoriza
      a un invitado a visualizarlo.
    """

    # =========================================================================
    # PREPARAR PEDIDO
    # =========================================================================

    def preparar_pedido(
        pedido_actual,
    ):
        """
        Prepara la información de seguimiento del pedido.
        """

        pedido_actual.refresh_from_db()

        # =====================================================================
        # ESTADO REAL DEL PAGO
        # =====================================================================

        pago_aprobado = bool(
            pedido_actual.pagado
            and pedido_actual.estado_pago
            == Pedido.EstadoPago.APROBADO
        )

        # =====================================================================
        # TIMELINE
        # =====================================================================

        timeline_actual = list(
            construir_timeline(
                pedido_actual
            )
            or []
        )

        # =====================================================================
        # AGREGAR PAGO CONFIRMADO
        # =====================================================================

        if pago_aprobado:

            existe_pago_confirmado = any(
                (
                    isinstance(
                        paso,
                        dict,
                    )
                    and str(
                        paso.get(
                            "titulo",
                            "",
                        )
                    )
                    .strip()
                    .lower()
                    == "pago confirmado"
                )
                for paso
                in timeline_actual
            )

            if not existe_pago_confirmado:

                indice_pago = 1

                for indice, paso in enumerate(
                    timeline_actual
                ):

                    if not isinstance(
                        paso,
                        dict,
                    ):
                        continue

                    titulo = (
                        str(
                            paso.get(
                                "titulo",
                                "",
                            )
                        )
                        .strip()
                        .lower()
                    )

                    if titulo == "pedido recibido":

                        paso[
                            "completado"
                        ] = True

                        paso[
                            "activo"
                        ] = False

                        indice_pago = (
                            indice
                            + 1
                        )

                        break

                paso_pago = {
                    "icono": (
                        "bi-credit-card-check"
                    ),

                    "titulo": (
                        "Pago confirmado"
                    ),

                    "descripcion": (
                        "El pago fue confirmado "
                        "correctamente."
                    ),

                    "fecha": (
                        pedido_actual.fecha_pago
                    ),

                    "completado": True,

                    "activo": False,
                }

                timeline_actual.insert(
                    indice_pago,
                    paso_pago,
                )

        return {
            "pedido": (
                pedido_actual
            ),

            "timeline": (
                timeline_actual
            ),

            "pago_confirmado": (
                pago_aprobado
            ),
        }

    # =========================================================================
    # RENDERIZAR PEDIDO AUTORIZADO
    # =========================================================================

    def renderizar_pedido(
        pedido_actual,
    ):
        datos = preparar_pedido(
            pedido_actual
        )

        form = BuscarPedidoForm()

        return render(
            request,
            "core/seguimiento_pedido.html",
            {
                "pedido": (
                    datos[
                        "pedido"
                    ]
                ),

                "form": form,

                "timeline": (
                    datos[
                        "timeline"
                    ]
                ),

                "pago_confirmado": (
                    datos[
                        "pago_confirmado"
                    ]
                ),
            },
        )

    # =========================================================================
    # NÚMERO RECIBIDO DESDE URL
    # =========================================================================

    numero_url = ""

    if numero:

        numero_url = (
            _normalizar_numero_pedido(
                numero
            )
        )

    # =========================================================================
    # POST
    # =========================================================================

    if request.method == "POST":

        numero_post = (
            request.POST.get(
                "numero",
                "",
            )
        )

        numero_post = (
            _normalizar_numero_pedido(
                numero_post
            )
        )

        # =====================================================================
        # USUARIO AUTENTICADO
        # =====================================================================

        if (
            request.user.is_authenticated
            and numero_post
        ):

            pedido_usuario = (
                _queryset_pedidos()
                .filter(
                    numero__iexact=(
                        numero_post
                    )
                )
                .first()
            )

            if pedido_usuario:

                es_admin = bool(
                    request.user.is_staff
                )

                es_propietario = bool(
                    pedido_usuario.usuario_id
                    == request.user.id
                )

                if (
                    es_admin
                    or es_propietario
                ):

                    return redirect(
                        "core:seguimiento_pedido_numero",
                        numero=(
                            pedido_usuario.numero
                        ),
                    )

        # =====================================================================
        # INVITADO
        # =====================================================================

        form = BuscarPedidoForm(
            request.POST
        )

        if form.is_valid():

            numero_form = (
                form.cleaned_data.get(
                    "numero"
                )
                or ""
            )

            numero_normalizado = (
                _normalizar_numero_pedido(
                    numero_form
                )
            )

            rut_form = (
                form.cleaned_data.get(
                    "rut"
                )
                or ""
            )

            rut_normalizado = (
                _normalizar_rut(
                    rut_form
                )
            )

            if not numero_normalizado:

                form.add_error(
                    "numero",
                    (
                        "Ingresa el número "
                        "del pedido."
                    ),
                )

            elif not rut_normalizado:

                form.add_error(
                    "rut",
                    (
                        "Ingresa el RUT asociado "
                        "al pedido."
                    ),
                )

            else:

                pedido_encontrado = (
                    _queryset_pedidos()
                    .filter(
                        numero__iexact=(
                            numero_normalizado
                        )
                    )
                    .first()
                )

                if pedido_encontrado is None:

                    form.add_error(
                        None,
                        (
                            "No pudimos validar los datos "
                            "del pedido. Revisa el número "
                            "y el RUT ingresados."
                        ),
                    )

                else:

                    rut_pedido = (
                        _normalizar_rut(
                            pedido_encontrado.rut
                        )
                    )

                    if (
                        not rut_pedido
                        or rut_normalizado
                        != rut_pedido
                    ):

                        form.add_error(
                            None,
                            (
                                "No pudimos validar los datos "
                                "del pedido. Revisa el número "
                                "y el RUT ingresados."
                            ),
                        )

                    else:

                        # =====================================================
                        # AUTORIZAR SEGUIMIENTO
                        # =====================================================

                        _autorizar_pedido_en_sesion(
                            request,
                            pedido_encontrado.numero,
                        )

                        # =====================================================
                        # AUTORIZAR COMPROBANTE EN ESTA SESIÓN
                        # =====================================================

                        comprobantes_autorizados = (
                            request.session.get(
                                "pedidos_comprobante_autorizados",
                                [],
                            )
                        )

                        if not isinstance(
                            comprobantes_autorizados,
                            list,
                        ):
                            comprobantes_autorizados = []

                        if (
                            pedido_encontrado.numero
                            not in comprobantes_autorizados
                        ):

                            comprobantes_autorizados.append(
                                pedido_encontrado.numero
                            )

                        request.session[
                            "pedidos_comprobante_autorizados"
                        ] = (
                            comprobantes_autorizados[
                                -MAX_PEDIDOS_AUTORIZADOS_SESION:
                            ]
                        )

                        request.session.modified = True

                        return redirect(
                            "core:seguimiento_pedido_numero",
                            numero=(
                                pedido_encontrado.numero
                            ),
                        )

    # =========================================================================
    # GET
    # =========================================================================

    else:

        if numero_url:

            pedido_encontrado = (
                _queryset_pedidos()
                .filter(
                    numero__iexact=(
                        numero_url
                    )
                )
                .first()
            )

            if pedido_encontrado:

                if _usuario_puede_ver(
                    request,
                    pedido_encontrado,
                ):

                    return renderizar_pedido(
                        pedido_encontrado
                    )

            form = BuscarPedidoForm(
                initial={
                    "numero": (
                        numero_url
                    ),
                }
            )

        else:

            form = BuscarPedidoForm()

    # =========================================================================
    # RENDER SIN PEDIDO AUTORIZADO
    # =========================================================================

    return render(
        request,
        "core/seguimiento_pedido.html",
        {
            "pedido": None,

            "form": form,

            "timeline": [],

            "pago_confirmado": False,
        },
    )

# ==========================================================================
# PANEL ADMINISTRATIVO DE PEDIDOS
# ==========================================================================
@staff_member_required
def panel_pedidos(request):
    """
    Panel administrativo de pedidos optimizado.

    REGLAS:

    - El tablero operativo muestra únicamente ventas pagadas.
    - La bandeja "Pagos pendientes" muestra solamente pedidos
      creados durante las últimas 48 horas.
    - Los pendientes anteriores a 48 horas no se muestran.
    - ?actualizar_panel=1 continúa siendo una consulta liviana.
    - version_panel solo cambia cuando cambian los contadores
      reales de las bandejas.
    - Cambios internos en Pedido.actualizado NO provocan
      recargas automáticas innecesarias.
    """

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

    # =========================================================================
    # QUERYSET BASE
    # =========================================================================

    pedidos = (
        _queryset_panel_pedidos()
        .annotate(
            total_unidades=Sum(
                "items__cantidad"
            ),
        )
    )

    # =========================================================================
    # BÚSQUEDA
    # =========================================================================

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
    # ORDEN GENERAL
    # =========================================================================

    pedidos = pedidos.order_by(
        "-actualizado",
    )

    # =========================================================================
    # VENTAS CONFIRMADAS
    # =========================================================================

    ventas_confirmadas = (
        pedidos
        .filter(
            pagado=True,
            estado_pago=(
                Pedido.EstadoPago.APROBADO
            ),
        )
    )

    # =========================================================================
    # LÍMITE DE 48 HORAS
    # =========================================================================

    limite_pendientes = (
        timezone.now()
        - timedelta(
            hours=48
        )
    )

    # =========================================================================
    # ALERTA GLOBAL DE PAGOS PENDIENTES
    # ÚLTIMAS 48 HORAS
    # =========================================================================

    pendientes_alerta_48h = (
        Pedido.objects
        .filter(
            pagado=False,
            estado_pago__in=[
                Pedido.EstadoPago.PENDIENTE,
                Pedido.EstadoPago.INICIADO,
            ],
            creado__gte=(
                limite_pendientes
            ),
        )
    )

    # =========================================================================
    # BANDEJA DE PAGOS PENDIENTES
    # ÚLTIMAS 48 HORAS
    # =========================================================================

    pendientes_pago = (
        pedidos
        .filter(
            pagado=False,
            estado_pago__in=[
                Pedido.EstadoPago.PENDIENTE,
                Pedido.EstadoPago.INICIADO,
            ],
            creado__gte=(
                limite_pendientes
            ),
        )
        .order_by(
            "-creado",
        )
    )

    # =========================================================================
    # NUEVOS
    # =========================================================================

    nuevos = (
        ventas_confirmadas
        .filter(
            estado=(
                Pedido.EstadoPedido.CONFIRMADO
            ),
        )
        .order_by(
            "-actualizado",
        )
    )

    # =========================================================================
    # EN OPERACIÓN
    # =========================================================================

    operacion = (
        ventas_confirmadas
        .filter(
            estado__in=[
                Pedido.EstadoPedido.PREPARACION,
                Pedido.EstadoPedido.LISTO,
            ],
        )
        .order_by(
            "-actualizado",
        )
    )

    # =========================================================================
    # EN DESPACHO
    # =========================================================================

    despacho = (
        ventas_confirmadas
        .filter(
            estado=(
                Pedido.EstadoPedido.ENVIADO
            ),
        )
        .order_by(
            "-actualizado",
        )
    )

    # =========================================================================
    # FINALIZADOS
    # =========================================================================

    finalizados = (
        ventas_confirmadas
        .filter(
            estado__in=[
                Pedido.EstadoPedido.ENTREGADO,
                Pedido.EstadoPedido.CANCELADO,
            ],
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
    }

    # =========================================================================
    # CONTADORES DE BANDEJAS
    # =========================================================================

    totales = {
        clave: queryset.count()
        for clave, queryset
        in bandejas_querysets.items()
    }

    # =========================================================================
    # PAGOS PENDIENTES
    # ALERTA GLOBAL DE 48 HORAS
    # =========================================================================

    total_pendientes_recientes = (
        pendientes_alerta_48h.count()
    )

    total_pendientes_pago = (
        total_pendientes_recientes
    )

    # =========================================================================
    # PENDIENTES EXPIRADOS
    # =========================================================================

    total_pendientes_expirados = 0

    # =========================================================================
    # ÚLTIMA ACTUALIZACIÓN
    # =========================================================================
    #
    # Este valor se conserva como información para el frontend,
    # pero NO forma parte de version_panel.
    #
    # De esta forma un simple save() sobre un pedido no provoca
    # una recarga automática si ningún pedido cambió realmente
    # de bandeja.
    # =========================================================================

    ultima_actualizacion = (
        pedidos
        .values_list(
            "actualizado",
            flat=True,
        )
        .first()
    )

    # =========================================================================
    # VERSIÓN ESTABLE DEL TABLERO
    # =========================================================================
    #
    # La versión depende únicamente de los contadores reales
    # de las bandejas.
    # =========================================================================

    version_panel = "|".join(
        [
            str(
                totales[
                    "nuevos"
                ]
            ),
            str(
                totales[
                    "operacion"
                ]
            ),
            str(
                totales[
                    "despacho"
                ]
            ),
            str(
                totales[
                    "finalizados"
                ]
            ),
            str(
                total_pendientes_pago
            ),
        ]
    )

    # =========================================================================
    # CONSULTA LIVIANA DEL FRONTEND
    # =========================================================================
    #
    # El JavaScript puede consultar:
    #
    #     ?actualizar_panel=1
    #
    # sin volver a cargar todo el HTML.
    # =========================================================================

    if (
        request.GET.get(
            "actualizar_panel"
        )
        == "1"
    ):
        response = JsonResponse(
            {
                "ok": True,

                "version": (
                    version_panel
                ),

                "ultima_actualizacion": (
                    ultima_actualizacion.isoformat()
                    if ultima_actualizacion
                    else None
                ),

                "totales": {
                    "nuevos": (
                        totales[
                            "nuevos"
                        ]
                    ),

                    "operacion": (
                        totales[
                            "operacion"
                        ]
                    ),

                    "despacho": (
                        totales[
                            "despacho"
                        ]
                    ),

                    "finalizados": (
                        totales[
                            "finalizados"
                        ]
                    ),

                    "pendientes": (
                        total_pendientes_pago
                    ),

                    "pendientes_recientes": (
                        total_pendientes_recientes
                    ),
                },
            }
        )

        # =====================================================================
        # EVITAR CACHÉ DEL POLLING
        # =====================================================================

        response[
            "Cache-Control"
        ] = (
            "no-store, no-cache, "
            "must-revalidate, max-age=0"
        )

        response[
            "Pragma"
        ] = "no-cache"

        response[
            "Expires"
        ] = "0"

        return response

    # =========================================================================
    # NOMBRES DE BANDEJAS
    # =========================================================================

    bandejas_nombres = {
        "nuevos": (
            "Nuevos"
        ),

        "operacion": (
            "En operación"
        ),

        "despacho": (
            "En despacho"
        ),

        "finalizados": (
            "Finalizados"
        ),

        "pendientes": (
            "Pagos pendientes"
        ),
    }

    # =========================================================================
    # ICONOS
    # =========================================================================

    bandejas_iconos = {
        "nuevos": (
            "bi-bag-check"
        ),

        "operacion": (
            "bi-box-seam"
        ),

        "despacho": (
            "bi-truck"
        ),

        "finalizados": (
            "bi-check2-circle"
        ),

        "pendientes": (
            "bi-clock-history"
        ),
    }

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

    # =========================================================================
    # PAGINACIÓN
    # =========================================================================

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

        page_obj = (
            paginador
            .get_page(
                request.GET.get(
                    "page",
                    1,
                )
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
    # Si estamos mostrando una bandeja completa,
    # no evaluamos también las cuatro columnas principales.
    # =========================================================================

    bandejas = []

    if not mostrar_bandeja:
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
                    "clave": (
                        clave
                    ),

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

                    "total": (
                        total
                    ),

                    "pedidos": (
                        queryset[
                            :PEDIDOS_VISIBLES_POR_BANDEJA
                        ]
                    ),

                    "hay_mas": (
                        total
                        > PEDIDOS_VISIBLES_POR_BANDEJA
                    ),
                }
            )

    # =========================================================================
    # CONTEXTO
    # =========================================================================

    contexto = {
        # =====================================================================
        # TABLERO
        # =====================================================================

        "bandejas": (
            bandejas
        ),

        "version_panel": (
            version_panel
        ),

        # =====================================================================
        # BANDEJA
        # =====================================================================

        "bandeja_actual": (
            bandeja_actual
        ),

        "titulo_bandeja": (
            titulo_bandeja
        ),

        "mostrar_bandeja": (
            mostrar_bandeja
        ),

        # =====================================================================
        # PAGINACIÓN
        # =====================================================================

        "page_obj": (
            page_obj
        ),

        # =====================================================================
        # BÚSQUEDA
        # =====================================================================

        "busqueda": (
            busqueda
        ),

        # =====================================================================
        # CONTADORES PRINCIPALES
        # =====================================================================

        "total_principal": (
            totales[
                "nuevos"
            ]
        ),

        "total_operacion": (
            totales[
                "operacion"
            ]
        ),

        "total_despacho": (
            totales[
                "despacho"
            ]
        ),

        "total_cerrados": (
            totales[
                "finalizados"
            ]
        ),

        # =====================================================================
        # PAGOS PENDIENTES
        # =====================================================================

        "total_pendientes_pago": (
            total_pendientes_pago
        ),

        "total_pendientes_recientes": (
            total_pendientes_recientes
        ),

        "total_pendientes_expirados": (
            total_pendientes_expirados
        ),

        # =====================================================================
        # INFORMACIÓN DE ACTUALIZACIÓN
        # =====================================================================

        "ultima_actualizacion": (
            ultima_actualizacion
        ),

        # =====================================================================
        # COMPATIBILIDAD CON EL TEMPLATE ACTUAL
        # =====================================================================

        "principal": (
            nuevos[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ]
            if not mostrar_bandeja
            else []
        ),

        "operacion": (
            operacion[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ]
            if not mostrar_bandeja
            else []
        ),

        "despacho": (
            despacho[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ]
            if not mostrar_bandeja
            else []
        ),

        "cerrados": (
            finalizados[
                :PEDIDOS_VISIBLES_POR_BANDEJA
            ]
            if not mostrar_bandeja
            else []
        ),
    }

    # =========================================================================
    # RENDER
    # =========================================================================

    return render(
        request,
        "core/gestion/panel_pedidos.html",
        contexto,
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

    REGLAS:

    1. PEDIDO PAGADO
       - Puede avanzar de estado operativo.

    2. PEDIDO PENDIENTE DE PAGO
       - Puede abrirse desde el panel administrativo.
       - No puede avanzar de estado.

    3. PEDIDO ENVIADO
       - Requiere número de seguimiento.
       - Se asigna automáticamente Blue Express.
       - Se guarda el número de seguimiento antes
         de completar el cambio de estado.
       - Se envía correo de despacho después
         de guardar correctamente.

    4. PEDIDO ENTREGADO
       - Se envía correo de entrega.

    5. NOTIFICACIONES
       - Los servicios de correo evitan duplicados.

    6. El acceso es exclusivo para staff.
    """

    # =========================================================================
    # NORMALIZAR NÚMERO
    # =========================================================================

    numero = (
        _normalizar_numero_pedido(
            numero
        )
    )

    # =========================================================================
    # OBTENER PEDIDO
    # =========================================================================

    pedido = get_object_or_404(
        _queryset_detalle_pedido(),
        numero__iexact=numero,
    )

    # =========================================================================
    # ESTADO REAL DEL PAGO
    # =========================================================================

    pago_aprobado = bool(
        pedido.pagado
        and pedido.estado_pago
        == Pedido.EstadoPago.APROBADO
    )

    # =========================================================================
    # PAGO PENDIENTE
    # =========================================================================

    es_pago_pendiente = bool(
        not pedido.pagado
        and pedido.estado_pago
        in [
            Pedido.EstadoPago.PENDIENTE,
            Pedido.EstadoPago.INICIADO,
        ]
    )

    # =========================================================================
    # PUEDE AVANZAR
    # =========================================================================

    puede_avanzar_estado = (
        pago_aprobado
    )

    # =========================================================================
    # FORMULARIO
    # =========================================================================

    form = ActualizarEstadoPedidoForm(
        request.POST or None,
        pedido=pedido,
    )

    # =========================================================================
    # POST
    # =========================================================================

    if request.method == "POST":

        # =====================================================================
        # IMPEDIR AVANCE SIN PAGO
        # =====================================================================

        if not pago_aprobado:

            form.add_error(
                None,
                (
                    "Este pedido todavía no tiene el pago "
                    "confirmado. No puede avanzar de estado."
                ),
            )

        # =====================================================================
        # FORMULARIO VÁLIDO
        # =====================================================================

        elif form.is_valid():

            # =================================================================
            # NUEVO ESTADO
            # =================================================================

            nuevo_estado = (
                form.cleaned_data[
                    "nuevo_estado"
                ]
            )

            # =================================================================
            # COMENTARIO
            # =================================================================

            comentario = (
                form.cleaned_data.get(
                    "comentario",
                    "",
                )
                or ""
            ).strip()

            # =================================================================
            # NÚMERO DE SEGUIMIENTO
            # =================================================================

            numero_seguimiento = (
                form.cleaned_data.get(
                    "numero_seguimiento",
                    "",
                )
                or ""
            ).strip()

            # =================================================================
            # NORMALIZAR NÚMERO DE SEGUIMIENTO
            # =================================================================

            if numero_seguimiento:

                numero_seguimiento = (
                    numero_seguimiento
                    .strip()
                    .upper()
                )

            # =================================================================
            # GUARDAR ESTADO ANTERIOR
            # =================================================================

            estado_anterior = (
                pedido.estado
            )

            # =================================================================
            # VALIDAR BLUE EXPRESS ANTES DE ENVIAR
            # =================================================================

            if (
                nuevo_estado
                == Pedido.EstadoPedido.ENVIADO
                and not numero_seguimiento
            ):

                form.add_error(
                    "numero_seguimiento",
                    (
                        "Debes ingresar el número de "
                        "seguimiento de Blue Express "
                        "antes de marcar el pedido "
                        "como enviado."
                    ),
                )

            else:

                try:

                    # =========================================================
                    # TRANSACCIÓN
                    # =========================================================

                    with transaction.atomic():

                        # =====================================================
                        # BLUE EXPRESS
                        # =====================================================

                        if (
                            nuevo_estado
                            == Pedido.EstadoPedido.ENVIADO
                        ):

                            # =================================================
                            # GUARDAR TRANSPORTISTA
                            # =================================================

                            pedido.transportista = (
                                Pedido.Transportista.BLUEXPRESS
                            )

                            # =================================================
                            # GUARDAR NÚMERO DE SEGUIMIENTO
                            # =================================================

                            pedido.numero_seguimiento = (
                                numero_seguimiento
                            )

                            pedido.save(
                                update_fields=[
                                    "transportista",
                                    "numero_seguimiento",
                                    "actualizado",
                                ]
                            )

                        # =====================================================
                        # CAMBIAR ESTADO
                        # =====================================================

                        pedido_actualizado = (
                            cambiar_estado_pedido(
                                pedido=pedido,
                                nuevo_estado=nuevo_estado,
                                comentario=comentario,
                                usuario=request.user,
                            )
                        )

                        # =====================================================
                        # COMPROBAR CAMBIO REAL
                        # =====================================================

                        cambio_estado = (
                            estado_anterior
                            != pedido_actualizado.estado
                        )

                        # =====================================================
                        # CORREO DE DESPACHO
                        # =====================================================

                        if (
                            cambio_estado
                            and pedido_actualizado.estado
                            == Pedido.EstadoPedido.ENVIADO
                        ):

                            pedido_id = (
                                pedido_actualizado.pk
                            )

                            transaction.on_commit(
                                lambda pedido_id=pedido_id:
                                enviar_correo_despacho(
                                    Pedido.objects.get(
                                        pk=pedido_id
                                    )
                                )
                            )

                        # =====================================================
                        # CORREO DE ENTREGA
                        # =====================================================

                        elif (
                            cambio_estado
                            and pedido_actualizado.estado
                            == Pedido.EstadoPedido.ENTREGADO
                        ):

                            pedido_id = (
                                pedido_actualizado.pk
                            )

                            transaction.on_commit(
                                lambda pedido_id=pedido_id:
                                enviar_correo_entrega(
                                    Pedido.objects.get(
                                        pk=pedido_id
                                    )
                                )
                            )

                # =================================================================
                # ERROR DE VALIDACIÓN
                # =================================================================

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

                # =================================================================
                # ERROR INESPERADO
                # =================================================================

                except Exception as error:

                    logger.exception(
                        (
                            "Error inesperado actualizando "
                            "estado operativo del pedido. "
                            "Pedido=%s "
                            "Estado=%s "
                            "Seguimiento=%s "
                            "Error=%s"
                        ),
                        pedido.numero,
                        nuevo_estado,
                        numero_seguimiento,
                        error,
                    )

                    form.add_error(
                        None,
                        (
                            "No fue posible actualizar el estado "
                            "del pedido. Intenta nuevamente."
                        ),
                    )

                # =================================================================
                # TODO CORRECTO
                # =================================================================

                else:

                    # =============================================================
                    # MENSAJE ESPECIAL SI FUE ENVIADO
                    # =============================================================

                    if (
                        pedido_actualizado.estado
                        == Pedido.EstadoPedido.ENVIADO
                    ):

                        messages.success(
                            request,
                            (
                                "El pedido "
                                f"{pedido_actualizado.numero} "
                                "fue marcado como enviado. "
                                "Número de seguimiento Blue Express: "
                                f"{pedido_actualizado.numero_seguimiento}"
                            ),
                        )

                    # =============================================================
                    # MENSAJE NORMAL
                    # =============================================================

                    else:

                        messages.success(
                            request,
                            (
                                "El pedido "
                                f"{pedido_actualizado.numero} "
                                "fue actualizado correctamente."
                            ),
                        )

                    # =============================================================
                    # REDIRECCIÓN
                    # =============================================================

                    return redirect(
                        "core:panel_pedido_detalle",
                        numero=(
                            pedido_actualizado.numero
                        ),
                    )

    # =========================================================================
    # HISTORIAL
    # =========================================================================

    historial = list(
        pedido.historial_estados.all()
    )

    # =========================================================================
    # TIMELINE
    # =========================================================================

    timeline = (
        construir_timeline(
            pedido
        )
        or []
    )

    # =========================================================================
    # DIAGNÓSTICO
    # =========================================================================

    if (
        pago_aprobado
        and not timeline
    ):

        logger.warning(
            (
                "Timeline vacía para pedido pagado. "
                "Pedido=%s "
                "Estado=%s "
                "EstadoPago=%s"
            ),
            pedido.numero,
            pedido.estado,
            pedido.estado_pago,
        )

    # =========================================================================
    # RENDER
    # =========================================================================

    return render(
        request,
        "core/gestion/panel_pedido_detalle.html",
        {
            # =================================================================
            # PEDIDO
            # =================================================================

            "pedido": (
                pedido
            ),

            # =================================================================
            # FORMULARIO
            # =================================================================

            "form": (
                form
            ),

            # =================================================================
            # TIMELINE
            # =================================================================

            "timeline": (
                timeline
            ),

            # =================================================================
            # HISTORIAL
            # =================================================================

            "historial": (
                historial
            ),

            # =================================================================
            # PAGO
            # =================================================================

            "pago_aprobado": (
                pago_aprobado
            ),

            # =================================================================
            # PAGO PENDIENTE
            # =================================================================

            "es_pago_pendiente": (
                es_pago_pendiente
            ),

            # =================================================================
            # PUEDE AVANZAR
            # =================================================================

            "puede_avanzar_estado": (
                puede_avanzar_estado
            ),
        },
    )
