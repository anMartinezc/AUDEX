import uuid

from django.db import migrations


def poblar_public_id_producto(
    apps,
    schema_editor,
):
    Producto = apps.get_model(
        "core",
        "Producto",
    )

    productos = Producto.objects.filter(
        public_id__isnull=True,
    )

    for producto in productos.iterator():
        producto.public_id = uuid.uuid4()

        producto.save(
            update_fields=[
                "public_id",
            ]
        )


def revertir_public_id_producto(
    apps,
    schema_editor,
):
    Producto = apps.get_model(
        "core",
        "Producto",
    )

    Producto.objects.update(
        public_id=None
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "core",
            "0022_producto_public_id_alter_producto_talla_envio_minima",
        ),
    ]

    operations = [
        migrations.RunPython(
            poblar_public_id_producto,
            revertir_public_id_producto,
        ),
    ]