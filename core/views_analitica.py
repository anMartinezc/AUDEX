from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import ceil

from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
)
from django.db.models import (
    Avg,
    Count,
    Sum,
)
from django.db.models.functions import (
    TruncDay,
    TruncMonth,
)
from django.shortcuts import render
from django.utils import timezone

from core.models import (
    Categoria,
    Pedido,
    PedidoItem,
    Producto,
)
from core.permisos import es_administrador_productos


MESES_CORTOS = [
    "",
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]


def _convertir_fecha(valor, predeterminada):
    if not valor:
        return predeterminada

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        return predeterminada


def _convertir_entero(
    valor,
    predeterminado=None,
    minimo=None,
    maximo=None,
):
    try:
        numero = int(valor)

    except (TypeError, ValueError):
        return predeterminado

    if minimo is not None:
        numero = max(
            minimo,
            numero,
        )

    if maximo is not None:
        numero = min(
            maximo,
            numero,
        )

    return numero


def _rango_datetime(
    desde,
    hasta,
):
    """
    Genera un rango [inicio, fin) compatible con campos DateTimeField.
    """

    zona = timezone.get_current_timezone()

    inicio = timezone.make_aware(
        datetime.combine(
            desde,
            time.min,
        ),
        zona,
    )

    fin = timezone.make_aware(
        datetime.combine(
            hasta + timedelta(days=1),
            time.min,
        ),
        zona,
    )

    return inicio, fin


def _siguiente_mes(fecha):
    if fecha.month == 12:
        return date(
            fecha.year + 1,
            1,
            1,
        )

    return date(
        fecha.year,
        fecha.month + 1,
        1,
    )


def _generar_periodos(
    desde,
    hasta,
    agrupacion,
):
    periodos = []

    if agrupacion == "dia":
        actual = desde

        while actual <= hasta:
            periodos.append(actual)
            actual += timedelta(days=1)

        return periodos

    actual = date(
        desde.year,
        desde.month,
        1,
    )

    limite = date(
        hasta.year,
        hasta.month,
        1,
    )

    while actual <= limite:
        periodos.append(actual)
        actual = _siguiente_mes(actual)

    return periodos


def _clave_periodo(
    fecha,
    agrupacion,
):
    if agrupacion == "mes":
        return date(
            fecha.year,
            fecha.month,
            1,
        )

    return date(
        fecha.year,
        fecha.month,
        fecha.day,
    )


def _etiqueta_periodo(
    fecha,
    agrupacion,
):
    if agrupacion == "mes":
        return (
            f"{MESES_CORTOS[fecha.month]} "
            f"{fecha.year}"
        )

    return fecha.strftime(
        "%d/%m/%Y"
    )


@login_required(
    login_url="core:login",
)
@user_passes_test(
    es_administrador_productos,
    login_url="core:inicio",
)
def analisis_ventas(request):
    hoy = timezone.localdate()

    desde_predeterminado = date(
        hoy.year,
        1,
        1,
    )

    desde = _convertir_fecha(
        request.GET.get("desde"),
        desde_predeterminado,
    )

    hasta = _convertir_fecha(
        request.GET.get("hasta"),
        hoy,
    )

    if desde > hasta:
        desde, hasta = hasta, desde

    agrupacion = request.GET.get(
        "agrupar",
        "mes",
    )

    if agrupacion not in {
        "dia",
        "mes",
    }:
        agrupacion = "mes"

    categoria_id = _convertir_entero(
        request.GET.get("categoria"),
    )

    producto_id = _convertir_entero(
        request.GET.get("producto"),
    )

    inicio, fin = _rango_datetime(
        desde,
        hasta,
    )

    # ---------------------------------------------------------------------
    # PEDIDOS APROBADOS
    # ---------------------------------------------------------------------

    pedidos_aprobados = Pedido.objects.filter(
        pagado=True,
        estado_pago=Pedido.EstadoPago.APROBADO,
        fecha_pago__gte=inicio,
        fecha_pago__lt=fin,
    )

    items = PedidoItem.objects.filter(
        pedido__in=pedidos_aprobados,
    ).select_related(
        "pedido",
        "producto",
        "producto__categoria",
    )

    if categoria_id:
        items = items.filter(
            producto__categoria_id=categoria_id,
        )

    if producto_id:
        items = items.filter(
            producto_id=producto_id,
        )

    pedidos_filtrados = Pedido.objects.filter(
        pk__in=items.values(
            "pedido_id"
        ),
    )

    # ---------------------------------------------------------------------
    # INDICADORES GENERALES
    # ---------------------------------------------------------------------

    resumen_items = items.aggregate(
        ingresos=Sum("total"),
        unidades=Sum("cantidad"),
    )

    ingresos = (
        resumen_items["ingresos"]
        or Decimal("0")
    )

    unidades = (
        resumen_items["unidades"]
        or 0
    )

    cantidad_pedidos = (
        pedidos_filtrados.count()
    )

    ticket_promedio = (
        ingresos / cantidad_pedidos
        if cantidad_pedidos
        else Decimal("0")
    )

    resumen_pedidos = (
        pedidos_filtrados.aggregate(
            total_cobrado=Sum("total"),
            descuento=Sum("descuento"),
            despacho=Sum("despacho"),
            promedio_pedido=Avg("total"),
        )
    )

    # ---------------------------------------------------------------------
    # SERIE TEMPORAL
    # ---------------------------------------------------------------------

    zona = timezone.get_current_timezone()

    if agrupacion == "dia":
        truncador = TruncDay(
            "pedido__fecha_pago",
            tzinfo=zona,
        )
    else:
        truncador = TruncMonth(
            "pedido__fecha_pago",
            tzinfo=zona,
        )

    datos_periodo = (
        items
        .annotate(
            periodo=truncador,
        )
        .values(
            "periodo",
        )
        .annotate(
            ingresos=Sum("total"),
            unidades=Sum("cantidad"),
            pedidos=Count(
                "pedido_id",
                distinct=True,
            ),
        )
        .order_by(
            "periodo",
        )
    )

    mapa_periodos = {}

    for fila in datos_periodo:
        periodo = fila["periodo"]

        clave = _clave_periodo(
            periodo,
            agrupacion,
        )

        mapa_periodos[clave] = {
            "ingresos": int(
                fila["ingresos"]
                or 0
            ),
            "unidades": int(
                fila["unidades"]
                or 0
            ),
            "pedidos": int(
                fila["pedidos"]
                or 0
            ),
        }

    periodos = _generar_periodos(
        desde,
        hasta,
        agrupacion,
    )

    grafico_ventas = {
        "labels": [
            _etiqueta_periodo(
                periodo,
                agrupacion,
            )
            for periodo in periodos
        ],
        "ingresos": [
            mapa_periodos
            .get(
                periodo,
                {},
            )
            .get(
                "ingresos",
                0,
            )
            for periodo in periodos
        ],
        "unidades": [
            mapa_periodos
            .get(
                periodo,
                {},
            )
            .get(
                "unidades",
                0,
            )
            for periodo in periodos
        ],
        "pedidos": [
            mapa_periodos
            .get(
                periodo,
                {},
            )
            .get(
                "pedidos",
                0,
            )
            for periodo in periodos
        ],
    }

    # ---------------------------------------------------------------------
    # PRODUCTOS MÁS VENDIDOS
    # ---------------------------------------------------------------------

    top_productos_queryset = (
        items
        .values(
            "producto_id",
            "nombre_producto",
            "producto__categoria__nombre",
        )
        .annotate(
            unidades=Sum("cantidad"),
            ingresos=Sum("total"),
            pedidos=Count(
                "pedido_id",
                distinct=True,
            ),
        )
        .order_by(
            "-unidades",
            "-ingresos",
        )[:10]
    )

    top_productos = []

    for fila in top_productos_queryset:
        top_productos.append(
            {
                "producto_id": fila[
                    "producto_id"
                ],
                "nombre": fila[
                    "nombre_producto"
                ],
                "categoria": (
                    fila[
                        "producto__categoria__nombre"
                    ]
                    or "Sin categoría"
                ),
                "unidades": int(
                    fila["unidades"]
                    or 0
                ),
                "ingresos": int(
                    fila["ingresos"]
                    or 0
                ),
                "pedidos": int(
                    fila["pedidos"]
                    or 0
                ),
            }
        )

    grafico_productos = {
        "labels": [
            producto["nombre"]
            for producto in top_productos
        ],
        "unidades": [
            producto["unidades"]
            for producto in top_productos
        ],
        "ingresos": [
            producto["ingresos"]
            for producto in top_productos
        ],
    }

    # ---------------------------------------------------------------------
    # VENTAS POR CATEGORÍA
    # ---------------------------------------------------------------------

    ventas_categorias_queryset = (
        items
        .values(
            "producto__categoria__nombre",
        )
        .annotate(
            unidades=Sum("cantidad"),
            ingresos=Sum("total"),
        )
        .order_by(
            "-ingresos",
        )
    )

    ventas_categorias = []

    for fila in ventas_categorias_queryset:
        ventas_categorias.append(
            {
                "nombre": (
                    fila[
                        "producto__categoria__nombre"
                    ]
                    or "Sin categoría"
                ),
                "unidades": int(
                    fila["unidades"]
                    or 0
                ),
                "ingresos": int(
                    fila["ingresos"]
                    or 0
                ),
            }
        )

    grafico_categorias = {
        "labels": [
            categoria["nombre"]
            for categoria in ventas_categorias
        ],
        "unidades": [
            categoria["unidades"]
            for categoria in ventas_categorias
        ],
        "ingresos": [
            categoria["ingresos"]
            for categoria in ventas_categorias
        ],
    }

    # ---------------------------------------------------------------------
    # MÉTODOS DE PAGO
    # ---------------------------------------------------------------------

    nombres_metodos = dict(
        Pedido.MetodoPago.choices
    )

    metodos_queryset = (
        pedidos_filtrados
        .values(
            "metodo_pago",
        )
        .annotate(
            cantidad=Count("id"),
            total=Sum("total"),
        )
        .order_by(
            "-cantidad",
        )
    )

    metodos_pago = []

    for fila in metodos_queryset:
        metodos_pago.append(
            {
                "nombre": nombres_metodos.get(
                    fila["metodo_pago"],
                    fila["metodo_pago"],
                ),
                "cantidad": int(
                    fila["cantidad"]
                    or 0
                ),
                "total": int(
                    fila["total"]
                    or 0
                ),
            }
        )

    grafico_metodos = {
        "labels": [
            metodo["nombre"]
            for metodo in metodos_pago
        ],
        "cantidades": [
            metodo["cantidad"]
            for metodo in metodos_pago
        ],
    }

    pedidos_recientes = (
        pedidos_filtrados
        .order_by(
            "-fecha_pago",
        )[:8]
    )

    categorias = Categoria.objects.filter(
        activa=True,
    ).order_by(
        "nombre",
    )

    productos = Producto.objects.filter(
        activo=True,
    ).order_by(
        "nombre",
    )

    contexto = {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "agrupacion": agrupacion,
        "categoria_id": categoria_id,
        "producto_id": producto_id,
        "categorias": categorias,
        "productos": productos,

        "ingresos": ingresos,
        "unidades": unidades,
        "cantidad_pedidos": cantidad_pedidos,
        "ticket_promedio": ticket_promedio,

        "total_cobrado": (
            resumen_pedidos[
                "total_cobrado"
            ]
            or Decimal("0")
        ),
        "descuento_total": (
            resumen_pedidos[
                "descuento"
            ]
            or Decimal("0")
        ),
        "despacho_total": (
            resumen_pedidos[
                "despacho"
            ]
            or Decimal("0")
        ),

        "producto_lider": (
            top_productos[0]
            if top_productos
            else None
        ),

        "top_productos": top_productos,
        "ventas_categorias": ventas_categorias,
        "pedidos_recientes": pedidos_recientes,

        "grafico_ventas": grafico_ventas,
        "grafico_productos": grafico_productos,
        "grafico_categorias": grafico_categorias,
        "grafico_metodos": grafico_metodos,
    }

    return render(
        request,
        "core/gestion/analisis_ventas.html",
        contexto,
    )


@login_required(
    login_url="core:login",
)
@user_passes_test(
    es_administrador_productos,
    login_url="core:inicio",
)
def analisis_stock(request):
    hoy = timezone.localdate()

    desde = _convertir_fecha(
        request.GET.get("desde"),
        hoy - timedelta(days=29),
    )

    hasta = _convertir_fecha(
        request.GET.get("hasta"),
        hoy,
    )

    if desde > hasta:
        desde, hasta = hasta, desde

    categoria_id = _convertir_entero(
        request.GET.get("categoria"),
    )

    stock_critico = _convertir_entero(
        request.GET.get("stock_critico"),
        predeterminado=5,
        minimo=0,
        maximo=9999,
    )

    plazo_reposicion = _convertir_entero(
        request.GET.get("plazo_reposicion"),
        predeterminado=15,
        minimo=1,
        maximo=365,
    )

    dias_seguridad = _convertir_entero(
        request.GET.get("dias_seguridad"),
        predeterminado=7,
        minimo=0,
        maximo=365,
    )

    inicio, fin = _rango_datetime(
        desde,
        hasta,
    )

    cantidad_dias = max(
        (
            hasta - desde
        ).days + 1,
        1,
    )

    # ---------------------------------------------------------------------
    # PRODUCTOS
    # ---------------------------------------------------------------------

    productos_queryset = (
        Producto.objects
        .filter(
            activo=True,
        )
        .select_related(
            "categoria",
        )
        .order_by(
            "nombre",
        )
    )

    if categoria_id:
        productos_queryset = (
            productos_queryset.filter(
                categoria_id=categoria_id,
            )
        )

    # ---------------------------------------------------------------------
    # VENTAS DEL PERÍODO
    # ---------------------------------------------------------------------

    items_periodo = PedidoItem.objects.filter(
        pedido__pagado=True,
        pedido__estado_pago=(
            Pedido.EstadoPago.APROBADO
        ),
        pedido__fecha_pago__gte=inicio,
        pedido__fecha_pago__lt=fin,
        producto_id__isnull=False,
    )

    if categoria_id:
        items_periodo = items_periodo.filter(
            producto__categoria_id=categoria_id,
        )

    ventas_por_producto_queryset = (
        items_periodo
        .values(
            "producto_id",
        )
        .annotate(
            unidades=Sum("cantidad"),
            ingresos=Sum("total"),
        )
    )

    ventas_por_producto = {
        fila["producto_id"]: {
            "unidades": int(
                fila["unidades"]
                or 0
            ),
            "ingresos": int(
                fila["ingresos"]
                or 0
            ),
        }
        for fila in ventas_por_producto_queryset
    }

    productos_analisis = []

    total_stock = 0
    total_reservado = 0
    total_disponible = 0
    valor_inventario = Decimal("0")
    cantidad_agotados = 0
    cantidad_criticos = 0
    reposicion_sugerida_total = 0

    stock_por_categoria = {}

    for producto in productos_queryset:
        venta = ventas_por_producto.get(
            producto.pk,
            {
                "unidades": 0,
                "ingresos": 0,
            },
        )

        unidades_vendidas = venta[
            "unidades"
        ]

        velocidad_diaria = (
            unidades_vendidas
            / cantidad_dias
        )

        stock_disponible = max(
            producto.stock
            - producto.stock_reservado,
            0,
        )

        if velocidad_diaria > 0:
            dias_cobertura = (
                stock_disponible
                / velocidad_diaria
            )
        else:
            dias_cobertura = None

        punto_reposicion = ceil(
            velocidad_diaria
            * (
                plazo_reposicion
                + dias_seguridad
            )
        )

        reposicion_sugerida = max(
            punto_reposicion
            - stock_disponible,
            0,
        )

        if stock_disponible <= 0:
            estado = "agotado"
            cantidad_agotados += 1

        elif stock_disponible <= stock_critico:
            estado = "critico"
            cantidad_criticos += 1

        elif (
            dias_cobertura is not None
            and dias_cobertura
            <= (
                plazo_reposicion
                + dias_seguridad
            )
        ):
            estado = "bajo"

        else:
            estado = "normal"

        valor_producto = (
            producto.precio_actual
            * producto.stock
        )

        total_stock += producto.stock
        total_reservado += (
            producto.stock_reservado
        )
        total_disponible += stock_disponible
        valor_inventario += valor_producto
        reposicion_sugerida_total += (
            reposicion_sugerida
        )

        categoria_nombre = (
            producto.categoria.nombre
        )

        if categoria_nombre not in stock_por_categoria:
            stock_por_categoria[
                categoria_nombre
            ] = {
                "stock": 0,
                "disponible": 0,
                "valor": Decimal("0"),
            }

        stock_por_categoria[
            categoria_nombre
        ]["stock"] += producto.stock

        stock_por_categoria[
            categoria_nombre
        ]["disponible"] += (
            stock_disponible
        )

        stock_por_categoria[
            categoria_nombre
        ]["valor"] += valor_producto

        productos_analisis.append(
            {
                "id": producto.pk,
                "nombre": producto.nombre,
                "categoria": categoria_nombre,
                "stock": producto.stock,
                "reservado": (
                    producto.stock_reservado
                ),
                "disponible": stock_disponible,
                "vendidas": unidades_vendidas,
                "ingresos": venta["ingresos"],
                "velocidad_diaria": round(
                    velocidad_diaria,
                    2,
                ),
                "dias_cobertura": (
                    round(
                        dias_cobertura,
                        1,
                    )
                    if dias_cobertura
                    is not None
                    else None
                ),
                "punto_reposicion": (
                    punto_reposicion
                ),
                "reponer": reposicion_sugerida,
                "valor": int(
                    valor_producto
                ),
                "estado": estado,
            }
        )

    orden_estados = {
        "agotado": 0,
        "critico": 1,
        "bajo": 2,
        "normal": 3,
    }

    productos_analisis.sort(
        key=lambda producto: (
            orden_estados[
                producto["estado"]
            ],
            producto["disponible"],
            producto["nombre"],
        )
    )

    # ---------------------------------------------------------------------
    # SALIDAS DIARIAS
    # ---------------------------------------------------------------------

    salidas_queryset = (
        items_periodo
        .annotate(
            dia=TruncDay(
                "pedido__fecha_pago",
                tzinfo=(
                    timezone
                    .get_current_timezone()
                ),
            ),
        )
        .values(
            "dia",
        )
        .annotate(
            unidades=Sum("cantidad"),
        )
        .order_by(
            "dia",
        )
    )

    salidas_por_dia = {}

    for fila in salidas_queryset:
        clave = fila["dia"].date()

        salidas_por_dia[clave] = int(
            fila["unidades"]
            or 0
        )

    dias_periodo = _generar_periodos(
        desde,
        hasta,
        "dia",
    )

    grafico_salidas = {
        "labels": [
            dia.strftime("%d/%m")
            for dia in dias_periodo
        ],
        "unidades": [
            salidas_por_dia.get(
                dia,
                0,
            )
            for dia in dias_periodo
        ],
    }

    # ---------------------------------------------------------------------
    # GRÁFICOS DE STOCK
    # ---------------------------------------------------------------------

    productos_stock_grafico = sorted(
        productos_analisis,
        key=lambda producto: (
            producto["disponible"],
            producto["nombre"],
        ),
    )[:15]

    grafico_stock = {
        "labels": [
            producto["nombre"]
            for producto
            in productos_stock_grafico
        ],
        "disponible": [
            producto["disponible"]
            for producto
            in productos_stock_grafico
        ],
        "reservado": [
            producto["reservado"]
            for producto
            in productos_stock_grafico
        ],
    }

    productos_consumo = sorted(
        productos_analisis,
        key=lambda producto: (
            -producto["vendidas"],
            producto["nombre"],
        ),
    )[:10]

    grafico_consumo = {
        "labels": [
            producto["nombre"]
            for producto in productos_consumo
        ],
        "vendidas": [
            producto["vendidas"]
            for producto in productos_consumo
        ],
        "cobertura": [
            (
                producto["dias_cobertura"]
                or 0
            )
            for producto in productos_consumo
        ],
    }

    categorias_stock = [
        {
            "nombre": nombre,
            "stock": datos["stock"],
            "disponible": datos[
                "disponible"
            ],
            "valor": int(
                datos["valor"]
            ),
        }
        for nombre, datos
        in stock_por_categoria.items()
    ]

    categorias_stock.sort(
        key=lambda categoria: (
            -categoria["stock"]
        )
    )

    grafico_categorias = {
        "labels": [
            categoria["nombre"]
            for categoria
            in categorias_stock
        ],
        "stock": [
            categoria["stock"]
            for categoria
            in categorias_stock
        ],
    }

    categorias = Categoria.objects.filter(
        activa=True,
    ).order_by(
        "nombre",
    )

    contexto = {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "categoria_id": categoria_id,
        "stock_critico": stock_critico,
        "plazo_reposicion": plazo_reposicion,
        "dias_seguridad": dias_seguridad,
        "cantidad_dias": cantidad_dias,
        "categorias": categorias,

        "total_stock": total_stock,
        "total_reservado": total_reservado,
        "total_disponible": total_disponible,
        "valor_inventario": valor_inventario,
        "cantidad_agotados": cantidad_agotados,
        "cantidad_criticos": cantidad_criticos,
        "reposicion_sugerida_total": (
            reposicion_sugerida_total
        ),

        "productos_analisis": (
            productos_analisis
        ),
        "categorias_stock": categorias_stock,

        "grafico_stock": grafico_stock,
        "grafico_salidas": grafico_salidas,
        "grafico_consumo": grafico_consumo,
        "grafico_categorias": (
            grafico_categorias
        ),
    }

    return render(
        request,
        "core/gestion/analisis_stock.html",
        contexto,
    )