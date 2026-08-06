from django.contrib import admin

from .models import *



@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "activa",
        "orden",
    )

    list_editable = (
        "activa",
        "orden",
    )

    search_fields = ("nombre",)

    prepopulated_fields = {
        "slug": ("nombre",),
    }


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "categoria",
        "precio",
        "precio_oferta",
        "stock",
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
        "caracteristica_1",
        "caracteristica_2",
        "caracteristica_3",
    )

    list_editable = (
        "precio",
        "precio_oferta",
        "stock",
        "destacado",
        "activo",
    )

    prepopulated_fields = {
        "slug": ("nombre",),
    }

    readonly_fields = (
        "creado",
        "actualizado",
    )


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    can_delete = False

    readonly_fields = (
        "producto",
        "nombre_producto",
        "precio_unitario",
        "cantidad",
        "total",
    )


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "nombre",
        "apellido",
        "total",
        "metodo_pago",
        "estado",
        "creado",
    )

    list_filter = (
        "estado",
        "metodo_pago",
        "creado",
    )

    search_fields = (
        "numero",
        "nombre",
        "apellido",
        "rut",
        "email",
    )

    readonly_fields = (
        "numero",
        "subtotal",
        "descuento",
        "despacho",
        "total",
        "creado",
        "actualizado",
    )

    inlines = [
        PedidoItemInline,
    ]


@admin.register(CarritoUsuario)
class CarritoUsuarioAdmin(
    admin.ModelAdmin
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




@admin.register(Favorito)
class FavoritoAdmin(
    admin.ModelAdmin
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