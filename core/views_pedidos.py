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

    IMPORTANTE:

    No realiza llamadas externas.
    Nubox se consulta después mediante polling AJAX.
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
def _normalizar_rut(
    rut,
) -> str:
    """
    Normaliza un RUT para comparaciones.

    Ejemplos:

    12.345.678-9 -> 12345678-9
    12345678-9   -> 12345678-9
    12 345 678-9 -> 12345678-9
    """

    return (
        str(
            rut
            or ""
        )
        .strip()
        .upper()
        .replace(
            ".",
            "",
        )
        .replace(
            " ",
            "",
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
       - Debe ingresar:
            número de pedido
            +
            RUT utilizado en la compra.
       - Una vez validados ambos datos, el pedido queda
         autorizado temporalmente en la sesión.

    3. ADMINISTRADOR
       - Puede consultar cualquier pedido.

    SEGURIDAD:

    - Conocer solamente el número de pedido no autoriza
      a un invitado a visualizarlo.
    - La descarga de la boleta utiliza un endpoint protegido.
    """

    # =========================================================================
    # VARIABLES GENERALES
    # =========================================================================

    pedido = None
    timeline = []

    pago_confirmado = False

    boleta_disponible = False
    boleta_descarga_url = None


    # =========================================================================
    # PREPARAR PEDIDO AUTORIZADO
    # =========================================================================

    def preparar_pedido(
        pedido_actual,
    ):
        """
        Prepara toda la información que verá el cliente.

        Incluye:

        - timeline;
        - paso "Pago confirmado";
        - estado real del pago;
        - disponibilidad de boleta;
        - URL segura para descargar la boleta.
        """

        # =====================================================================
        # REFRESCAR DESDE BASE DE DATOS
        # =====================================================================

        pedido_actual.refresh_from_db()


        # =====================================================================
        # CONFIRMACIÓN REAL DEL PAGO
        # =====================================================================
        #
        # No asumimos que está pagado solamente porque
        # exista el pedido.
        #
        # Ambos valores deben confirmar el pago.
        # =====================================================================

        pago_aprobado = bool(
            pedido_actual.pagado
            and pedido_actual.estado_pago
            == Pedido.EstadoPago.APROBADO
        )


        # =====================================================================
        # TIMELINE ORIGINAL
        # =====================================================================

        timeline_actual = list(
            construir_timeline(
                pedido_actual
            )
            or []
        )


        # =====================================================================
        # AGREGAR "PAGO CONFIRMADO"
        # =====================================================================

        if pago_aprobado:

            # =================================================================
            # COMPROBAR SI YA EXISTE
            # =================================================================

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

                # =============================================================
                # POSICIÓN POR DEFECTO
                # =============================================================
                #
                # Normalmente irá:
                #
                # 1. Pedido recibido
                # 2. Pago confirmado
                # =============================================================

                indice_pago = 1


                # =============================================================
                # BUSCAR "PEDIDO RECIBIDO"
                # =============================================================

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

                        # =====================================================
                        # PEDIDO RECIBIDO YA ESTÁ COMPLETADO
                        # =====================================================

                        paso[
                            "completado"
                        ] = True

                        paso[
                            "activo"
                        ] = False


                        # =====================================================
                        # INSERTAR PAGO JUSTO DESPUÉS
                        # =====================================================

                        indice_pago = (
                            indice
                            + 1
                        )

                        break


                # =============================================================
                # PASO PAGO CONFIRMADO
                # =============================================================
                #
                # IMPORTANTE:
                #
                # Este paso solamente existe cuando:
                #
                #     pagado=True
                #
                # y:
                #
                #     estado_pago=APROBADO
                #
                # Por lo tanto siempre debe mostrarse como
                # COMPLETADO y nunca como paso activo.
                # =============================================================

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

                    # No inventamos una fecha de pago.
                    # Si más adelante agregas un campo
                    # específico, puedes utilizarlo aquí.
                    "fecha": None,

                    "completado": True,

                    "activo": False,
                }


                # =============================================================
                # INSERTAR EN TIMELINE
                # =============================================================

                timeline_actual.insert(
                    indice_pago,
                    paso_pago,
                )


        # =====================================================================
        # BOLETA DISPONIBLE
        # =====================================================================
        #
        # Solamente habilitamos la descarga cuando:
        #
        # - el pago fue aprobado;
        # - existe documento;
        # - la boleta está marcada como emitida.
        # =====================================================================

        boleta_lista = bool(
            pago_aprobado
            and pedido_actual.nubox_document_id
            and pedido_actual.nubox_emitido
        )


        # =====================================================================
        # URL SEGURA DE DESCARGA
        # =====================================================================
        #
        # IMPORTANTE:
        #
        # No enviamos directamente al cliente una URL interna
        # del proveedor.
        #
        # Utilizamos:
        #
        #     descargar_boleta_nubox
        #
        # Ese endpoint vuelve a comprobar:
        #
        # - autorización del pedido;
        # - pago aprobado;
        # - disponibilidad de la boleta.
        #
        # Por lo tanto funciona tanto para:
        #
        # - usuario autenticado dueño del pedido;
        # - invitado autorizado previamente con RUT.
        # =====================================================================

        descarga_url = None

        if boleta_lista:

            descarga_url = reverse(
                "core:descargar_boleta_nubox",
                kwargs={
                    "numero": (
                        pedido_actual.numero
                    ),
                },
            )


        # =====================================================================
        # RETORNO
        # =====================================================================

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

            "boleta_disponible": (
                boleta_lista
            ),

            "boleta_descarga_url": (
                descarga_url
            ),
        }


    # =========================================================================
    # RENDERIZAR PEDIDO AUTORIZADO
    # =========================================================================

    def renderizar_pedido(
        pedido_actual,
    ):
        """
        Renderiza un pedido después de comprobar
        que el usuario está autorizado.
        """

        datos = preparar_pedido(
            pedido_actual
        )

        form = (
            BuscarPedidoForm()
        )

        return render(
            request,
            "core/seguimiento_pedido.html",
            {
                "pedido": (
                    datos[
                        "pedido"
                    ]
                ),

                "form": (
                    form
                ),

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

                "boleta_disponible": (
                    datos[
                        "boleta_disponible"
                    ]
                ),

                "boleta_descarga_url": (
                    datos[
                        "boleta_descarga_url"
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
    #
    # Principalmente utilizado por clientes invitados
    # que buscan el pedido mediante número + RUT.
    #
    # También permitimos que un usuario autenticado
    # acceda a SU pedido sin tener que volver a ingresar
    # el RUT.
    # =========================================================================

    if request.method == "POST":

        # =====================================================================
        # NÚMERO ENVIADO
        # =====================================================================

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
        #
        # Antes de exigir número + RUT comprobamos si
        # el pedido pertenece al usuario autenticado.
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

                # =============================================================
                # ADMINISTRADOR
                # =============================================================

                es_admin = bool(
                    request.user.is_staff
                )


                # =============================================================
                # DUEÑO DEL PEDIDO
                # =============================================================

                es_propietario = bool(
                    pedido_usuario.usuario_id
                    == request.user.id
                )


                # =============================================================
                # ACCESO AUTOMÁTICO
                # =============================================================

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
        # INVITADO / VALIDACIÓN NÚMERO + RUT
        # =====================================================================

        form = BuscarPedidoForm(
            request.POST
        )


        # =====================================================================
        # FORMULARIO VÁLIDO
        # =====================================================================

        if form.is_valid():

            # =================================================================
            # NÚMERO
            # =================================================================

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


            # =================================================================
            # RUT
            # =================================================================

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


            # =================================================================
            # VALIDACIONES
            # =================================================================

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

                # =============================================================
                # BUSCAR PEDIDO
                # =============================================================

                pedido_encontrado = (
                    _queryset_pedidos()
                    .filter(
                        numero__iexact=(
                            numero_normalizado
                        )
                    )
                    .first()
                )


                # =============================================================
                # PEDIDO NO ENCONTRADO
                # =============================================================
                #
                # El mensaje es deliberadamente genérico.
                #
                # No revelamos si fue incorrecto:
                #
                # - el número;
                # - el RUT.
                # =============================================================

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

                    # =========================================================
                    # RUT GUARDADO
                    # =========================================================

                    rut_pedido = (
                        _normalizar_rut(
                            pedido_encontrado.rut
                        )
                    )


                    # =========================================================
                    # COMPARAR RUT
                    # =========================================================

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
                        # INVITADO VALIDADO CORRECTAMENTE
                        # =====================================================

                        _autorizar_pedido_en_sesion(
                            request,
                            pedido_encontrado.numero,
                        )


                        # =====================================================
                        # REDIRECCIONAR A SEGUIMIENTO
                        # =====================================================

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

        # =====================================================================
        # URL CON NÚMERO DE PEDIDO
        # =====================================================================
        #
        # Ejemplo:
        #
        # /seguimiento/AUD-XXXXXXXX/
        #
        # Aquí un usuario autenticado puede entrar
        # directamente desde "Mis compras".
        # =====================================================================

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


            # =================================================================
            # PEDIDO EXISTENTE
            # =================================================================

            if pedido_encontrado:

                # =============================================================
                # COMPROBAR ACCESO
                # =============================================================
                #
                # _usuario_puede_ver() permite:
                #
                # - staff;
                # - usuario dueño del pedido;
                # - invitado previamente validado por número + RUT.
                # =============================================================

                if _usuario_puede_ver(
                    request,
                    pedido_encontrado,
                ):

                    return renderizar_pedido(
                        pedido_encontrado
                    )


            # =================================================================
            # NO AUTORIZADO
            # =================================================================
            #
            # Si un invitado solamente conoce la URL:
            #
            # NO mostramos el pedido.
            #
            # Precargamos solamente el número para que
            # deba ingresar el RUT de la compra.
            # =================================================================

            form = BuscarPedidoForm(
                initial={
                    "numero": (
                        numero_url
                    ),
                }
            )


        # =====================================================================
        # URL SIN NÚMERO
        # =====================================================================

        else:

            form = (
                BuscarPedidoForm()
            )


    # =========================================================================
    # SEGURIDAD
    # =========================================================================
    #
    # Si llegamos hasta aquí todavía no existe
    # autorización para mostrar un pedido.
    # =========================================================================

    pedido = None
    timeline = []

    pago_confirmado = False

    boleta_disponible = False
    boleta_descarga_url = None


    # =========================================================================
    # RENDER BUSCADOR
    # =========================================================================

    return render(
        request,
        "core/seguimiento_pedido.html",
        {
            "pedido": (
                pedido
            ),

            "form": (
                form
            ),

            "timeline": (
                timeline
            ),

            "pago_confirmado": (
                pago_confirmado
            ),

            "boleta_disponible": (
                boleta_disponible
            ),

            "boleta_descarga_url": (
                boleta_descarga_url
            ),
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
      CREADOS durante las últimas 48 horas.
    - Los pendientes anteriores a 48 horas no se muestran.
    - La carga inicial NO consulta Nubox.
    - Nubox se actualiza mediante polling AJAX después de que
      el HTML ya fue mostrado.
    - ?actualizar_panel=1 continúa siendo una consulta liviana.
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
    # QUERYSET BASE LIVIANO
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
        pedidos.filter(
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
    # ALERTA GLOBAL DE PAGOS PENDIENTES - ÚLTIMAS 48 HORAS
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # Esta consulta es INDEPENDIENTE de:
    #
    # - la bandeja abierta;
    # - el buscador;
    # - la paginación;
    # - haber hecho clic previamente en la alerta.
    #
    # Mientras exista al menos un pedido:
    #
    #     pagado=False
    #     estado_pago=PENDIENTE/INICIADO
    #     creado dentro de las últimas 48 horas
    #
    # la alerta seguirá apareciendo.
    #
    # Después de 48 horas desde pedido.creado desaparecerá
    # automáticamente del panel.
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
    # BANDEJA DE PAGOS PENDIENTES - ÚLTIMAS 48 HORAS
    # =========================================================================
    #
    # Esta sí parte del queryset del panel para conservar:
    #
    # - búsqueda;
    # - productos precargados;
    # - total_unidades.
    #
    # Al entrar desde la alerta sin búsqueda muestra todos
    # los pendientes creados en las últimas 48 horas.
    # =========================================================================

    pendientes_pago = (
        pedidos.filter(
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
    # BOLETAS PENDIENTES
    # =========================================================================
    #
    # Solo se consulta nuestra base de datos.
    # NO se llama Nubox durante el render.
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
    # CONTADORES
    # =========================================================================

    totales = {
        clave: queryset.count()
        for clave, queryset
        in bandejas_querysets.items()
    }


    # =========================================================================
    # PAGOS PENDIENTES - ALERTA GLOBAL 48 HORAS
    # =========================================================================
    #
    # El contador NO depende de filtros visuales.
    #
    # Por eso la alerta no desaparece al:
    #
    # - abrir la bandeja;
    # - volver al tablero;
    # - navegar por otras bandejas.
    # =========================================================================

    total_pendientes_recientes = (
        pendientes_alerta_48h.count()
    )

    total_pendientes_pago = (
        total_pendientes_recientes
    )

    # No mostramos historial de pendientes anteriores a 48 horas.
    total_pendientes_expirados = 0


    # =========================================================================
    # BOLETAS
    # =========================================================================

    total_boletas_pendientes = (
        totales[
            "boletas"
        ]
    )


    # =========================================================================
    # ÚLTIMA ACTUALIZACIÓN
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
    # VERSIÓN DEL TABLERO
    # =========================================================================

    version_panel = "|".join(
        [
            (
                ultima_actualizacion.isoformat()
                if ultima_actualizacion
                else ""
            ),

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

            str(
                total_boletas_pendientes
            ),
        ]
    )


    # =========================================================================
    # CONSULTA LIVIANA DEL FRONTEND
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

                    "boletas": (
                        total_boletas_pendientes
                    ),
                },
            }
        )

        response[
            "Cache-Control"
        ] = "no-store"

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

        "boletas": (
            "Boletas pendientes"
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

        "boletas": (
            "bi-receipt-cutoff"
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
            paginador.get_page(
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
    # Si estamos viendo una bandeja completa no evaluamos
    # también las cuatro columnas del tablero.
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

    return render(
        request,
        "core/gestion/panel_pedidos.html",
        {
            "bandejas": (
                bandejas
            ),

            "version_panel": (
                version_panel
            ),

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

            "busqueda": (
                busqueda
            ),

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

            "total_pendientes_pago": (
                total_pendientes_pago
            ),

            "total_pendientes_recientes": (
                total_pendientes_recientes
            ),

            "total_pendientes_expirados": (
                total_pendientes_expirados
            ),

            "total_boletas_pendientes": (
                total_boletas_pendientes
            ),

            # =============================================================
            # COMPATIBILIDAD
            # =============================================================

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
    Detalle administrativo optimizado de un pedido.

    REGLAS:

    1. PEDIDO PAGADO
       - Puede avanzar de estado operativo.
       - Puede mostrar/descargar la boleta cuando esté disponible.

    2. PEDIDO PENDIENTE DE PAGO
       - Puede abrirse desde el panel administrativo.
       - NO puede avanzar de estado.
       - NO consulta Nubox.

    3. RENDIMIENTO
       - La carga inicial NO llama sincronizar_estado_nubox().
       - No se realizan refresh_from_db() redundantes.
       - Nubox se consulta después mediante el polling AJAX
         de estado_boleta_nubox().
       - Un timeout de Nubox no bloquea la visualización
         inicial del detalle.

    4. El acceso sigue siendo exclusivo para staff.
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
    #
    # Precarga usuario, productos e historial.
    #
    # No realiza llamadas externas.
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
    # IMPORTANTE: NUBOX NO SE SINCRONIZA AQUÍ
    # =========================================================================
    #
    # Antes esta vista llamaba a:
    #
    #     sincronizar_estado_nubox(pedido)
    #
    # durante cada GET.
    #
    # Si Nubox demoraba 20 segundos, el detalle demoraba
    # esos mismos 20 segundos en abrir.
    #
    # Ahora:
    #
    # 1. Django renderiza inmediatamente con los datos de BD.
    # 2. El JavaScript llama a estado_boleta_nubox().
    # 3. Si la boleta cambia, el frontend actualiza/recarga.
    # =========================================================================


    # =========================================================================
    # FORMULARIO
    # =========================================================================

    form = ActualizarEstadoPedidoForm(
        request.POST or None,
        pedido=pedido,
    )


    # =========================================================================
    # POST - ACTUALIZAR ESTADO
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
                or ""
            ).strip()


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


            except Exception as error:

                logger.exception(
                    (
                        "Error inesperado actualizando "
                        "estado operativo del pedido. "
                        "Pedido=%s Estado=%s Error=%s"
                    ),
                    pedido.numero,
                    nuevo_estado,
                    error,
                )

                form.add_error(
                    None,
                    (
                        "No fue posible actualizar el estado "
                        "del pedido. Intenta nuevamente."
                    ),
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
            "pedido": (
                pedido
            ),

            "form": (
                form
            ),

            "timeline": (
                timeline
            ),

            "historial": (
                historial
            ),

            "pago_aprobado": (
                pago_aprobado
            ),

            "es_pago_pendiente": (
                es_pago_pendiente
            ),

            "puede_avanzar_estado": (
                puede_avanzar_estado
            ),
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
