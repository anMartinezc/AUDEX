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
import json
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
        Producto.objects.select_related("categoria"),
        slug=slug,
    )

    if not producto.activo and not es_administrador_productos(
        request.user
    ):
        return redirect("core:productos")

    contexto = {
        "producto": producto,
        "puede_administrar": es_administrador_productos(
            request.user
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

    def form_valid(self, form):
        messages.success(
            self.request,
            "Producto creado correctamente.",
        )

        return super().form_valid(form)


class ProductoEditarView(
    AdministradorProductosMixin,
    UpdateView,
):
    model = Producto
    form_class = ProductoForm
    template_name = "core/producto_formulario.html"
    success_url = reverse_lazy("core:productos")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Producto actualizado correctamente.",
        )

        return super().form_valid(form)


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


@ensure_csrf_cookie
def ofertas(request):
    """
    Página comercial de ofertas.

    Muestra:

    - Productos activos con una rebaja superior al 15%.
    - Cupones generales porcentuales.
    - Cupones generales de monto fijo en CLP.
    - El progreso de fidelidad del usuario autenticado.
    - Los códigos personales disponibles del usuario.

    Los valores de los cupones, compras mínimas,
    porcentajes, vigencias y montos fijos son definidos
    completamente desde el administrador.
    """

    ahora = timezone.now()

    # ------------------------------------------------------------------
    # PRODUCTOS CON MÁS DE 15% DE DESCUENTO
    # ------------------------------------------------------------------

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
                str(producto.precio)
            )
            - Decimal(
                str(producto.precio_oferta)
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
                str(producto.precio_oferta)
            ),
            producto.nombre.casefold(),
        )
    )

    mayor_descuento = max(
        (
            producto.porcentaje_oferta
            for producto in productos_oferta
        ),
        default=0,
    )

    mayor_stock = max(
        (
            producto.stock_oferta
            for producto in productos_oferta
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

    # ------------------------------------------------------------------
    # BASE DE CÓDIGOS GENERALES VIGENTES
    # ------------------------------------------------------------------

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
            | Q(
                fecha_inicio__lte=ahora,
            )
        )
        .filter(
            Q(
                fecha_fin__isnull=True,
            )
            | Q(
                fecha_fin__gt=ahora,
            )
        )
    )

    # ------------------------------------------------------------------
    # CUPONES DE MONTO FIJO EN CLP
    # ------------------------------------------------------------------
    #
    # Ejemplo definido desde el administrador:
    #
    # - Monto de descuento: $38.000
    # - Compra mínima: $313.000
    #
    # La vista no contiene valores comerciales escritos manualmente.
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # CUPONES PORCENTUALES
    # ------------------------------------------------------------------

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

    # Los cupones CLP aparecen primero para destacar
    # el formato "ahorra $X sobre compras de $X".
    codigos_generales = [
        *cupones_clp,
        *codigos_porcentaje,
    ]

    # Se destaca primero un cupón CLP.
    # Si no existe, se utiliza el primer porcentual.
    codigo_destacado = (
        codigos_generales[0]
        if codigos_generales
        else None
    )

    fechas_fin = [
        codigo.fecha_fin
        for codigo in codigos_generales
        if codigo.fecha_fin
    ]

    campana_vence_en = (
        min(fechas_fin)
        if fechas_fin
        else None
    )

    # ------------------------------------------------------------------
    # PROGRAMA DE FIDELIDAD
    # ------------------------------------------------------------------

    configuracion_fidelidad = (
        ConfiguracionFidelidad.obtener()
    )

    fidelidad = None
    codigos_personales = []

    if (
        request.user.is_authenticated
        and configuracion_fidelidad.activa
    ):
        saldo = (
            SaldoFidelidad.objects
            .filter(
                usuario=request.user,
            )
            .first()
        )

        saldo_actual = Decimal(
            str(
                saldo.saldo_actual
                if saldo
                else 0
            )
        )

        monto_objetivo = Decimal(
            str(
                configuracion_fidelidad
                .monto_objetivo
                or 1
            )
        )

        if monto_objetivo <= 0:
            monto_objetivo = Decimal("1")

        faltante = max(
            monto_objetivo
            - saldo_actual,
            Decimal("0"),
        )

        progreso = min(
            int(
                saldo_actual
                * Decimal("100")
                / monto_objetivo
            ),
            100,
        )

        fidelidad = {
            "saldo_actual": saldo_actual,
            "monto_objetivo": monto_objetivo,
            "faltante": faltante,
            "progreso": progreso,
            "porcentaje": (
                configuracion_fidelidad
                .porcentaje
            ),
            "monto_minimo_compra": (
                configuracion_fidelidad
                .monto_minimo_compra
            ),
            "vigencia_dias": (
                configuracion_fidelidad
                .vigencia_dias
            ),
            "metas_cumplidas": (
                saldo.metas_cumplidas
                if saldo
                else 0
            ),
        }

        codigos_personales = list(
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                modalidad=(
                    CodigoDescuento
                    .Modalidad
                    .PORCENTAJE
                ),
                usuario_exclusivo=request.user,
                activo=True,
                consumido=False,
                porcentaje__isnull=False,
                porcentaje__gt=0,
            )
            .filter(
                Q(
                    fecha_inicio__isnull=True,
                )
                | Q(
                    fecha_inicio__lte=ahora,
                )
            )
            .filter(
                Q(
                    fecha_fin__isnull=True,
                )
                | Q(
                    fecha_fin__gt=ahora,
                )
            )
            .order_by(
                "fecha_fin",
                "-creado",
            )
        )

    # ------------------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------------------

    contexto = {
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

        "configuracion_fidelidad": (
            configuracion_fidelidad
        ),
        "fidelidad": (
            fidelidad
        ),
        "codigos_personales": (
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
    carrito = _obtener_carrito(request)

    ids_productos = []

    for producto_id in carrito.keys():
        try:
            ids_productos.append(int(producto_id))
        except (TypeError, ValueError):
            continue

    productos = {
        producto.id: producto
        for producto in Producto.objects.filter(
            id__in=ids_productos,
            activo=True,
        ).select_related("categoria")
    }

    items = []
    subtotal = Decimal("0")
    cantidad_total = 0
    carrito_limpio = {}

    for producto_id_texto, datos in carrito.items():
        try:
            producto_id = int(producto_id_texto)
            cantidad = int(datos.get("cantidad", 1))
        except (TypeError, ValueError, AttributeError):
            continue

        producto = productos.get(producto_id)

        if producto is None:
            continue

        cantidad = max(1, cantidad)

        if producto.stock <= 0:
            continue

        cantidad = min(cantidad, producto.stock)

        precio_unitario = producto.precio_actual
        total_linea = precio_unitario * cantidad

        subtotal += total_linea
        cantidad_total += cantidad

        carrito_limpio[str(producto.id)] = {
            "cantidad": cantidad,
        }

        items.append(
            {
                "id": producto.id,
                "nombre": producto.nombre,
                "slug": producto.slug,
                "categoria": producto.categoria.nombre,
                "cantidad": cantidad,
                "stock": producto.stock,
                "precio": int(precio_unitario),
                "precio_formateado": f"${int(precio_unitario):,}".replace(
                    ",",
                    ".",
                ),
                "total": int(total_linea),
                "total_formateado": f"${int(total_linea):,}".replace(
                    ",",
                    ".",
                ),
                "imagen": producto.imagen_mostrable or "",
                "url_detalle": producto.get_absolute_url(),
                "en_oferta": producto.en_oferta,
            }
        )

    if carrito_limpio != carrito:
        _guardar_carrito(request, carrito_limpio)

    return {
        "items": items,
        "cantidad_total": cantidad_total,
        "subtotal": int(subtotal),
        "subtotal_formateado": f"${int(subtotal):,}".replace(
            ",",
            ".",
        ),
        "vacio": len(items) == 0,
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
























def _errores_formulario(
    formulario,
):
    """
    Convierte los errores del formulario en un texto legible
    para mostrarlo mediante django.contrib.messages.
    """

    errores = []

    for campo, lista_errores in (
        formulario.errors.items()
    ):
        nombre_campo = (
            formulario.fields[campo].label
            if campo in formulario.fields
            else "Formulario"
        )

        for error in lista_errores:
            errores.append(
                f"{nombre_campo}: {error}"
            )

    return " ".join(
        errores
    )


@staff_member_required(
    login_url="core:login",
)
def gestion_descuentos(
    request,
):
    """
    Panel principal para:

    - crear varios códigos generales;
    - configurar el programa de fidelidad;
    - listar todos los códigos;
    - revisar los usos confirmados;
    - revisar el progreso de los clientes.
    """

    configuracion = (
        ConfiguracionFidelidad.obtener()
    )

    formulario_codigo = (
        CodigoGeneralForm()
    )

    formulario_fidelidad = (
        ConfiguracionFidelidadForm(
            instance=configuracion,
        )
    )

    busqueda = (
        request.GET.get(
            "q",
            "",
        )
        or ""
    ).strip()

    tipo = (
        request.GET.get(
            "tipo",
            "",
        )
        or ""
    ).strip()

    estado = (
        request.GET.get(
            "estado",
            "",
        )
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
                distinct=True,
            )
        )
    )

    if busqueda:
        codigos = codigos.filter(
            Q(
                codigo__icontains=busqueda,
            )
            | Q(
                nombre__icontains=busqueda,
            )
            | Q(
                descripcion__icontains=busqueda,
            )
            | Q(
                usuario_exclusivo__email__icontains=busqueda,
            )
            | Q(
                pedidos__numero__icontains=busqueda,
            )
        ).distinct()

    if tipo in TIPOS_CODIGO_VALIDOS:
        codigos = codigos.filter(
            tipo=tipo,
        )

    if estado in ESTADOS_FILTRO_VALIDOS:
        if estado == "activos":
            codigos = codigos.filter(
                activo=True,
                consumido=False,
            )

        elif estado == "inactivos":
            codigos = codigos.filter(
                activo=False,
            )

        elif estado == "consumidos":
            codigos = codigos.filter(
                consumido=True,
            )

    codigos = codigos.order_by(
        "-creado",
        "-pk",
    )

    pagina_codigos = Paginator(
        codigos,
        30,
    ).get_page(
        request.GET.get(
            "pagina"
        )
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
                    .select_related(
                        "producto",
                    )
                    .order_by(
                        "pk",
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
            "-pk",
        )
    )

    pagina_usos = Paginator(
        usos,
        20,
    ).get_page(
        request.GET.get(
            "pagina_usos"
        )
    )

    saldos = list(
        SaldoFidelidad.objects
        .select_related(
            "usuario",
        )
        .order_by(
            "-saldo_actual",
            "-actualizado",
        )[:20]
    )

    objetivo = Decimal(
        str(
            configuracion.monto_objetivo
            or 1
        )
    )

    if objetivo <= Decimal("0"):
        objetivo = Decimal("1")

    for saldo in saldos:
        saldo_actual = Decimal(
            str(
                saldo.saldo_actual
                or 0
            )
        )

        saldo.progreso = min(
            int(
                (
                    saldo_actual
                    * Decimal("100")
                )
                / objetivo
            ),
            100,
        )

        saldo.faltante = max(
            objetivo
            - saldo_actual,
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

    descuento_total = (
        usos_confirmados
        .aggregate(
            total=Sum(
                "descuento_aplicado"
            )
        )
        .get(
            "total"
        )
        or Decimal("0")
    )

    estadisticas = {
        "codigos_generales": (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .GENERAL
                )
            )
            .count()
        ),
        "codigos_fidelidad": (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                )
            )
            .count()
        ),
        "codigos_activos": (
            CodigoDescuento.objects
            .filter(
                activo=True,
                consumido=False,
            )
            .count()
        ),
        "usos_confirmados": (
            usos_confirmados.count()
        ),
        "descuento_total": (
            descuento_total
        ),
    }

    contexto = {
        "configuracion": configuracion,
        "formulario_codigo": (
            formulario_codigo
        ),
        "formulario_fidelidad": (
            formulario_fidelidad
        ),
        "pagina_codigos": (
            pagina_codigos
        ),
        "pagina_usos": (
            pagina_usos
        ),
        "saldos": saldos,
        "estadisticas": (
            estadisticas
        ),
        "busqueda": busqueda,
        "tipo": tipo,
        "estado": estado,
    }

    return render(
        request,
        (
            "core/gestion/"
            "gestion_descuentos.html"
        ),
        contexto,
    )


@staff_member_required(
    login_url="core:login",
)
@require_POST
def crear_codigo_general(
    request,
):
    """
    Crea un código general independiente.

    Pueden existir varios códigos generales activos al mismo tiempo.
    """

    formulario = CodigoGeneralForm(
        request.POST
    )

    if not formulario.is_valid():
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

        return redirect(
            "core:gestion_descuentos"
        )

    try:
        with transaction.atomic():
            codigo = formulario.save(
                commit=False
            )

            codigo.tipo = (
                CodigoDescuento
                .Tipo
                .GENERAL
            )

            codigo.usuario_exclusivo = None
            codigo.numero_meta = None
            codigo.consumido = False
            codigo.creado_por = request.user

            codigo.save()

    except IntegrityError:
        messages.error(
            request,
            (
                "Ya existe un código con "
                "ese identificador."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    except Exception as error:
        messages.error(
            request,
            (
                "No fue posible crear el código. "
                f"Detalle: {error}"
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

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


@staff_member_required(
    login_url="core:login",
)
@require_POST
def guardar_configuracion_fidelidad(
    request,
):
    configuracion = (
        ConfiguracionFidelidad.obtener()
    )

    formulario = (
        ConfiguracionFidelidadForm(
            request.POST,
            instance=configuracion,
        )
    )

    if not formulario.is_valid():
        messages.error(
            request,
            (
                _errores_formulario(
                    formulario
                )
                or (
                    "No fue posible guardar "
                    "la configuración."
                )
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    try:
        with transaction.atomic():
            configuracion = (
                formulario.save(
                    commit=False
                )
            )

            configuracion.actualizado_por = (
                request.user
            )

            configuracion.save()

    except Exception as error:
        messages.error(
            request,
            (
                "No fue posible guardar la "
                "configuración de fidelidad. "
                f"Detalle: {error}"
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    messages.success(
        request,
        (
            "La configuración de fidelidad "
            "fue actualizada."
        ),
    )

    return redirect(
        "core:gestion_descuentos"
    )


@staff_member_required(
    login_url="core:login",
)
@require_POST
def alternar_codigo_descuento(
    request,
    codigo_id,
):
    """
    Activa o desactiva códigos generales y premios personales.

    Se actualiza directamente el campo para no volver a ejecutar
    full_clean() sobre códigos históricos creados antes de esta versión.
    """

    codigo = get_object_or_404(
        CodigoDescuento,
        pk=codigo_id,
    )

    nuevo_estado = (
        not codigo.activo
    )

    actualizado = (
        CodigoDescuento.objects
        .filter(
            pk=codigo.pk,
        )
        .update(
            activo=nuevo_estado,
            actualizado=timezone.now(),
        )
    )

    if not actualizado:
        messages.error(
            request,
            (
                "No fue posible actualizar "
                "el estado del código."
            ),
        )

        return redirect(
            "core:gestion_descuentos"
        )

    estado_texto = (
        "activado"
        if nuevo_estado
        else "desactivado"
    )

    messages.success(
        request,
        (
            f"El código {codigo.codigo} "
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

def checkout(request):
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

    datos_iniciales = (
        obtener_datos_iniciales_checkout(
            request
        )
    )

    # -------------------------------------------------------------------------
    # FORMULARIO
    # -------------------------------------------------------------------------

    if request.method == "POST":
        form = CheckoutForm(
            request.POST,
            initial=datos_iniciales,
        )

        if form.is_valid():
            pedido = None

            try:
                # -------------------------------------------------------------
                # CREAR PEDIDO
                # -------------------------------------------------------------
                #
                # procesar_pedido_checkout() debe:
                #
                # - volver a validar productos y stock;
                # - resolver el código usando el RUT;
                # - crear Pedido y PedidoItem;
                # - reservar UsoCodigoDescuento;
                # - guardar el detalle histórico del descuento.
                # -------------------------------------------------------------

                with transaction.atomic():
                    pedido = (
                        procesar_pedido_checkout(
                            request=request,
                            form=form,
                            carrito=carrito,
                        )
                    )

                # -------------------------------------------------------------
                # INICIAR PAGO
                # -------------------------------------------------------------

                resultado_pago = (
                    iniciar_pago_pedido(
                        request=request,
                        pedido=pedido,
                    )
                )

                # -------------------------------------------------------------
                # REGISTRAR PEDIDO EN LA SESIÓN
                # -------------------------------------------------------------

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

                # -------------------------------------------------------------
                # REDIRECCIONAR AL PROVEEDOR
                # -------------------------------------------------------------

                if resultado_pago.url_redireccion:
                    return redirect(
                        resultado_pago.url_redireccion
                    )

                return redirect(
                    resultado_pago.nombre_url,
                    **resultado_pago.parametros_url,
                )

            except ErrorInicioPago as error:
                # El proveedor no pudo iniciar el pago.
                # El código reservado debe quedar nuevamente disponible.

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

                form.add_error(
                    None,
                    str(error),
                )

            except ValueError as error:
                # Incluye errores de stock, carrito, código inválido,
                # código ya utilizado, compra mínima o RUT faltante.

                request.session.pop(
                    "pedido_pago_en_curso",
                    None,
                )

                request.session.modified = True

                _liberar_descuento_si_corresponde(
                    pedido
                )

                form.add_error(
                    None,
                    str(error),
                )

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

    # -------------------------------------------------------------------------
    # CÓDIGO Y RUT PARA EL RESUMEN
    # -------------------------------------------------------------------------
    #
    # La validación del código necesita el RUT porque cada cliente
    # solamente puede utilizar cada código una vez.
    # -------------------------------------------------------------------------

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

    else:
        codigo_descuento = ""

        rut_descuento = (
            datos_iniciales.get(
                "rut",
                "",
            )
            or ""
        ).strip()

    # -------------------------------------------------------------------------
    # RESUMEN
    # -------------------------------------------------------------------------

    resumen = calcular_resumen_checkout(
        request=request,
        carrito_serializado=(
            carrito_serializado
        ),
        codigo=codigo_descuento,
        rut=rut_descuento,
    )

    # -------------------------------------------------------------------------
    # PREMIOS PERSONALES DISPONIBLES
    # -------------------------------------------------------------------------

    codigos_fidelidad = (
        obtener_codigos_disponibles(
            request.user
        )
    )

    # -------------------------------------------------------------------------
    # CONTEXTO
    # -------------------------------------------------------------------------

    contexto = {
        "form": form,
        "carrito": carrito_serializado,
        "resumen": resumen,
        "codigos_fidelidad": codigos_fidelidad,
        "comunas_por_region": (
            COMUNAS_POR_REGION
        ),
    }

    return render(
        request,
        "core/checkout.html",
        contexto,
    )


# ============================================================================
# CAMBIO OBLIGATORIO EN calcular_resumen_checkout()
# ============================================================================
#
# Su firma debe aceptar rut:
#
# def calcular_resumen_checkout(
#     *,
#     request,
#     carrito_serializado,
#     codigo="",
#     rut="",
# ):
#
# Y debe llamar:
#
# resultado = resolver_descuento(
#     usuario=request.user,
#     rut=rut,
#     subtotal=subtotal,
#     codigo=codigo,
#     bloquear=False,
# )
#
#
# El error actual:
#
# NameError: name 'resolver_descuento' is not defined
# NameError: name 'DescuentoError' is not defined
#
# se corrige con estos imports:
#
# from core.services.descuentos import (
#     DescuentoError,
#     resolver_descuento,
# )
# ============================================================================


# ============================================================================
# CAMBIO OBLIGATORIO EN EL ENDPOINT AJAX DEL CUPÓN
# ============================================================================
#
# El endpoint debe leer el RUT:
#
# rut = (
#     request.POST.get(
#         "rut",
#         "",
#     )
#     or ""
# ).strip()
#
# Y pasarlo al resumen:
#
# resumen = calcular_resumen_checkout(
#     request=request,
#     carrito_serializado=carrito_serializado,
#     codigo=codigo,
#     rut=rut,
# )
#
#
# En checkout.js agrega al URLSearchParams:
#
# const campoRut = document.getElementById("id_rut");
#
# cuerpo.set(
#     "rut",
#     campoRut?.value || ""
# );
# ============================================================================
@require_POST
def checkout_resumen_descuento(
    request,
):
    """
    Valida un código de descuento desde el checkout sin
    crear todavía el pedido.

    El RUT permite comprobar que el cliente no haya usado
    anteriormente el mismo código.
    """

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
                "porcentaje_descuento": 0,
                "descuento": 0,
                "descuento_formateado": "$0",
                "despacho": 0,
                "despacho_formateado": "$0",
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
                "porcentaje_descuento": 0,
                "descuento": 0,
                "descuento_formateado": "$0",
                "despacho": 0,
                "despacho_formateado": "$0",
                "total": 0,
                "total_formateado": "$0",
            },
            status=400,
        )

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

    resumen = calcular_resumen_checkout(
        request=request,
        carrito_serializado=(
            carrito_serializado
        ),
        codigo=codigo,
        rut=rut,
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

    codigo_aplicado = (
        resumen.get(
            "codigo_aplicado",
            "",
        )
        or ""
    )

    error_descuento = (
        resumen.get(
            "error_descuento",
            "",
        )
        or ""
    )

    def formatear_pesos(
        valor,
    ):
        valor_entero = int(
            Decimal(
                str(valor or 0)
            )
        )

        return (
            f"${valor_entero:,}"
            .replace(
                ",",
                ".",
            )
        )

    if error_descuento:
        mensaje = error_descuento
        codigo_aplicado = ""
        porcentaje = Decimal("0")

    elif codigo_aplicado:
        mensaje = (
            f"Código {codigo_aplicado} aplicado: "
            f"{porcentaje:g}% de descuento."
        )

    elif codigo:
        mensaje = (
            "El código no pudo aplicarse."
        )

    else:
        mensaje = (
            "No hay un código aplicado."
        )

    return JsonResponse(
        {
            "ok": not bool(
                error_descuento
            ),
            "mensaje": mensaje,
            "codigo_aplicado": (
                codigo_aplicado
            ),
            "porcentaje_descuento": (
                float(
                    porcentaje
                )
            ),
            "descuento": int(
                descuento
            ),
            "descuento_formateado": (
                formatear_pesos(
                    descuento
                )
            ),
            "despacho": int(
                despacho
            ),
            "despacho_formateado": (
                "Gratis"
                if despacho == 0
                else formatear_pesos(
                    despacho
                )
            ),
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
):
    """
    Calcula el resumen del checkout y valida el código de descuento.

    El RUT se utiliza para impedir que un mismo cliente utilice
    el mismo código más de una vez, incluso cuando compra como invitado.
    """

    subtotal = Decimal(
        str(
            carrito_serializado.get(
                "subtotal",
                0,
            )
            or 0
        )
    )

    codigo = (
        codigo
        or ""
    ).strip().upper()

    rut = (
        rut
        or ""
    ).strip().upper()

    error_descuento = ""

    try:
        resultado_descuento = resolver_descuento(
            usuario=request.user,
            rut=rut,
            subtotal=subtotal,
            codigo=codigo,
            bloquear=False,
        )

    except DescuentoError as error:
        resultado_descuento = None
        error_descuento = str(error)

    if resultado_descuento is None:
        descuento = Decimal("0")
        porcentaje = Decimal("0")
        codigo_aplicado = ""

        tipo_descuento = (
            Pedido.TipoDescuento.NINGUNO
        )

    else:
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

        codigo_aplicado = (
            resultado_descuento.codigo
            or ""
        )

        tipo_descuento = (
            resultado_descuento.tipo
            or Pedido.TipoDescuento.NINGUNO
        )

    descuento = max(
        min(
            descuento,
            subtotal,
        ),
        Decimal("0"),
    )

    subtotal_con_descuento = max(
        subtotal - descuento,
        Decimal("0"),
    )

    despacho = (
        Decimal("0")
        if subtotal_con_descuento
        >= META_DESPACHO_GRATIS
        else COSTO_DESPACHO
    )

    total = max(
        subtotal_con_descuento
        + despacho,
        Decimal("0"),
    )

    return {
        "subtotal": subtotal,
        "descuento": descuento,
        "porcentaje_descuento": porcentaje,
        "codigo_aplicado": codigo_aplicado,
        "tipo_descuento": tipo_descuento,
        "error_descuento": error_descuento,
        "despacho": despacho,
        "total": total,
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

    # -------------------------------------------------------------------------
    # CONTROL DE ACCESO
    # -------------------------------------------------------------------------

    if pedido.usuario_id:
        if not request.user.is_authenticated:
            return redirect(
                "core:inicio"
            )

        if (
            pedido.usuario_id != request.user.pk
            and not request.user.is_staff
        ):
            return redirect(
                "core:inicio"
            )

    # -------------------------------------------------------------------------
    # COMPROBAR QUE EL PAGO ESTÉ REALMENTE APROBADO
    # -------------------------------------------------------------------------

    pago_aprobado = (
        pedido.pagado
        and pedido.estado_pago
        == Pedido.EstadoPago.APROBADO
    )

    if not pago_aprobado:
        messages.warning(
            request,
            (
                "Este pedido todavía no tiene "
                "un pago confirmado."
            ),
        )

        return render(
            request,
            "core/pago_resultado.html",
            {
                "pedido": pedido,
                "resultado": "pendiente",
            },
            status=202,
        )

    # Utiliza la plantilla cuyo CSS ya está funcionando.
    return render(
        request,
        "core/pago_exitoso.html",
        {
            "pedido": pedido,
        },
    )




@require_GET
def mercadopago_retorno_exitoso(
    request,
    numero,
):
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

    # -------------------------------------------------------------------------
    # CONTROL DE ACCESO
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # PAGO APROBADO
    # -------------------------------------------------------------------------

    if pedido.pago_aprobado:
        carrito_vaciado = (
            _vaciar_carrito_pago_confirmado(
                request,
                pedido,
            )
        )

        logger.info(
            (
                "Retorno exitoso del pedido %s. "
                "Carrito vaciado=%s."
            ),
            pedido.numero,
            carrito_vaciado,
        )

        return render(
            request,
            "core/pago_exitoso.html",
            {
                "pedido": pedido,
                "carrito_vaciado": carrito_vaciado,
            },
        )

    # -------------------------------------------------------------------------
    # EL WEBHOOK TODAVÍA NO TERMINA
    # -------------------------------------------------------------------------

    logger.info(
        (
            "El navegador regresó para el pedido %s, "
            "pero el webhook todavía no lo marca aprobado."
        ),
        pedido.numero,
    )

    return render(
        request,
        "core/pago_resultado.html",
        {
            "pedido": pedido,
            "resultado": "pendiente",
        },
        status=202,
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

    return render(
        request,
        "core/pago_resultado.html",
        {
            "pedido": pedido,
            "resultado": "pendiente",
        },
    )


@require_GET
def mercadopago_retorno_fallido(
    request,
    numero,
):
    pedido = get_object_or_404(
        Pedido,
        numero=numero,
    )

    return render(
        request,
        "core/pago_resultado.html",
        {
            "pedido": pedido,
            "resultado": "fallido",
        },
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





def confirmar_pago_mercadopago(pago):
    if not isinstance(pago, dict):
        raise ConfirmacionPagoError(
            "Los datos del pago de Mercado Pago no son válidos."
        )

    payment_id = str(
        pago.get("id")
        or ""
    ).strip()

    estado_pago = str(
        pago.get("status")
        or ""
    ).strip().lower()

    numero_pedido = str(
        pago.get("external_reference")
        or ""
    ).strip()

    if not payment_id:
        raise ConfirmacionPagoError(
            "El pago no contiene un ID."
        )

    if not numero_pedido:
        raise ConfirmacionPagoError(
            "El pago no contiene external_reference."
        )

    if estado_pago != "approved":
        raise ConfirmacionPagoError(
            (
                "El pago todavía no está aprobado. "
                f"Estado recibido: {estado_pago or 'sin estado'}"
            )
        )

    try:
        pedido = Pedido.objects.get(
            numero=numero_pedido,
        )
    except Pedido.DoesNotExist as error:
        raise ConfirmacionPagoError(
            (
                "No existe un pedido asociado a la referencia "
                f"{numero_pedido}."
            )
        ) from error

    monto_pagado = Decimal(
        str(
            pago.get("transaction_amount")
            or "0"
        )
    )

    if monto_pagado != pedido.total:
        raise ConfirmacionPagoError(
            (
                "El monto pagado no coincide con el pedido. "
                f"Pedido: {pedido.total}. "
                f"Pago: {monto_pagado}."
            )
        )

    return marcar_pedido_como_pagado(
        pedido_id=pedido.pk,
        datos_pago={
            "metodo": Pedido.MetodoPago.MERCADOPAGO,
            "payment_id": payment_id,
            "mercadopago_status": estado_pago,
            "mercadopago_status_detail": pago.get(
                "status_detail"
            ),
            "payment_type": pago.get(
                "payment_type_id"
            ),
            "transaction_amount": monto_pagado,
        },
    )



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
    contexto = {
        "usuario_perfil": request.user,
    }

    return render(
        request,
        "core/cuenta/perfil.html",
        contexto,
    )