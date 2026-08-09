# core/views_descuentos.py

from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    Prefetch,
    Q,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from core.forms_descuentos import (
    CodigoGeneralMontoFijoForm,
    CodigoGeneralPorcentajeForm,
    MetaFidelidadMontoFijoForm,
    MetaFidelidadPorcentajeForm,
)
from core.models import (
    CodigoDescuento,
    MetaFidelidad,
    PedidoItem,
    SaldoFidelidad,
    UsoCodigoDescuento,
)


# ============================================================================
# ERRORES DE FORMULARIO
# ============================================================================


def _errores_formulario(formulario):
    errores = []

    for error in formulario.non_field_errors():
        errores.append(
            str(error)
        )

    for campo, lista_errores in formulario.errors.items():
        if campo == "__all__":
            continue

        if campo in formulario.fields:
            nombre = (
                formulario.fields[campo].label
                or campo
            )
        else:
            nombre = campo

        for error in lista_errores:
            errores.append(
                f"{nombre}: {error}"
            )

    return " ".join(
        errores
    )


# ============================================================================
# PROGRESO DE FIDELIDAD
# ============================================================================


def _preparar_saldos_fidelidad():
    """
    Calcula el progreso de cada cliente hacia
    su próxima meta activa de fidelidad.
    """

    metas_activas = list(
        MetaFidelidad.objects
        .filter(
            activa=True,
        )
        .order_by(
            "monto_objetivo",
            "orden",
            "pk",
        )
    )

    saldos = list(
        SaldoFidelidad.objects
        .select_related(
            "usuario"
        )
        .order_by(
            "-total_historico"
        )[:50]
    )

    for saldo in saldos:
        acumulado = (
            saldo.total_historico
            or Decimal("0")
        )

        proxima_meta = None

        for meta in metas_activas:
            if (
                meta.monto_objetivo
                > acumulado
            ):
                proxima_meta = meta
                break

        saldo.proxima_meta = (
            proxima_meta
        )

        # --------------------------------------------------------------
        # TODAS LAS METAS ALCANZADAS
        # --------------------------------------------------------------

        if proxima_meta is None:
            saldo.objetivo_actual = None
            saldo.faltante = Decimal("0")
            saldo.progreso = 100

            continue

        # --------------------------------------------------------------
        # META ACTUAL
        # --------------------------------------------------------------

        objetivo = (
            proxima_meta.monto_objetivo
            or Decimal("1")
        )

        if objetivo <= Decimal("0"):
            objetivo = Decimal("1")

        saldo.objetivo_actual = (
            objetivo
        )

        saldo.faltante = max(
            objetivo - acumulado,
            Decimal("0"),
        )

        saldo.progreso = min(
            max(
                int(
                    acumulado
                    * Decimal("100")
                    / objetivo
                ),
                0,
            ),
            100,
        )

    return saldos


# ============================================================================
# METAS / DESCUENTOS PARA CLIENTES FRECUENTES
# ============================================================================


def _obtener_metas_fidelidad():
    """
    Obtiene los beneficios configurados para clientes frecuentes.

    MetaFidelidad representa la configuración del beneficio.

    CodigoDescuento con tipo FIDELIDAD representa el código
    personal generado posteriormente para un usuario.
    """

    metas = list(
        MetaFidelidad.objects
        .select_related(
            "creado_por",
        )
        .annotate(
            # ----------------------------------------------------------
            # CÓDIGOS PERSONALES GENERADOS DESDE ESTA META
            # ----------------------------------------------------------

            total_generados=Count(
                "codigos_generados",
                distinct=True,
            ),

            # ----------------------------------------------------------
            # CÓDIGOS PERSONALES UTILIZADOS
            # ----------------------------------------------------------

            total_usados=Count(
                "codigos_generados",
                filter=Q(
                    codigos_generados__usos__estado=(
                        UsoCodigoDescuento
                        .Estado
                        .CONFIRMADO
                    )
                ),
                distinct=True,
            ),
        )
        .order_by(
            "monto_objetivo",
            "orden",
            "pk",
        )
    )

    for meta in metas:
        meta.total_pendientes = max(
            (
                meta.total_generados
                - meta.total_usados
            ),
            0,
        )

        # Solo se puede eliminar físicamente
        # si todavía no generó códigos personales.
        meta.puede_eliminar = (
            meta.total_generados == 0
        )

    return metas


# ============================================================================
# CONTEXTO DEL PANEL
# ============================================================================


def construir_contexto_descuentos(
    request,
    formularios_con_error=None,
):
    formularios_con_error = (
        formularios_con_error
        or {}
    )

    # ==================================================================
    # FORMULARIOS
    # ==================================================================

    form_general_porcentaje = (
        formularios_con_error.get(
            "form_general_porcentaje"
        )
    )

    if form_general_porcentaje is None:
        form_general_porcentaje = (
            CodigoGeneralPorcentajeForm()
        )

    form_general_clp = (
        formularios_con_error.get(
            "form_general_clp"
        )
    )

    if form_general_clp is None:
        form_general_clp = (
            CodigoGeneralMontoFijoForm()
        )

    form_fidelidad_porcentaje = (
        formularios_con_error.get(
            "form_fidelidad_porcentaje"
        )
    )

    if form_fidelidad_porcentaje is None:
        form_fidelidad_porcentaje = (
            MetaFidelidadPorcentajeForm()
        )

    form_fidelidad_clp = (
        formularios_con_error.get(
            "form_fidelidad_clp"
        )
    )

    if form_fidelidad_clp is None:
        form_fidelidad_clp = (
            MetaFidelidadMontoFijoForm()
        )

    # ==================================================================
    # FILTROS
    # ==================================================================

    busqueda = (
        request.GET.get(
            "q",
            "",
        )
        or ""
    ).strip()

    modalidad = (
        request.GET.get(
            "modalidad",
            "",
        )
        or ""
    ).strip()

    estado = (
        request.GET.get(
            "estado",
            "todos",
        )
        or "todos"
    ).strip()

    estados_validos = {
        "todos",
        "activos",
        "desactivados",
        "consumidos",
    }

    if estado not in estados_validos:
        estado = "todos"

    # ==================================================================
    # ELEMENTOS OCULTOS POR EL ADMINISTRADOR
    #
    # IMPORTANTE:
    # Esto NO modifica la base de datos.
    # Se guarda solamente en request.session.
    # ==================================================================

    codigos_ocultos_ids = (
        request.session.get(
            "codigos_descuento_ocultos",
            [],
        )
        or []
    )

    metas_ocultas_ids = (
        request.session.get(
            "metas_fidelidad_ocultas",
            [],
        )
        or []
    )

    # Convertimos todo a enteros válidos.
    codigos_ocultos_ids_limpios = []

    for codigo_id in codigos_ocultos_ids:
        try:
            codigo_id = int(
                codigo_id
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if codigo_id not in codigos_ocultos_ids_limpios:
            codigos_ocultos_ids_limpios.append(
                codigo_id
            )

    metas_ocultas_ids_limpios = []

    for meta_id in metas_ocultas_ids:
        try:
            meta_id = int(
                meta_id
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if meta_id not in metas_ocultas_ids_limpios:
            metas_ocultas_ids_limpios.append(
                meta_id
            )

    codigos_ocultos_ids = (
        codigos_ocultos_ids_limpios
    )

    metas_ocultas_ids = (
        metas_ocultas_ids_limpios
    )

    # ==================================================================
    # REGLA:
    #
    # Un elemento ACTIVO nunca puede permanecer oculto.
    #
    # Si estaba oculto y luego el administrador lo activa,
    # automáticamente vuelve al listado visible.
    # ==================================================================

    codigos_activos_que_estaban_ocultos = set(
        CodigoDescuento.objects
        .filter(
            pk__in=codigos_ocultos_ids,
            activo=True,
        )
        .values_list(
            "pk",
            flat=True,
        )
    )

    if codigos_activos_que_estaban_ocultos:
        codigos_ocultos_ids = [
            codigo_id
            for codigo_id in codigos_ocultos_ids
            if codigo_id
            not in codigos_activos_que_estaban_ocultos
        ]

    metas_activas_que_estaban_ocultas = set(
        MetaFidelidad.objects
        .filter(
            pk__in=metas_ocultas_ids,
            activa=True,
        )
        .values_list(
            "pk",
            flat=True,
        )
    )

    if metas_activas_que_estaban_ocultas:
        metas_ocultas_ids = [
            meta_id
            for meta_id in metas_ocultas_ids
            if meta_id
            not in metas_activas_que_estaban_ocultas
        ]

    # Guardamos la limpieza de sesión.
    request.session[
        "codigos_descuento_ocultos"
    ] = codigos_ocultos_ids

    request.session[
        "metas_fidelidad_ocultas"
    ] = metas_ocultas_ids

    request.session.modified = True

    # ==================================================================
    # CÓDIGOS GENERALES - QUERYSET BASE
    # ==================================================================

    codigos_generales = (
        CodigoDescuento.objects
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .GENERAL
            ),
        )
        .select_related(
            "creado_por",
        )
        .annotate(
            # ----------------------------------------------------------
            # USOS CONFIRMADOS
            # ----------------------------------------------------------

            total_usos=Count(
                "usos",
                filter=Q(
                    usos__estado=(
                        UsoCodigoDescuento
                        .Estado
                        .CONFIRMADO
                    )
                ),
                distinct=True,
            ),

            # ----------------------------------------------------------
            # CLIENTES DISTINTOS QUE LO USARON
            # ----------------------------------------------------------

            clientes_usaron=Count(
                "usos__cliente_clave",
                filter=Q(
                    usos__estado=(
                        UsoCodigoDescuento
                        .Estado
                        .CONFIRMADO
                    )
                ),
                distinct=True,
            ),

            # ----------------------------------------------------------
            # CUALQUIER REGISTRO DE USO
            # ----------------------------------------------------------

            total_registros_uso=Count(
                "usos",
                distinct=True,
            ),
        )
    )

    # ==================================================================
    # BÚSQUEDA CÓDIGOS GENERALES
    # ==================================================================

    if busqueda:
        codigos_generales = (
            codigos_generales.filter(
                Q(
                    codigo__icontains=busqueda
                )
                |
                Q(
                    nombre__icontains=busqueda
                )
                |
                Q(
                    descripcion__icontains=busqueda
                )
            )
        )

    # ==================================================================
    # MODALIDAD CÓDIGOS GENERALES
    # ==================================================================

    if (
        modalidad
        in CodigoDescuento.Modalidad.values
    ):
        codigos_generales = (
            codigos_generales.filter(
                modalidad=modalidad,
            )
        )

    # ==================================================================
    # SEPARAR GENERALES VISIBLES / OCULTOS
    #
    # Solo los DESACTIVADOS pueden aparecer en ocultos.
    # ==================================================================

    codigos_generales_ocultos = (
        codigos_generales
        .filter(
            pk__in=codigos_ocultos_ids,
            activo=False,
        )
        .order_by(
            "-creado"
        )
    )

    codigos_generales_visibles = (
        codigos_generales
        .exclude(
            pk__in=codigos_ocultos_ids,
        )
    )

    # ==================================================================
    # FILTRAR ESTADO DE LOS VISIBLES
    # ==================================================================

    if estado == "activos":
        codigos_generales_visibles = (
            codigos_generales_visibles
            .filter(
                activo=True,
            )
        )

    elif estado == "desactivados":
        codigos_generales_visibles = (
            codigos_generales_visibles
            .filter(
                activo=False,
            )
        )

    elif estado == "consumidos":
        # Los códigos generales no son
        # consumidos globalmente.
        codigos_generales_visibles = (
            codigos_generales_visibles.none()
        )

    codigos_generales_visibles = (
        codigos_generales_visibles
        .order_by(
            "-creado"
        )
    )

    # ==================================================================
    # PAGINACIÓN GENERALES VISIBLES
    # ==================================================================

    pagina_codigos_generales = (
        Paginator(
            codigos_generales_visibles,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_generales"
            )
        )
    )

    # ==================================================================
    # PAGINACIÓN GENERALES OCULTOS
    # ==================================================================

    pagina_codigos_generales_ocultos = (
        Paginator(
            codigos_generales_ocultos,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_generales_ocultos"
            )
        )
    )

    # ==================================================================
    # DESCUENTOS / METAS DE FIDELIDAD
    # ==================================================================

    metas_fidelidad = (
        _obtener_metas_fidelidad()
    )

    # ==================================================================
    # FILTRAR METAS POR BÚSQUEDA Y MODALIDAD
    # ==================================================================

    metas_filtradas = []

    for meta in metas_fidelidad:

        # --------------------------------------------------------------
        # BÚSQUEDA
        # --------------------------------------------------------------

        if busqueda:
            texto_busqueda = (
                busqueda.casefold()
            )

            nombre_meta = (
                meta.nombre
                or ""
            ).casefold()

            prefijo_meta = (
                meta.prefijo_codigo
                or ""
            ).casefold()

            if (
                texto_busqueda
                not in nombre_meta
                and texto_busqueda
                not in prefijo_meta
            ):
                continue

        # --------------------------------------------------------------
        # MODALIDAD
        # --------------------------------------------------------------

        if (
            modalidad
            in MetaFidelidad.Modalidad.values
            and meta.modalidad != modalidad
        ):
            continue

        metas_filtradas.append(
            meta
        )

    # ==================================================================
    # SEPARAR METAS VISIBLES / OCULTAS
    #
    # Una meta activa nunca permanece oculta.
    # ==================================================================

    metas_fidelidad_visibles = []

    metas_fidelidad_ocultas = []

    for meta in metas_filtradas:

        if (
            meta.pk in metas_ocultas_ids
            and not meta.activa
        ):
            metas_fidelidad_ocultas.append(
                meta
            )
        else:
            metas_fidelidad_visibles.append(
                meta
            )

    # ==================================================================
    # FILTRAR ESTADO DE METAS VISIBLES
    # ==================================================================

    if estado == "activos":
        metas_fidelidad_visibles = [
            meta
            for meta in metas_fidelidad_visibles
            if meta.activa
        ]

    elif estado == "desactivados":
        metas_fidelidad_visibles = [
            meta
            for meta in metas_fidelidad_visibles
            if not meta.activa
        ]

    elif estado == "consumidos":
        metas_fidelidad_visibles = []

    # ==================================================================
    # CÓDIGOS PERSONALES DE FIDELIDAD - QUERYSET BASE
    # ==================================================================

    codigos_fidelidad = (
        CodigoDescuento.objects
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),
        )
        .select_related(
            "usuario_exclusivo",
            "creado_por",
            "meta_fidelidad",
        )
        .annotate(
            total_usos=Count(
                "usos",
                filter=Q(
                    usos__estado=(
                        UsoCodigoDescuento
                        .Estado
                        .CONFIRMADO
                    )
                ),
                distinct=True,
            ),

            total_registros_uso=Count(
                "usos",
                distinct=True,
            ),
        )
    )

    # ==================================================================
    # BÚSQUEDA CÓDIGOS PERSONALES
    # ==================================================================

    if busqueda:
        codigos_fidelidad = (
            codigos_fidelidad.filter(
                Q(
                    codigo__icontains=busqueda
                )
                |
                Q(
                    nombre__icontains=busqueda
                )
                |
                Q(
                    usuario_exclusivo__email__icontains=(
                        busqueda
                    )
                )
                |
                Q(
                    usuario_exclusivo__username__icontains=(
                        busqueda
                    )
                )
                |
                Q(
                    meta_fidelidad__nombre__icontains=(
                        busqueda
                    )
                )
            )
        )

    # ==================================================================
    # MODALIDAD CÓDIGOS PERSONALES
    # ==================================================================

    if (
        modalidad
        in CodigoDescuento.Modalidad.values
    ):
        codigos_fidelidad = (
            codigos_fidelidad.filter(
                modalidad=modalidad,
            )
        )

    # ==================================================================
    # SEPARAR CÓDIGOS PERSONALES VISIBLES / OCULTOS
    # ==================================================================

    codigos_fidelidad_ocultos = (
        codigos_fidelidad
        .filter(
            pk__in=codigos_ocultos_ids,
            activo=False,
        )
        .order_by(
            "-creado"
        )
    )

    codigos_fidelidad_visibles = (
        codigos_fidelidad
        .exclude(
            pk__in=codigos_ocultos_ids,
        )
    )

    # ==================================================================
    # FILTRO DE ESTADO CÓDIGOS PERSONALES VISIBLES
    # ==================================================================

    if estado == "activos":
        codigos_fidelidad_visibles = (
            codigos_fidelidad_visibles
            .filter(
                activo=True,
                consumido=False,
            )
        )

    elif estado == "desactivados":
        codigos_fidelidad_visibles = (
            codigos_fidelidad_visibles
            .filter(
                activo=False,
                consumido=False,
            )
        )

    elif estado == "consumidos":
        codigos_fidelidad_visibles = (
            codigos_fidelidad_visibles
            .filter(
                consumido=True,
            )
        )

    codigos_fidelidad_visibles = (
        codigos_fidelidad_visibles
        .order_by(
            "-creado"
        )
    )

    # ==================================================================
    # PAGINACIÓN CÓDIGOS PERSONALES VISIBLES
    # ==================================================================

    pagina_codigos_fidelidad = (
        Paginator(
            codigos_fidelidad_visibles,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_fidelidad"
            )
        )
    )

    # ==================================================================
    # PAGINACIÓN CÓDIGOS PERSONALES OCULTOS
    # ==================================================================

    pagina_codigos_fidelidad_ocultos = (
        Paginator(
            codigos_fidelidad_ocultos,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_fidelidad_ocultos"
            )
        )
    )

    # ==================================================================
    # PROGRESO DE FIDELIDAD
    # ==================================================================

    saldos = (
        _preparar_saldos_fidelidad()
    )

    # ==================================================================
    # HISTORIAL DE USOS CONFIRMADOS
    # ==================================================================

    usos = (
        UsoCodigoDescuento.objects
        .select_related(
            "codigo",
            "codigo__usuario_exclusivo",
            "codigo__meta_fidelidad",
            "pedido",
            "usuario",
        )
        .prefetch_related(
            Prefetch(
                "pedido__items",
                queryset=(
                    PedidoItem.objects
                    .select_related(
                        "producto"
                    )
                    .order_by(
                        "pk"
                    )
                ),
            )
        )
        .filter(
            estado=(
                UsoCodigoDescuento
                .Estado
                .CONFIRMADO
            )
        )
        .order_by(
            "-confirmado_en",
            "-reservado_en",
        )
    )

    pagina_usos = (
        Paginator(
            usos,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_usos"
            )
        )
    )

    # ==================================================================
    # CONTEXTO FINAL
    # ==================================================================

    contexto = {
        # --------------------------------------------------------------
        # FORMULARIOS
        # --------------------------------------------------------------

        "form_general_porcentaje": (
            form_general_porcentaje
        ),

        "form_general_clp": (
            form_general_clp
        ),

        "form_fidelidad_porcentaje": (
            form_fidelidad_porcentaje
        ),

        "form_fidelidad_clp": (
            form_fidelidad_clp
        ),

        # --------------------------------------------------------------
        # CÓDIGOS GENERALES VISIBLES
        # --------------------------------------------------------------

        "pagina_codigos_generales": (
            pagina_codigos_generales
        ),

        # --------------------------------------------------------------
        # CÓDIGOS GENERALES OCULTOS
        # --------------------------------------------------------------

        "pagina_codigos_generales_ocultos": (
            pagina_codigos_generales_ocultos
        ),

        # --------------------------------------------------------------
        # TODAS LAS METAS
        # Compatibilidad con templates anteriores.
        # --------------------------------------------------------------

        "metas_fidelidad": (
            metas_fidelidad
        ),

        # --------------------------------------------------------------
        # METAS VISIBLES
        # --------------------------------------------------------------

        "metas_fidelidad_visibles": (
            metas_fidelidad_visibles
        ),

        # --------------------------------------------------------------
        # METAS OCULTAS
        # --------------------------------------------------------------

        "metas_fidelidad_ocultas": (
            metas_fidelidad_ocultas
        ),

        # --------------------------------------------------------------
        # CÓDIGOS PERSONALES VISIBLES
        # --------------------------------------------------------------

        "pagina_codigos_fidelidad": (
            pagina_codigos_fidelidad
        ),

        # --------------------------------------------------------------
        # CÓDIGOS PERSONALES OCULTOS
        # --------------------------------------------------------------

        "pagina_codigos_fidelidad_ocultos": (
            pagina_codigos_fidelidad_ocultos
        ),

        # --------------------------------------------------------------
        # PROGRESO DE CLIENTES
        # --------------------------------------------------------------

        "saldos": (
            saldos
        ),

        # --------------------------------------------------------------
        # HISTORIAL
        # --------------------------------------------------------------

        "pagina_usos": (
            pagina_usos
        ),

        # --------------------------------------------------------------
        # FILTROS
        # --------------------------------------------------------------

        "busqueda": (
            busqueda
        ),

        "modalidad": (
            modalidad
        ),

        "estado": (
            estado
        ),

        # --------------------------------------------------------------
        # IDs OCULTOS
        # Útiles si necesitas comprobarlos en template.
        # --------------------------------------------------------------

        "codigos_ocultos_ids": (
            codigos_ocultos_ids
        ),

        "metas_ocultas_ids": (
            metas_ocultas_ids
        ),
    }

    return contexto

# ============================================================================
# PANEL PRINCIPAL
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_GET
def gestion_descuentos(
    request,
):
    contexto = (
        construir_contexto_descuentos(
            request=request,
        )
    )

    return render(
        request,
        "core/gestion/gestion_descuentos.html",
        contexto,
    )


# ============================================================================
# CREAR CÓDIGOS GENERALES
# ============================================================================


def _crear_codigo_descuento(
    *,
    request,
    formulario_clase,
    formulario_contexto,
):
    formulario = (
        formulario_clase(
            request.POST
        )
    )

    if formulario.is_valid():
        codigo = formulario.save(
            commit=False
        )

        codigo.creado_por = (
            request.user
        )

        codigo.save()

        messages.success(
            request,
            (
                f"El código {codigo.codigo} "
                "fue creado correctamente."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    messages.error(
        request,
        (
            _errores_formulario(
                formulario
            )
            or (
                "No fue posible crear "
                "el código."
            )
        ),
    )

    contexto = (
        construir_contexto_descuentos(
            request=request,
            formularios_con_error={
                formulario_contexto: (
                    formulario
                ),
            },
        )
    )

    return render(
        request,
        "core/gestion/gestion_descuentos.html",
        contexto,
        status=400,
    )


# ============================================================================
# CREAR GENERAL PORCENTUAL
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def crear_codigo_general_porcentaje(
    request,
):
    return _crear_codigo_descuento(
        request=request,
        formulario_clase=(
            CodigoGeneralPorcentajeForm
        ),
        formulario_contexto=(
            "form_general_porcentaje"
        ),
    )


# ============================================================================
# CREAR GENERAL CLP
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def crear_codigo_general_clp(
    request,
):
    return _crear_codigo_descuento(
        request=request,
        formulario_clase=(
            CodigoGeneralMontoFijoForm
        ),
        formulario_contexto=(
            "form_general_clp"
        ),
    )


# ============================================================================
# CREAR METAS / BENEFICIOS DE FIDELIDAD
# ============================================================================


def _crear_meta_fidelidad(
    *,
    request,
    formulario_clase,
    formulario_contexto,
):
    formulario = (
        formulario_clase(
            request.POST
        )
    )

    if formulario.is_valid():
        meta = formulario.save(
            commit=False
        )

        meta.creado_por = (
            request.user
        )

        meta.save()

        messages.success(
            request,
            (
                f"El beneficio «{meta.nombre}» "
                "para clientes frecuentes "
                "fue creado correctamente."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    messages.error(
        request,
        (
            _errores_formulario(
                formulario
            )
            or (
                "No fue posible crear "
                "el beneficio de fidelidad."
            )
        ),
    )

    contexto = (
        construir_contexto_descuentos(
            request=request,
            formularios_con_error={
                formulario_contexto: (
                    formulario
                ),
            },
        )
    )

    return render(
        request,
        "core/gestion/gestion_descuentos.html",
        contexto,
        status=400,
    )


# ============================================================================
# CREAR META FIDELIDAD PORCENTUAL
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def crear_meta_fidelidad_porcentaje(
    request,
):
    return _crear_meta_fidelidad(
        request=request,
        formulario_clase=(
            MetaFidelidadPorcentajeForm
        ),
        formulario_contexto=(
            "form_fidelidad_porcentaje"
        ),
    )


# ============================================================================
# CREAR META FIDELIDAD CLP
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def crear_meta_fidelidad_clp(
    request,
):
    return _crear_meta_fidelidad(
        request=request,
        formulario_clase=(
            MetaFidelidadMontoFijoForm
        ),
        formulario_contexto=(
            "form_fidelidad_clp"
        ),
    )


# ============================================================================
# OCULTAR / MOSTRAR CÓDIGO
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def alternar_codigo_descuento(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoDescuento,
        pk=codigo_id,
    )

    nuevo_estado = (
        not codigo.activo
    )

    CodigoDescuento.objects.filter(
        pk=codigo.pk,
    ).update(
        activo=nuevo_estado,
        actualizado=timezone.now(),
    )

    if nuevo_estado:
        messages.success(
            request,
            (
                f"El código {codigo.codigo} "
                "fue activado y volverá a mostrarse."
            ),
        )

    else:
        messages.success(
            request,
            (
                f"El código {codigo.codigo} "
                "fue ocultado y desactivado "
                "para nuevas compras."
            ),
        )

    return redirect(
        "core:gestion_descuentos"
    )


# ============================================================================
# ELIMINAR CÓDIGO
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def eliminar_codigo_descuento(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoDescuento,
        pk=codigo_id,
    )

    codigo_texto = (
        codigo.codigo
    )

    # ------------------------------------------------------------------
    # SI TIENE HISTORIAL, NO SE ELIMINA
    # ------------------------------------------------------------------

    if codigo.usos.exists():
        messages.error(
            request,
            (
                f"El código {codigo_texto} no puede "
                "eliminarse porque posee historial "
                "de uso. Puedes ocultarlo."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    # ------------------------------------------------------------------
    # SI ESTÁ ASOCIADO A UN PEDIDO, TAMPOCO LO BORRAMOS
    # ------------------------------------------------------------------

    if codigo.pedidos.exists():
        messages.error(
            request,
            (
                f"El código {codigo_texto} está "
                "asociado a pedidos y no puede "
                "eliminarse. Puedes ocultarlo."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    codigo.delete()

    messages.success(
        request,
        (
            f"El código {codigo_texto} "
            "fue eliminado correctamente."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )


# ============================================================================
# OCULTAR / MOSTRAR BENEFICIO DE FIDELIDAD
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def alternar_meta_fidelidad(
    request,
    meta_id,
):
    meta = get_object_or_404(
        MetaFidelidad,
        pk=meta_id,
    )

    nuevo_estado = (
        not meta.activa
    )

    MetaFidelidad.objects.filter(
        pk=meta.pk,
    ).update(
        activa=nuevo_estado,
        actualizado=timezone.now(),
    )

    if nuevo_estado:
        messages.success(
            request,
            (
                f"El beneficio «{meta.nombre}» "
                "fue activado nuevamente."
            ),
        )

    else:
        messages.success(
            request,
            (
                f"El beneficio «{meta.nombre}» "
                "fue ocultado. No generará nuevos "
                "premios mientras permanezca inactivo."
            ),
        )

    return redirect(
        "core:gestion_descuentos"
    )


# ============================================================================
# ELIMINAR BENEFICIO DE FIDELIDAD
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def eliminar_meta_fidelidad(
    request,
    meta_id,
):
    """
    Una meta solo puede eliminarse si todavía
    no generó ningún código personal.

    Si ya generó códigos debe ocultarse/desactivarse
    para conservar el historial.
    """

    meta = get_object_or_404(
        MetaFidelidad,
        pk=meta_id,
    )

    nombre_meta = (
        meta.nombre
    )

    if meta.codigos_generados.exists():
        messages.error(
            request,
            (
                f"El beneficio «{nombre_meta}» no puede "
                "eliminarse porque ya generó códigos "
                "personales. Puedes ocultarlo para evitar "
                "que genere nuevos premios."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    meta.delete()

    messages.success(
        request,
        (
            f"El beneficio «{nombre_meta}» "
            "fue eliminado correctamente."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )






# ============================================================================
# OCULTAR CÓDIGO DESACTIVADO DEL LISTADO PRINCIPAL
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def ocultar_codigo_descuento(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoDescuento,
        pk=codigo_id,
    )

    # Solo códigos desactivados pueden ocultarse.
    if codigo.activo:
        messages.error(
            request,
            (
                f"Primero debes desactivar el código "
                f"{codigo.codigo} antes de ocultarlo."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    ocultos = request.session.get(
        "codigos_descuento_ocultos",
        [],
    )

    if codigo.pk not in ocultos:
        ocultos.append(
            codigo.pk
        )

    request.session[
        "codigos_descuento_ocultos"
    ] = ocultos

    request.session.modified = True

    messages.success(
        request,
        (
            f"El código {codigo.codigo} fue movido "
            "a la sección de códigos ocultos."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )


# ============================================================================
# MOSTRAR NUEVAMENTE CÓDIGO OCULTO
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def mostrar_codigo_descuento(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoDescuento,
        pk=codigo_id,
    )

    ocultos = request.session.get(
        "codigos_descuento_ocultos",
        [],
    )

    ocultos = [
        pk
        for pk in ocultos
        if pk != codigo.pk
    ]

    request.session[
        "codigos_descuento_ocultos"
    ] = ocultos

    request.session.modified = True

    messages.success(
        request,
        (
            f"El código {codigo.codigo} volvió "
            "al listado principal."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )






# ============================================================================
# OCULTAR META DE FIDELIDAD
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def ocultar_meta_fidelidad(
    request,
    meta_id,
):
    meta = get_object_or_404(
        MetaFidelidad,
        pk=meta_id,
    )

    if meta.activa:
        messages.error(
            request,
            (
                f"Primero debes desactivar el beneficio "
                f"«{meta.nombre}» antes de ocultarlo."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    ocultas = request.session.get(
        "metas_fidelidad_ocultas",
        [],
    )

    if meta.pk not in ocultas:
        ocultas.append(
            meta.pk
        )

    request.session[
        "metas_fidelidad_ocultas"
    ] = ocultas

    request.session.modified = True

    messages.success(
        request,
        (
            f"El beneficio «{meta.nombre}» fue movido "
            "a la sección de beneficios ocultos."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )


# ============================================================================
# MOSTRAR META DE FIDELIDAD
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def mostrar_meta_fidelidad(
    request,
    meta_id,
):
    meta = get_object_or_404(
        MetaFidelidad,
        pk=meta_id,
    )

    ocultas = request.session.get(
        "metas_fidelidad_ocultas",
        [],
    )

    ocultas = [
        pk
        for pk in ocultas
        if pk != meta.pk
    ]

    request.session[
        "metas_fidelidad_ocultas"
    ] = ocultas

    request.session.modified = True

    messages.success(
        request,
        (
            f"El beneficio «{meta.nombre}» volvió "
            "al listado principal."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )