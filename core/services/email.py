# pedidos/services/email.py

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def enviar_confirmacion_compra(pedido, pdf_boleta):
    contexto = {
        "pedido": pedido,
        "items": pedido.items.all(),
        "url_pedido": (
            f"{settings.SITE_URL}/mi-cuenta/pedidos/"
            f"{pedido.id_publico}/"
        ),
    }

    html = render_to_string(
        "emails/compra_confirmada.html",
        contexto,
    )

    texto = render_to_string(
        "emails/compra_confirmada.txt",
        contexto,
    )

    correo = EmailMultiAlternatives(
        subject=f"Compra confirmada #{pedido.id_publico}",
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[pedido.email],
    )

    correo.attach_alternative(html, "text/html")

    correo.attach(
        f"boleta-{pedido.dte_folio}.pdf",
        pdf_boleta,
        "application/pdf",
    )

    correo.send(fail_silently=False)