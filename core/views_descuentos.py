# core/views_descuentos.py

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
)
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    Prefetch,
    Q,
    Sum,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from core.forms_descuentos import (
    CodigoGeneralForm,
    ConfiguracionFidelidadForm,
)
from core.models import (
    CodigoDescuento,
    ConfiguracionFidelidad,
    PedidoItem,
    SaldoFidelidad,
    UsoCodigoDescuento,
)


def es_staff(usuario):
    return (
        usuario.is_authenticated
        and usuario.is_staff
    )


@login_required(login_url="core:login")
@user_passes_test(
    es_staff,
    login_url="core:inicio",
)
def gestion_descuentos(request):
    configuracion = ConfiguracionFidelidad.obtener()

    formulario_codigo = CodigoGeneralForm()

    formulario_fidelidad = ConfiguracionFidelidadForm(
        instance=configuracion,
    )

    busqueda = (
        request.GET.get("q", "")
        or ""
    ).strip()

    tipo = (
        request.GET.get("tipo", "")
        or ""
    ).strip()

    estado = (
        request.GET.get("estado", "")
        or ""
    ).strip()

    codigos = (
        CodigoDescuento.objects
        .select_related(
            "usuario_exclusivo",
            "creado_por",
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
            )
        )
        .all()
    )

    if busqueda:
        codigos = codigos.filter(
            Q(codigo__icontains=busqueda)
            | Q(nombre__icontains=busqueda)
            | Q(
                usuario_exclusivo__email__icontains=busqueda
            )
            | Q(
                usuario_exclusivo__username__icontains=busqueda
            )
        )

    if tipo in CodigoDescuento.Tipo.values:
        codigos = codigos.filter(tipo=tipo)

    if estado == "activos":
        codigos = codigos.filter(activo=True)
    elif estado == "inactivos":
        codigos = codigos.filter(activo=False)

    pagina_codigos = Paginator(
        codigos.order_by("-creado"),
        30,
    ).get_page(
        request.GET.get("pagina")
    )

    usos = (
        UsoCodigoDescuento.objects
        .select_related(
            "codigo",
            "pedido",
            "usuario",
        )
        .prefetch_related(
            Prefetch(
                "pedido__items",
                queryset=(
                    PedidoItem.objects
                    .select_related("producto")
                    .order_by("pk")
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
        .order_by("-confirmado_en")
    )

    pagina_usos = Paginator(
        usos,
        20,
    ).get_page(
        request.GET.get("pagina_usos")
    )

    saldos = list(
        SaldoFidelidad.objects
        .select_related("usuario")
        .order_by("-saldo_actual")[:20]
    )

    objetivo = (
        configuracion.monto_objetivo
        or Decimal("1")
    )

    for saldo in saldos:
        saldo.progreso = min(
            int(
                saldo.saldo_actual
                * Decimal("100")
                / objetivo
            ),
            100,
        )

        saldo.faltante = max(
            objetivo - saldo.saldo_actual,
            Decimal("0"),
        )

    usos_confirmados = (
        UsoCodigoDescuento.objects
        .filter(
            estado=(
                UsoCodigoDescuento
                .Estado
                .CONFIRMADO
            )
        )
    )

    estadisticas = {
        "codigos_generales": (
            CodigoDescuento.objects
            .filter(
                tipo=CodigoDescuento.Tipo.GENERAL
            )
            .count()
        ),
        "codigos_fidelidad": (
            CodigoDescuento.objects
            .filter(
                tipo=CodigoDescuento.Tipo.FIDELIDAD
            )
            .count()
        ),
        "codigos_activos": (
            CodigoDescuento.objects
            .filter(activo=True)
            .count()
        ),
        "usos_confirmados": usos_confirmados.count(),
        "descuento_total": (
            usos_confirmados.aggregate(
                total=Sum("descuento_aplicado")
            )["total"]
            or Decimal("0")
        ),
    }

    contexto = {
        "configuracion": configuracion,
        "formulario_codigo": formulario_codigo,
        "formulario_fidelidad": formulario_fidelidad,
        "pagina_codigos": pagina_codigos,
        "pagina_usos": pagina_usos,
        "saldos": saldos,
        "estadisticas": estadisticas,
        "busqueda": busqueda,
        "tipo": tipo,
        "estado": estado,
    }

    return render(
        request,
        "core/gestion/gestion_descuentos.html",
        contexto,
    )


@login_required(login_url="core:login")
@user_passes_test(
    es_staff,
    login_url="core:inicio",
)
@require_POST
def crear_codigo_general(request):
    formulario = CodigoGeneralForm(
        request.POST
    )

    if formulario.is_valid():
        codigo = formulario.save(commit=False)
        codigo.creado_por = request.user
        codigo.save()

        messages.success(
            request,
            f"El código {codigo.codigo} fue creado.",
        )
    else:
        errores = " ".join(
            error
            for lista in formulario.errors.values()
            for error in lista
        )

        messages.error(
            request,
            errores or "No fue posible crear el código.",
        )

    return redirect("core:gestion_descuentos")


@login_required(login_url="core:login")
@user_passes_test(
    es_staff,
    login_url="core:inicio",
)
@require_POST
def guardar_configuracion_fidelidad(request):
    configuracion = ConfiguracionFidelidad.obtener()

    formulario = ConfiguracionFidelidadForm(
        request.POST,
        instance=configuracion,
    )

    if formulario.is_valid():
        configuracion = formulario.save(commit=False)
        configuracion.actualizado_por = request.user
        configuracion.save()

        messages.success(
            request,
            "La configuración de fidelidad fue actualizada.",
        )
    else:
        errores = " ".join(
            error
            for lista in formulario.errors.values()
            for error in lista
        )

        messages.error(
            request,
            errores or (
                "No fue posible guardar la configuración."
            ),
        )

    return redirect("core:gestion_descuentos")


@login_required(login_url="core:login")
@user_passes_test(
    es_staff,
    login_url="core:inicio",
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

    codigo.activo = not codigo.activo

    codigo.save(
        update_fields=[
            "activo",
            "actualizado",
        ]
    )

    estado_texto = (
        "activado"
        if codigo.activo
        else "desactivado"
    )

    messages.success(
        request,
        (
            f"El código {codigo.codigo} "
            f"fue {estado_texto}."
        ),
    )

    return redirect("core:gestion_descuentos")