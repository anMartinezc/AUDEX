from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_descuentos, views_pedidos
from .views_analitica import analisis_stock, analisis_ventas


app_name = "core"


urlpatterns = [

    # =========================================================================
    # PÁGINAS PRINCIPALES
    # =========================================================================

    path("", views.inicio, name="inicio"),
    path("productos/", views.productos, name="productos"),
    path("categorias/", views.categorias, name="categorias"),
    path("ofertas/", views.ofertas, name="ofertas"),
    path("nosotros/", views.nosotros, name="nosotros"),


    # =========================================================================
    # PRODUCTOS
    # =========================================================================

    path("productos/nuevo/", views.ProductoCrearView.as_view(), name="producto_crear"),
    path("productos/<uuid:public_id>/", views.producto_detalle, name="producto_detalle"),
    path("productos/<uuid:public_id>/editar/", views.ProductoEditarView.as_view(), name="producto_editar"),
    path("productos/<slug:slug>/eliminar/", views.ProductoEliminarView.as_view(), name="producto_eliminar"),


    # =========================================================================
    # CATEGORÍAS
    # =========================================================================

    path("categorias/nueva/", views.CategoriaCrearView.as_view(), name="categoria_crear"),


    # =========================================================================
    # RESEÑAS DE PRODUCTOS
    # =========================================================================

    path("productos/<uuid:public_id>/resena/", views.guardar_resena_producto, name="guardar_resena_producto"),
    path("resenas/<int:resena_id>/responder/", views.responder_resena_producto, name="responder_resena_producto"),
    path("resenas/<int:resena_id>/estado/", views.cambiar_estado_resena, name="cambiar_estado_resena"),
    path("resenas/imagenes/<int:imagen_id>/eliminar/", views.eliminar_imagen_resena, name="eliminar_imagen_resena"),


    # =========================================================================
    # CARRITO
    # =========================================================================

    path("carrito/", views.carrito_estado, name="carrito_estado"),
    path("carrito/completo/", views.carrito_completo, name="carrito_completo"),
    path("carrito/agregar/", views.carrito_agregar, name="carrito_agregar"),
    path("carrito/actualizar/", views.carrito_actualizar, name="carrito_actualizar"),
    path("carrito/eliminar/", views.carrito_eliminar, name="carrito_eliminar"),
    path("carrito/vaciar/", views.carrito_vaciar, name="carrito_vaciar"),


    # =========================================================================
    # CHECKOUT
    # =========================================================================

    path("checkout/", views.checkout, name="checkout"),
    path("checkout/resumen-descuento/", views.checkout_resumen_descuento, name="checkout_resumen_descuento"),


    # =========================================================================
    # CONFIRMACIÓN DE PEDIDO
    # =========================================================================

    path("pedido/<str:numero>/confirmacion/", views.pedido_confirmacion, name="pedido_confirmacion"),


    # =========================================================================
    # WEBPAY / TRANSBANK
    # =========================================================================

    path("webpay/retorno/", views.webpay_retorno, name="webpay_retorno"),


    # =========================================================================
    # MERCADO PAGO
    # =========================================================================

    path("pago/mercadopago/exitoso/<str:numero>/", views.mercadopago_retorno_exitoso, name="mercadopago_retorno_exitoso"),
    path("pago/mercadopago/pendiente/<str:numero>/", views.mercadopago_retorno_pendiente, name="mercadopago_retorno_pendiente"),
    path("pago/mercadopago/fallido/<str:numero>/", views.mercadopago_retorno_fallido, name="mercadopago_retorno_fallido"),
    path("webhooks/mercadopago/", views.mercadopago_webhook, name="mercadopago_webhook"),


    # =========================================================================
    # COMPROBANTE DE PAGO
    # =========================================================================

    path("mis-compras/<str:numero>/comprobante/", views.comprobante_pago, name="comprobante_pago"),


    # =========================================================================
    # NUBOX / BOLETA ELECTRÓNICA
    # =========================================================================

    path("pedido/<str:numero>/nubox/estado/", views_pedidos.estado_boleta_nubox, name="estado_boleta_nubox"),
    path("pedidos/<str:numero>/boleta/", views_pedidos.descargar_boleta_nubox, name="descargar_boleta_nubox"),


    # =========================================================================
    # SEGUIMIENTO DE PEDIDOS
    # =========================================================================

    path("seguimiento/", views_pedidos.seguimiento_pedido, name="seguimiento_pedido"),
    path("seguimiento/<str:numero>/", views_pedidos.seguimiento_pedido, name="seguimiento_pedido_numero"),


    # =========================================================================
    # MI CUENTA
    # =========================================================================

    path("mi-cuenta/compras/", views_pedidos.mis_compras, name="mis_compras"),
    path("mi-cuenta/favoritos/", views.mis_favoritos, name="mis_favoritos"),
    path("mi-cuenta/perfil/", views.mi_perfil, name="mi_perfil"),


    # =========================================================================
    # AUTENTICACIÓN
    # =========================================================================

    path("cuenta/iniciar-sesion/", auth_views.LoginView.as_view(template_name="core/cuenta/login.html", redirect_authenticated_user=True), name="login"),
    path("cuenta/cerrar-sesion/", views.cerrar_sesion, name="logout"),


    # =========================================================================
    # FAVORITOS
    # =========================================================================

    path("favoritos/estado/", views.favoritos_estado, name="favoritos_estado"),
    path("favoritos/alternar/", views.favorito_alternar, name="favorito_alternar"),


    # =========================================================================
    # GESTIÓN DE PEDIDOS
    # =========================================================================

    path("gestion/pedidos/", views_pedidos.panel_pedidos, name="panel_pedidos"),
    path("gestion/pedidos/<str:numero>/", views_pedidos.panel_pedido_detalle, name="panel_pedido_detalle"),


    # =========================================================================
    # GESTIÓN DE ANALÍTICA
    # =========================================================================

    path("gestion/analisis/ventas/", analisis_ventas, name="analisis_ventas"),
    path("gestion/analisis/stock/", analisis_stock, name="analisis_stock"),


    # =========================================================================
    # GESTIÓN DE DESCUENTOS
    # =========================================================================

    path("gestion/descuentos/", views_descuentos.gestion_descuentos, name="gestion_descuentos"),

    path("gestion/descuentos/general/porcentaje/crear/", views_descuentos.crear_codigo_general_porcentaje, name="crear_codigo_general_porcentaje"),
    path("gestion/descuentos/general/clp/crear/", views_descuentos.crear_codigo_general_clp, name="crear_codigo_general_clp"),

    path("gestion/descuentos/fidelidad/porcentaje/crear/", views_descuentos.crear_meta_fidelidad_porcentaje, name="crear_meta_fidelidad_porcentaje"),
    path("gestion/descuentos/fidelidad/clp/crear/", views_descuentos.crear_meta_fidelidad_clp, name="crear_meta_fidelidad_clp"),

    path("gestion/descuentos/codigo/<int:codigo_id>/alternar/", views_descuentos.alternar_codigo_descuento, name="alternar_codigo_descuento"),
    path("gestion/descuentos/codigo/<int:codigo_id>/eliminar/", views_descuentos.eliminar_codigo_descuento, name="eliminar_codigo_descuento"),
    path("gestion/descuentos/codigo/<int:codigo_id>/ocultar/", views_descuentos.ocultar_codigo_descuento, name="ocultar_codigo_descuento"),
    path("gestion/descuentos/codigo/<int:codigo_id>/mostrar/", views_descuentos.mostrar_codigo_descuento, name="mostrar_codigo_descuento"),

    path("gestion/descuentos/meta/<int:meta_id>/alternar/", views_descuentos.alternar_meta_fidelidad, name="alternar_meta_fidelidad"),
    path("gestion/descuentos/meta/<int:meta_id>/eliminar/", views_descuentos.eliminar_meta_fidelidad, name="eliminar_meta_fidelidad"),
    path("gestion/descuentos/meta/<int:meta_id>/ocultar/", views_descuentos.ocultar_meta_fidelidad, name="ocultar_meta_fidelidad"),
    path("gestion/descuentos/meta/<int:meta_id>/mostrar/", views_descuentos.mostrar_meta_fidelidad, name="mostrar_meta_fidelidad"),


    # =========================================================================
    # INFORMACIÓN / AYUDA
    # =========================================================================

    path("preguntas-frecuentes/", views.faq, name="faq"),
    path("despachos/", views.despachos, name="despachos"),
    path("cambios-devoluciones/", views.cambios_devoluciones, name="cambios_devoluciones"),
    path("garantia/", views.garantia, name="garantia"),
    path("contacto/", views.contacto, name="contacto"),


    # =========================================================================
    # LEGAL
    # =========================================================================

    path("terminos-condiciones/", views.terminos_condiciones, name="terminos_condiciones"),
    path("politica-privacidad/", views.politica_privacidad, name="politica_privacidad"),
    path("politica-cookies/", views.politica_cookies, name="politica_cookies"),

]