from django.contrib import admin

from unfold.admin import ModelAdmin, TabularInline

from .models import (
    CarritoUsuario,
    Categoria,
    CodigoDescuento,
    CorreoPedido,
    Favorito,
    MetaFidelidad,
    Pedido,
    PedidoHistorialEstado,
    PedidoItem,
    Producto,
    ProductoImagen,
    SaldoFidelidad,
    UsoCodigoDescuento,
)


# ============================================================
# CONFIGURACIÓN BASE AUDEX + DJANGO UNFOLD
# ============================================================

class AudexModelAdmin(ModelAdmin):
    """
    Configuración visual común para todos los modelos
    administrados por AUDEX.
    """

    list_fullwidth = True
    list_filter_submit = True
    warn_unsaved_form = True
    change_form_show_cancel_button = True


# ============================================================
# CATEGORÍAS
# ============================================================

@admin.register(Categoria)
class CategoriaAdmin(AudexModelAdmin):
    list_display = (
        "nombre",
        "activa",
        "orden",
    )

    list_editable = (
        "activa",
        "orden",
    )

    list_filter = (
        "activa",
    )

    search_fields = (
        "nombre",
        "descripcion",
    )

    prepopulated_fields = {
        "slug": (
            "nombre",
        ),
    }

    ordering = (
        "orden",
        "nombre",
    )


# ============================================================
# IMÁGENES DE PRODUCTOS
# ============================================================

class ProductoImagenInline(TabularInline):
    model = ProductoImagen

    extra = 1

    fields = (
        "imagen",
        "texto_alt",
        "orden",
    )

    ordering = (
        "orden",
        "id",
    )


@admin.register(ProductoImagen)
class ProductoImagenAdmin(AudexModelAdmin):
    list_display = (
        "producto",
        "orden",
        "texto_alt",
        "creado",
    )

    list_editable = (
        "orden",
    )

    search_fields = (
        "producto__nombre",
        "texto_alt",
    )

    autocomplete_fields = (
        "producto",
    )

    readonly_fields = (
        "creado",
        "actualizado",
    )

    ordering = (
        "producto",
        "orden",
        "id",
    )


# ============================================================
# PRODUCTOS
# ============================================================

@admin.register(Producto)
class ProductoAdmin(AudexModelAdmin):
    list_display = (
        "nombre",
        "categoria",
        "precio",
        "precio_oferta",
        "en_oferta_admin",
        "stock",
        "stock_reservado",
        "stock_disponible_admin",
        "destacado",
        "activo",
    )

    list_filter = (
        "categoria",
        "activo",
        "destacado",
        "cancelacion_ruido",
    )

    search_fields = (
        "nombre",
        "descripcion_corta",
        "descripcion",
        "caracteristica_1",
        "caracteristica_2",
        "caracteristica_3",
        "bluetooth",
        "resistencia_agua",
    )

    list_editable = (
        "precio",
        "precio_oferta",
        "stock",
        "destacado",
        "activo",
    )

    autocomplete_fields = (
        "categoria",
    )

    prepopulated_fields = {
        "slug": (
            "nombre",
        ),
    }

    readonly_fields = (
        "stock_reservado",
        "stock_disponible_admin",
        "en_oferta_admin",
        "porcentaje_descuento_admin",
        "cantidad_imagenes_admin",
        "creado",
        "actualizado",
    )

    fieldsets = (
        (
            "Información general",
            {
                "fields": (
                    "categoria",
                    "nombre",
                    "slug",
                    "descripcion_corta",
                    "descripcion",
                ),
            },
        ),
        (
            "Imagen principal",
            {
                "fields": (
                    "imagen",
                    "imagen_url",
                    "cantidad_imagenes_admin",
                ),
            },
        ),
        (
            "Precio",
            {
                "fields": (
                    "precio",
                    "precio_oferta",
                    "en_oferta_admin",
                    "porcentaje_descuento_admin",
                ),
            },
        ),
        (
            "Stock",
            {
                "fields": (
                    "stock",
                    "stock_reservado",
                    "stock_disponible_admin",
                ),
            },
        ),
        (
            "Características",
            {
                "fields": (
                    "caracteristica_1",
                    "caracteristica_2",
                    "caracteristica_3",
                    "autonomia_horas",
                    "bluetooth",
                    "resistencia_agua",
                    "cancelacion_ruido",
                ),
            },
        ),
        (
            "Estado",
            {
                "fields": (
                    "destacado",
                    "activo",
                ),
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "creado",
                    "actualizado",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    inlines = (
        ProductoImagenInline,
    )

    ordering = (
        "-destacado",
        "-creado",
    )

    list_per_page = 50

    @admin.display(
        boolean=True,
        description="En oferta",
    )
    def en_oferta_admin(self, obj):
        return obj.en_oferta

    @admin.display(
        description="Stock disponible",
    )
    def stock_disponible_admin(
        self,
        obj,
    ):
        return obj.stock_disponible

    @admin.display(
        description="% descuento",
    )
    def porcentaje_descuento_admin(
        self,
        obj,
    ):
        if not obj.en_oferta:
            return "—"

        return (
            f"{obj.porcentaje_descuento}%"
        )

    @admin.display(
        description="Total imágenes",
    )
    def cantidad_imagenes_admin(
        self,
        obj,
    ):
        return obj.cantidad_imagenes


# ============================================================
# ÍTEMS DE PEDIDO
# ============================================================

class PedidoItemInline(TabularInline):
    model = PedidoItem

    tab = True

    extra = 0

    can_delete = False

    fields = (
        "producto",
        "nombre_producto",
        "precio_lista_unitario",
        "precio_unitario",
        "descuento_producto_unitario",
        "cantidad",
        "total",
        "descuento_codigo",
        "total_final",
    )

    readonly_fields = fields

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(PedidoItem)
class PedidoItemAdmin(AudexModelAdmin):
    list_display = (
        "pedido",
        "nombre_producto",
        "cantidad",
        "precio_lista_unitario",
        "precio_unitario",
        "descuento_producto_unitario",
        "descuento_codigo",
        "total_final",
    )

    search_fields = (
        "pedido__numero",
        "nombre_producto",
        "producto__nombre",
    )

    list_filter = (
        "pedido__metodo_pago",
        "pedido__estado_pago",
    )

    readonly_fields = (
        "pedido",
        "producto",
        "nombre_producto",
        "precio_lista_unitario",
        "precio_unitario",
        "descuento_producto_unitario",
        "cantidad",
        "total",
        "descuento_codigo",
        "total_final",
    )

    list_select_related = (
        "pedido",
        "producto",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# HISTORIAL DE PEDIDOS - INLINE
# ============================================================

class PedidoHistorialEstadoInline(
    TabularInline
):
    model = PedidoHistorialEstado

    tab = True

    extra = 0

    can_delete = False

    fields = (
        "estado_anterior",
        "estado_nuevo",
        "usuario",
        "comentario",
        "creado",
    )

    readonly_fields = fields

    ordering = (
        "creado",
    )

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# PEDIDOS
# ============================================================

@admin.register(Pedido)
class PedidoAdmin(AudexModelAdmin):
    list_display = (
        "numero",
        "nombre_cliente_admin",
        "total",
        "metodo_pago",
        "estado_pago",
        "pagado",
        "estado",
        "nubox_emitido",
        "creado",
    )

    list_filter = (
        "estado",
        "estado_pago",
        "pagado",
        "metodo_pago",
        "nubox_emitido",
        "nubox_estado",
        "tipo_descuento",
        "stock_descontado",
        "correo_confirmacion_enviado",
        "creado",
    )

    search_fields = (
        "numero",
        "nombre",
        "apellido",
        "rut",
        "email",
        "telefono",
        "webpay_token",
        "webpay_buy_order",
        "webpay_authorization_code",
        "mercadopago_payment_id",
        "mercadopago_preference_id",
        "nubox_document_id",
        "=nubox_folio",
        "codigo_descuento",
    )

    readonly_fields = (
        # Identificación
        "numero",

        # Pago general
        "metodo_pago",
        "estado_pago",
        "pagado",
        "fecha_pago",

        # Montos
        "subtotal",
        "descuento",
        "despacho",
        "total",

        # Webpay
        "webpay_token",
        "webpay_buy_order",
        "webpay_authorization_code",
        "webpay_response_code",
        "webpay_payment_type_code",
        "webpay_installments_number",
        "webpay_transaction_date",

        # Mercado Pago
        "mercadopago_preference_id",
        "mercadopago_payment_id",
        "mercadopago_status",
        "mercadopago_status_detail",
        "mercadopago_payment_type",
        "mercadopago_transaction_amount",

        # Nubox
        "nubox_document_id",
        "nubox_folio",
        "nubox_idempotence_id",
        "nubox_estado",
        "nubox_emitido",
        "nubox_emitido_en",
        "nubox_ultimo_error",

        # Descuentos
        "codigo_descuento_obj",
        "codigo_descuento",
        "tipo_descuento",
        "porcentaje_descuento",
        "fidelidad_contabilizada",

        # Procesamiento
        "stock_descontado",
        "correo_confirmacion_enviado",
        "fecha_correo_confirmacion",

        # Auditoría
        "creado",
        "actualizado",
    )

    autocomplete_fields = (
        "usuario",
    )

    list_select_related = (
        "usuario",
        "codigo_descuento_obj",
    )

    inlines = (
        PedidoItemInline,
        PedidoHistorialEstadoInline,
    )

    date_hierarchy = "creado"

    ordering = (
        "-creado",
    )

    list_per_page = 50

    fieldsets = (
        (
            "Pedido",
            {
                "fields": (
                    "numero",
                    "usuario",
                    "estado",
                ),
            },
        ),

        (
            "Cliente",
            {
                "fields": (
                    (
                        "nombre",
                        "apellido",
                    ),
                    (
                        "rut",
                        "telefono",
                    ),
                    "email",
                ),
            },
        ),

        (
            "Dirección de despacho",
            {
                "fields": (
                    (
                        "region",
                        "comuna",
                    ),
                    (
                        "direccion",
                        "numero_direccion",
                    ),
                    "departamento",
                    "referencia",
                ),
            },
        ),

        (
            "Códigos territoriales Nubox / SII",
            {
                "fields": (
                    "nubox_region_codigo",
                    "nubox_comuna_codigo",
                ),
            },
        ),

        (
            "Pago",
            {
                "fields": (
                    "metodo_pago",
                    "estado_pago",
                    "pagado",
                    "fecha_pago",
                ),
            },
        ),

        (
            "Montos",
            {
                "fields": (
                    "subtotal",
                    "descuento",
                    "despacho",
                    "total",
                ),
            },
        ),

        (
            "Descuento aplicado",
            {
                "fields": (
                    "codigo_descuento_obj",
                    "codigo_descuento",
                    "tipo_descuento",
                    "porcentaje_descuento",
                    "fidelidad_contabilizada",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Webpay",
            {
                "fields": (
                    "webpay_token",
                    "webpay_buy_order",
                    "webpay_authorization_code",
                    "webpay_response_code",
                    "webpay_payment_type_code",
                    "webpay_installments_number",
                    "webpay_transaction_date",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Mercado Pago",
            {
                "fields": (
                    "mercadopago_preference_id",
                    "mercadopago_payment_id",
                    "mercadopago_status",
                    "mercadopago_status_detail",
                    "mercadopago_payment_type",
                    "mercadopago_transaction_amount",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Nubox",
            {
                "fields": (
                    "nubox_document_id",
                    "nubox_folio",
                    "nubox_idempotence_id",
                    "nubox_estado",
                    "nubox_emitido",
                    "nubox_emitido_en",
                    "nubox_ultimo_error",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Procesamiento interno",
            {
                "fields": (
                    "stock_descontado",
                    "correo_confirmacion_enviado",
                    "fecha_correo_confirmacion",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Información adicional",
            {
                "fields": (
                    "notas",
                ),
            },
        ),

        (
            "Auditoría",
            {
                "fields": (
                    "creado",
                    "actualizado",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Cliente",
    )
    def nombre_cliente_admin(
        self,
        obj,
    ):
        return obj.nombre_completo


# ============================================================
# HISTORIAL DE ESTADOS
# ============================================================

@admin.register(PedidoHistorialEstado)
class PedidoHistorialEstadoAdmin(
    AudexModelAdmin
):
    list_display = (
        "pedido",
        "estado_anterior",
        "estado_nuevo",
        "realizado_por",
        "creado",
    )

    list_filter = (
        "estado_nuevo",
        "creado",
    )

    search_fields = (
        "pedido__numero",
        "usuario__username",
        "usuario__email",
        "comentario",
    )

    readonly_fields = (
        "pedido",
        "usuario",
        "estado_anterior",
        "estado_nuevo",
        "comentario",
        "realizado_por",
        "creado",
    )

    list_select_related = (
        "pedido",
        "usuario",
    )

    ordering = (
        "-creado",
    )

    date_hierarchy = "creado"

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# CÓDIGOS DE DESCUENTO
# ============================================================

@admin.register(CodigoDescuento)
class CodigoDescuentoAdmin(
    AudexModelAdmin
):
    list_display = (
        "codigo",
        "nombre",
        "tipo",
        "modalidad",
        "valor_admin",
        "monto_minimo",
        "activo",
        "consumido",
        "vigente_admin",
        "fecha_fin",
    )

    list_filter = (
        "tipo",
        "modalidad",
        "activo",
        "consumido",
        "fecha_inicio",
        "fecha_fin",
    )

    search_fields = (
        "codigo",
        "nombre",
        "descripcion",
        "usuario_exclusivo__username",
        "usuario_exclusivo__email",
        "meta_fidelidad__nombre",
    )

    list_editable = (
        "activo",
    )

    raw_id_fields = (
        "usuario_exclusivo",
        "meta_fidelidad",
    )

    readonly_fields = (
        "vigente_admin",
        "creado_por",
        "creado",
        "actualizado",
    )

    date_hierarchy = "creado"

    ordering = (
        "-creado",
    )

    fieldsets = (
        (
            "Código",
            {
                "fields": (
                    "tipo",
                    "modalidad",
                    "nombre",
                    "codigo",
                    "descripcion",
                    "activo",
                    "consumido",
                    "vigente_admin",
                ),
            },
        ),

        (
            "Valor del descuento",
            {
                "fields": (
                    "porcentaje",
                    "monto_descuento",
                    "monto_minimo",
                    "monto_maximo_descuento",
                ),
            },
        ),

        (
            "Vigencia",
            {
                "fields": (
                    "fecha_inicio",
                    "fecha_fin",
                ),
            },
        ),

        (
            "Fidelidad",
            {
                "fields": (
                    "usuario_exclusivo",
                    "meta_fidelidad",
                    "numero_meta",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Auditoría",
            {
                "fields": (
                    "creado_por",
                    "creado",
                    "actualizado",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Valor",
    )
    def valor_admin(
        self,
        obj,
    ):
        if obj.es_porcentaje:
            return (
                f"{obj.porcentaje}%"
            )

        if obj.monto_descuento is None:
            return "—"

        valor = (
            f"{obj.monto_descuento:,.0f}"
            .replace(
                ",",
                ".",
            )
        )

        return f"${valor}"

    @admin.display(
        boolean=True,
        description="Vigente",
    )
    def vigente_admin(
        self,
        obj,
    ):
        return obj.vigente

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.creado_por_id:
            obj.creado_por = (
                request.user
            )

        super().save_model(
            request,
            obj,
            form,
            change,
        )


# ============================================================
# METAS DE FIDELIDAD
# ============================================================

@admin.register(MetaFidelidad)
class MetaFidelidadAdmin(
    AudexModelAdmin
):
    list_display = (
        "nombre",
        "monto_objetivo",
        "modalidad",
        "premio_admin",
        "vigencia_dias",
        "activa",
        "orden",
    )

    list_filter = (
        "activa",
        "modalidad",
    )

    search_fields = (
        "nombre",
        "prefijo_codigo",
    )

    list_editable = (
        "activa",
        "orden",
    )

    readonly_fields = (
        "creado_por",
        "creado",
        "actualizado",
    )

    ordering = (
        "monto_objetivo",
        "orden",
    )

    fieldsets = (
        (
            "Meta",
            {
                "fields": (
                    "nombre",
                    "activa",
                    "monto_objetivo",
                    "orden",
                ),
            },
        ),

        (
            "Premio",
            {
                "fields": (
                    "modalidad",
                    "porcentaje",
                    "monto_descuento",
                    "monto_minimo_compra",
                    "monto_maximo_descuento",
                    "vigencia_dias",
                ),
            },
        ),

        (
            "Generación del código",
            {
                "fields": (
                    "prefijo_codigo",
                ),
            },
        ),

        (
            "Auditoría",
            {
                "fields": (
                    "creado_por",
                    "creado",
                    "actualizado",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Premio",
    )
    def premio_admin(
        self,
        obj,
    ):
        if (
            obj.modalidad
            == obj.Modalidad.PORCENTAJE
        ):
            return (
                f"{obj.porcentaje}%"
            )

        if obj.monto_descuento is None:
            return "—"

        valor = (
            f"{obj.monto_descuento:,.0f}"
            .replace(
                ",",
                ".",
            )
        )

        return f"${valor}"

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.creado_por_id:
            obj.creado_por = (
                request.user
            )

        super().save_model(
            request,
            obj,
            form,
            change,
        )


# ============================================================
# SALDO DE FIDELIDAD
# ============================================================

@admin.register(SaldoFidelidad)
class SaldoFidelidadAdmin(
    AudexModelAdmin
):
    list_display = (
        "usuario",
        "saldo_actual",
        "total_historico",
        "metas_cumplidas",
        "actualizado",
    )

    search_fields = (
        "usuario__username",
        "usuario__email",
        "usuario__first_name",
        "usuario__last_name",
    )

    ordering = (
        "-total_historico",
    )

    readonly_fields = (
        "usuario",
        "saldo_actual",
        "total_historico",
        "metas_cumplidas",
        "actualizado",
    )

    list_select_related = (
        "usuario",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# USOS DE CÓDIGOS DE DESCUENTO
# ============================================================

@admin.register(UsoCodigoDescuento)
class UsoCodigoDescuentoAdmin(
    AudexModelAdmin
):
    list_display = (
        "codigo",
        "pedido",
        "usuario",
        "estado",
        "subtotal_original",
        "descuento_aplicado",
        "total_final",
        "reservado_en",
        "confirmado_en",
    )

    list_filter = (
        "estado",
        "reservado_en",
        "confirmado_en",
    )

    search_fields = (
        "codigo__codigo",
        "pedido__numero",
        "usuario__username",
        "usuario__email",
        "cliente_clave",
        "rut_enmascarado",
    )

    readonly_fields = (
        "codigo",
        "pedido",
        "usuario",
        "cliente_clave",
        "rut_enmascarado",
        "estado",
        "subtotal_original",
        "descuento_aplicado",
        "total_final",
        "reservado_en",
        "confirmado_en",
        "liberado_en",
    )

    list_select_related = (
        "codigo",
        "pedido",
        "usuario",
    )

    date_hierarchy = (
        "reservado_en"
    )

    ordering = (
        "-reservado_en",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# CORREOS DE PEDIDOS
# ============================================================

@admin.register(CorreoPedido)
class CorreoPedidoAdmin(
    AudexModelAdmin
):
    list_display = (
        "pedido",
        "email",
        "tipo",
        "estado",
        "enviado_en",
        "creado_en",
    )

    list_filter = (
        "tipo",
        "estado",
        "creado_en",
        "enviado_en",
    )

    search_fields = (
        "pedido__numero",
        "email",
        "ultimo_error",
    )

    readonly_fields = (
        "pedido",
        "email",
        "tipo",
        "estado",
        "enviado_en",
        "ultimo_error",
        "creado_en",
        "actualizado_en",
    )

    list_select_related = (
        "pedido",
    )

    date_hierarchy = "creado_en"

    ordering = (
        "-creado_en",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# CARRITOS
# ============================================================

@admin.register(CarritoUsuario)
class CarritoUsuarioAdmin(
    AudexModelAdmin
):
    list_display = (
        "usuario",
        "actualizado",
    )

    search_fields = (
        "usuario__username",
        "usuario__email",
    )

    readonly_fields = (
        "actualizado",
    )

    list_select_related = (
        "usuario",
    )

    ordering = (
        "-actualizado",
    )


# ============================================================
# FAVORITOS
# ============================================================

@admin.register(Favorito)
class FavoritoAdmin(
    AudexModelAdmin
):
    list_display = (
        "usuario",
        "producto",
        "creado",
    )

    list_filter = (
        "creado",
    )

    search_fields = (
        "usuario__username",
        "usuario__email",
        "producto__nombre",
    )

    autocomplete_fields = (
        "usuario",
        "producto",
    )

    readonly_fields = (
        "creado",
    )

    list_select_related = (
        "usuario",
        "producto",
    )

    ordering = (
        "-creado",
    )