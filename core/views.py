from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Case, DecimalField, F, Q, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView
from django.views.decorators.csrf import ensure_csrf_cookie
from .forms import *
from .models import *
from django.db import OperationalError
from .permisos import es_administrador_productos
from core.services.blue_express import *
import json
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, When
from core.services.favoritos import obtener_ids_favoritos
from decimal import Decimal
from django.shortcuts import get_object_or_404, render
from .services.mercadopago import *
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from .services.pagos import *
from .models import Producto
import json
from core.services.descuentos import *
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
import json
from decimal import Decimal, InvalidOperation
import requests
from django.http import HttpResponse, JsonResponse
from core.services.confirmacion_pago import *
from core.services.mercadopago import *
from core.pagos.security import validar_firma_mercado_pago
import logging
from core.services.carrito_persistente import *
from django.contrib.auth import (
    logout as django_logout,
)
from core.services.descuentos import (
    DescuentoError,
    liberar_uso_codigo_pedido,
    obtener_codigos_disponibles,
    resolver_descuento,
)
from core.services.checkout import *


from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from core.services.pagos import *
from core.services.favoritos import *
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.core.paginator import Paginator
from django.db import (
    IntegrityError,
    transaction,
)
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
from django.utils import timezone
from django.views.decorators.http import (
    require_POST,
)

from core.forms_descuentos import *

from core.models import *

from core.services.webpay import (
    obtener_transaccion_webpay,
)


TIPOS_CODIGO_VALIDOS = {
    valor
    for valor, _ in CodigoDescuento.Tipo.choices
}

ESTADOS_FILTRO_VALIDOS = {
    "activos",
    "inactivos",
    "consumidos",
}
logger = logging.getLogger(__name__)



class AdministradorProductosMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return es_administrador_productos(self.request.user)


def inicio(request):
    return render(request, "core/inicio.html")

@ensure_csrf_cookie
def productos(request):
    productos_queryset = (
        Producto.objects
        .filter(
            activo=True,
            categoria__activa=True,
        )
        .select_related("categoria")
    )

    categorias = Categoria.objects.filter(
        activa=True,
        productos__activo=True,
    ).distinct()

    busqueda = request.GET.get("q", "").strip()
    categoria_slug = request.GET.get("categoria", "").strip()
    orden = request.GET.get("orden", "destacados")

    if busqueda:
        productos_queryset = productos_queryset.filter(
            Q(nombre__icontains=busqueda)
            | Q(descripcion_corta__icontains=busqueda)
            | Q(descripcion__icontains=busqueda)
            | Q(caracteristica_1__icontains=busqueda)
            | Q(caracteristica_2__icontains=busqueda)
            | Q(caracteristica_3__icontains=busqueda)
        )

    if categoria_slug:
        productos_queryset = productos_queryset.filter(
            categoria__slug=categoria_slug
        )

    productos_queryset = productos_queryset.annotate(
        precio_orden=Case(
            When(
                precio_oferta__isnull=False,
                precio_oferta__lt=F("precio"),
                then=F("precio_oferta"),
            ),
            default=F("precio"),
            output_field=DecimalField(
                max_digits=12,
                decimal_places=0,
            ),
        )
    )

    if orden == "menor":
        productos_queryset = productos_queryset.order_by(
            "precio_orden"
        )
    elif orden == "mayor":
        productos_queryset = productos_queryset.order_by(
            "-precio_orden"
        )
    elif orden == "nombre":
        productos_queryset = productos_queryset.order_by("nombre")
    else:
        productos_queryset = productos_queryset.order_by(
            "-destacado",
            "-creado",
        )

    contexto = {
        "productos": productos_queryset,
        "categorias": categorias,
        "cantidad_productos": productos_queryset.count(),
        "busqueda": busqueda,
        "categoria_actual": categoria_slug,
        "orden_actual": orden,
        "puede_administrar": es_administrador_productos(
            request.user
        ),
    }

    return render(
        request,
        "core/productos.html",
        contexto,
    )

@ensure_csrf_cookie
def producto_detalle(request, slug):
    producto = get_object_or_404(
        Producto.objects
        .select_related("categoria")
        .prefetch_related("imagenes"),
        slug=slug,
    )

    if (
        not producto.activo
        and not es_administrador_productos(
            request.user
        )
    ):
        return redirect(
            "core:productos"
        )

    contexto = {
        "producto": producto,
        "puede_administrar": (
            es_administrador_productos(
                request.user
            )
        ),
    }

    return render(
        request,
        "core/producto_detalle.html",
        contexto,
    )

class ProductoCrearView(
    AdministradorProductosMixin,
    CreateView,
):
    model = Producto
    form_class = ProductoForm
    template_name = "core/producto_formulario.html"
    success_url = reverse_lazy("core:productos")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            context["imagenes_formset"] = ProductoImagenFormSet(
                self.request.POST,
                self.request.FILES,
            )
        else:
            context["imagenes_formset"] = ProductoImagenFormSet()

        return context

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()

        imagenes_formset = context[
            "imagenes_formset"
        ]

        if not imagenes_formset.is_valid():
            return self.form_invalid(form)

        self.object = form.save()

        imagenes_formset.instance = self.object
        imagenes_formset.save()

        messages.success(
            self.request,
            "Producto creado correctamente.",
        )

        return HttpResponseRedirect(
            self.get_success_url()
        )


class ProductoEditarView(
    AdministradorProductosMixin,
    UpdateView,
):
    model = Producto
    form_class = ProductoForm
    template_name = "core/producto_formulario.html"
    success_url = reverse_lazy("core:productos")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            context["imagenes_formset"] = ProductoImagenFormSet(
                self.request.POST,
                self.request.FILES,
                instance=self.object,
            )
        else:
            context["imagenes_formset"] = ProductoImagenFormSet(
                instance=self.object,
            )

        return context

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()

        imagenes_formset = context[
            "imagenes_formset"
        ]

        if not imagenes_formset.is_valid():
            return self.form_invalid(form)

        self.object = form.save()

        imagenes_formset.instance = self.object
        imagenes_formset.save()

        messages.success(
            self.request,
            "Producto actualizado correctamente.",
        )

        return HttpResponseRedirect(
            self.get_success_url()
        )




    
class ProductoEliminarView(
    AdministradorProductosMixin,
    DeleteView,
):
    model = Producto
    template_name = "core/producto_confirmar_eliminar.html"
    success_url = reverse_lazy("core:productos")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Producto eliminado correctamente.",
        )

        return super().form_valid(form)


class CategoriaCrearView(
    AdministradorProductosMixin,
    CreateView,
):
    model = Categoria
    form_class = CategoriaForm
    template_name = "core/categoria_formulario.html"
    success_url = reverse_lazy("core:productos")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Categoría creada correctamente.",
        )

        return super().form_valid(form)





def _obtener_carrito(request):
    return obtener_carrito(
        request
    )


def _guardar_carrito(
    request,
    carrito,
):
    return guardar_carrito(
        request,
        carrito,
    )



def productos(request):
    productos_queryset = Producto.objects.select_related(
        "categoria"
    ).filter(
        activo=True,
        categoria__activa=True,
    )

    categorias = Categoria.objects.filter(
        activa=True
    ).order_by(
        "orden",
        "nombre",
    )

    busqueda = request.GET.get("q", "").strip()
    categoria_slug = request.GET.get(
        "categoria",
        "",
    ).strip()

    orden = request.GET.get(
        "orden",
        "destacados",
    )

    if busqueda:
        productos_queryset = productos_queryset.filter(
            Q(nombre__icontains=busqueda)
            | Q(descripcion_corta__icontains=busqueda)
            | Q(descripcion__icontains=busqueda)
            | Q(caracteristica_1__icontains=busqueda)
            | Q(caracteristica_2__icontains=busqueda)
            | Q(caracteristica_3__icontains=busqueda)
        )

    if categoria_slug:
        productos_queryset = productos_queryset.filter(
            categoria__slug=categoria_slug
        )

    productos_queryset = productos_queryset.annotate(
        precio_orden=Case(
            When(
                precio_oferta__isnull=False,
                precio_oferta__lt=F("precio"),
                then=F("precio_oferta"),
            ),
            default=F("precio"),
            output_field=DecimalField(
                max_digits=12,
                decimal_places=0,
            ),
        )
    )

    if orden == "menor":
        productos_queryset = productos_queryset.order_by(
            "precio_orden"
        )

    elif orden == "mayor":
        productos_queryset = productos_queryset.order_by(
            "-precio_orden"
        )

    elif orden == "nombre":
        productos_queryset = productos_queryset.order_by(
            "nombre"
        )

    else:
        productos_queryset = productos_queryset.order_by(
            "-destacado",
            "-creado",
        )

    context = {
        "productos": productos_queryset,
        "categorias": categorias,
        "cantidad_productos": productos_queryset.count(),
        "busqueda": busqueda,
        "categoria_actual": categoria_slug,
        "orden_actual": orden,
        "puede_administrar": es_administrador_productos(
            request.user
        ),
    }

    return render(
        request,
        "core/productos.html",
        context,
    )


def categorias(request):
    return render(request, "core/categorias.html")





# ======================================================================
# HELPERS DE FIDELIDAD
# ======================================================================


def _generar_codigo_fidelidad_unico(
    usuario,
    meta,
):
    """
    Genera un código único para una recompensa de fidelidad.

    Ejemplo:
        AUDEXFIEL-12-3-A1B2C3D4

    donde:
        12 = ID del usuario
        3  = ID de la meta
    """

    prefijo = (
        meta.prefijo_codigo
        or "AUDEXFIEL"
    ).strip().upper()

    while True:

        token = (
            uuid.uuid4()
            .hex[:8]
            .upper()
        )

        codigo = (
            f"{prefijo}-"
            f"{usuario.pk}-"
            f"{meta.pk}-"
            f"{token}"
        )

        # El modelo admite máximo 64 caracteres.
        codigo = codigo[:64]

        existe = (
            CodigoDescuento.objects
            .filter(
                codigo=codigo,
            )
            .exists()
        )

        if not existe:
            return codigo


def _obtener_total_compras_aprobadas(
    usuario,
):
    """
    Calcula el acumulado REAL del usuario para fidelidad.

    Solamente contabiliza:

    - Pedidos pertenecientes al usuario.
    - Pago marcado como pagado.
    - Estado de pago APROBADO.
    - Mercado Pago o Webpay.

    No contabiliza:

    - Transferencias.
    - Pagos pendientes.
    - Pagos iniciados.
    - Pagos rechazados.
    - Pagos cancelados.
    - Pagos reembolsados.
    - Pagos en revisión.
    """

    resultado = (
        Pedido.objects
        .filter(
            usuario=usuario,
            pagado=True,
            estado_pago=(
                Pedido
                .EstadoPago
                .APROBADO
            ),
            metodo_pago__in=[
                Pedido
                .MetodoPago
                .WEBPAY,

                Pedido
                .MetodoPago
                .MERCADOPAGO,
            ],
        )
        .aggregate(
            total=Sum(
                "total"
            )
        )
    )

    return Decimal(
        str(
            resultado["total"]
            or 0
        )
    )


@transaction.atomic
def _sincronizar_fidelidad_usuario(
    usuario,
):
    """
    Sincroniza completamente la fidelidad del usuario.

    1. Recalcula el histórico usando pedidos realmente aprobados.
    2. Actualiza SaldoFidelidad.
    3. Marca como contabilizados los pedidos aprobados.
    4. Detecta todas las metas alcanzadas.
    5. Genera una recompensa si la meta nunca fue entregada.
    6. NO vuelve a generar el código si:
       - ya fue utilizado;
       - fue desactivado por administración;
       - ya existe por cualquier motivo.
    """

    # ==================================================================
    # TOTAL REAL PAGADO
    # ==================================================================

    acumulado = (
        _obtener_total_compras_aprobadas(
            usuario
        )
    )

    # ==================================================================
    # SALDO DE FIDELIDAD
    # ==================================================================

    saldo, _ = (
        SaldoFidelidad.objects
        .select_for_update()
        .get_or_create(
            usuario=usuario,
            defaults={
                "saldo_actual": (
                    acumulado
                ),
                "total_historico": (
                    acumulado
                ),
                "metas_cumplidas": 0,
            },
        )
    )

    # El histórico se reconstruye desde Pedido.
    #
    # Así evitamos:
    # - compras duplicadas;
    # - acumulados antiguos incorrectos;
    # - pedidos rechazados contabilizados;
    # - pedidos reembolsados contabilizados.
    saldo.total_historico = acumulado

    # Por ahora saldo_actual representa también
    # lo acumulado vigente para las metas.
    saldo.saldo_actual = acumulado

    # ==================================================================
    # MARCAR PEDIDOS VÁLIDOS COMO CONTABILIZADOS
    # ==================================================================

    (
        Pedido.objects
        .filter(
            usuario=usuario,
            pagado=True,
            estado_pago=(
                Pedido
                .EstadoPago
                .APROBADO
            ),
            metodo_pago__in=[
                Pedido
                .MetodoPago
                .WEBPAY,

                Pedido
                .MetodoPago
                .MERCADOPAGO,
            ],
            fidelidad_contabilizada=False,
        )
        .update(
            fidelidad_contabilizada=True
        )
    )

    # Si un pedido dejó de ser válido
    # (por ejemplo, reembolsado),
    # dejamos consistente el indicador.
    (
        Pedido.objects
        .filter(
            usuario=usuario,
            fidelidad_contabilizada=True,
        )
        .exclude(
            pagado=True,
            estado_pago=(
                Pedido
                .EstadoPago
                .APROBADO
            ),
            metodo_pago__in=[
                Pedido
                .MetodoPago
                .WEBPAY,

                Pedido
                .MetodoPago
                .MERCADOPAGO,
            ],
        )
        .update(
            fidelidad_contabilizada=False
        )
    )

    # ==================================================================
    # METAS ACTIVAS
    # ==================================================================

    metas = list(
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

    # ==================================================================
    # GENERAR RECOMPENSAS
    # ==================================================================

    for numero_meta, meta in enumerate(
        metas,
        start=1,
    ):

        objetivo = Decimal(
            str(
                meta.monto_objetivo
                or 0
            )
        )

        if objetivo <= 0:
            continue

        if acumulado < objetivo:
            continue

        # --------------------------------------------------------------
        # MUY IMPORTANTE
        #
        # Buscamos el código aunque:
        #
        # - esté consumido;
        # - esté desactivado;
        # - esté vencido.
        #
        # Si existe, NO generamos otro.
        #
        # Así el administrador puede bloquearlo simplemente
        # colocando activo=False.
        #
        # Y si el cliente ya lo utilizó, consumido=True evita
        # que vuelva a recibir la recompensa.
        # --------------------------------------------------------------

        codigo_existente = (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                usuario_exclusivo=usuario,
                meta_fidelidad=meta,
            )
            .first()
        )

        if codigo_existente:
            continue

        ahora = timezone.now()

        fecha_fin = (
            ahora
            + timezone.timedelta(
                days=meta.vigencia_dias
            )
        )

        datos_codigo = {
            "tipo": (
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),

            "usuario_exclusivo": (
                usuario
            ),

            "meta_fidelidad": (
                meta
            ),

            "numero_meta": (
                numero_meta
            ),

            "nombre": (
                f"Premio fidelidad - "
                f"{meta.nombre}"
            ),

            "codigo": (
                _generar_codigo_fidelidad_unico(
                    usuario,
                    meta,
                )
            ),

            "descripcion": (
                f"Premio desbloqueado al "
                f"alcanzar ${meta.monto_objetivo:,.0f} "
                f"en compras aprobadas."
            ),

            "activo": True,

            "consumido": False,

            "modalidad": (
                meta.modalidad
            ),

            "monto_minimo": (
                meta.monto_minimo_compra
                or Decimal("0")
            ),

            "fecha_inicio": (
                ahora
            ),

            "fecha_fin": (
                fecha_fin
            ),
        }

        # --------------------------------------------------------------
        # PREMIO PORCENTUAL
        # --------------------------------------------------------------

        if (
            meta.modalidad
            == MetaFidelidad
            .Modalidad
            .PORCENTAJE
        ):

            datos_codigo.update(
                {
                    "porcentaje": (
                        meta.porcentaje
                    ),

                    "monto_descuento": (
                        None
                    ),

                    "monto_maximo_descuento": (
                        meta
                        .monto_maximo_descuento
                    ),
                }
            )

        # --------------------------------------------------------------
        # PREMIO MONTO FIJO
        # --------------------------------------------------------------

        else:

            datos_codigo.update(
                {
                    "porcentaje": (
                        None
                    ),

                    "monto_descuento": (
                        meta.monto_descuento
                    ),

                    "monto_maximo_descuento": (
                        None
                    ),
                }
            )

        CodigoDescuento.objects.create(
            **datos_codigo
        )

    # ==================================================================
    # CANTIDAD HISTÓRICA DE PREMIOS GENERADOS
    # ==================================================================

    #
    # Aquí NO filtramos activo=True ni consumido=False.
    #
    # Si ya recibió un premio, sigue siendo una meta históricamente
    # cumplida aunque:
    #
    # - haya usado el código;
    # - el administrador lo haya desactivado;
    # - el código haya vencido.
    #

    total_premios_generados = (
        CodigoDescuento.objects
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),
            usuario_exclusivo=usuario,
        )
        .count()
    )

    saldo.metas_cumplidas = (
        total_premios_generados
    )

    saldo.save(
        update_fields=[
            "saldo_actual",
            "total_historico",
            "metas_cumplidas",
            "actualizado",
        ]
    )

    return saldo


# ======================================================================
# OFERTAS
# ======================================================================

@ensure_csrf_cookie
def ofertas(request):
    """
    Página comercial de ofertas.

    Muestra:

    - Productos activos con una rebaja superior al 15%.
    - Todos los códigos generales activos y vigentes.
    - Códigos generales porcentuales.
    - Códigos generales de monto fijo en CLP.
    - Todas las metas activas del programa de fidelidad.
    - Progreso real del usuario utilizando solamente compras
      aprobadas por Mercado Pago o Webpay.
    - Próxima recompensa del usuario.
    - Códigos personales disponibles.
    """

    ahora = timezone.now()

    # ==================================================================
    # PRODUCTOS CON MÁS DE 15% DE DESCUENTO
    # ==================================================================

    candidatos = list(
        Producto.objects
        .select_related(
            "categoria",
        )
        .filter(
            activo=True,
            categoria__activa=True,
            precio_oferta__isnull=False,
            precio_oferta__gt=0,
        )
    )

    productos_oferta = []

    for producto in candidatos:

        if not producto.en_oferta:
            continue

        porcentaje = int(
            producto.porcentaje_descuento
            or 0
        )

        if porcentaje <= 15:
            continue

        producto.porcentaje_oferta = (
            porcentaje
        )

        producto.ahorro_oferta = max(
            Decimal(
                str(
                    producto.precio
                )
            )
            - Decimal(
                str(
                    producto.precio_oferta
                )
            ),
            Decimal("0"),
        )

        producto.stock_oferta = int(
            producto.stock_disponible
        )

        productos_oferta.append(
            producto
        )

    productos_oferta.sort(
        key=lambda producto: (
            producto.stock_oferta <= 0,
            -producto.porcentaje_oferta,
            Decimal(
                str(
                    producto.precio_oferta
                )
            ),
            producto.nombre.casefold(),
        )
    )

    mayor_descuento = max(
        (
            producto.porcentaje_oferta
            for producto
            in productos_oferta
        ),
        default=0,
    )

    mayor_stock = max(
        (
            producto.stock_oferta
            for producto
            in productos_oferta
        ),
        default=1,
    )

    for producto in productos_oferta:

        if producto.stock_oferta <= 0:
            producto.stock_porcentaje = 0
            continue

        producto.stock_porcentaje = max(
            8,
            min(
                int(
                    producto.stock_oferta
                    * 100
                    / mayor_stock
                ),
                100,
            ),
        )

    hero_producto = (
        productos_oferta[0]
        if productos_oferta
        else None
    )

    # ==================================================================
    # CÓDIGOS GENERALES ACTIVOS Y VIGENTES
    # ==================================================================

    codigos_base = (
        CodigoDescuento.objects
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .GENERAL
            ),
            activo=True,
        )
        .filter(
            Q(
                fecha_inicio__isnull=True,
            )
            |
            Q(
                fecha_inicio__lte=ahora,
            )
        )
        .filter(
            Q(
                fecha_fin__isnull=True,
            )
            |
            Q(
                fecha_fin__gt=ahora,
            )
        )
    )

    # ==================================================================
    # CÓDIGOS GENERALES CLP
    # ==================================================================

    cupones_clp = list(
        codigos_base
        .filter(
            modalidad=(
                CodigoDescuento
                .Modalidad
                .MONTO_FIJO
            ),
            monto_descuento__isnull=False,
            monto_descuento__gt=0,
        )
        .order_by(
            "monto_minimo",
            "-monto_descuento",
            "fecha_fin",
            "-creado",
        )
    )

    # ==================================================================
    # CÓDIGOS GENERALES PORCENTUALES
    # ==================================================================

    codigos_porcentaje = list(
        codigos_base
        .filter(
            modalidad=(
                CodigoDescuento
                .Modalidad
                .PORCENTAJE
            ),
            porcentaje__isnull=False,
            porcentaje__gt=0,
        )
        .order_by(
            "-porcentaje",
            "monto_minimo",
            "fecha_fin",
            "-creado",
        )
    )

    # ==================================================================
    # CÓDIGOS GENERALES UTILIZADOS
    # ==================================================================

    codigos_generales = [
        *cupones_clp,
        *codigos_porcentaje,
    ]

    codigos_generales_usados = set()

    if request.user.is_authenticated:

        cliente_clave = (
            f"USER:{request.user.pk}"
        )

        codigos_generales_usados = set(
            UsoCodigoDescuento.objects
            .filter(
                cliente_clave=cliente_clave,
                estado=(
                    UsoCodigoDescuento
                    .Estado
                    .CONFIRMADO
                ),
                codigo__tipo=(
                    CodigoDescuento
                    .Tipo
                    .GENERAL
                ),
            )
            .values_list(
                "codigo_id",
                flat=True,
            )
        )

    for codigo in codigos_generales:

        codigo.usado_por_cliente = (
            codigo.pk
            in codigos_generales_usados
        )

    # ==================================================================
    # CÓDIGO DESTACADO
    # ==================================================================

    codigos_disponibles_para_destacar = [
        codigo
        for codigo in codigos_generales
        if not codigo.usado_por_cliente
    ]

    codigo_destacado = (
        codigos_disponibles_para_destacar[0]
        if codigos_disponibles_para_destacar
        else (
            codigos_generales[0]
            if codigos_generales
            else None
        )
    )

    # ==================================================================
    # PRÓXIMO VENCIMIENTO
    # ==================================================================

    fechas_fin = [
        codigo.fecha_fin
        for codigo in codigos_generales
        if (
            codigo.fecha_fin
            and not codigo.usado_por_cliente
        )
    ]

    campana_vence_en = (
        min(
            fechas_fin
        )
        if fechas_fin
        else None
    )

    # ==================================================================
    # METAS ACTIVAS
    # ==================================================================

    metas_fidelidad = list(
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

    programa_fidelidad_activo = bool(
        metas_fidelidad
    )

    # ==================================================================
    # FIDELIDAD
    # ==================================================================

    fidelidad = None
    codigos_personales = []

    if request.user.is_authenticated:

        # --------------------------------------------------------------
        # CLAVE DEL CLIENTE
        # --------------------------------------------------------------

        cliente_clave = (
            f"USER:{request.user.pk}"
        )

        # --------------------------------------------------------------
        # SINCRONIZAR CON LOS PEDIDOS REALES
        # --------------------------------------------------------------

        saldo = (
            _sincronizar_fidelidad_usuario(
                request.user
            )
        )

        acumulado = Decimal(
            str(
                saldo.total_historico
                or 0
            )
        )

        # --------------------------------------------------------------
        # CÓDIGOS DE FIDELIDAD YA UTILIZADOS
        #
        # Un código será considerado utilizado si existe un registro
        # CONFIRMADO en UsoCodigoDescuento para este usuario.
        #
        # Esto evita depender exclusivamente del campo "consumido"
        # del CodigoDescuento.
        # --------------------------------------------------------------

        codigos_fidelidad_usados = set(
            UsoCodigoDescuento.objects
            .filter(
                cliente_clave=cliente_clave,
                estado=(
                    UsoCodigoDescuento
                    .Estado
                    .CONFIRMADO
                ),
                codigo__tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                codigo__usuario_exclusivo=(
                    request.user
                ),
            )
            .values_list(
                "codigo_id",
                flat=True,
            )
        )

        # --------------------------------------------------------------
        # CÓDIGOS PERSONALES DISPONIBLES
        #
        # Primero obtenemos los códigos que potencialmente podrían
        # utilizarse y después excluimos cualquier código que tenga
        # un UsoCodigoDescuento CONFIRMADO.
        #
        # Solo mostramos los que:
        #
        # - pertenecen al usuario;
        # - siguen activos;
        # - todavía no fueron consumidos;
        # - no tienen uso confirmado;
        # - siguen vigentes.
        # --------------------------------------------------------------

        codigos_personales = list(
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                usuario_exclusivo=(
                    request.user
                ),
                activo=True,
                consumido=False,
            )
            .exclude(
                pk__in=(
                    codigos_fidelidad_usados
                )
            )
            .filter(
                Q(
                    modalidad=(
                        CodigoDescuento
                        .Modalidad
                        .PORCENTAJE
                    ),
                    porcentaje__isnull=False,
                    porcentaje__gt=0,
                )
                |
                Q(
                    modalidad=(
                        CodigoDescuento
                        .Modalidad
                        .MONTO_FIJO
                    ),
                    monto_descuento__isnull=False,
                    monto_descuento__gt=0,
                )
            )
            .filter(
                Q(
                    fecha_inicio__isnull=True,
                )
                |
                Q(
                    fecha_inicio__lte=ahora,
                )
            )
            .filter(
                Q(
                    fecha_fin__isnull=True,
                )
                |
                Q(
                    fecha_fin__gt=ahora,
                )
            )
            .select_related(
                "meta_fidelidad",
            )
            .order_by(
                "fecha_fin",
                "-creado",
            )
        )

        # --------------------------------------------------------------
        # TODOS LOS CÓDIGOS GENERADOS POR META
        #
        # IMPORTANTE:
        #
        # Aquí consultamos también:
        #
        # - códigos consumidos;
        # - códigos desactivados;
        # - códigos vencidos;
        #
        # Esto es necesario para saber si una meta ya entregó su
        # premio anteriormente y mostrar correctamente su estado.
        # --------------------------------------------------------------

        todos_codigos_meta = (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                usuario_exclusivo=(
                    request.user
                ),
                meta_fidelidad__isnull=False,
            )
            .select_related(
                "meta_fidelidad"
            )
            .order_by(
                "meta_fidelidad_id",
                "-creado",
                "-pk",
            )
        )

        # --------------------------------------------------------------
        # CÓDIGO MÁS RECIENTE DE CADA META
        #
        # Como el queryset está ordenado por meta y luego por creación
        # descendente, solamente guardamos el primer código encontrado
        # para cada meta.
        # --------------------------------------------------------------

        codigos_por_meta = {}

        for codigo in todos_codigos_meta:

            if (
                codigo.meta_fidelidad_id
                not in codigos_por_meta
            ):
                codigos_por_meta[
                    codigo.meta_fidelidad_id
                ] = codigo

        # --------------------------------------------------------------
        # PROGRESO POR META
        # --------------------------------------------------------------

        for meta in metas_fidelidad:

            objetivo = Decimal(
                str(
                    meta.monto_objetivo
                    or 0
                )
            )

            if objetivo <= 0:
                objetivo = Decimal("1")

            faltante = max(
                objetivo - acumulado,
                Decimal("0"),
            )

            progreso = min(
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

            meta.progreso_cliente = (
                progreso
            )

            meta.faltante_cliente = (
                faltante
            )

            meta.alcanzada_cliente = (
                acumulado >= objetivo
            )

            codigo_meta = (
                codigos_por_meta.get(
                    meta.pk
                )
            )

            meta.codigo_personal_cliente = (
                codigo_meta
            )

            # ----------------------------------------------------------
            # DETERMINAR SI EL CÓDIGO YA FUE UTILIZADO
            #
            # Consideramos utilizado cuando:
            #
            # 1. CodigoDescuento.consumido == True
            #
            # O
            #
            # 2. Existe UsoCodigoDescuento CONFIRMADO.
            #
            # La segunda condición protege frente a posibles estados
            # desincronizados del campo "consumido".
            # ----------------------------------------------------------

            codigo_utilizado = bool(
                codigo_meta
                and (
                    codigo_meta.consumido
                    or (
                        codigo_meta.pk
                        in codigos_fidelidad_usados
                    )
                )
            )

            # ----------------------------------------------------------
            # CÓDIGO DISPONIBLE
            # ----------------------------------------------------------

            meta.codigo_disponible_cliente = (
                bool(
                    codigo_meta
                    and codigo_meta.activo
                    and not codigo_utilizado
                    and codigo_meta.vigente
                )
            )

            # ----------------------------------------------------------
            # CÓDIGO YA UTILIZADO
            # ----------------------------------------------------------

            meta.codigo_consumido_cliente = (
                codigo_utilizado
            )

            # ----------------------------------------------------------
            # CÓDIGO DESACTIVADO
            #
            # Si ya fue utilizado, priorizamos el estado "utilizado"
            # por sobre "desactivado".
            # ----------------------------------------------------------

            meta.codigo_desactivado_cliente = (
                bool(
                    codigo_meta
                    and not codigo_meta.activo
                    and not codigo_utilizado
                )
            )

            # ----------------------------------------------------------
            # CÓDIGO VENCIDO
            #
            # Estado adicional útil para el template.
            # ----------------------------------------------------------

            meta.codigo_vencido_cliente = (
                bool(
                    codigo_meta
                    and codigo_meta.activo
                    and not codigo_utilizado
                    and not codigo_meta.vigente
                )
            )

        # --------------------------------------------------------------
        # PRÓXIMA META
        # --------------------------------------------------------------

        proxima_meta = None

        for meta in metas_fidelidad:

            objetivo = Decimal(
                str(
                    meta.monto_objetivo
                    or 0
                )
            )

            if objetivo > acumulado:
                proxima_meta = meta
                break

        # --------------------------------------------------------------
        # RESUMEN
        # --------------------------------------------------------------

        if proxima_meta:

            fidelidad = {
                "saldo_actual": (
                    acumulado
                ),

                "meta": (
                    proxima_meta
                ),

                "monto_objetivo": (
                    proxima_meta
                    .monto_objetivo
                ),

                "faltante": (
                    proxima_meta
                    .faltante_cliente
                ),

                "progreso": (
                    proxima_meta
                    .progreso_cliente
                ),

                "metas_cumplidas": (
                    saldo.metas_cumplidas
                ),

                "todas_alcanzadas": (
                    False
                ),
            }

        else:

            fidelidad = {
                "saldo_actual": (
                    acumulado
                ),

                "meta": None,

                "monto_objetivo": None,

                "faltante": (
                    Decimal("0")
                ),

                "progreso": 100,

                "metas_cumplidas": (
                    saldo.metas_cumplidas
                ),

                "todas_alcanzadas": (
                    bool(
                        metas_fidelidad
                    )
                ),
            }

    # ==================================================================
    # CONTEXTO
    # ==================================================================

    contexto = {
        # PRODUCTOS
        "productos_oferta": (
            productos_oferta
        ),

        "cantidad_ofertas": len(
            productos_oferta
        ),

        "mayor_descuento": (
            mayor_descuento
        ),

        "hero_producto": (
            hero_producto
        ),

        # CÓDIGOS GENERALES
        "codigos_generales": (
            codigos_generales
        ),

        "cantidad_codigos_generales": len(
            codigos_generales
        ),

        "codigos_porcentaje": (
            codigos_porcentaje
        ),

        "cantidad_codigos_porcentaje": len(
            codigos_porcentaje
        ),

        "cupones_clp": (
            cupones_clp
        ),

        "cantidad_cupones_clp": len(
            cupones_clp
        ),

        "codigo_destacado": (
            codigo_destacado
        ),

        "campana_vence_en": (
            campana_vence_en
        ),

        # FIDELIDAD
        "programa_fidelidad_activo": (
            programa_fidelidad_activo
        ),

        "metas_fidelidad": (
            metas_fidelidad
        ),

        "cantidad_metas_fidelidad": len(
            metas_fidelidad
        ),

        "fidelidad": (
            fidelidad
        ),

        "codigos_personales": (
            codigos_personales
        ),

        "cantidad_codigos_personales": len(
            codigos_personales
        ),
    }

    return render(
        request,
        "core/ofertas.html",
        contexto,
    )


def nosotros(request):
    return render(request, "core/nosotros.html")











def _serializar_carrito(request):
    carrito = _obtener_carrito(
        request
    )

    # =========================================================================
    # IDS DE PRODUCTOS
    # =========================================================================

    ids_productos = []

    for producto_id in carrito.keys():
        try:
            ids_productos.append(
                int(producto_id)
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    # =========================================================================
    # PRODUCTOS
    # =========================================================================

    productos = {
        producto.id: producto
        for producto in Producto.objects.filter(
            id__in=ids_productos,
            activo=True,
        ).select_related(
            "categoria"
        )
    }

    # =========================================================================
    # ACUMULADORES
    # =========================================================================

    items = []

    subtotal = Decimal(
        "0"
    )

    subtotal_precio_lista = Decimal(
        "0"
    )

    ahorro_ofertas = Decimal(
        "0"
    )

    cantidad_total = 0

    cantidad_productos_con_oferta = 0

    carrito_limpio = {}

    # =========================================================================
    # RECORRER CARRITO
    # =========================================================================

    for (
        producto_id_texto,
        datos,
    ) in carrito.items():

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

        producto = productos.get(
            producto_id
        )

        if producto is None:
            continue

        # ---------------------------------------------------------------------
        # CANTIDAD
        # ---------------------------------------------------------------------

        cantidad = max(
            1,
            cantidad,
        )

        if producto.stock <= 0:
            continue

        cantidad = min(
            cantidad,
            producto.stock,
        )

        # ---------------------------------------------------------------------
        # PRECIOS
        # ---------------------------------------------------------------------

        precio_original = Decimal(
            str(
                producto.precio
                or 0
            )
        )

        precio_unitario = Decimal(
            str(
                producto.precio_actual
                or 0
            )
        )

        # ---------------------------------------------------------------------
        # TOTAL DE LA LÍNEA
        # ---------------------------------------------------------------------

        total_original_linea = (
            precio_original
            * cantidad
        )

        total_linea = (
            precio_unitario
            * cantidad
        )

        # ---------------------------------------------------------------------
        # AHORRO DEL PRODUCTO
        # ---------------------------------------------------------------------

        ahorro_unitario = max(
            precio_original
            - precio_unitario,
            Decimal(
                "0"
            ),
        )

        ahorro_linea = (
            ahorro_unitario
            * cantidad
        )

        # ---------------------------------------------------------------------
        # PORCENTAJE DE DESCUENTO
        # ---------------------------------------------------------------------

        porcentaje_descuento = 0

        if (
            producto.en_oferta
            and precio_original > 0
        ):
            porcentaje_descuento = int(
                round(
                    (
                        ahorro_unitario
                        / precio_original
                    )
                    * Decimal(
                        "100"
                    )
                )
            )

        # ---------------------------------------------------------------------
        # ACUMULADORES
        # ---------------------------------------------------------------------

        subtotal += total_linea

        subtotal_precio_lista += (
            total_original_linea
        )

        ahorro_ofertas += (
            ahorro_linea
        )

        cantidad_total += (
            cantidad
        )

        if producto.en_oferta:
            cantidad_productos_con_oferta += (
                cantidad
            )

        # ---------------------------------------------------------------------
        # CARRITO LIMPIO
        # ---------------------------------------------------------------------

        carrito_limpio[
            str(
                producto.id
            )
        ] = {
            "cantidad": cantidad,
        }

        # ---------------------------------------------------------------------
        # ITEM SERIALIZADO
        # ---------------------------------------------------------------------

        items.append(
            {
                # =============================================================
                # IDENTIFICACIÓN
                # =============================================================

                "id": producto.id,

                "nombre": (
                    producto.nombre
                ),

                "slug": (
                    producto.slug
                ),

                "categoria": (
                    producto.categoria.nombre
                ),

                # =============================================================
                # CANTIDAD / STOCK
                # =============================================================

                "cantidad": cantidad,

                "stock": (
                    producto.stock
                ),

                # =============================================================
                # PRECIO ORIGINAL
                # =============================================================

                "precio_original": int(
                    precio_original
                ),

                "precio_original_formateado": (
                    f"${int(precio_original):,}"
                    .replace(
                        ",",
                        ".",
                    )
                ),

                # =============================================================
                # PRECIO ACTUAL
                # =============================================================

                "precio": int(
                    precio_unitario
                ),

                "precio_formateado": (
                    f"${int(precio_unitario):,}"
                    .replace(
                        ",",
                        ".",
                    )
                ),

                # =============================================================
                # TOTAL ORIGINAL DE LA LÍNEA
                # =============================================================

                "total_original": int(
                    total_original_linea
                ),

                "total_original_formateado": (
                    f"${int(total_original_linea):,}"
                    .replace(
                        ",",
                        ".",
                    )
                ),

                # =============================================================
                # TOTAL ACTUAL DE LA LÍNEA
                # =============================================================

                "total": int(
                    total_linea
                ),

                "total_formateado": (
                    f"${int(total_linea):,}"
                    .replace(
                        ",",
                        ".",
                    )
                ),

                # =============================================================
                # OFERTA / AHORRO
                # =============================================================

                "en_oferta": (
                    producto.en_oferta
                ),

                "porcentaje_descuento": (
                    porcentaje_descuento
                ),

                "ahorro_unitario": int(
                    ahorro_unitario
                ),

                "ahorro_unitario_formateado": (
                    f"${int(ahorro_unitario):,}"
                    .replace(
                        ",",
                        ".",
                    )
                ),

                "ahorro_linea": int(
                    ahorro_linea
                ),

                "ahorro_linea_formateado": (
                    f"${int(ahorro_linea):,}"
                    .replace(
                        ",",
                        ".",
                    )
                ),

                # =============================================================
                # IMAGEN / URL
                # =============================================================

                "imagen": (
                    producto.imagen_mostrable
                    or ""
                ),

                "url_detalle": (
                    producto.get_absolute_url()
                ),
            }
        )

    # =========================================================================
    # SINCRONIZAR CARRITO
    # =========================================================================

    if carrito_limpio != carrito:
        _guardar_carrito(
            request,
            carrito_limpio,
        )

    # =========================================================================
    # FORMATEADOR LOCAL
    # =========================================================================

    def formatear_pesos(
        valor,
    ):
        return (
            f"${int(valor):,}"
            .replace(
                ",",
                ".",
            )
        )

    # =========================================================================
    # RESPUESTA
    # =========================================================================

    return {
        # ---------------------------------------------------------------------
        # ITEMS
        # ---------------------------------------------------------------------

        "items": items,

        # ---------------------------------------------------------------------
        # CANTIDADES
        # ---------------------------------------------------------------------

        "cantidad_total": (
            cantidad_total
        ),

        "cantidad_productos_con_oferta": (
            cantidad_productos_con_oferta
        ),

        # ---------------------------------------------------------------------
        # SUBTOTAL PRECIO LISTA
        # ---------------------------------------------------------------------

        "subtotal_precio_lista": int(
            subtotal_precio_lista
        ),

        "subtotal_precio_lista_formateado": (
            formatear_pesos(
                subtotal_precio_lista
            )
        ),

        # ---------------------------------------------------------------------
        # AHORRO POR OFERTAS
        # ---------------------------------------------------------------------

        "ahorro_ofertas": int(
            ahorro_ofertas
        ),

        "ahorro_ofertas_formateado": (
            formatear_pesos(
                ahorro_ofertas
            )
        ),

        "tiene_ofertas": (
            ahorro_ofertas > 0
        ),

        # ---------------------------------------------------------------------
        # SUBTOTAL REAL
        # ---------------------------------------------------------------------

        "subtotal": int(
            subtotal
        ),

        "subtotal_formateado": (
            formatear_pesos(
                subtotal
            )
        ),

        # ---------------------------------------------------------------------
        # ESTADO
        # ---------------------------------------------------------------------

        "vacio": (
            len(items) == 0
        ),
    }




@require_GET
def carrito_estado(request):
    return JsonResponse(
        {
            "ok": True,
            "carrito": _serializar_carrito(request),
        }
    )


@require_POST
def carrito_agregar(request):
    try:
        datos = json.loads(request.body or "{}")
        producto_id = int(datos.get("producto_id"))
        cantidad = int(datos.get("cantidad", 1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Los datos enviados no son válidos.",
            },
            status=400,
        )

    producto = get_object_or_404(
        Producto,
        id=producto_id,
        activo=True,
    )

    if producto.stock <= 0:
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Este producto está agotado.",
            },
            status=400,
        )

    cantidad = max(1, cantidad)

    carrito = _obtener_carrito(request)
    clave_producto = str(producto.id)

    cantidad_actual = int(
        carrito.get(
            clave_producto,
            {},
        ).get(
            "cantidad",
            0,
        )
    )

    nueva_cantidad = cantidad_actual + cantidad

    if nueva_cantidad > producto.stock:
        return JsonResponse(
            {
                "ok": False,
                "mensaje": (
                    f"Solo quedan {producto.stock} unidades disponibles."
                ),
            },
            status=400,
        )

    carrito[clave_producto] = {
        "cantidad": nueva_cantidad,
    }

    _guardar_carrito(request, carrito)

    return JsonResponse(
        {
            "ok": True,
            "mensaje": f"{producto.nombre} fue agregado al carrito.",
            "producto_id": producto.id,
            "carrito": _serializar_carrito(request),
        }
    )


@require_POST
def carrito_actualizar(request):
    try:
        datos = json.loads(request.body or "{}")
        producto_id = int(datos.get("producto_id"))
        cantidad = int(datos.get("cantidad"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Los datos enviados no son válidos.",
            },
            status=400,
        )

    producto = get_object_or_404(
        Producto,
        id=producto_id,
        activo=True,
    )

    carrito = _obtener_carrito(request)
    clave_producto = str(producto.id)

    if clave_producto not in carrito:
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "El producto no está en el carrito.",
            },
            status=404,
        )

    if cantidad <= 0:
        carrito.pop(clave_producto, None)
    else:
        if cantidad > producto.stock:
            return JsonResponse(
                {
                    "ok": False,
                    "mensaje": (
                        f"Solo quedan {producto.stock} unidades disponibles."
                    ),
                },
                status=400,
            )

        carrito[clave_producto] = {
            "cantidad": cantidad,
        }

    _guardar_carrito(request, carrito)

    return JsonResponse(
        {
            "ok": True,
            "mensaje": "Carrito actualizado.",
            "carrito": _serializar_carrito(request),
        }
    )


@require_POST
def carrito_eliminar(request):
    try:
        datos = json.loads(request.body or "{}")
        producto_id = str(int(datos.get("producto_id")))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "El producto indicado no es válido.",
            },
            status=400,
        )

    carrito = _obtener_carrito(request)
    carrito.pop(producto_id, None)

    _guardar_carrito(request, carrito)

    return JsonResponse(
        {
            "ok": True,
            "mensaje": "Producto eliminado del carrito.",
            "carrito": _serializar_carrito(request),
        }
    )


@require_POST
def carrito_vaciar(request):
    _guardar_carrito(request, {})

    return JsonResponse(
        {
            "ok": True,
            "mensaje": "El carrito fue vaciado.",
            "carrito": _serializar_carrito(request),
        }
    )


def carrito_completo(request):
    """
    Página completa del carrito.

    El contenido inicial se obtiene desde la sesión.
    JavaScript seguirá utilizando las mismas rutas AJAX
    del carrito lateral.
    """

    carrito = _serializar_carrito(request)

    contexto = {
        "carrito": carrito,
    }

    return render(
        request,
        "core/carrito_completo.html",
        contexto,
    )





















# ============================================================================
# GESTIÓN DE DESCUENTOS Y FIDELIDAD
# ============================================================================


def _errores_formulario(
    formulario,
):
    """
    Convierte los errores de un formulario
    en un mensaje legible.
    """

    errores = []

    for error in formulario.non_field_errors():
        errores.append(
            str(error)
        )

    for campo, lista_errores in (
        formulario.errors.items()
    ):
        if campo == "__all__":
            continue

        if campo in formulario.fields:
            nombre_campo = (
                formulario.fields[
                    campo
                ].label
                or campo
            )
        else:
            nombre_campo = campo

        for error in lista_errores:
            errores.append(
                f"{nombre_campo}: {error}"
            )

    return " ".join(
        errores
    )


# ============================================================================
# SALDOS / PROGRESO DE FIDELIDAD
# ============================================================================


def _preparar_saldos_fidelidad():
    """
    Calcula para cada cliente:

    - gasto acumulado;
    - próxima meta activa;
    - cuánto falta;
    - porcentaje de avance.
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

        if proxima_meta is None:
            saldo.objetivo_actual = None
            saldo.faltante = Decimal("0")
            saldo.progreso = 100

            continue

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
        or CodigoGeneralPorcentajeForm()
    )

    form_general_clp = (
        formularios_con_error.get(
            "form_general_clp"
        )
        or CodigoGeneralMontoFijoForm()
    )

    form_fidelidad_porcentaje = (
        formularios_con_error.get(
            "form_fidelidad_porcentaje"
        )
        or MetaFidelidadPorcentajeForm()
    )

    form_fidelidad_clp = (
        formularios_con_error.get(
            "form_fidelidad_clp"
        )
        or MetaFidelidadMontoFijoForm()
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

    # ==================================================================
    # TODOS LOS CÓDIGOS
    # ==================================================================

    codigos = (
        CodigoDescuento.objects
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

            total_registros_uso=Count(
                "usos",
                distinct=True,
            ),
        )
    )

    # ==================================================================
    # BÚSQUEDA
    # ==================================================================

    if busqueda:
        codigos = codigos.filter(
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

    # ==================================================================
    # MODALIDAD
    # ==================================================================

    if (
        modalidad
        in CodigoDescuento.Modalidad.values
    ):
        codigos = codigos.filter(
            modalidad=modalidad
        )

    # ==================================================================
    # ESTADO
    # ==================================================================

    if estado == "activos":
        codigos = codigos.filter(
            activo=True,
        )

    elif estado == "ocultos":
        codigos = codigos.filter(
            activo=False,
        )

    elif estado == "consumidos":
        codigos = codigos.filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),
            consumido=True,
        )

    elif estado == "todos":
        pass

    else:
        estado = "todos"

    # ==================================================================
    # CÓDIGOS GENERALES
    # ==================================================================

    codigos_generales = (
        codigos
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .GENERAL
            )
        )
        .order_by(
            "-creado"
        )
    )

    pagina_codigos_generales = (
        Paginator(
            codigos_generales,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_generales"
            )
        )
    )

    # ==================================================================
    # CÓDIGOS DE FIDELIDAD
    # ==================================================================

    codigos_fidelidad = (
        codigos
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            )
        )
        .order_by(
            "-creado"
        )
    )

    pagina_codigos_fidelidad = (
        Paginator(
            codigos_fidelidad,
            20,
        )
        .get_page(
            request.GET.get(
                "pagina_fidelidad"
            )
        )
    )

    # ==================================================================
    # SALDOS / PROGRESO DE CLIENTES
    # ==================================================================

    saldos = (
        _preparar_saldos_fidelidad()
    )

    # ==================================================================
    # HISTORIAL DE CÓDIGOS USADOS
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
    # CONTEXTO
    # ==================================================================

    return {
        # Formularios
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

        # Códigos separados
        "pagina_codigos_generales": (
            pagina_codigos_generales
        ),

        "pagina_codigos_fidelidad": (
            pagina_codigos_fidelidad
        ),

        # Fidelidad
        "saldos": (
            saldos
        ),

        # Historial
        "pagina_usos": (
            pagina_usos
        ),

        # Filtros
        "busqueda": (
            busqueda
        ),

        "modalidad": (
            modalidad
        ),

        "estado": (
            estado
        ),
    }


# ============================================================================
# Eliminar código de descuento (solo si no tiene registros de uso confirmados)
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

    if codigo.usos.exists():
        messages.error(
            request,
            (
                f"El código {codigo_texto} tiene historial "
                "de uso y no puede eliminarse. "
                "Puedes ocultarlo."
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
        (
            "core/gestion/"
            "gestion_descuentos.html"
        ),
        contexto,
    )


# ============================================================================
# CREACIÓN DE CÓDIGOS GENERALES
# ============================================================================


def _crear_codigo_descuento(
    *,
    request,
    formulario_clase,
    formulario_contexto,
):
    formulario = formulario_clase(
        request.POST
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

    mensaje = (
        _errores_formulario(
            formulario
        )
    )

    messages.error(
        request,
        mensaje
        or (
            "No fue posible crear el código. "
            "Revisa los campos indicados."
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
        (
            "core/gestion/"
            "gestion_descuentos.html"
        ),
        contexto,
        status=400,
    )


# ============================================================================
# 1. CREAR GENERAL PORCENTUAL
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
# 2. CREAR GENERAL CLP
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
# CREACIÓN DE METAS
# ============================================================================


def _crear_meta_fidelidad(
    *,
    request,
    formulario_clase,
    formulario_contexto,
):
    formulario = formulario_clase(
        request.POST
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
                f"La meta «{meta.nombre}» "
                "fue creada correctamente."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    mensaje = (
        _errores_formulario(
            formulario
        )
    )

    messages.error(
        request,
        mensaje
        or (
            "No fue posible crear la meta. "
            "Revisa los campos indicados."
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
        (
            "core/gestion/"
            "gestion_descuentos.html"
        ),
        contexto,
        status=400,
    )


# ============================================================================
# 3. CREAR META FIDELIDAD PORCENTUAL
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
# 4. CREAR META FIDELIDAD CLP
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
# ACTIVAR / DESACTIVAR CÓDIGO
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
                "fue activado nuevamente."
            ),
        )

    else:
        messages.success(
            request,
            (
                f"El código {codigo.codigo} fue ocultado "
                "y quedó desactivado para nuevas compras."
            ),
        )

    return redirect(
        "core:gestion_descuentos"
    )




# ============================================================================
# ACTIVAR / DESACTIVAR META
# ============================================================================


@staff_member_required(
    login_url="core:login",
)
@require_POST
def alternar_meta_fidelidad(
    request,
    meta_id,
):
    """
    Activa o desactiva una meta.

    Desactivar una meta impide que genere
    nuevos premios.

    Los códigos que ya hayan sido generados
    conservan su propio estado.
    """

    meta = get_object_or_404(
        MetaFidelidad,
        pk=meta_id,
    )

    nuevo_estado = (
        not meta.activa
    )

    actualizado = (
        MetaFidelidad.objects
        .filter(
            pk=meta.pk,
        )
        .update(
            activa=nuevo_estado,
            actualizado=timezone.now(),
        )
    )

    if not actualizado:
        messages.error(
            request,
            (
                "No fue posible actualizar "
                "la meta."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    estado_texto = (
        "activada"
        if nuevo_estado
        else "desactivada"
    )

    messages.success(
        request,
        (
            f"La meta «{meta.nombre}» "
            f"fue {estado_texto}."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )









META_DESPACHO_GRATIS = Decimal("50000")
COSTO_DESPACHO = Decimal("4")
DESCUENTO_AUDEX10 = Decimal("0.10")




# ============================================================================
# LIBERAR UN CÓDIGO RESERVADO CUANDO NO SE PUEDE INICIAR EL PAGO
# ============================================================================

def _liberar_descuento_si_corresponde(
    pedido,
):
    """
    Libera la reserva del código cuando el pedido fue creado,
    pero el proveedor de pago no pudo iniciarse.

    No elimina el historial del pedido y no afecta códigos que
    ya hayan sido confirmados como utilizados.
    """

    if pedido is None:
        return

    try:
        liberar_uso_codigo_pedido(
            pedido
        )

    except Exception:
        logger.exception(
            (
                "No fue posible liberar el código "
                "reservado del pedido %s."
            ),
            pedido.numero,
        )


# ============================================================================
# CHECKOUT COMPLETO ACTUALIZADO
# ============================================================================




def _sincronizar_totales_pedido_antes_pago(
    *,
    pedido,
    carrito_serializado,
):
    """
    Recalcula los montos definitivos del Pedido inmediatamente
    antes de enviarlo al proveedor de pago.

    Fuente de verdad:

        subtotal actual de productos
        - descuento ya reservado/guardado en Pedido
        + tarifa Blue Express actual
        = total definitivo

    Esto evita que Mercado Pago o Webpay reciban un total antiguo.
    """

    # =========================================================================
    # SUBTOTAL ACTUAL DEL CARRITO
    # =========================================================================

    subtotal = Decimal(
        str(
            carrito_serializado.get(
                "subtotal",
                0,
            )
            or 0
        )
    )

    if subtotal <= 0:
        raise ValueError(
            "El subtotal del pedido debe ser mayor que $0."
        )

    # =========================================================================
    # DESCUENTO YA VALIDADO EN EL PEDIDO
    # =========================================================================
    #
    # No volvemos a resolver el código aquí.
    #
    # procesar_pedido_checkout() ya debe haber validado y reservado
    # el código. Solamente utilizamos el monto que quedó guardado
    # históricamente en Pedido.
    # =========================================================================

    descuento = Decimal(
        str(
            getattr(
                pedido,
                "descuento",
                0,
            )
            or 0
        )
    )

    descuento = max(
        min(
            descuento,
            subtotal,
        ),
        Decimal("0"),
    )

    # =========================================================================
    # REGIÓN DEFINITIVA DEL PEDIDO
    # =========================================================================

    region = (
        str(
            getattr(
                pedido,
                "region",
                "",
            )
            or ""
        )
        .strip()
    )

    if not region:
        raise ValueError(
            "El pedido no tiene una región de despacho."
        )

    # =========================================================================
    # RECALCULAR BLUE EXPRESS
    # =========================================================================

    cotizacion = cotizar_blue_express(
        carrito_serializado=(
            carrito_serializado
        ),
        region=region,
    )

    despacho = Decimal(
        str(
            cotizacion.costo
            or 0
        )
    )

    if despacho <= 0:
        raise ValueError(
            "El valor de despacho debe ser mayor que $0."
        )

    # =========================================================================
    # SUBTOTAL DESPUÉS DEL CÓDIGO
    # =========================================================================

    subtotal_con_descuento = max(
        subtotal - descuento,
        Decimal("0"),
    )

    # =========================================================================
    # TOTAL DEFINITIVO
    # =========================================================================

    total = (
        subtotal_con_descuento
        + despacho
    )

    if total <= 0:
        raise ValueError(
            "El total definitivo del pedido no es válido."
        )

    # =========================================================================
    # GUARDAR
    # =========================================================================

    pedido.subtotal = subtotal
    pedido.descuento = descuento
    pedido.despacho = despacho
    pedido.total = total

    pedido.save(
        update_fields=[
            "subtotal",
            "descuento",
            "despacho",
            "total",
            "actualizado",
        ]
    )

    # =========================================================================
    # LOG DE DIAGNÓSTICO
    # =========================================================================

    logger.info(
        (
            "Totales definitivos pedido %s: "
            "subtotal=%s descuento=%s "
            "despacho=%s total=%s "
            "BlueExpress=%s/%s cantidad=%s"
        ),
        pedido.numero,
        subtotal,
        descuento,
        despacho,
        total,
        getattr(
            cotizacion,
            "zona",
            "",
        ),
        getattr(
            cotizacion,
            "talla",
            "",
        ),
        getattr(
            cotizacion,
            "cantidad_productos",
            0,
        ),
    )

    return pedido







def checkout(request):
    # =========================================================================
    # OBTENER CARRITO
    # =========================================================================

    carrito = _obtener_carrito(
        request
    )

    if not carrito:
        messages.warning(
            request,
            "Tu carrito está vacío.",
        )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # SERIALIZAR CARRITO
    # =========================================================================

    carrito_serializado = (
        _serializar_carrito(
            request
        )
    )

    if carrito_serializado.get(
        "vacio",
        True,
    ):
        messages.warning(
            request,
            "Tu carrito está vacío.",
        )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # DATOS INICIALES
    # =========================================================================

    datos_iniciales = (
        obtener_datos_iniciales_checkout(
            request
        )
    )

    # =========================================================================
    # FORMULARIO
    # =========================================================================

    if request.method == "POST":

        form = CheckoutForm(
            request.POST,
            initial=datos_iniciales,
        )

        # =====================================================================
        # FORMULARIO VÁLIDO
        # =====================================================================

        if form.is_valid():

            pedido = None

            try:
                # =============================================================
                # CREAR PEDIDO
                # =============================================================
                #
                # procesar_pedido_checkout() debe:
                #
                # - volver a validar productos;
                # - validar stock;
                # - validar el código de descuento;
                # - reservar el código si corresponde;
                # - crear Pedido;
                # - crear PedidoItem;
                # - guardar el descuento histórico.
                #
                # Luego sincronizamos nuevamente los importes definitivos
                # antes de entregarlos al proveedor de pago.
                # =============================================================

                with transaction.atomic():

                    pedido = (
                        procesar_pedido_checkout(
                            request=request,
                            form=form,
                            carrito=carrito,
                        )
                    )

                    # =========================================================
                    # SINCRONIZAR TOTAL DEFINITIVO
                    # =========================================================
                    #
                    # Esto garantiza:
                    #
                    # subtotal productos
                    # - descuento adicional
                    # + Blue Express
                    # = pedido.total
                    #
                    # pedido.total será el valor que Mercado Pago / Webpay
                    # deberá cobrar.
                    # =========================================================

                    pedido = (
                        _sincronizar_totales_pedido_antes_pago(
                            pedido=pedido,
                            carrito_serializado=(
                                carrito_serializado
                            ),
                        )
                    )

                # =============================================================
                # REFRESCAR PEDIDO DESDE BASE DE DATOS
                # =============================================================
                #
                # Así nos aseguramos de que iniciar_pago_pedido() reciba
                # exactamente los valores persistidos.
                # =============================================================

                pedido.refresh_from_db(
                    fields=[
                        "subtotal",
                        "descuento",
                        "despacho",
                        "total",
                    ]
                )

                # =============================================================
                # VALIDACIÓN FINAL DE SEGURIDAD
                # =============================================================

                subtotal_pedido = Decimal(
                    str(
                        pedido.subtotal
                        or 0
                    )
                )

                descuento_pedido = Decimal(
                    str(
                        pedido.descuento
                        or 0
                    )
                )

                despacho_pedido = Decimal(
                    str(
                        pedido.despacho
                        or 0
                    )
                )

                total_pedido = Decimal(
                    str(
                        pedido.total
                        or 0
                    )
                )

                total_esperado = max(
                    (
                        subtotal_pedido
                        - descuento_pedido
                        + despacho_pedido
                    ),
                    Decimal(
                        "0"
                    ),
                )

                if total_pedido != total_esperado:
                    raise ValueError(
                        (
                            "El total definitivo del pedido "
                            "no coincide con su desglose. "
                            f"Subtotal: {subtotal_pedido}, "
                            f"descuento: {descuento_pedido}, "
                            f"despacho: {despacho_pedido}, "
                            f"total guardado: {total_pedido}, "
                            f"total esperado: {total_esperado}."
                        )
                    )

                if total_pedido <= 0:
                    raise ValueError(
                        (
                            "El total definitivo del pedido "
                            "debe ser mayor que $0."
                        )
                    )

                # =============================================================
                # LOG DE DIAGNÓSTICO
                # =============================================================

                logger.info(
                    (
                        "Pedido %s antes de iniciar pago: "
                        "subtotal=%s descuento=%s "
                        "despacho=%s total=%s"
                    ),
                    pedido.numero,
                    pedido.subtotal,
                    pedido.descuento,
                    pedido.despacho,
                    pedido.total,
                )

                # =============================================================
                # INICIAR PAGO
                # =============================================================

                resultado_pago = (
                    iniciar_pago_pedido(
                        request=request,
                        pedido=pedido,
                    )
                )

                # =============================================================
                # VALIDAR RESULTADO DEL PROVEEDOR
                # =============================================================

                if resultado_pago is None:
                    raise ErrorInicioPago(
                        (
                            "El proveedor de pago "
                            "no entregó una respuesta válida."
                        )
                    )

                # =============================================================
                # REGISTRAR PEDIDO EN SESIÓN
                # =============================================================

                _registrar_pedido_pago_en_curso(
                    request,
                    pedido,
                )

                logger.info(
                    (
                        "Pedido %s registrado como pago "
                        "en curso en la sesión %s."
                    ),
                    pedido.numero,
                    request.session.session_key,
                )

                # =============================================================
                # WEBPAY / PROVEEDORES QUE REQUIEREN POST
                # =============================================================
                #
                # Webpay entrega:
                #
                # - una URL de Transbank;
                # - un token_ws.
                #
                # No debemos hacer redirect(url), ya que token_ws
                # debe enviarse mediante POST.
                #
                # Para ello renderizamos una página intermedia que
                # contiene un formulario oculto y se autoenvía.
                # =============================================================

                url_post = getattr(
                    resultado_pago,
                    "url_post",
                    None,
                )

                datos_post = getattr(
                    resultado_pago,
                    "datos_post",
                    None,
                )

                if url_post:

                    if not isinstance(
                        datos_post,
                        dict,
                    ):
                        raise ErrorInicioPago(
                            (
                                "El proveedor de pago requiere "
                                "una redirección POST, pero no "
                                "entregó los datos necesarios."
                            )
                        )

                    if not datos_post:
                        raise ErrorInicioPago(
                            (
                                "El proveedor de pago requiere "
                                "una redirección POST, pero los "
                                "datos recibidos están vacíos."
                            )
                        )

                    logger.info(
                        (
                            "Pedido %s será enviado al "
                            "proveedor mediante POST."
                        ),
                        pedido.numero,
                    )

                    return render(
                        request,
                        "core/redireccion_pago.html",
                        {
                            "url": (
                                url_post
                            ),
                            "datos": (
                                datos_post
                            ),
                        },
                    )

                # =============================================================
                # MERCADO PAGO / REDIRECCIÓN EXTERNA NORMAL
                # =============================================================

                url_redireccion = getattr(
                    resultado_pago,
                    "url_redireccion",
                    None,
                )

                if url_redireccion:

                    logger.info(
                        (
                            "Pedido %s será redirigido "
                            "al proveedor mediante URL."
                        ),
                        pedido.numero,
                    )

                    return redirect(
                        url_redireccion
                    )

                # =============================================================
                # REDIRECCIÓN INTERNA
                # =============================================================
                #
                # Ejemplo:
                #
                # transferencia bancaria
                #
                # nombre_url = core:pedido_confirmacion
                # parametros_url = {"numero": pedido.numero}
                # =============================================================

                nombre_url = getattr(
                    resultado_pago,
                    "nombre_url",
                    None,
                )

                parametros_url = getattr(
                    resultado_pago,
                    "parametros_url",
                    None,
                )

                if nombre_url:

                    if parametros_url is None:
                        parametros_url = {}

                    if not isinstance(
                        parametros_url,
                        dict,
                    ):
                        raise ErrorInicioPago(
                            (
                                "Los parámetros de redirección "
                                "del proveedor no son válidos."
                            )
                        )

                    return redirect(
                        nombre_url,
                        **parametros_url,
                    )

                # =============================================================
                # RESULTADO SIN DESTINO
                # =============================================================

                raise ErrorInicioPago(
                    (
                        "El método de pago no entregó "
                        "un destino válido para continuar."
                    )
                )

            # =================================================================
            # ERROR AL INICIAR EL PROVEEDOR
            # =================================================================

            except ErrorInicioPago as error:

                request.session.pop(
                    "pedido_pago_en_curso",
                    None,
                )

                request.session.modified = True

                _liberar_descuento_si_corresponde(
                    pedido
                )

                if pedido is not None:
                    registrar_error_inicio_pago(
                        pedido=pedido,
                        mensaje=str(error),
                    )

                logger.warning(
                    (
                        "No fue posible iniciar el pago "
                        "del pedido %s: %s"
                    ),
                    (
                        pedido.numero
                        if pedido is not None
                        else "sin pedido"
                    ),
                    error,
                )

                form.add_error(
                    None,
                    str(error),
                )

            # =================================================================
            # ERROR CONTROLADO
            # =================================================================

            except ValueError as error:

                request.session.pop(
                    "pedido_pago_en_curso",
                    None,
                )

                request.session.modified = True

                _liberar_descuento_si_corresponde(
                    pedido
                )

                logger.warning(
                    (
                        "Error validando checkout. "
                        "Pedido=%s. Error=%s"
                    ),
                    (
                        pedido.numero
                        if pedido is not None
                        else "sin pedido"
                    ),
                    error,
                )

                form.add_error(
                    None,
                    str(error),
                )

            # =================================================================
            # ERROR INESPERADO
            # =================================================================

            except Exception as error:

                request.session.pop(
                    "pedido_pago_en_curso",
                    None,
                )

                request.session.modified = True

                _liberar_descuento_si_corresponde(
                    pedido
                )

                logger.exception(
                    (
                        "Error inesperado procesando "
                        "el checkout: %s"
                    ),
                    error,
                )

                form.add_error(
                    None,
                    (
                        "No fue posible procesar "
                        "el pedido. Intenta nuevamente."
                    ),
                )

    else:

        form = CheckoutForm(
            initial=datos_iniciales,
        )

    # =========================================================================
    # CÓDIGO, RUT Y REGIÓN PARA EL RESUMEN
    # =========================================================================
    #
    # El RUT se utiliza para validar que el cliente no haya utilizado
    # anteriormente el mismo código.
    #
    # La región se utiliza para calcular Blue Express.
    # =========================================================================

    if request.method == "POST":

        codigo_descuento = (
            request.POST.get(
                "codigo_descuento",
                "",
            )
            or ""
        ).strip().upper()

        rut_descuento = (
            request.POST.get(
                "rut",
                "",
            )
            or ""
        ).strip()

        region_envio = (
            request.POST.get(
                "region",
                "",
            )
            or ""
        ).strip()

    else:

        codigo_descuento = ""

        rut_descuento = (
            datos_iniciales.get(
                "rut",
                "",
            )
            or ""
        ).strip()

        region_envio = (
            datos_iniciales.get(
                "region",
                "",
            )
            or ""
        ).strip()

    # =========================================================================
    # RESUMEN
    # =========================================================================

    resumen = calcular_resumen_checkout(
        request=request,

        carrito_serializado=(
            carrito_serializado
        ),

        codigo=(
            codigo_descuento
        ),

        rut=(
            rut_descuento
        ),

        region=(
            region_envio
        ),
    )

    # =========================================================================
    # PREMIOS PERSONALES
    # =========================================================================

    codigos_fidelidad = (
        obtener_codigos_disponibles(
            request.user
        )
    )

    # =========================================================================
    # CONTEXTO
    # =========================================================================

    contexto = {
        "form": (
            form
        ),

        "carrito": (
            carrito_serializado
        ),

        "resumen": (
            resumen
        ),

        "codigos_fidelidad": (
            codigos_fidelidad
        ),

        "comunas_por_region": (
            COMUNAS_POR_REGION
        ),
    }

    # =========================================================================
    # RENDER
    # =========================================================================

    return render(
        request,
        "core/checkout.html",
        contexto,
    )







@require_POST
def checkout_resumen_descuento(
    request,
):
    """
    Recalcula dinámicamente el resumen del checkout.

    Incluye:

    - código de descuento;
    - subtotal;
    - descuento adicional;
    - subtotal con descuento;
    - despacho Blue Express;
    - total final.

    IMPORTANTE:

    Un código solamente se considera visualmente aplicado
    cuando genera un descuento REAL mayor que $0.

    El despacho puede cotizarse desde que el usuario
    selecciona región y comuna.
    """

    # =========================================================================
    # CARRITO
    # =========================================================================

    carrito = _obtener_carrito(
        request
    )

    if not carrito:
        return JsonResponse(
            {
                "ok": False,

                "mensaje": (
                    "Tu carrito está vacío."
                ),

                "codigo_aplicado": "",

                "tiene_descuento_aplicado": False,

                "porcentaje_descuento": 0,

                "descuento": 0,

                "descuento_formateado": "$0",

                "subtotal": 0,

                "subtotal_formateado": "$0",

                "subtotal_con_descuento": 0,

                "subtotal_con_descuento_formateado": "$0",

                "despacho": 0,

                "despacho_formateado": (
                    "Selecciona región y comuna"
                ),

                "total": 0,

                "total_formateado": "$0",
            },
            status=400,
        )

    carrito_serializado = (
        _serializar_carrito(
            request
        )
    )

    if carrito_serializado.get(
        "vacio",
        True,
    ):
        return JsonResponse(
            {
                "ok": False,

                "mensaje": (
                    "Tu carrito está vacío."
                ),

                "codigo_aplicado": "",

                "tiene_descuento_aplicado": False,

                "porcentaje_descuento": 0,

                "descuento": 0,

                "descuento_formateado": "$0",

                "subtotal": 0,

                "subtotal_formateado": "$0",

                "subtotal_con_descuento": 0,

                "subtotal_con_descuento_formateado": "$0",

                "despacho": 0,

                "despacho_formateado": (
                    "Selecciona región y comuna"
                ),

                "total": 0,

                "total_formateado": "$0",
            },
            status=400,
        )

    # =========================================================================
    # DATOS RECIBIDOS
    # =========================================================================

    codigo = (
        request.POST.get(
            "codigo_descuento",
            "",
        )
        or ""
    ).strip().upper()

    rut = (
        request.POST.get(
            "rut",
            "",
        )
        or ""
    ).strip().upper()

    region = (
        request.POST.get(
            "region",
            "",
        )
        or ""
    ).strip()

    comuna = (
        request.POST.get(
            "comuna",
            "",
        )
        or ""
    ).strip()

    direccion = (
        request.POST.get(
            "direccion",
            "",
        )
        or ""
    ).strip()

    numero_direccion = (
        request.POST.get(
            "numero_direccion",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # DATOS NECESARIOS PARA COTIZAR DESPACHO
    # =========================================================================
    #
    # Para mostrar el costo de despacho dinámicamente
    # solamente exigimos:
    #
    # - región;
    # - comuna.
    #
    # Dirección y número siguen siendo recibidos y pueden
    # continuar siendo obligatorios al confirmar el pedido,
    # pero ya no bloquean la cotización del despacho.
    # =========================================================================

    datos_envio_completos = all(
        [
            region,
            comuna,
        ]
    )

    # =========================================================================
    # CALCULAR RESUMEN
    # =========================================================================

    resumen = calcular_resumen_checkout(
        request=request,

        carrito_serializado=(
            carrito_serializado
        ),

        codigo=codigo,

        rut=rut,

        region=(
            region
            if datos_envio_completos
            else ""
        ),
    )

    # =========================================================================
    # MONTOS
    # =========================================================================

    subtotal = Decimal(
        str(
            resumen.get(
                "subtotal",
                0,
            )
            or 0
        )
    )

    descuento = Decimal(
        str(
            resumen.get(
                "descuento",
                0,
            )
            or 0
        )
    )

    subtotal_con_descuento = Decimal(
        str(
            resumen.get(
                "subtotal_con_descuento",
                subtotal,
            )
            or 0
        )
    )

    despacho = Decimal(
        str(
            resumen.get(
                "despacho",
                0,
            )
            or 0
        )
    )

    total = Decimal(
        str(
            resumen.get(
                "total",
                0,
            )
            or 0
        )
    )

    porcentaje = Decimal(
        str(
            resumen.get(
                "porcentaje_descuento",
                0,
            )
            or 0
        )
    )

    # =========================================================================
    # RESULTADO DEL CÓDIGO
    # =========================================================================

    codigo_aplicado = (
        resumen.get(
            "codigo_aplicado",
            "",
        )
        or ""
    ).strip().upper()

    error_descuento = (
        resumen.get(
            "error_descuento",
            "",
        )
        or ""
    )

    # -------------------------------------------------------------------------
    # ESTA ES LA REGLA IMPORTANTE
    # -------------------------------------------------------------------------

    tiene_descuento_aplicado = bool(
        codigo_aplicado
        and descuento > 0
        and not error_descuento
    )

    # -------------------------------------------------------------------------
    # Si no existe descuento real, limpiamos el código del resultado visual.
    # -------------------------------------------------------------------------

    if not tiene_descuento_aplicado:
        codigo_aplicado = ""

        descuento = Decimal(
            "0"
        )

        porcentaje = Decimal(
            "0"
        )

        subtotal_con_descuento = (
            subtotal
        )

    # =========================================================================
    # BLUE EXPRESS
    # =========================================================================

    error_despacho = (
        resumen.get(
            "error_despacho",
            "",
        )
        or ""
    )

    talla_envio = (
        resumen.get(
            "talla_envio",
            "",
        )
        or ""
    )

    zona_envio = (
        resumen.get(
            "zona_envio",
            "",
        )
        or ""
    )

    cantidad_envio = int(
        resumen.get(
            "cantidad_envio",
            0,
        )
        or 0
    )

    # =========================================================================
    # FORMATEADOR CLP
    # =========================================================================

    def formatear_pesos(
        valor,
    ):
        valor_entero = int(
            Decimal(
                str(
                    valor
                    or 0
                )
            )
        )

        return (
            f"${valor_entero:,}"
            .replace(
                ",",
                ".",
            )
        )

    # =========================================================================
    # MENSAJE DEL CÓDIGO
    # =========================================================================

    if error_descuento:
        mensaje = (
            error_descuento
        )

    elif tiene_descuento_aplicado:

        if porcentaje > 0:
            mensaje = (
                f"Código {codigo_aplicado} aplicado: "
                f"{porcentaje:g}% de descuento."
            )

        else:
            mensaje = (
                f"Código {codigo_aplicado} aplicado: "
                f"{formatear_pesos(descuento)} "
                "de descuento."
            )

    elif codigo:
        mensaje = (
            "El código no generó un descuento aplicable."
        )

    else:
        mensaje = (
            "Puedes usar un código general "
            "o un premio personal."
        )

    # =========================================================================
    # DESPACHO
    # =========================================================================

    if not datos_envio_completos:
        despacho_formateado = (
            "Selecciona región y comuna"
        )

    elif error_despacho:
        despacho_formateado = (
            "No disponible"
        )

    elif despacho > 0:
        despacho_formateado = (
            formatear_pesos(
                despacho
            )
        )

    else:
        despacho_formateado = (
            "No disponible"
        )

    # =========================================================================
    # RESPUESTA JSON
    # =========================================================================

    return JsonResponse(
        {
            "ok": not bool(
                error_descuento
                or error_despacho
            ),

            "mensaje": mensaje,

            # -----------------------------------------------------------------
            # SUBTOTAL
            # -----------------------------------------------------------------

            "subtotal": int(
                subtotal
            ),

            "subtotal_formateado": (
                formatear_pesos(
                    subtotal
                )
            ),

            # -----------------------------------------------------------------
            # DESCUENTO ADICIONAL
            # -----------------------------------------------------------------

            "tiene_descuento_aplicado": (
                tiene_descuento_aplicado
            ),

            "codigo_aplicado": (
                codigo_aplicado
            ),

            "porcentaje_descuento": float(
                porcentaje
            ),

            "descuento": int(
                descuento
            ),

            "descuento_formateado": (
                formatear_pesos(
                    descuento
                )
            ),

            # -----------------------------------------------------------------
            # SUBTOTAL CON DESCUENTO
            # -----------------------------------------------------------------

            "subtotal_con_descuento": int(
                subtotal_con_descuento
            ),

            "subtotal_con_descuento_formateado": (
                formatear_pesos(
                    subtotal_con_descuento
                )
            ),

            # -----------------------------------------------------------------
            # DESPACHO
            # -----------------------------------------------------------------

            "despacho": int(
                despacho
            ),

            "despacho_formateado": (
                despacho_formateado
            ),

            "talla_envio": (
                talla_envio
            ),

            "zona_envio": (
                zona_envio
            ),

            "cantidad_envio": (
                cantidad_envio
            ),

            "error_despacho": (
                error_despacho
            ),

            # -----------------------------------------------------------------
            # TOTAL FINAL
            # -----------------------------------------------------------------

            "total": int(
                total
            ),

            "total_formateado": (
                formatear_pesos(
                    total
                )
            ),
        }
    )

def calcular_resumen_checkout(
    *,
    request,
    carrito_serializado,
    codigo="",
    rut="",
    region="",
):
    """
    Calcula el resumen económico completo del checkout.

    Orden de cálculo:

    1. subtotal de productos, ya considerando ofertas;
    2. descuento adicional por código;
    3. subtotal después del código;
    4. despacho Blue Express;
    5. total final.

    Un código solamente se considera aplicado cuando
    genera un descuento efectivo mayor que $0.
    """

    # =========================================================================
    # SUBTOTAL
    # =========================================================================

    subtotal = Decimal(
        str(
            carrito_serializado.get(
                "subtotal",
                0,
            )
            or 0
        )
    )

    # =========================================================================
    # NORMALIZAR
    # =========================================================================

    codigo = (
        codigo
        or ""
    ).strip().upper()

    rut = (
        rut
        or ""
    ).strip().upper()

    region = (
        region
        or ""
    ).strip()

    # =========================================================================
    # VALORES INICIALES DEL DESCUENTO
    # =========================================================================

    descuento = Decimal(
        "0"
    )

    porcentaje = Decimal(
        "0"
    )

    codigo_aplicado = ""

    tipo_descuento = (
        Pedido.TipoDescuento.NINGUNO
    )

    error_descuento = ""

    # =========================================================================
    # RESOLVER DESCUENTO
    # =========================================================================

    try:
        resultado_descuento = (
            resolver_descuento(
                usuario=request.user,
                rut=rut,
                subtotal=subtotal,
                codigo=codigo,
                bloquear=False,
            )
        )

    except DescuentoError as error:
        resultado_descuento = None

        error_descuento = str(
            error
        )

    # =========================================================================
    # RESULTADO
    # =========================================================================

    if resultado_descuento is not None:

        descuento = Decimal(
            str(
                resultado_descuento.descuento
                or 0
            )
        )

        porcentaje = Decimal(
            str(
                resultado_descuento.porcentaje
                or 0
            )
        )

        codigo_resultado = (
            resultado_descuento.codigo
            or ""
        ).strip().upper()

        tipo_resultado = (
            resultado_descuento.tipo
            or Pedido.TipoDescuento.NINGUNO
        )

        # ---------------------------------------------------------------------
        # PROTEGER EL DESCUENTO
        # ---------------------------------------------------------------------

        descuento = max(
            min(
                descuento,
                subtotal,
            ),
            Decimal(
                "0"
            ),
        )

        # ---------------------------------------------------------------------
        # IMPORTANTE:
        # solamente aceptamos el código como aplicado si produce ahorro real.
        # ---------------------------------------------------------------------

        if (
            codigo_resultado
            and descuento > 0
        ):
            codigo_aplicado = (
                codigo_resultado
            )

            tipo_descuento = (
                tipo_resultado
            )

        else:
            descuento = Decimal(
                "0"
            )

            porcentaje = Decimal(
                "0"
            )

            codigo_aplicado = ""

            tipo_descuento = (
                Pedido.TipoDescuento.NINGUNO
            )

    # =========================================================================
    # SUBTOTAL CON DESCUENTO ADICIONAL
    # =========================================================================

    subtotal_con_descuento = max(
        subtotal - descuento,
        Decimal(
            "0"
        ),
    )

    # =========================================================================
    # DESPACHO BLUE EXPRESS
    # =========================================================================

    despacho = Decimal(
        "0"
    )

    talla_envio = ""
    zona_envio = ""
    cantidad_envio = 0

    error_despacho = ""

    if region:

        try:
            cotizacion = (
                cotizar_blue_express(
                    carrito_serializado=(
                        carrito_serializado
                    ),
                    region=region,
                )
            )

            despacho = Decimal(
                str(
                    cotizacion.costo
                    or 0
                )
            )

            talla_envio = str(
                cotizacion.talla
                or ""
            )

            zona_envio = str(
                cotizacion.zona
                or ""
            )

            cantidad_envio = int(
                cotizacion.cantidad_productos
                or 0
            )

            if despacho <= 0:
                raise ValueError(
                    (
                        "Blue Express devolvió "
                        "una tarifa de despacho "
                        "igual o inferior a $0."
                    )
                )

            if cantidad_envio <= 0:
                raise ValueError(
                    (
                        "No fue posible determinar "
                        "la cantidad de productos "
                        "para calcular el despacho."
                    )
                )

            if not talla_envio:
                raise ValueError(
                    (
                        "No fue posible determinar "
                        "la talla del despacho."
                    )
                )

            if not zona_envio:
                raise ValueError(
                    (
                        "No fue posible determinar "
                        "la zona del despacho."
                    )
                )

        except ValueError as error:
            despacho = Decimal(
                "0"
            )

            talla_envio = ""
            zona_envio = ""
            cantidad_envio = 0

            error_despacho = str(
                error
            )

    # =========================================================================
    # TOTAL FINAL
    # =========================================================================

    total = max(
        subtotal_con_descuento
        + despacho,
        Decimal(
            "0"
        ),
    )

    # =========================================================================
    # INDICADOR DE DESCUENTO REAL
    # =========================================================================

    tiene_descuento_aplicado = bool(
        codigo_aplicado
        and descuento > 0
    )

    # =========================================================================
    # RESPUESTA
    # =========================================================================

    return {
        # ---------------------------------------------------------------------
        # PRODUCTOS
        # ---------------------------------------------------------------------

        "subtotal": (
            subtotal
        ),

        # ---------------------------------------------------------------------
        # DESCUENTO ADICIONAL
        # ---------------------------------------------------------------------

        "tiene_descuento_aplicado": (
            tiene_descuento_aplicado
        ),

        "descuento": (
            descuento
        ),

        "porcentaje_descuento": (
            porcentaje
        ),

        "codigo_aplicado": (
            codigo_aplicado
        ),

        "tipo_descuento": (
            tipo_descuento
        ),

        "error_descuento": (
            error_descuento
        ),

        # ---------------------------------------------------------------------
        # SUBTOTAL DESPUÉS DEL DESCUENTO
        # ---------------------------------------------------------------------

        "subtotal_con_descuento": (
            subtotal_con_descuento
        ),

        # ---------------------------------------------------------------------
        # BLUE EXPRESS
        # ---------------------------------------------------------------------

        "despacho": (
            despacho
        ),

        "talla_envio": (
            talla_envio
        ),

        "zona_envio": (
            zona_envio
        ),

        "cantidad_envio": (
            cantidad_envio
        ),

        "error_despacho": (
            error_despacho
        ),

        # ---------------------------------------------------------------------
        # TOTAL FINAL
        # ---------------------------------------------------------------------

        "total": (
            total
        ),
    }


def valor_mercadopago_valido(valor):
    if valor is None:
        return False

    valor = str(valor).strip()

    return (
        bool(valor)
        and valor.lower()
        not in {
            "null",
            "none",
            "undefined",
        }
    )


@require_GET
def pedido_confirmacion(
    request,
    numero,
):
    """
    Página central de resultado de un pedido.

    Selecciona automáticamente el template según
    el estado REAL del pago.

    Estados soportados:

    - aprobado
    - rechazado
    - cancelado
    - pendiente
    - revision
    - reembolsado

    Los templates se encuentran en:

    core/templates/core/pagos/
    """

    # =========================================================================
    # OBTENER PEDIDO
    # =========================================================================

    pedido = get_object_or_404(
        Pedido.objects
        .select_related(
            "usuario",
        )
        .prefetch_related(
            "items__producto__categoria",
        ),
        numero=numero,
    )

    # =========================================================================
    # CONTROL DE ACCESO
    # =========================================================================

    if pedido.usuario_id:

        if not request.user.is_authenticated:
            return redirect(
                "core:inicio"
            )

        if (
            pedido.usuario_id
            != request.user.pk
            and not request.user.is_staff
        ):
            return redirect(
                "core:inicio"
            )

    # =========================================================================
    # NORMALIZAR MÉTODO DE PAGO
    # =========================================================================

    metodo_pago = str(
        pedido.metodo_pago
        or ""
    ).strip().lower()

    # =========================================================================
    # PROVEEDOR
    # =========================================================================

    if (
        metodo_pago
        == Pedido.MetodoPago.WEBPAY
    ):

        proveedor = "webpay"

        proveedor_nombre = (
            "Webpay Plus"
        )

        proveedor_empresa = (
            "Transbank"
        )

    elif (
        metodo_pago
        == Pedido.MetodoPago.MERCADOPAGO
    ):

        proveedor = "mercadopago"

        proveedor_nombre = (
            "Mercado Pago"
        )

        proveedor_empresa = (
            "Mercado Pago"
        )

    elif (
        metodo_pago
        == Pedido.MetodoPago.TRANSFERENCIA
    ):

        proveedor = "transferencia"

        proveedor_nombre = (
            "Transferencia bancaria"
        )

        proveedor_empresa = (
            "Audex"
        )

    else:

        proveedor = "otro"

        proveedor_nombre = (
            pedido.get_metodo_pago_display()
            if pedido.metodo_pago
            else "Método de pago"
        )

        proveedor_empresa = ""

    # =========================================================================
    # CONTEXTO BASE
    # =========================================================================

    contexto = {
        "pedido": pedido,
        "proveedor": proveedor,
        "proveedor_nombre": (
            proveedor_nombre
        ),
        "proveedor_empresa": (
            proveedor_empresa
        ),
    }

    # =========================================================================
    # APROBADO
    # =========================================================================

    pago_aprobado = bool(
        pedido.pagado
        and pedido.estado_pago
        == Pedido.EstadoPago.APROBADO
    )

    if pago_aprobado:

        contexto.update(
            {
                "resultado": "aprobado",

                "titulo_resultado": (
                    "¡Tu compra fue confirmada!"
                ),

                "mensaje_resultado": (
                    "Recibimos correctamente "
                    "el pago de tu pedido."
                ),
            }
        )

        logger.info(
            (
                "Resultado pago aprobado. "
                "Pedido=%s proveedor=%s."
            ),
            pedido.numero,
            proveedor,
        )

        return render(
            request,
            "core/pagos/pago_exitoso.html",
            contexto,
            status=200,
        )

    # =========================================================================
    # ESTADO DE PAGO
    # =========================================================================

    estado_pago = (
        pedido.estado_pago
    )

    # =========================================================================
    # RECHAZADO
    # =========================================================================

    if (
        estado_pago
        == Pedido.EstadoPago.RECHAZADO
    ):

        contexto["resultado"] = (
            "rechazado"
        )

        if proveedor == "webpay":

            contexto[
                "titulo_resultado"
            ] = (
                "Tu pago con Webpay "
                "fue rechazado"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "Transbank no aprobó la "
                "transacción. No se confirmó "
                "ningún cobro para este pedido."
            )

        elif proveedor == "mercadopago":

            contexto[
                "titulo_resultado"
            ] = (
                "Tu pago con Mercado Pago "
                "fue rechazado"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "Mercado Pago no aprobó "
                "la transacción. Puedes "
                "intentarlo nuevamente."
            )

        else:

            contexto[
                "titulo_resultado"
            ] = (
                "Tu pago fue rechazado"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "El proveedor no pudo "
                "aprobar la transacción."
            )

        logger.warning(
            (
                "Resultado pago rechazado. "
                "Pedido=%s proveedor=%s."
            ),
            pedido.numero,
            proveedor,
        )

        return render(
            request,
            "core/pagos/pago_rechazado.html",
            contexto,
            status=200,
        )

    # =========================================================================
    # CANCELADO
    # =========================================================================

    if (
        estado_pago
        == Pedido.EstadoPago.CANCELADO
    ):

        contexto["resultado"] = (
            "cancelado"
        )

        if proveedor == "webpay":

            contexto[
                "titulo_resultado"
            ] = (
                "Cancelaste el pago "
                "con Webpay"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "La operación con Webpay "
                "fue cancelada antes de "
                "completarse."
            )

        elif proveedor == "mercadopago":

            contexto[
                "titulo_resultado"
            ] = (
                "Cancelaste el pago "
                "con Mercado Pago"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "La operación fue cancelada "
                "antes de que Mercado Pago "
                "confirmara el pago."
            )

        else:

            contexto[
                "titulo_resultado"
            ] = (
                "Pago cancelado"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "La operación fue cancelada "
                "antes de completarse."
            )

        logger.info(
            (
                "Resultado pago cancelado. "
                "Pedido=%s proveedor=%s."
            ),
            pedido.numero,
            proveedor,
        )

        return render(
            request,
            "core/pagos/pago_cancelado.html",
            contexto,
            status=200,
        )

    # =========================================================================
    # REEMBOLSADO
    # =========================================================================

    if (
        estado_pago
        == Pedido.EstadoPago.REEMBOLSADO
    ):

        contexto.update(
            {
                "resultado": (
                    "reembolsado"
                ),

                "titulo_resultado": (
                    "Tu pago fue reembolsado"
                ),

                "mensaje_resultado": (
                    "Este pedido registra "
                    "un pago que posteriormente "
                    "fue reembolsado."
                ),
            }
        )

        logger.info(
            (
                "Resultado pago reembolsado. "
                "Pedido=%s proveedor=%s."
            ),
            pedido.numero,
            proveedor,
        )

        return render(
            request,
            (
                "core/pagos/"
                "pago_reembolsado.html"
            ),
            contexto,
            status=200,
        )

    # =========================================================================
    # REVISIÓN
    # =========================================================================

    if (
        estado_pago
        == Pedido.EstadoPago.REVISION
    ):

        contexto.update(
            {
                "resultado": "revision",

                "titulo_resultado": (
                    "Estamos revisando "
                    "tu pago"
                ),

                "mensaje_resultado": (
                    "Recibimos información "
                    "del proveedor, pero "
                    "necesitamos verificarla "
                    "antes de confirmar "
                    "definitivamente el pedido."
                ),
            }
        )

        logger.warning(
            (
                "Resultado pago revisión. "
                "Pedido=%s proveedor=%s."
            ),
            pedido.numero,
            proveedor,
        )

        return render(
            request,
            "core/pagos/pago_revision.html",
            contexto,
            status=202,
        )

    # =========================================================================
    # PENDIENTE / INICIADO
    # =========================================================================

    if estado_pago in {
        Pedido.EstadoPago.PENDIENTE,
        Pedido.EstadoPago.INICIADO,
    }:

        contexto["resultado"] = (
            "pendiente"
        )

        if proveedor == "webpay":

            contexto[
                "titulo_resultado"
            ] = (
                "El pago con Webpay "
                "aún no está confirmado"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "Todavía no tenemos una "
                "confirmación definitiva "
                "de Transbank para este pedido."
            )

        elif proveedor == "mercadopago":

            contexto[
                "titulo_resultado"
            ] = (
                "El pago con Mercado Pago "
                "aún está pendiente"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "Mercado Pago todavía no "
                "ha confirmado definitivamente "
                "esta transacción."
            )

        elif proveedor == "transferencia":

            contexto[
                "titulo_resultado"
            ] = (
                "Transferencia pendiente "
                "de confirmación"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "Tu pedido está registrado "
                "y todavía estamos esperando "
                "confirmar la transferencia."
            )

        else:

            contexto[
                "titulo_resultado"
            ] = (
                "Pago pendiente"
            )

            contexto[
                "mensaje_resultado"
            ] = (
                "Este pedido todavía no "
                "tiene un pago confirmado."
            )

        logger.info(
            (
                "Resultado pago pendiente. "
                "Pedido=%s proveedor=%s "
                "estado_pago=%s."
            ),
            pedido.numero,
            proveedor,
            estado_pago,
        )

        return render(
            request,
            "core/pagos/pago_pendiente.html",
            contexto,
            status=202,
        )

    # =========================================================================
    # ESTADO NO RECONOCIDO
    # =========================================================================

    contexto.update(
        {
            "resultado": "revision",

            "titulo_resultado": (
                "No pudimos determinar "
                "el estado del pago"
            ),

            "mensaje_resultado": (
                "El pedido existe, pero "
                "su estado de pago requiere "
                "una revisión."
            ),
        }
    )

    logger.error(
        (
            "Estado de pago no reconocido. "
            "Pedido=%s proveedor=%s "
            "estado_pago=%s."
        ),
        pedido.numero,
        proveedor,
        estado_pago,
    )

    return render(
        request,
        "core/pagos/pago_revision.html",
        contexto,
        status=202,
    )














@require_GET
def mercadopago_retorno_exitoso(
    request,
    numero,
):
    """
    Procesa el retorno SUCCESS de Mercado Pago.

    Mercado Pago puede redirigir al navegador antes
    de que el webhook termine de procesarse.

    Esta vista:

    - obtiene el Pedido;
    - valida acceso;
    - consulta el pago real;
    - valida referencia y monto;
    - persiste el estado real;
    - confirma pagos aprobados;
    - vacía carrito solo cuando corresponde;
    - redirige siempre a pedido_confirmacion(),
      que selecciona el template correcto.
    """

    # =========================================================================
    # PEDIDO
    # =========================================================================

    pedido = get_object_or_404(
        Pedido.objects
        .select_related(
            "usuario",
        )
        .prefetch_related(
            "items__producto__categoria",
        ),
        numero=numero,
    )

    # =========================================================================
    # CONTROL DE ACCESO
    # =========================================================================

    if pedido.usuario_id:

        if not request.user.is_authenticated:
            return redirect(
                "core:inicio"
            )

        if (
            pedido.usuario_id
            != request.user.pk
            and not request.user.is_staff
        ):
            return redirect(
                "core:inicio"
            )

    # =========================================================================
    # SI YA ESTÁ APROBADO
    # =========================================================================

    if pedido.pago_aprobado:

        carrito_vaciado = (
            _vaciar_carrito_pago_confirmado(
                request,
                pedido,
            )
        )

        logger.info(
            (
                "Retorno Mercado Pago. "
                "Pedido=%s ya aprobado. "
                "Carrito_vaciado=%s."
            ),
            pedido.numero,
            carrito_vaciado,
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # DATOS RETORNADOS
    # =========================================================================

    payment_id = (
        request.GET.get(
            "payment_id"
        )
        or request.GET.get(
            "collection_id"
        )
        or ""
    ).strip()

    status_retorno = (
        request.GET.get(
            "status"
        )
        or request.GET.get(
            "collection_status"
        )
        or ""
    ).strip().lower()

    referencia_retorno = (
        request.GET.get(
            "external_reference"
        )
        or ""
    ).strip()

    preference_id = (
        request.GET.get(
            "preference_id"
        )
        or ""
    ).strip()

    logger.info(
        (
            "Retorno SUCCESS Mercado Pago. "
            "Pedido=%s "
            "payment_id=%s "
            "status=%s "
            "external_reference=%s "
            "preference_id=%s."
        ),
        pedido.numero,
        payment_id or "vacío",
        status_retorno or "vacío",
        referencia_retorno or "vacía",
        preference_id or "vacía",
    )

    # =========================================================================
    # VALIDAR REFERENCIA DEL RETORNO
    # =========================================================================

    if (
        referencia_retorno
        and referencia_retorno
        != pedido.numero
    ):

        logger.error(
            (
                "Retorno Mercado Pago inválido. "
                "Pedido=%s referencia=%s."
            ),
            pedido.numero,
            referencia_retorno,
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.REVISION
        )

        pedido.save(
            update_fields=[
                "estado_pago",
                "actualizado",
            ]
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # GUARDAR PREFERENCE ID
    # =========================================================================

    if preference_id:

        pedido.mercadopago_preference_id = (
            preference_id
        )

        pedido.save(
            update_fields=[
                "mercadopago_preference_id",
                "actualizado",
            ]
        )

    # =========================================================================
    # CONSULTAR PAGO
    # =========================================================================

    if payment_id:

        try:

            pago = obtener_pago(
                payment_id
            )

            if not isinstance(
                pago,
                dict,
            ):
                raise MercadoPagoError(
                    (
                        "Mercado Pago devolvió "
                        "un pago inválido."
                    )
                )

            # =================================================================
            # DATOS REALES DEL PAGO
            # =================================================================

            estado_pago_mp = (
                str(
                    pago.get(
                        "status"
                    )
                    or ""
                )
                .strip()
                .lower()
            )

            status_detail = (
                str(
                    pago.get(
                        "status_detail"
                    )
                    or ""
                )
                .strip()
            )

            referencia_pago = (
                str(
                    pago.get(
                        "external_reference"
                    )
                    or ""
                )
                .strip()
            )

            payment_type = (
                str(
                    pago.get(
                        "payment_type_id"
                    )
                    or ""
                )
                .strip()
            )

            monto_pago = Decimal(
                str(
                    pago.get(
                        "transaction_amount"
                    )
                    or "0"
                )
            )

            logger.info(
                (
                    "Pago Mercado Pago consultado. "
                    "Pedido=%s "
                    "payment_id=%s "
                    "status=%s "
                    "status_detail=%s "
                    "referencia=%s "
                    "monto=%s."
                ),
                pedido.numero,
                payment_id,
                estado_pago_mp,
                status_detail,
                referencia_pago,
                monto_pago,
            )

            # =================================================================
            # VALIDAR REFERENCIA
            # =================================================================

            if (
                referencia_pago
                != pedido.numero
            ):
                raise MercadoPagoError(
                    (
                        "El pago consultado no pertenece "
                        "al pedido actual. "
                        f"Pedido={pedido.numero}, "
                        f"referencia={referencia_pago}."
                    )
                )

            # =================================================================
            # VALIDAR MONTO
            # =================================================================

            total_pedido = Decimal(
                str(
                    pedido.total
                    or 0
                )
            )

            if (
                monto_pago
                != total_pedido
            ):

                pedido.pagado = False

                pedido.estado_pago = (
                    Pedido.EstadoPago.REVISION
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_pago_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.mercadopago_payment_type = (
                    payment_type
                )

                pedido.mercadopago_transaction_amount = (
                    monto_pago
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado_pago",
                        "mercadopago_payment_id",
                        "mercadopago_status",
                        "mercadopago_status_detail",
                        "mercadopago_payment_type",
                        "mercadopago_transaction_amount",
                        "actualizado",
                    ]
                )

                logger.error(
                    (
                        "Monto Mercado Pago distinto. "
                        "Pedido=%s pedido_total=%s "
                        "mp_total=%s."
                    ),
                    pedido.numero,
                    total_pedido,
                    monto_pago,
                )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # APROBADO
            # =================================================================

            if (
                estado_pago_mp
                == "approved"
            ):

                confirmar_pago_mercadopago(
                    pago
                )

                pedido.refresh_from_db()

                if pedido.pago_aprobado:

                    carrito_vaciado = (
                        _vaciar_carrito_pago_confirmado(
                            request,
                            pedido,
                        )
                    )

                    logger.info(
                        (
                            "Mercado Pago aprobado desde retorno. "
                            "Pedido=%s payment_id=%s "
                            "carrito_vaciado=%s."
                        ),
                        pedido.numero,
                        payment_id,
                        carrito_vaciado,
                    )

                    return redirect(
                        "core:pedido_confirmacion",
                        numero=pedido.numero,
                    )

            # =================================================================
            # PENDIENTE
            # =================================================================

            if estado_pago_mp in {
                "pending",
                "in_process",
                "in_mediation",
                "authorized",
            }:

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.PENDIENTE
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.PENDIENTE
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_pago_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.mercadopago_payment_type = (
                    payment_type
                )

                pedido.mercadopago_transaction_amount = (
                    monto_pago
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado",
                        "estado_pago",
                        "mercadopago_payment_id",
                        "mercadopago_status",
                        "mercadopago_status_detail",
                        "mercadopago_payment_type",
                        "mercadopago_transaction_amount",
                        "actualizado",
                    ]
                )

                logger.info(
                    (
                        "Mercado Pago pendiente persistido. "
                        "Pedido=%s status=%s."
                    ),
                    pedido.numero,
                    estado_pago_mp,
                )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # RECHAZADO
            # =================================================================

            if (
                estado_pago_mp
                == "rejected"
            ):

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.CANCELADO
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.RECHAZADO
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_pago_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.mercadopago_payment_type = (
                    payment_type
                )

                pedido.mercadopago_transaction_amount = (
                    monto_pago
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado",
                        "estado_pago",
                        "mercadopago_payment_id",
                        "mercadopago_status",
                        "mercadopago_status_detail",
                        "mercadopago_payment_type",
                        "mercadopago_transaction_amount",
                        "actualizado",
                    ]
                )

                try:
                    _liberar_descuento_si_corresponde(
                        pedido
                    )

                except Exception:

                    logger.exception(
                        (
                            "No se pudo liberar descuento "
                            "tras rechazo Mercado Pago. "
                            "Pedido=%s."
                        ),
                        pedido.numero,
                    )

                logger.warning(
                    (
                        "Mercado Pago rechazado persistido. "
                        "Pedido=%s payment_id=%s."
                    ),
                    pedido.numero,
                    payment_id,
                )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # CANCELADO
            # =================================================================

            if estado_pago_mp in {
                "cancelled",
                "canceled",
            }:

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.CANCELADO
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.CANCELADO
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_pago_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.mercadopago_payment_type = (
                    payment_type
                )

                pedido.mercadopago_transaction_amount = (
                    monto_pago
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado",
                        "estado_pago",
                        "mercadopago_payment_id",
                        "mercadopago_status",
                        "mercadopago_status_detail",
                        "mercadopago_payment_type",
                        "mercadopago_transaction_amount",
                        "actualizado",
                    ]
                )

                try:
                    _liberar_descuento_si_corresponde(
                        pedido
                    )

                except Exception:

                    logger.exception(
                        (
                            "No se pudo liberar descuento "
                            "tras cancelación Mercado Pago. "
                            "Pedido=%s."
                        ),
                        pedido.numero,
                    )

                logger.info(
                    (
                        "Mercado Pago cancelado persistido. "
                        "Pedido=%s payment_id=%s."
                    ),
                    pedido.numero,
                    payment_id,
                )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # ESTADO NO CONTEMPLADO
            # =================================================================

            pedido.pagado = False

            pedido.estado_pago = (
                Pedido.EstadoPago.REVISION
            )

            pedido.mercadopago_payment_id = (
                payment_id
            )

            pedido.mercadopago_status = (
                estado_pago_mp
            )

            pedido.mercadopago_status_detail = (
                status_detail
            )

            pedido.save(
                update_fields=[
                    "pagado",
                    "estado_pago",
                    "mercadopago_payment_id",
                    "mercadopago_status",
                    "mercadopago_status_detail",
                    "actualizado",
                ]
            )

            logger.warning(
                (
                    "Estado Mercado Pago no contemplado. "
                    "Pedido=%s status=%s. "
                    "Marcado para revisión."
                ),
                pedido.numero,
                estado_pago_mp,
            )

        except MercadoPagoError as error:

            logger.exception(
                (
                    "Error verificando Mercado Pago. "
                    "Pedido=%s payment_id=%s: %s"
                ),
                pedido.numero,
                payment_id,
                error,
            )

            pedido.estado_pago = (
                Pedido.EstadoPago.REVISION
            )

            pedido.save(
                update_fields=[
                    "estado_pago",
                    "actualizado",
                ]
            )

        except ConfirmacionPagoError as error:

            logger.exception(
                (
                    "Error confirmando Mercado Pago. "
                    "Pedido=%s payment_id=%s: %s"
                ),
                pedido.numero,
                payment_id,
                error,
            )

            pedido.estado_pago = (
                Pedido.EstadoPago.REVISION
            )

            pedido.save(
                update_fields=[
                    "estado_pago",
                    "actualizado",
                ]
            )

        except Exception as error:

            logger.exception(
                (
                    "Error inesperado Mercado Pago. "
                    "Pedido=%s payment_id=%s: %s"
                ),
                pedido.numero,
                payment_id,
                error,
            )

            pedido.estado_pago = (
                Pedido.EstadoPago.REVISION
            )

            pedido.save(
                update_fields=[
                    "estado_pago",
                    "actualizado",
                ]
            )

    # =========================================================================
    # REFRESH FINAL
    # =========================================================================

    pedido.refresh_from_db()

    if pedido.pago_aprobado:

        _vaciar_carrito_pago_confirmado(
            request,
            pedido,
        )

    # =========================================================================
    # REDIRECCIÓN CENTRAL
    # =========================================================================

    return redirect(
        "core:pedido_confirmacion",
        numero=pedido.numero,
    )


@require_GET
def mercadopago_retorno_pendiente(
    request,
    numero,
):
    pedido = get_object_or_404(
        Pedido,
        numero=numero,
    )

    # =========================================================================
    # NO SOBREESCRIBIR UN PAGO YA APROBADO
    # =========================================================================

    if not pedido.pago_aprobado:

        pedido.pagado = False

        pedido.estado = (
            Pedido.EstadoPedido.PENDIENTE
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.PENDIENTE
        )

        pedido.save(
            update_fields=[
                "pagado",
                "estado",
                "estado_pago",
                "actualizado",
            ]
        )

    logger.info(
        (
            "Retorno pendiente Mercado Pago. "
            "Pedido=%s estado_pago=%s."
        ),
        pedido.numero,
        pedido.estado_pago,
    )

    return redirect(
        "core:pedido_confirmacion",
        numero=pedido.numero,
    )



@require_GET
def mercadopago_retorno_fallido(
    request,
    numero,
):
    """
    Procesa el retorno FAILURE de Mercado Pago.

    Llegar a esta URL NO implica automáticamente
    que el pago haya sido rechazado.

    Reglas:

    - approved -> confirmar pago;
    - rejected -> rechazado;
    - pending/in_process/etc. -> pendiente;
    - cancelled/canceled -> cancelado;
    - sin payment_id -> cancelado;
    - payment_id no verificable -> cancelado;
    - estado vacío/desconocido -> cancelado;
    - referencia perteneciente a otro pedido -> revisión.
    """

    # =========================================================================
    # PEDIDO
    # =========================================================================

    pedido = get_object_or_404(
        Pedido.objects.select_related(
            "usuario",
        ),
        numero=numero,
    )

    # =========================================================================
    # CONTROL DE ACCESO
    # =========================================================================

    if pedido.usuario_id:

        if not request.user.is_authenticated:
            return redirect(
                "core:inicio"
            )

        if (
            pedido.usuario_id
            != request.user.pk
            and not request.user.is_staff
        ):
            return redirect(
                "core:inicio"
            )

    # =========================================================================
    # NO TOCAR UN PEDIDO YA PAGADO
    # =========================================================================

    if pedido.pago_aprobado:

        logger.info(
            (
                "Retorno FAILURE Mercado Pago ignorado. "
                "Pedido=%s ya aprobado."
            ),
            pedido.numero,
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # DATOS DEL RETORNO
    # =========================================================================

    payment_id = (
        request.GET.get(
            "payment_id"
        )
        or request.GET.get(
            "collection_id"
        )
        or ""
    ).strip()

    status_retorno = (
        request.GET.get(
            "status"
        )
        or request.GET.get(
            "collection_status"
        )
        or ""
    ).strip().lower()

    referencia_retorno = (
        request.GET.get(
            "external_reference"
        )
        or ""
    ).strip()

    preference_id = (
        request.GET.get(
            "preference_id"
        )
        or ""
    ).strip()

    logger.info(
        (
            "Retorno FAILURE Mercado Pago. "
            "Pedido=%s "
            "payment_id=%s "
            "status=%s "
            "external_reference=%s."
        ),
        pedido.numero,
        payment_id or "vacío",
        status_retorno or "vacío",
        referencia_retorno or "vacía",
    )

    # =========================================================================
    # REFERENCIA INCORRECTA = CASO DE SEGURIDAD / REVISIÓN
    # =========================================================================

    if (
        referencia_retorno
        and referencia_retorno
        != pedido.numero
    ):

        logger.error(
            (
                "Retorno Mercado Pago pertenece "
                "a otro pedido. "
                "Esperado=%s recibido=%s."
            ),
            pedido.numero,
            referencia_retorno,
        )

        pedido.pagado = False

        pedido.estado_pago = (
            Pedido.EstadoPago.REVISION
        )

        pedido.save(
            update_fields=[
                "pagado",
                "estado_pago",
                "actualizado",
            ]
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # PREFERENCE ID
    # =========================================================================

    if preference_id:

        pedido.mercadopago_preference_id = (
            preference_id
        )

        pedido.save(
            update_fields=[
                "mercadopago_preference_id",
                "actualizado",
            ]
        )

    # =========================================================================
    # CONSULTAR PAYMENT_ID SI EXISTE
    # =========================================================================

    if payment_id:

        try:

            pago = obtener_pago(
                payment_id
            )

            if not isinstance(
                pago,
                dict,
            ):
                raise MercadoPagoError(
                    "Respuesta de pago inválida."
                )

            estado_mp = str(
                pago.get(
                    "status"
                )
                or ""
            ).strip().lower()

            status_detail = str(
                pago.get(
                    "status_detail"
                )
                or ""
            ).strip()

            referencia_pago = str(
                pago.get(
                    "external_reference"
                )
                or ""
            ).strip()

            payment_type = str(
                pago.get(
                    "payment_type_id"
                )
                or ""
            ).strip()

            monto_raw = pago.get(
                "transaction_amount"
            )

            monto_pago = None

            if monto_raw is not None:
                monto_pago = Decimal(
                    str(
                        monto_raw
                    )
                )

            logger.info(
                (
                    "Pago consultado desde FAILURE MP. "
                    "Pedido=%s "
                    "payment_id=%s "
                    "status=%s "
                    "detail=%s."
                ),
                pedido.numero,
                payment_id,
                estado_mp or "vacío",
                status_detail or "vacío",
            )

            # =================================================================
            # REFERENCIA DEL PAGO
            # =================================================================

            if (
                referencia_pago
                and referencia_pago
                != pedido.numero
            ):

                logger.error(
                    (
                        "Payment Mercado Pago pertenece "
                        "a otro pedido. "
                        "Pedido=%s referencia=%s."
                    ),
                    pedido.numero,
                    referencia_pago,
                )

                pedido.pagado = False

                pedido.estado_pago = (
                    Pedido.EstadoPago.REVISION
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado_pago",
                        "actualizado",
                    ]
                )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # APROBADO
            # =================================================================

            if estado_mp == "approved":

                confirmar_pago_mercadopago(
                    pago
                )

                pedido.refresh_from_db()

                if pedido.pago_aprobado:

                    _vaciar_carrito_pago_confirmado(
                        request,
                        pedido,
                    )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # RECHAZADO REAL
            # =================================================================

            if estado_mp == "rejected":

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.CANCELADO
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.RECHAZADO
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.mercadopago_payment_type = (
                    payment_type
                )

                campos = [
                    "pagado",
                    "estado",
                    "estado_pago",
                    "mercadopago_payment_id",
                    "mercadopago_status",
                    "mercadopago_status_detail",
                    "mercadopago_payment_type",
                    "actualizado",
                ]

                if monto_pago is not None:

                    pedido.mercadopago_transaction_amount = (
                        monto_pago
                    )

                    campos.append(
                        "mercadopago_transaction_amount"
                    )

                pedido.save(
                    update_fields=campos
                )

                try:
                    _liberar_descuento_si_corresponde(
                        pedido
                    )
                except Exception:
                    logger.exception(
                        (
                            "Error liberando descuento "
                            "tras rechazo MP. Pedido=%s."
                        ),
                        pedido.numero,
                    )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # PENDIENTE
            # =================================================================

            if estado_mp in {
                "pending",
                "in_process",
                "in_mediation",
                "authorized",
            }:

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.PENDIENTE
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.PENDIENTE
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado",
                        "estado_pago",
                        "mercadopago_payment_id",
                        "mercadopago_status",
                        "mercadopago_status_detail",
                        "actualizado",
                    ]
                )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # CANCELADO EXPLÍCITO
            # =================================================================

            if estado_mp in {
                "cancelled",
                "canceled",
            }:

                pedido.pagado = False

                pedido.estado = (
                    Pedido.EstadoPedido.CANCELADO
                )

                pedido.estado_pago = (
                    Pedido.EstadoPago.CANCELADO
                )

                pedido.mercadopago_payment_id = (
                    payment_id
                )

                pedido.mercadopago_status = (
                    estado_mp
                )

                pedido.mercadopago_status_detail = (
                    status_detail
                )

                pedido.save(
                    update_fields=[
                        "pagado",
                        "estado",
                        "estado_pago",
                        "mercadopago_payment_id",
                        "mercadopago_status",
                        "mercadopago_status_detail",
                        "actualizado",
                    ]
                )

                try:
                    _liberar_descuento_si_corresponde(
                        pedido
                    )
                except Exception:
                    logger.exception(
                        (
                            "Error liberando descuento "
                            "tras cancelación MP. "
                            "Pedido=%s."
                        ),
                        pedido.numero,
                    )

                return redirect(
                    "core:pedido_confirmacion",
                    numero=pedido.numero,
                )

            # =================================================================
            # ESTADO VACÍO / DESCONOCIDO EN FAILURE
            # =================================================================
            #
            # No existe evidencia suficiente para decir
            # "rechazado" ni para mandar a "revisión".
            #
            # En este contexto interpretamos que el usuario
            # abandonó/canceló Checkout Pro.
            # =================================================================

            logger.info(
                (
                    "FAILURE MP sin estado concluyente. "
                    "Pedido=%s payment_id=%s status=%s. "
                    "Se interpretará como CANCELADO."
                ),
                pedido.numero,
                payment_id,
                estado_mp or "vacío",
            )

        except Exception as error:

            # =================================================================
            # NO PODEMOS CONSULTAR PAYMENT ID
            # =================================================================
            #
            # En una URL FAILURE no vamos a mostrar
            # "En revisión" solo porque el ID no pueda
            # verificarse.
            #
            # No tenemos evidencia de cobro.
            # Se considera cancelación del intento.
            # =================================================================

            logger.warning(
                (
                    "No se pudo verificar payment_id=%s "
                    "en retorno FAILURE MP. "
                    "Pedido=%s. "
                    "Se interpretará como CANCELADO. "
                    "Error=%s"
                ),
                payment_id,
                pedido.numero,
                error,
            )

    # =========================================================================
    # CANCELACIÓN / ABANDONO
    # =========================================================================
    #
    # Llegamos aquí cuando:
    #
    # - no existe payment_id;
    # - payment_id no se pudo consultar;
    # - Mercado Pago no entregó un estado concluyente;
    # - usuario presionó volver sin completar la compra.
    #
    # =========================================================================

    pedido.refresh_from_db()

    # Seguridad:
    # el webhook pudo aprobar el pago mientras
    # procesábamos el retorno.
    if pedido.pago_aprobado:

        logger.info(
            (
                "Pedido %s fue aprobado mientras "
                "se procesaba FAILURE MP. "
                "No se cancelará."
            ),
            pedido.numero,
        )

        _vaciar_carrito_pago_confirmado(
            request,
            pedido,
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    pedido.pagado = False

    pedido.estado = (
        Pedido.EstadoPedido.CANCELADO
    )

    pedido.estado_pago = (
        Pedido.EstadoPago.CANCELADO
    )

    pedido.save(
        update_fields=[
            "pagado",
            "estado",
            "estado_pago",
            "actualizado",
        ]
    )

    # =========================================================================
    # LIBERAR DESCUENTO
    # =========================================================================

    try:

        _liberar_descuento_si_corresponde(
            pedido
        )

    except Exception:

        logger.exception(
            (
                "Error liberando descuento "
                "tras abandono Mercado Pago. "
                "Pedido=%s."
            ),
            pedido.numero,
        )

    # =========================================================================
    # LOG
    # =========================================================================

    logger.info(
        (
            "Checkout Mercado Pago cancelado/abandonado. "
            "Pedido=%s "
            "payment_id=%s "
            "status_retorno=%s "
            "estado_pago=%s."
        ),
        pedido.numero,
        payment_id or "vacío",
        status_retorno or "vacío",
        pedido.estado_pago,
    )

    # =========================================================================
    # MENSAJE
    # =========================================================================

    messages.warning(
        request,
        (
            "Cancelaste el proceso de pago "
            "con Mercado Pago. "
            "No se confirmó ningún cobro."
        ),
    )

    # =========================================================================
    # RESULTADO
    # =========================================================================

    return redirect(
        "core:pedido_confirmacion",
        numero=pedido.numero,
    )


@transaction.atomic
def actualizar_pedido_desde_pago(
    *,
    pedido,
    pago,
):
    pedido = (
        Pedido.objects
        .select_for_update()
        .select_related("usuario")
        .get(pk=pedido.pk)
    )

    payment_id = str(
        pago.get("id")
        or ""
    ).strip()

    status = str(
        pago.get("status")
        or ""
    ).strip().lower()

    status_detail = str(
        pago.get("status_detail")
        or ""
    ).strip()

    external_reference = str(
        pago.get("external_reference")
        or ""
    ).strip()

    transaction_amount = Decimal(
        str(
            pago.get(
                "transaction_amount",
                0,
            )
        )
    )

    # -------------------------------------------------------------------------
    # VALIDACIONES
    # -------------------------------------------------------------------------

    if external_reference != pedido.numero:
        raise ValueError(
            "La referencia del pago no coincide con el pedido."
        )

    # -------------------------------------------------------------------------
    # REGISTRAR INFORMACIÓN DE MERCADO PAGO
    # -------------------------------------------------------------------------

    pedido.mercadopago_payment_id = payment_id
    pedido.mercadopago_status = status
    pedido.mercadopago_status_detail = status_detail

    pedido.mercadopago_payment_type = str(
        pago.get("payment_type_id")
        or ""
    ).strip()

    pedido.mercadopago_transaction_amount = (
        transaction_amount
    )

    # -------------------------------------------------------------------------
    # PAGO APROBADO
    # -------------------------------------------------------------------------

    if status == "approved":
        if transaction_amount != pedido.total:
            pedido.estado = (
                Pedido.EstadoPedido.PENDIENTE
            )

            pedido.estado_pago = (
                Pedido.EstadoPago.REVISION
            )

            pedido.pagado = False

            pedido.save(
                update_fields=[
                    "mercadopago_payment_id",
                    "mercadopago_status",
                    "mercadopago_status_detail",
                    "mercadopago_payment_type",
                    "mercadopago_transaction_amount",
                    "estado",
                    "estado_pago",
                    "pagado",
                    "actualizado",
                ]
            )

            raise ValueError(
                "El monto pagado no coincide con el total del pedido."
            )

        pago_ya_estaba_aprobado = (
            pedido.pagado
            and pedido.estado_pago
            == Pedido.EstadoPago.APROBADO
        )

        # Descontar stock una sola vez.
        if not pedido.stock_descontado:
            descontar_stock_pedido(
                pedido
            )

            pedido.stock_descontado = True

        pedido.pagado = True

        pedido.estado = (
            Pedido.EstadoPedido.CONFIRMADO
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.APROBADO
        )

        if not pedido.fecha_pago:
            pedido.fecha_pago = timezone.now()

        pedido.save(
            update_fields=[
                "mercadopago_payment_id",
                "mercadopago_status",
                "mercadopago_status_detail",
                "mercadopago_payment_type",
                "mercadopago_transaction_amount",
                "pagado",
                "estado",
                "estado_pago",
                "fecha_pago",
                "stock_descontado",
                "actualizado",
            ]
        )

        # El correo se ejecuta después de confirmar la transacción.
        #
        # enviar_confirmacion_pago() debe ser idempotente, es decir,
        # no volver a enviar a una dirección que ya recibió el correo.
        if (
            not pedido.correo_confirmacion_enviado
            or not pago_ya_estaba_aprobado
        ):
            transaction.on_commit(
                partial(
                    enviar_confirmacion_pago,
                    pedido_id=pedido.pk,
                )
            )

    # -------------------------------------------------------------------------
    # PAGO PENDIENTE
    # -------------------------------------------------------------------------

    elif status in {
        "pending",
        "in_process",
        "authorized",
    }:
        pedido.pagado = False

        pedido.estado = (
            Pedido.EstadoPedido.PENDIENTE
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.INICIADO
        )

        pedido.save(
            update_fields=[
                "mercadopago_payment_id",
                "mercadopago_status",
                "mercadopago_status_detail",
                "mercadopago_payment_type",
                "mercadopago_transaction_amount",
                "pagado",
                "estado",
                "estado_pago",
                "actualizado",
            ]
        )

    # -------------------------------------------------------------------------
    # PAGO RECHAZADO
    # -------------------------------------------------------------------------

    elif status == "rejected":
        pedido.pagado = False

        pedido.estado = (
            Pedido.EstadoPedido.CANCELADO
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.RECHAZADO
        )

        pedido.save(
            update_fields=[
                "mercadopago_payment_id",
                "mercadopago_status",
                "mercadopago_status_detail",
                "mercadopago_payment_type",
                "mercadopago_transaction_amount",
                "pagado",
                "estado",
                "estado_pago",
                "actualizado",
            ]
        )

    # -------------------------------------------------------------------------
    # PAGO CANCELADO
    # -------------------------------------------------------------------------

    elif status == "cancelled":
        pedido.pagado = False

        pedido.estado = (
            Pedido.EstadoPedido.CANCELADO
        )

        pedido.estado_pago = (
            Pedido.EstadoPago.CANCELADO
        )

        pedido.save(
            update_fields=[
                "mercadopago_payment_id",
                "mercadopago_status",
                "mercadopago_status_detail",
                "mercadopago_payment_type",
                "mercadopago_transaction_amount",
                "pagado",
                "estado",
                "estado_pago",
                "actualizado",
            ]
        )

    # -------------------------------------------------------------------------
    # PAGO REEMBOLSADO
    # -------------------------------------------------------------------------

    elif status in {
        "refunded",
        "charged_back",
    }:
        pedido.pagado = False

        pedido.estado_pago = (
            Pedido.EstadoPago.REEMBOLSADO
        )

        pedido.save(
            update_fields=[
                "mercadopago_payment_id",
                "mercadopago_status",
                "mercadopago_status_detail",
                "mercadopago_payment_type",
                "mercadopago_transaction_amount",
                "pagado",
                "estado_pago",
                "actualizado",
            ]
        )

    else:
        pedido.estado_pago = (
            Pedido.EstadoPago.REVISION
        )

        pedido.save(
            update_fields=[
                "mercadopago_payment_id",
                "mercadopago_status",
                "mercadopago_status_detail",
                "mercadopago_payment_type",
                "mercadopago_transaction_amount",
                "estado_pago",
                "actualizado",
            ]
        )

    return pedido



def descontar_stock_pedido(
    pedido,
):
    if pedido.stock_descontado:
        return

    items = (
        pedido.items
        .select_related(
            "producto"
        )
        .all()
    )

    productos_bloqueados = {}

    for item in items:
        if item.producto_id is None:
            raise ValueError(
                (
                    f"El producto "
                    f"{item.nombre_producto} "
                    "ya no existe."
                )
            )

        producto = (
            Producto.objects
            .select_for_update()
            .get(
                pk=item.producto_id
            )
        )

        if producto.stock < item.cantidad:
            raise ValueError(
                (
                    "No existe stock suficiente "
                    f"de {producto.nombre}. "
                    f"Disponible: {producto.stock}."
                )
            )

        productos_bloqueados[
            item.producto_id
        ] = producto

    for item in items:
        producto = productos_bloqueados[
            item.producto_id
        ]

        producto.stock -= item.cantidad

        producto.save(
            update_fields=[
                "stock",
            ]
        )






@csrf_exempt
@require_POST
def mercadopago_webhook(request):
    """
    Procesa notificaciones de pagos de Mercado Pago.

    Para evitar confirmaciones duplicadas, solamente se procesan
    notificaciones de tipo payment.

    Las notificaciones merchant_order se ignoran porque Mercado Pago
    también envía la notificación payment correspondiente.
    """

    # -------------------------------------------------------------------------
    # LEER EL CUERPO JSON
    # -------------------------------------------------------------------------

    try:
        payload = json.loads(
            request.body or b"{}"
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        TypeError,
    ):
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    payload_data = payload.get(
        "data",
        {},
    )

    if not isinstance(payload_data, dict):
        payload_data = {}

    # -------------------------------------------------------------------------
    # OBTENER TIPO DE NOTIFICACIÓN
    # -------------------------------------------------------------------------

    topic = str(
        payload.get("type")
        or request.GET.get("type")
        or request.GET.get("topic")
        or ""
    ).strip().lower()

    # -------------------------------------------------------------------------
    # OBTENER ID DEL RECURSO
    # -------------------------------------------------------------------------

    resource_id = str(
        payload_data.get("id")
        or request.GET.get("data.id")
        or request.GET.get("id")
        or ""
    ).strip()

    action = str(
        payload.get("action")
        or ""
    ).strip().lower()

    logger.info(
        (
            "Webhook Mercado Pago recibido. "
            "Topic=%s, action=%s, resource_id=%s"
        ),
        topic,
        action,
        resource_id,
    )

    # -------------------------------------------------------------------------
    # VALIDAR DATOS MÍNIMOS
    # -------------------------------------------------------------------------

    if not topic:
        logger.warning(
            "Webhook Mercado Pago ignorado: falta topic/type."
        )

        return HttpResponse(
            "ignored",
            status=200,
        )

    if not resource_id:
        logger.warning(
            (
                "Webhook Mercado Pago ignorado: "
                "falta resource_id. Topic=%s"
            ),
            topic,
        )

        return HttpResponse(
            "ignored",
            status=200,
        )

    # -------------------------------------------------------------------------
    # IGNORAR MERCHANT ORDER
    # -------------------------------------------------------------------------
    #
    # Mercado Pago normalmente enviará también una notificación payment.
    # Procesar ambas provoca intentos simultáneos de modificar pedido,
    # stock y correos.
    # -------------------------------------------------------------------------

    if topic in {
        "merchant_order",
        "merchant_orders",
        "topic_merchant_order_wh",
    }:
        logger.info(
            (
                "Merchant order ignorada para evitar "
                "procesamiento duplicado. ID=%s"
            ),
            resource_id,
        )

        return HttpResponse(
            "ok",
            status=200,
        )

    # -------------------------------------------------------------------------
    # IGNORAR OTROS TIPOS DE NOTIFICACIÓN
    # -------------------------------------------------------------------------

    if topic not in {
        "payment",
        "payments",
    }:
        logger.info(
            (
                "Notificación Mercado Pago ignorada. "
                "Topic=%s, resource_id=%s"
            ),
            topic,
            resource_id,
        )

        return HttpResponse(
            "ok",
            status=200,
        )

    try:
        # ---------------------------------------------------------------------
        # CONSULTAR EL PAGO DIRECTAMENTE EN MERCADO PAGO
        # ---------------------------------------------------------------------

        pago = obtener_pago(
            resource_id
        )

        if not isinstance(pago, dict):
            raise MercadoPagoError(
                "Mercado Pago devolvió un pago inválido."
            )

        payment_id = str(
            pago.get("id")
            or resource_id
        ).strip()

        estado_pago = str(
            pago.get("status")
            or ""
        ).strip().lower()

        referencia_externa = str(
            pago.get("external_reference")
            or ""
        ).strip()

        logger.info(
            (
                "Pago Mercado Pago consultado. "
                "Payment ID=%s, status=%s, referencia=%s"
            ),
            payment_id,
            estado_pago,
            referencia_externa,
        )

        # ---------------------------------------------------------------------
        # PROCESAR SOLAMENTE PAGOS APROBADOS
        # ---------------------------------------------------------------------

        if estado_pago != "approved":
            logger.info(
                (
                    "Pago todavía no aprobado. "
                    "Payment ID=%s, status=%s"
                ),
                payment_id,
                estado_pago,
            )

            return HttpResponse(
                "ok",
                status=200,
            )

        # Esta función debe ser idempotente:
        #
        # - Buscar el pedido mediante external_reference.
        # - Validar el monto.
        # - Confirmar el stock una sola vez.
        # - Marcar estado_pago como APROBADO.
        # - Marcar pagado=True.
        # - Programar el correo después del commit.
        confirmar_pago_mercadopago(
            pago
        )

    except OperationalError as error:
        logger.exception(
            (
                "Base de datos temporalmente bloqueada "
                "procesando pago %s: %s"
            ),
            resource_id,
            error,
        )

        # Mercado Pago volverá a intentar la notificación.
        return HttpResponse(
            "error",
            status=500,
        )

    except MercadoPagoError as error:
        logger.exception(
            (
                "Error consultando Mercado Pago. "
                "Payment ID=%s: %s"
            ),
            resource_id,
            error,
        )

        return HttpResponse(
            "error",
            status=500,
        )

    except ConfirmacionPagoError as error:
        logger.exception(
            (
                "Error confirmando pago de Mercado Pago. "
                "Payment ID=%s: %s"
            ),
            resource_id,
            error,
        )

        return HttpResponse(
            "error",
            status=500,
        )

    except Exception as error:
        logger.exception(
            (
                "Error inesperado procesando webhook "
                "de Mercado Pago. Payment ID=%s: %s"
            ),
            resource_id,
            error,
        )

        return HttpResponse(
            "error",
            status=500,
        )

    return HttpResponse(
        "ok",
        status=200,
    )





def confirmar_pago_mercadopago(
    pago,
):
    """
    Confirma un pago de Mercado Pago contra un Pedido.

    Valida:

    - estructura del pago;
    - payment_id;
    - estado approved;
    - external_reference;
    - existencia del pedido;
    - monto pagado;
    - idempotencia del pago.

    La confirmación definitiva del pedido se delega en
    marcar_pedido_como_pagado().
    """

    # =========================================================================
    # VALIDAR PAYLOAD
    # =========================================================================

    if not isinstance(
        pago,
        dict,
    ):
        raise ConfirmacionPagoError(
            (
                "Los datos del pago de "
                "Mercado Pago no son válidos."
            )
        )

    # =========================================================================
    # DATOS PRINCIPALES
    # =========================================================================

    payment_id = str(
        pago.get(
            "id"
        )
        or ""
    ).strip()

    estado_pago = str(
        pago.get(
            "status"
        )
        or ""
    ).strip().lower()

    status_detail = str(
        pago.get(
            "status_detail"
        )
        or ""
    ).strip()

    numero_pedido = str(
        pago.get(
            "external_reference"
        )
        or ""
    ).strip()

    payment_type = str(
        pago.get(
            "payment_type_id"
        )
        or ""
    ).strip()

    currency_id = str(
        pago.get(
            "currency_id"
        )
        or ""
    ).strip().upper()

    # =========================================================================
    # VALIDACIONES BÁSICAS
    # =========================================================================

    if not payment_id:
        raise ConfirmacionPagoError(
            (
                "El pago de Mercado Pago "
                "no contiene un ID."
            )
        )

    if not numero_pedido:
        raise ConfirmacionPagoError(
            (
                "El pago no contiene "
                "external_reference."
            )
        )

    if estado_pago != "approved":
        raise ConfirmacionPagoError(
            (
                "El pago todavía no está aprobado. "
                f"Estado recibido: "
                f"{estado_pago or 'sin estado'}."
            )
        )

    # =========================================================================
    # MONTO PAGADO
    # =========================================================================

    try:
        monto_pagado = Decimal(
            str(
                pago.get(
                    "transaction_amount"
                )
                or "0"
            )
        )

    except (
        TypeError,
        ValueError,
        InvalidOperation,
    ) as error:
        raise ConfirmacionPagoError(
            (
                "Mercado Pago devolvió "
                "un monto inválido."
            )
        ) from error

    if monto_pagado <= 0:
        raise ConfirmacionPagoError(
            (
                "El monto pagado debe "
                "ser mayor que $0."
            )
        )

    # =========================================================================
    # OBTENER PEDIDO
    # =========================================================================

    try:
        pedido = (
            Pedido.objects
            .select_related(
                "usuario"
            )
            .get(
                numero=numero_pedido,
            )
        )

    except Pedido.DoesNotExist as error:
        raise ConfirmacionPagoError(
            (
                "No existe un pedido asociado "
                "a la referencia "
                f"{numero_pedido}."
            )
        ) from error

    # =========================================================================
    # TOTAL DEL PEDIDO
    # =========================================================================

    try:
        total_pedido = Decimal(
            str(
                pedido.total
                or 0
            )
        )

    except (
        TypeError,
        ValueError,
        InvalidOperation,
    ) as error:
        raise ConfirmacionPagoError(
            (
                "El pedido tiene un "
                "total inválido."
            )
        ) from error

    if total_pedido <= 0:
        raise ConfirmacionPagoError(
            (
                "El pedido no tiene "
                "un total válido."
            )
        )

    # =========================================================================
    # VALIDAR MONTO
    # =========================================================================

    if monto_pagado != total_pedido:
        raise ConfirmacionPagoError(
            (
                "El monto pagado no coincide "
                "con el total del pedido. "
                f"Pedido: {total_pedido}. "
                f"Pago: {monto_pagado}."
            )
        )

    # =========================================================================
    # VALIDAR MONEDA
    # =========================================================================
    #
    # Como Audex trabaja en CLP, si Mercado Pago devuelve currency_id
    # verificamos que efectivamente sea CLP.
    # =========================================================================

    if (
        currency_id
        and currency_id != "CLP"
    ):
        raise ConfirmacionPagoError(
            (
                "La moneda del pago no coincide "
                "con la moneda del pedido. "
                f"Moneda recibida: {currency_id}."
            )
        )

    # =========================================================================
    # IDEMPOTENCIA
    # =========================================================================
    #
    # Mercado Pago puede llamar varias veces al webhook y además
    # el navegador puede entrar por la URL de retorno exitoso.
    #
    # Si este mismo payment_id ya confirmó el pedido, no debemos:
    #
    # - volver a descontar stock;
    # - volver a consumir código;
    # - volver a enviar correo.
    #
    # =========================================================================

    pedido_payment_id = str(
        getattr(
            pedido,
            "mercadopago_payment_id",
            "",
        )
        or ""
    ).strip()

    if (
        pedido.pago_aprobado
        and pedido_payment_id
        and pedido_payment_id == payment_id
    ):
        logger.info(
            (
                "Pago Mercado Pago ya confirmado. "
                "Pedido=%s, payment_id=%s."
            ),
            pedido.numero,
            payment_id,
        )

        return pedido

    # =========================================================================
    # VALIDAR PAYMENT ID DISTINTO
    # =========================================================================

    if (
        pedido_payment_id
        and pedido_payment_id != payment_id
        and pedido.pago_aprobado
    ):
        raise ConfirmacionPagoError(
            (
                "El pedido ya fue confirmado "
                "con otro pago de Mercado Pago. "
                f"Pedido={pedido.numero}, "
                f"payment_id_actual={pedido_payment_id}, "
                f"payment_id_recibido={payment_id}."
            )
        )

    # =========================================================================
    # LOG
    # =========================================================================

    logger.info(
        (
            "Confirmando pago Mercado Pago. "
            "Pedido=%s, payment_id=%s, "
            "status=%s, monto=%s, "
            "payment_type=%s."
        ),
        pedido.numero,
        payment_id,
        estado_pago,
        monto_pagado,
        payment_type,
    )

    # =========================================================================
    # CONFIRMAR PEDIDO
    # =========================================================================
    #
    # IMPORTANTE:
    #
    # marcar_pedido_como_pagado debe estar IMPORTADA
    # en este archivo si está definida en core/services/pagos.py.
    #
    # Ejemplo:
    #
   
    #
    # =========================================================================

    try:
        pedido_confirmado = (
            marcar_pedido_como_pagado(
                pedido_id=pedido.pk,

                datos_pago={
                    "metodo": (
                        Pedido
                        .MetodoPago
                        .MERCADOPAGO
                    ),

                    "payment_id": (
                        payment_id
                    ),

                    "mercadopago_status": (
                        estado_pago
                    ),

                    "mercadopago_status_detail": (
                        status_detail
                    ),

                    "payment_type": (
                        payment_type
                    ),

                    "transaction_amount": (
                        monto_pagado
                    ),
                },
            )
        )

    except ConfirmacionPagoError:
        raise

    except Exception as error:
        raise ConfirmacionPagoError(
            (
                "No fue posible marcar el "
                "pedido como pagado. "
                f"Pedido={pedido.numero}. "
                f"Detalle: {error}"
            )
        ) from error

    # =========================================================================
    # LOG FINAL
    # =========================================================================

    logger.info(
        (
            "Pago Mercado Pago confirmado correctamente. "
            "Pedido=%s, payment_id=%s."
        ),
        pedido.numero,
        payment_id,
    )

    return pedido_confirmado






def obtener_datos_iniciales_checkout(request):
  

    if not request.user.is_authenticated:
        return {}

    return {
        "nombre": request.user.first_name,
        "apellido": request.user.last_name,
        "email": request.user.email,
    }




def registrar_error_inicio_pago(
    *,
    pedido,
    mensaje,
):
    """
    Guarda el error de inicio de pago cuando
    el modelo contiene campos para ello.
    """

    campos_actualizados = []

    if hasattr(pedido, "estado_pago"):
        pedido.estado_pago = "error"
        campos_actualizados.append("estado_pago")

    if hasattr(pedido, "error_pago"):
        pedido.error_pago = mensaje[:500]
        campos_actualizados.append("error_pago")

    if campos_actualizados:
        pedido.save(
            update_fields=campos_actualizados,
        )






















def _registrar_pedido_pago_en_curso(
    request,
    pedido,
):
    """
    Guarda en la sesión qué pedido está siendo pagado.

    Esto permite vaciar únicamente el carrito correspondiente
    cuando Mercado Pago regrese con el pago aprobado.
    """

    request.session[
        "pedido_pago_en_curso"
    ] = pedido.numero

    request.session.modified = True


def _vaciar_carrito_pago_confirmado(
    request,
    pedido,
):
    """
    Vacía el carrito solamente cuando el pedido aprobado
    corresponde al pago iniciado desde esta sesión.

    Evita que abrir la confirmación de una compra antigua
    elimine un carrito nuevo.
    """

    numero_en_sesion = request.session.get(
        "pedido_pago_en_curso"
    )

    if numero_en_sesion != pedido.numero:
        logger.warning(
            (
                "No se vació el carrito del pedido %s. "
                "Pedido registrado en sesión: %s."
            ),
            pedido.numero,
            numero_en_sesion or "ninguno",
        )

        return False

    _guardar_carrito(
        request,
        {},
    )

    request.session.pop(
        "pedido_pago_en_curso",
        None,
    )

    request.session.modified = True

    logger.info(
        "Carrito vaciado después del pago del pedido %s.",
        pedido.numero,
    )

    return True








@property
def stock_disponible(self):
    return max(self.stock - self.stock_reservado, 0)






class PagoInvalido(Exception):
    pass


def consultar_pago(payment_id):
    response = requests.get(
        f"https://api.mercadopago.com/v1/payments/{payment_id}",
        headers={
            "Authorization": (
                f"Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}"
            ),
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()


@transaction.atomic
def confirmar_pedido_pagado(pedido_id, pago):
    pedido = (
        Pedido.objects
        .select_for_update()
        .prefetch_related("items")
        .get(pk=pedido_id)
    )

    # Idempotencia: el webhook puede llegar varias veces.
    if pedido.estado == Pedido.Estado.PAGADO:
        return pedido, False

    if pago.get("status") != "approved":
        raise PagoInvalido("El pago aún no está aprobado.")

    if str(pago.get("external_reference")) != str(pedido.id_publico):
        raise PagoInvalido("La referencia del pedido no coincide.")

    try:
        monto_pagado = Decimal(str(pago["transaction_amount"]))
    except (KeyError, InvalidOperation) as exc:
        raise PagoInvalido("Monto de pago inválido.") from exc

    if monto_pagado != pedido.total:
        raise PagoInvalido("El monto pagado no coincide con el pedido.")

    if pago.get("currency_id") != pedido.moneda:
        raise PagoInvalido("La moneda del pago no coincide.")

    items = list(pedido.items.all())

    productos = {
        producto.pk: producto
        for producto in Producto.objects.select_for_update().filter(
            pk__in=[item.producto_id for item in items]
        )
    }

    for item in items:
        producto = productos[item.producto_id]

        if producto.stock < item.cantidad:
            pedido.estado = Pedido.Estado.REVISION
            pedido.save(update_fields=["estado"])
            raise PagoInvalido(
                f"Stock inconsistente para {producto.nombre}."
            )

        producto.stock -= item.cantidad
        producto.stock_reservado = max(
            producto.stock_reservado - item.cantidad,
            0,
        )

        producto.save(
            update_fields=["stock", "stock_reservado"]
        )

    pedido.estado = Pedido.Estado.PAGADO
    pedido.mercado_pago_id = str(pago["id"])
    pedido.stock_confirmado = True
    pedido.pagado_en = timezone.now()

    pedido.save(update_fields=[
        "estado",
        "mercado_pago_id",
        "stock_confirmado",
        "pagado_en",
        "actualizado_en",
    ])

    # Ejecutar solamente después de confirmar la transacción.
    transaction.on_commit(
        lambda: iniciar_postventa(pedido.pk)
    )

    return pedido, True


def iniciar_postventa(pedido_id):

    from services.postventa import (
        emitir_boleta_y_enviar_correo,
    )

    emitir_boleta_y_enviar_correo(pedido_id)


@csrf_exempt
@require_POST
def webhook_mercado_pago(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    data_id = (
        request.GET.get("data.id")
        or payload.get("data", {}).get("id")
    )

    if not validar_firma_mercado_pago(request, data_id):
        return JsonResponse(
            {"error": "Firma inválida"},
            status=401,
        )

    tipo = payload.get("type") or request.GET.get("type")

    if tipo != "payment":
        return HttpResponse(status=200)

    try:
        pago = consultar_pago(data_id)
    except requests.RequestException:
        # Mercado Pago podrá reintentar la notificación.
        return HttpResponse(status=503)

    clave_evento = f"{pago['id']}:{pago.get('status')}"

    EventoPago.objects.get_or_create(
        clave=clave_evento,
        defaults={
            "payment_id": str(pago["id"]),
            "estado": pago.get("status", ""),
            "payload": pago,
        },
    )

    referencia = pago.get("external_reference")

    try:
        pedido = Pedido.objects.get(id_publico=referencia)
    except (Pedido.DoesNotExist, ValueError):
        return JsonResponse(
            {"error": "Pedido no encontrado"},
            status=404,
        )

    if pago.get("status") == "approved":
        try:
            confirmar_pedido_pagado(pedido.pk, pago)
        except PagoInvalido:
            return HttpResponse(status=200)

    elif pago.get("status") in {
        "rejected",
        "cancelled",
    }:
        # Aquí se debe liberar la reserva de stock.
        pass

    return HttpResponse(status=200)




@require_POST
def cerrar_sesion(request):
    """
    Conserva el carrito y los favoritos
    después de cerrar sesión.
    """

    carrito_actual = (
        _obtener_carrito(
            request
        )
    )

    favoritos_actuales = (
        obtener_ids_favoritos(
            request
        )
    )

    django_logout(
        request
    )

    _guardar_carrito(
        request,
        carrito_actual,
    )

    guardar_favoritos_en_sesion(
        request,
        favoritos_actuales,
    )

    messages.success(
        request,
        (
            "Sesión cerrada "
            "correctamente."
        ),
    )

    return redirect(
        "core:inicio"
    )


@require_GET
def favoritos_estado(request):
    ids_favoritos = (
        obtener_ids_favoritos(
            request
        )
    )

    return JsonResponse(
        {
            "ok": True,
            "favoritos": {
                "ids": ids_favoritos,
                "total": len(
                    ids_favoritos
                ),
            },
        }
    )


@require_POST
def favorito_alternar(request):
    try:
        datos = json.loads(
            request.body or "{}"
        )

        producto_id = int(
            datos.get(
                "producto_id"
            )
        )

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": (
                    "El producto indicado "
                    "no es válido."
                ),
            },
            status=400,
        )

    producto = get_object_or_404(
        Producto,
        id=producto_id,
        activo=True,
    )

    resultado = alternar_favorito(
        request=request,
        producto=producto,
    )

    mensaje = (
        f"{producto.nombre} fue guardado "
        "en favoritos."
        if resultado["activo"]
        else (
            f"{producto.nombre} fue eliminado "
            "de favoritos."
        )
    )

    return JsonResponse(
        {
            "ok": True,
            "mensaje": mensaje,
            "producto_id": producto.id,
            "favorito": resultado[
                "activo"
            ],
            "favoritos": {
                "ids": resultado["ids"],
                "total": resultado["total"],
            },
        }
    )






def mis_favoritos(request):
    """
    Invitado:
        obtiene favoritos desde la sesión.

    Usuario autenticado:
        obtiene los favoritos asociados a su cuenta.
    """

    ids_favoritos = obtener_ids_favoritos(
        request
    )

    productos_favoritos = (
        Producto.objects
        .filter(
            id__in=ids_favoritos,
            activo=True,
        )
        .select_related(
            "categoria"
        )
    )

    if ids_favoritos:
        orden_favoritos = Case(
            *[
                When(
                    pk=producto_id,
                    then=posicion,
                )
                for posicion, producto_id
                in enumerate(ids_favoritos)
            ],
            output_field=IntegerField(),
        )

        productos_favoritos = (
            productos_favoritos
            .order_by(
                orden_favoritos
            )
        )

    contexto = {
        "productos_favoritos": productos_favoritos,
        "cantidad_favoritos": len(
            ids_favoritos
        ),
    }

    return render(
        request,
        "core/cuenta/favoritos.html",
        contexto,
    )

@login_required(
    login_url="core:login"
)
def mi_perfil(request):

    es_usuario_google = (
        request.user.socialaccount_set
        .filter(provider="google")
        .exists()
    )

    contexto = {
        "usuario_perfil": request.user,
        "es_usuario_google": es_usuario_google,
    }

    return render(
        request,
        "core/cuenta/perfil.html",
        contexto,
    )



@csrf_exempt
def webpay_retorno(request):
    """
    Procesa el retorno desde Webpay Plus.

    Flujo:

    1. Obtiene token_ws.
    2. Si no existe token, considera la operación cancelada.
    3. Confirma la transacción directamente con Transbank.
    4. Valida:
       - response_code
       - status
       - buy_order
       - monto
       - token de sesión
    5. Si Transbank rechaza:
       - guarda RECHAZADO;
       - no descuenta stock;
       - no genera Bsale;
       - libera descuentos reservados.
    6. Si Transbank autoriza:
       - marca el Pedido como pagado;
       - descuenta stock;
       - confirma descuento;
       - genera Bsale mediante el flujo central.
    7. Vacía el carrito únicamente después del pago confirmado.
    8. Limpia los datos temporales de Webpay.
    9. Redirige a pedido_confirmacion(), que selecciona
       el HTML según el estado persistido.
    """

    # =========================================================================
    # TOKEN RETORNADO POR WEBPAY
    # =========================================================================

    token_ws = (
        request.POST.get(
            "token_ws",
            "",
        )
        or request.GET.get(
            "token_ws",
            "",
        )
        or ""
    ).strip()

    # =========================================================================
    # DATOS WEBPAY GUARDADOS EN SESIÓN
    # =========================================================================

    numero_pedido_sesion = str(
        request.session.get(
            "webpay_pedido",
            "",
        )
        or ""
    ).strip()

    token_sesion = str(
        request.session.get(
            "webpay_token",
            "",
        )
        or ""
    ).strip()

    pedido_pago_en_curso = str(
        request.session.get(
            "pedido_pago_en_curso",
            "",
        )
        or ""
    ).strip()

    logger.info(
        (
            "Retorno Webpay recibido. "
            "pedido_webpay=%s "
            "pedido_pago_en_curso=%s "
            "token_sesion=%s "
            "token_retorno=%s"
        ),
        numero_pedido_sesion or "vacío",
        pedido_pago_en_curso or "vacío",
        bool(token_sesion),
        bool(token_ws),
    )

    # =========================================================================
    # SIN TOKEN = CANCELACIÓN / ABANDONO
    # =========================================================================

    if not token_ws:

        logger.warning(
            (
                "Retorno Webpay sin token. "
                "Pedido en sesión=%s"
            ),
            numero_pedido_sesion,
        )

        if numero_pedido_sesion:

            try:
                pedido = Pedido.objects.get(
                    numero=numero_pedido_sesion
                )

                if not pedido.pagado:

                    pedido.estado = (
                        Pedido.EstadoPedido.CANCELADO
                    )

                    pedido.estado_pago = (
                        Pedido.EstadoPago.CANCELADO
                    )

                    pedido.pagado = False

                    pedido.save(
                        update_fields=[
                            "estado",
                            "estado_pago",
                            "pagado",
                            "actualizado",
                        ]
                    )

                    try:
                        _liberar_descuento_si_corresponde(
                            pedido
                        )
                    except Exception:
                        logger.exception(
                            (
                                "No fue posible liberar "
                                "el descuento del pedido %s "
                                "tras cancelación Webpay."
                            ),
                            pedido.numero,
                        )

                    logger.info(
                        (
                            "Pedido %s marcado como "
                            "Webpay CANCELADO."
                        ),
                        pedido.numero,
                    )

            except Pedido.DoesNotExist:

                logger.warning(
                    (
                        "No existe el pedido %s "
                        "guardado en sesión Webpay."
                    ),
                    numero_pedido_sesion,
                )

        # ---------------------------------------------------------------------
        # LIMPIAR SESIÓN
        # ---------------------------------------------------------------------

        request.session.pop(
            "webpay_token",
            None,
        )

        request.session.pop(
            "webpay_pedido",
            None,
        )

        request.session.pop(
            "pedido_pago_en_curso",
            None,
        )

        request.session.modified = True

        messages.warning(
            request,
            (
                "Cancelaste el pago con Webpay. "
                "No se confirmó ningún cobro."
            ),
        )

        if numero_pedido_sesion:

            return redirect(
                "core:pedido_confirmacion",
                numero=numero_pedido_sesion,
            )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # VALIDAR TOKEN CONTRA SESIÓN
    # =========================================================================

    if (
        token_sesion
        and token_sesion != token_ws
    ):

        logger.error(
            (
                "Token Webpay distinto al iniciado. "
                "Pedido sesión=%s"
            ),
            numero_pedido_sesion,
        )

        messages.error(
            request,
            (
                "La transacción retornada por Webpay "
                "no coincide con el pago iniciado."
            ),
        )

        if numero_pedido_sesion:
            return redirect(
                "core:pedido_confirmacion",
                numero=numero_pedido_sesion,
            )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # CONFIRMAR TRANSACCIÓN DIRECTAMENTE CON TRANSBANK
    # =========================================================================

    try:

        transaccion = (
            obtener_transaccion_webpay()
        )

        respuesta = (
            transaccion.commit(
                token_ws
            )
        )

        logger.info(
            "RESPUESTA COMMIT WEBPAY: %s",
            respuesta,
        )

    except Exception as error:

        logger.exception(
            (
                "Error confirmando transacción "
                "Webpay: %s"
            ),
            error,
        )

        messages.error(
            request,
            (
                "No fue posible confirmar "
                "la transacción con Webpay."
            ),
        )

        if numero_pedido_sesion:
            return redirect(
                "core:pedido_confirmacion",
                numero=numero_pedido_sesion,
            )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # NORMALIZAR RESPUESTA TRANSBANK
    # =========================================================================

    if isinstance(
        respuesta,
        dict,
    ):

        response_code = (
            respuesta.get(
                "response_code"
            )
        )

        status = str(
            respuesta.get(
                "status",
                "",
            )
            or ""
        ).strip().upper()

        buy_order = str(
            respuesta.get(
                "buy_order",
                "",
            )
            or ""
        ).strip()

        amount_raw = (
            respuesta.get(
                "amount"
            )
        )

        authorization_code = str(
            respuesta.get(
                "authorization_code",
                "",
            )
            or ""
        ).strip()

        payment_type_code = str(
            respuesta.get(
                "payment_type_code",
                "",
            )
            or ""
        ).strip()

        card_detail = (
            respuesta.get(
                "card_detail"
            )
            or {}
        )

    else:

        response_code = getattr(
            respuesta,
            "response_code",
            None,
        )

        status = str(
            getattr(
                respuesta,
                "status",
                "",
            )
            or ""
        ).strip().upper()

        buy_order = str(
            getattr(
                respuesta,
                "buy_order",
                "",
            )
            or ""
        ).strip()

        amount_raw = getattr(
            respuesta,
            "amount",
            None,
        )

        authorization_code = str(
            getattr(
                respuesta,
                "authorization_code",
                "",
            )
            or ""
        ).strip()

        payment_type_code = str(
            getattr(
                respuesta,
                "payment_type_code",
                "",
            )
            or ""
        ).strip()

        card_detail = (
            getattr(
                respuesta,
                "card_detail",
                {},
            )
            or {}
        )

    # =========================================================================
    # LOG RESPUESTA TRANSBANK
    # =========================================================================

    logger.info(
        (
            "CONFIRMACIÓN WEBPAY: "
            "response_code=%s "
            "status=%s "
            "buy_order=%s "
            "amount=%s "
            "authorization_code=%s "
            "payment_type_code=%s "
            "pedido_sesion=%s"
        ),
        response_code,
        status,
        buy_order,
        amount_raw,
        authorization_code,
        payment_type_code,
        numero_pedido_sesion,
    )

    # =========================================================================
    # VALIDAR BUY ORDER
    # =========================================================================

    if not buy_order:

        logger.error(
            "Webpay no devolvió buy_order válido."
        )

        messages.error(
            request,
            (
                "Webpay no devolvió una "
                "orden de compra válida."
            ),
        )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # BUSCAR PEDIDO
    # =========================================================================

    try:

        pedido = (
            Pedido.objects.get(
                numero=buy_order
            )
        )

    except Pedido.DoesNotExist:

        logger.error(
            (
                "Webpay devolvió buy_order "
                "inexistente: %s"
            ),
            buy_order,
        )

        messages.error(
            request,
            (
                "No fue posible asociar "
                "el pago con un pedido válido."
            ),
        )

        return redirect(
            "core:productos"
        )

    # =========================================================================
    # VALIDAR MÉTODO DE PAGO
    # =========================================================================

    metodo_pedido = str(
        pedido.metodo_pago
        or ""
    ).strip().lower()

    if (
        metodo_pedido
        != Pedido.MetodoPago.WEBPAY
    ):

        logger.error(
            (
                "Intento de confirmar con Webpay "
                "un pedido de otro método. "
                "Pedido=%s metodo=%s"
            ),
            pedido.numero,
            metodo_pedido,
        )

        messages.error(
            request,
            (
                "El método de pago del pedido "
                "no coincide con Webpay."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # VALIDAR PEDIDO CONTRA SESIÓN WEBPAY
    # =========================================================================

    if (
        numero_pedido_sesion
        and numero_pedido_sesion
        != buy_order
    ):

        logger.error(
            (
                "Webpay buy_order no coincide "
                "con pedido en sesión. "
                "Sesion=%s Webpay=%s"
            ),
            numero_pedido_sesion,
            buy_order,
        )

        messages.error(
            request,
            (
                "La transacción de Webpay "
                "no coincide con el pedido iniciado."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # VALIDAR PEDIDO EN CURSO
    # =========================================================================

    if (
        pedido_pago_en_curso
        and pedido_pago_en_curso
        != pedido.numero
    ):

        logger.error(
            (
                "Pedido Webpay no coincide con "
                "pedido_pago_en_curso. "
                "Pedido=%s Sesion=%s"
            ),
            pedido.numero,
            pedido_pago_en_curso,
        )

        messages.error(
            request,
            (
                "El pedido confirmado no coincide "
                "con el proceso de pago iniciado."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # VALIDAR MONTO
    # =========================================================================

    try:

        amount = Decimal(
            str(
                amount_raw
            )
        )

        total_pedido = Decimal(
            str(
                pedido.total
                or 0
            )
        )

    except Exception as error:

        logger.exception(
            (
                "Error validando monto "
                "Webpay: %s"
            ),
            error,
        )

        messages.error(
            request,
            (
                "Webpay devolvió un monto "
                "que no pudo ser validado."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # COMPARAR MONTO
    # =========================================================================

    if amount != total_pedido:

        logger.error(
            (
                "Monto Webpay distinto "
                "al total del pedido. "
                "Pedido=%s "
                "Total pedido=%s "
                "Webpay=%s"
            ),
            pedido.numero,
            total_pedido,
            amount,
        )

        # ---------------------------------------------------------------------
        # MONTO INCONSISTENTE -> REVISIÓN
        # ---------------------------------------------------------------------

        pedido.pagado = False

        pedido.estado_pago = (
            Pedido.EstadoPago.REVISION
        )

        pedido.webpay_token = (
            token_ws
            or ""
        )

        pedido.webpay_buy_order = (
            buy_order
            or pedido.numero
        )

        pedido.webpay_authorization_code = (
            authorization_code
            or ""
        )

        pedido.webpay_payment_type_code = (
            payment_type_code
            or ""
        )

        if response_code is not None:

            try:
                pedido.webpay_response_code = int(
                    response_code
                )

            except (
                TypeError,
                ValueError,
            ):
                pedido.webpay_response_code = None

        pedido.save(
            update_fields=[
                "pagado",
                "estado_pago",
                "webpay_token",
                "webpay_buy_order",
                "webpay_authorization_code",
                "webpay_payment_type_code",
                "webpay_response_code",
                "actualizado",
            ]
        )

        messages.error(
            request,
            (
                "El monto confirmado por Webpay "
                "no coincide con el total del pedido."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # VALIDAR APROBACIÓN TRANSBANK
    # =========================================================================

    aprobado = bool(
        response_code == 0
        and status == "AUTHORIZED"
    )

    # =========================================================================
    # TRANSBANK RECHAZÓ EL PAGO
    # =========================================================================

    if not aprobado:

        logger.warning(
            (
                "Pago Webpay no aprobado. "
                "Pedido=%s "
                "status=%s "
                "response_code=%s"
            ),
            pedido.numero,
            status,
            response_code,
        )

        # ---------------------------------------------------------------------
        # GUARDAR RESPUESTA WEBPAY
        # ---------------------------------------------------------------------

        pedido.webpay_token = (
            token_ws
            or ""
        )

        pedido.webpay_buy_order = (
            buy_order
            or pedido.numero
        )

        pedido.webpay_authorization_code = (
            authorization_code
            or ""
        )

        pedido.webpay_payment_type_code = (
            payment_type_code
            or ""
        )

        if response_code is not None:

            try:
                pedido.webpay_response_code = int(
                    response_code
                )

            except (
                TypeError,
                ValueError,
            ):
                pedido.webpay_response_code = None

        # ---------------------------------------------------------------------
        # ESTADO REAL DEL PEDIDO
        # ---------------------------------------------------------------------

        pedido.pagado = False

        pedido.estado_pago = (
            Pedido.EstadoPago.RECHAZADO
        )

        pedido.estado = (
            Pedido.EstadoPedido.CANCELADO
        )

        pedido.save(
            update_fields=[
                "webpay_token",
                "webpay_buy_order",
                "webpay_authorization_code",
                "webpay_response_code",
                "webpay_payment_type_code",
                "pagado",
                "estado_pago",
                "estado",
                "actualizado",
            ]
        )

        # ---------------------------------------------------------------------
        # LIBERAR DESCUENTO
        # ---------------------------------------------------------------------

        try:

            _liberar_descuento_si_corresponde(
                pedido
            )

        except Exception:

            logger.exception(
                (
                    "Error liberando descuento "
                    "tras rechazo Webpay. "
                    "Pedido=%s"
                ),
                pedido.numero,
            )

        # ---------------------------------------------------------------------
        # LIMPIAR SESIÓN
        # ---------------------------------------------------------------------

        request.session.pop(
            "webpay_token",
            None,
        )

        request.session.pop(
            "webpay_pedido",
            None,
        )

        request.session.pop(
            "pedido_pago_en_curso",
            None,
        )

        request.session.modified = True

        # ---------------------------------------------------------------------
        # LOG
        # ---------------------------------------------------------------------

        logger.info(
            (
                "Rechazo Webpay persistido. "
                "Pedido=%s "
                "estado=%s "
                "estado_pago=%s "
                "pagado=%s "
                "response_code=%s."
            ),
            pedido.numero,
            pedido.estado,
            pedido.estado_pago,
            pedido.pagado,
            pedido.webpay_response_code,
        )

        # ---------------------------------------------------------------------
        # MENSAJE
        # ---------------------------------------------------------------------

        messages.error(
            request,
            (
                "Tu pago con Webpay fue rechazado. "
                "No se confirmó ningún cobro."
            ),
        )

        # ---------------------------------------------------------------------
        # REDIRECCIÓN
        # ---------------------------------------------------------------------

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # WEBPAY CONFIRMÓ EL PAGO
    # =========================================================================

    logger.info(
        (
            "Webpay AUTORIZÓ el pago. "
            "Pedido=%s "
            "response_code=%s "
            "status=%s "
            "amount=%s"
        ),
        pedido.numero,
        response_code,
        status,
        amount,
    )

    # =========================================================================
    # ÚLTIMOS DÍGITOS TARJETA
    # =========================================================================

    card_number = ""

    if isinstance(
        card_detail,
        dict,
    ):

        card_number = str(
            card_detail.get(
                "card_number",
                "",
            )
            or ""
        ).strip()

    # =========================================================================
    # MARCAR PEDIDO COMO PAGADO
    # =========================================================================

    try:

        pedido = (
            marcar_pedido_como_pagado(
                pedido_id=pedido.pk,

                datos_pago={
                    "metodo": (
                        Pedido.MetodoPago.WEBPAY
                    ),

                    "payment_id": (
                        authorization_code
                        or token_ws
                    ),

                    "transaction_id": (
                        authorization_code
                        or token_ws
                    ),

                    "status": status,

                    "transaction_amount": (
                        amount
                    ),

                    "response_code": (
                        response_code
                    ),

                    "authorization_code": (
                        authorization_code
                    ),

                    "payment_type_code": (
                        payment_type_code
                    ),

                    "card_number": (
                        card_number
                    ),

                    "token_ws": (
                        token_ws
                    ),
                },
            )
        )

    except ValueError as error:

        logger.exception(
            (
                "Error confirmando pedido "
                "Webpay %s: %s"
            ),
            pedido.numero,
            error,
        )

        messages.error(
            request,
            str(
                error
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    except Exception as error:

        logger.exception(
            (
                "Error inesperado confirmando "
                "pedido Webpay %s: %s"
            ),
            pedido.numero,
            error,
        )

        messages.error(
            request,
            (
                "El pago fue autorizado, pero ocurrió "
                "un problema al confirmar el pedido."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # RECARGAR PEDIDO
    # =========================================================================

    pedido.refresh_from_db()

    # =========================================================================
    # VALIDACIÓN FINAL
    # =========================================================================

    pedido_confirmado = bool(
        pedido.pagado
        and pedido.estado_pago
        == Pedido.EstadoPago.APROBADO
    )

    if not pedido_confirmado:

        logger.error(
            (
                "Webpay autorizó el pago pero "
                "el pedido no quedó confirmado. "
                "Pedido=%s "
                "pagado=%s "
                "estado_pago=%s"
            ),
            pedido.numero,
            pedido.pagado,
            pedido.estado_pago,
        )

        messages.error(
            request,
            (
                "El pago fue aprobado por Webpay, "
                "pero no fue posible confirmar "
                "el pedido correctamente."
            ),
        )

        return redirect(
            "core:pedido_confirmacion",
            numero=pedido.numero,
        )

    # =========================================================================
    # VACIAR CARRITO
    # =========================================================================

    carrito_antes = (
        _obtener_carrito(
            request
        )
    )

    logger.info(
        (
            "CARRITO ANTES DE VACIAR WEBPAY. "
            "Pedido=%s contenido=%s"
        ),
        pedido.numero,
        carrito_antes,
    )

    carrito_vaciado = (
        _vaciar_carrito_pago_confirmado(
            request,
            pedido,
        )
    )

    carrito_despues = (
        _obtener_carrito(
            request
        )
    )

    # =========================================================================
    # SEGUNDO INTENTO SEGURO
    # =========================================================================

    if (
        carrito_despues
        and pedido_pago_en_curso
        == pedido.numero
    ):

        logger.warning(
            (
                "El carrito sigue con contenido "
                "después del primer vaciado Webpay. "
                "Pedido=%s"
            ),
            pedido.numero,
        )

        _guardar_carrito(
            request,
            {},
        )

        request.session.pop(
            "pedido_pago_en_curso",
            None,
        )

        request.session.modified = True

        carrito_despues = (
            _obtener_carrito(
                request
            )
        )

        carrito_vaciado = (
            not bool(
                carrito_despues
            )
        )

    # =========================================================================
    # LIMPIAR INFORMACIÓN TEMPORAL WEBPAY
    # =========================================================================

    request.session.pop(
        "webpay_token",
        None,
    )

    request.session.pop(
        "webpay_pedido",
        None,
    )

    request.session.pop(
        "pedido_pago_en_curso",
        None,
    )

    request.session.modified = True

    # =========================================================================
    # LOG FINAL
    # =========================================================================

    logger.info(
        (
            "WEBPAY COMPLETADO CORRECTAMENTE. "
            "Pedido=%s "
            "pagado=%s "
            "estado_pago=%s "
            "status_webpay=%s "
            "response_code=%s "
            "monto=%s "
            "carrito_vaciado=%s"
        ),
        pedido.numero,
        pedido.pagado,
        pedido.estado_pago,
        status,
        response_code,
        amount,
        carrito_vaciado,
    )

    # =========================================================================
    # MENSAJE
    # =========================================================================

    messages.success(
        request,
        (
            "Tu pago mediante Webpay "
            "fue confirmado correctamente."
        ),
    )

    # =========================================================================
    # CONFIRMACIÓN
    # =========================================================================

    return redirect(
        "core:pedido_confirmacion",
        numero=pedido.numero,
    )