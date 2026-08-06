from django.urls import path

from . import views
from django.contrib.auth import views as auth_views
from . import views_pedidos
from core.views_analitica import *
from core.views_descuentos import (
    alternar_codigo_descuento,
    crear_codigo_general,
    gestion_descuentos,
    guardar_configuracion_fidelidad,
)


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
    ),path(
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
        "gestion/descuentos/",
        gestion_descuentos,
        name="gestion_descuentos",
    ),



    




    path(
        "checkout/resumen-descuento/",
        views.checkout_resumen_descuento,
        name="checkout_resumen_descuento",
    ),









    path(
        "gestion/descuentos/",
        gestion_descuentos,
        name="gestion_descuentos",
    ),

    path(
        "gestion/descuentos/general/crear/",
        crear_codigo_general,
        name="crear_codigo_general",
    ),

    path(
        "gestion/descuentos/fidelidad/guardar/",
        guardar_configuracion_fidelidad,
        name="guardar_configuracion_fidelidad",
    ),

    path(
        "gestion/descuentos/codigo/<int:codigo_id>/alternar/",
        alternar_codigo_descuento,
        name="alternar_codigo_descuento",
    ),

]