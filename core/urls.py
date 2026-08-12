from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_descuentos, views_pedidos
from .views_analitica import analisis_stock, analisis_ventas


gestion_descuentos = views.gestion_descuentos
crear_codigo_general_porcentaje = views.crear_codigo_general_porcentaje
crear_codigo_general_clp = views.crear_codigo_general_clp
alternar_codigo_descuento = views_descuentos.alternar_codigo_descuento

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("categorias/", views.categorias, name="categorias"),
    path("ofertas/", views.ofertas, name="ofertas"),
    path("nosotros/", views.nosotros, name="nosotros"),

    path(
        "productos/",
        views.productos,
        name="productos",
    ),
    path(
        "productos/nuevo/",
        views.ProductoCrearView.as_view(),
        name="producto_crear",
    ),
    path(
        "productos/<slug:slug>/",
        views.producto_detalle,
        name="producto_detalle",
    ),
    path(
        "productos/<slug:slug>/editar/",
        views.ProductoEditarView.as_view(),
        name="producto_editar",
    ),
    path(
        "productos/<slug:slug>/eliminar/",
        views.ProductoEliminarView.as_view(),
        name="producto_eliminar",
    ),
    path(
        "categorias/nueva/",
        views.CategoriaCrearView.as_view(),
        name="categoria_crear",
    ),
    path(
        "categorias/",
        views.categorias,
        name="categorias",
    ),
    path(
        "ofertas/",
        views.ofertas,
        name="ofertas",
    ),
    path(
        "nosotros/",
        views.nosotros,
        name="nosotros",
    ),
    







    path(
        "carrito/",
        views.carrito_estado,
        name="carrito_estado",
    ),
    path(
        "carrito/agregar/",
        views.carrito_agregar,
        name="carrito_agregar",
    ),
    path(
        "carrito/actualizar/",
        views.carrito_actualizar,
        name="carrito_actualizar",
    ),
    path(
        "carrito/eliminar/",
        views.carrito_eliminar,
        name="carrito_eliminar",
    ),
    path(
        "carrito/vaciar/",
        views.carrito_vaciar,
        name="carrito_vaciar",
    ),

    path(
    "carrito/completo/",
    views.carrito_completo,
    name="carrito_completo",
    ),


    path(
    "checkout/",
    views.checkout,
    name="checkout",
    ),

    path(
    "pedido/<str:numero>/confirmacion/",
    views.pedido_confirmacion,
    name="pedido_confirmacion",
    ),






    path(
        "pedido/<str:numero>/confirmacion/",
        views.pedido_confirmacion,
        name="pedido_confirmacion",
    ),


    path(
    "pago/mercadopago/exitoso/<str:numero>/",
    views.mercadopago_retorno_exitoso,
    name="mercadopago_retorno_exitoso",
    ),

    path(
        "pago/mercadopago/pendiente/<str:numero>/",
        views.mercadopago_retorno_pendiente,
        name="mercadopago_retorno_pendiente",
    ),

    path(
        "pago/mercadopago/fallido/<str:numero>/",
        views.mercadopago_retorno_fallido,
        name="mercadopago_retorno_fallido",
    ),

    path(
        "webhooks/mercadopago/",
        views.mercadopago_webhook,
        name="mercadopago_webhook",
    ),
    path(
        "mercadopago/webhook/",
        views.webhook_mercado_pago,
        name="webhook_mercado_pago",
    ),

    path(
        "seguimiento/",
        views_pedidos.seguimiento_pedido,
        name="seguimiento_pedido",
    ),

    path(
        "seguimiento/<str:numero>/",
        views_pedidos.seguimiento_pedido,
        name="seguimiento_pedido_numero",
    ),

    path(
        "gestion/pedidos/",
        views_pedidos.panel_pedidos,
        name="panel_pedidos",
    ),

        path(
        "mi-cuenta/compras/",
        views_pedidos.mis_compras,
        name="mis_compras",
    ),

    path(
        "seguimiento/",
        views_pedidos.seguimiento_pedido,
        name="seguimiento_pedido",
    ),

    path(
        "seguimiento/<str:numero>/",
        views_pedidos.seguimiento_pedido,
        name="seguimiento_pedido_numero",
    ),

    path(
        "gestion/pedidos/<str:numero>/",
        views_pedidos.panel_pedido_detalle,
        name="panel_pedido_detalle",
    ),


    path(
        "cuenta/iniciar-sesion/",
        auth_views.LoginView.as_view(
            template_name="core/cuenta/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path(
    "cuenta/cerrar-sesion/",
    views.cerrar_sesion,
    name="logout",
    ),




    path(
    "favoritos/estado/",
    views.favoritos_estado,
    name="favoritos_estado",
    ),

    path(
        "favoritos/alternar/",
        views.favorito_alternar,
        name="favorito_alternar",
    ),


    path(
    "mi-cuenta/favoritos/",
    views.mis_favoritos,
    name="mis_favoritos",
    ),

    path(
        "mi-cuenta/perfil/",
        views.mi_perfil,
        name="mi_perfil",
    ),



    path(
        "gestion/analisis/ventas/",
        analisis_ventas,
        name="analisis_ventas",
    ),

    path(
        "gestion/analisis/stock/",
        analisis_stock,
        name="analisis_stock",
    ),





    




    path(
        "checkout/resumen-descuento/",
        views.checkout_resumen_descuento,
        name="checkout_resumen_descuento",
    ),









   
    path(
        (
            "gestion/descuentos/"
            "general/porcentaje/crear/"
        ),
        views_descuentos.crear_codigo_general_porcentaje,
        name="crear_codigo_general_porcentaje",
    ),

    path(
        (
            "gestion/descuentos/"
            "general/clp/crear/"
        ),
        views_descuentos.crear_codigo_general_clp,
        name="crear_codigo_general_clp",
    ),

  

  



  




path(
    "gestion/descuentos/",
    views_descuentos.gestion_descuentos,
    name="gestion_descuentos",
),

path(
    "gestion/descuentos/general/porcentaje/crear/",
    views_descuentos.crear_codigo_general_porcentaje,
    name="crear_codigo_general_porcentaje",
),

path(
    "gestion/descuentos/general/clp/crear/",
    views_descuentos.crear_codigo_general_clp,
    name="crear_codigo_general_clp",
),

path(
    "gestion/descuentos/fidelidad/porcentaje/crear/",
    views_descuentos.crear_meta_fidelidad_porcentaje,
    name="crear_meta_fidelidad_porcentaje",
),

path(
    "gestion/descuentos/fidelidad/clp/crear/",
    views_descuentos.crear_meta_fidelidad_clp,
    name="crear_meta_fidelidad_clp",
),
path(
    "gestion/descuentos/meta/<int:meta_id>/eliminar/",
    views_descuentos.eliminar_meta_fidelidad,
    name="eliminar_meta_fidelidad",
),

path(
    "gestion/descuentos/codigo/<int:codigo_id>/alternar/",
    views_descuentos.alternar_codigo_descuento,
    name="alternar_codigo_descuento",
),


path(
    "gestion/descuentos/codigo/<int:codigo_id>/eliminar/",
    views_descuentos.eliminar_codigo_descuento,
    name="eliminar_codigo_descuento",
),

path(
    "gestion/descuentos/meta/<int:meta_id>/alternar/",
    views_descuentos.alternar_meta_fidelidad,
    name="alternar_meta_fidelidad",
),



path(
    "gestion/descuentos/codigo/<int:codigo_id>/ocultar/",
    views_descuentos.ocultar_codigo_descuento,
    name="ocultar_codigo_descuento",
),

path(
    "gestion/descuentos/codigo/<int:codigo_id>/mostrar/",
    views_descuentos.mostrar_codigo_descuento,
    name="mostrar_codigo_descuento",
),

path(
    "gestion/descuentos/meta/<int:meta_id>/ocultar/",
    views_descuentos.ocultar_meta_fidelidad,
    name="ocultar_meta_fidelidad",
),

path(
    "gestion/descuentos/meta/<int:meta_id>/mostrar/",
    views_descuentos.mostrar_meta_fidelidad,
    name="mostrar_meta_fidelidad",
),







    path(
        "webpay/retorno/",
        views.webpay_retorno,
        name="webpay_retorno",
    ),
]