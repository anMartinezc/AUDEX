# pedidos/services/postventa.py

from django.core.files.base import ContentFile
from django.db import transaction

from core.models import (
    CorreoConfirmacionPedido,
    Pedido,
)
from tributario.provider import ProveedorDTE

from .email import enviar_confirmacion_compra


def emitir_boleta_y_enviar_correo(pedido_id):
    pedido = (
        Pedido.objects
        .prefetch_related("items")
        .get(pk=pedido_id)
    )

    if pedido.estado != Pedido.Estado.PAGADO:
        return

    if pedido.correo_enviado:
        return

    emisor = ProveedorDTE()
    resultado = emisor.emitir_boleta(pedido)

    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(
            pk=pedido_id
        )

        if not pedido.dte_folio:
            pedido.dte_folio = resultado.folio
            pedido.dte_tipo = resultado.tipo
            pedido.dte_estado = resultado.estado

            pedido.dte_pdf.save(
                f"boleta-{resultado.folio}.pdf",
                ContentFile(resultado.pdf),
                save=False,
            )

            pedido.save(update_fields=[
                "dte_folio",
                "dte_tipo",
                "dte_estado",
                "dte_pdf",
            ])

    enviar_confirmacion_compra(
        pedido,
        resultado.pdf,
    )

    Pedido.objects.filter(
        pk=pedido_id,
        correo_enviado=False,
    ).update(correo_enviado=True)