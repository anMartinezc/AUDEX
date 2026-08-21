# pedidos/services/email.py

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string


def enviar_confirmacion_compra(pedido, pdf_boleta):
    """
    Envía al cliente la confirmación de compra
    junto con la boleta en PDF.
    """

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

    correo.attach_alternative(
        html,
        "text/html",
    )

    correo.attach(
        f"boleta-{pedido.dte_folio}.pdf",
        pdf_boleta,
        "application/pdf",
    )

    correo.send(
        fail_silently=False,
    )


def obtener_correos_administradores():
    """
    Obtiene los correos de todos los usuarios administradores
    activos del sistema.
    """

    User = get_user_model()

    return list(
        User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True),
            is_active=True,
        )
        .exclude(email="")
        .exclude(email__isnull=True)
        .values_list(
            "email",
            flat=True,
        )
        .distinct()
    )


def enviar_notificacion_compra_administradores(pedido):
    """
    Notifica a todos los administradores cuando
    se confirma una nueva compra.
    """

    correos_admin = obtener_correos_administradores()

    if not correos_admin:
        return 0

    contexto = {
        "pedido": pedido,
        "items": pedido.items.all(),
        "url_pedido": (
            f"{settings.SITE_URL}/gestion/pedidos/"
            f"{pedido.id_publico}/"
        ),
    }

    html = render_to_string(
        "emails/admin_nueva_compra.html",
        contexto,
    )

    texto = render_to_string(
        "emails/admin_nueva_compra.txt",
        contexto,
    )

    correo = EmailMultiAlternatives(
        subject=f"Nueva compra confirmada #{pedido.id_publico}",
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,

        # Se usa BCC para no exponer los correos
        # de los administradores entre sí.
        to=[settings.DEFAULT_FROM_EMAIL],
        bcc=correos_admin,
    )

    correo.attach_alternative(
        html,
        "text/html",
    )

    correo.send(
        fail_silently=False,
    )

    return len(correos_admin)