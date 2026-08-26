# core/services/resend_email.py

import base64
import logging
from collections.abc import Sequence

import resend
from django.conf import settings


logger = logging.getLogger(__name__)


class ResendEmailError(Exception):
    """
    Error controlado al enviar correos mediante Resend.
    """


def _normalizar_destinatarios(
    destinatarios: str | Sequence[str] | None,
) -> list[str]:
    """
    Convierte un correo individual o una colección
    en una lista limpia.
    """

    if not destinatarios:
        return []

    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]

    return [
        str(correo).strip()
        for correo in destinatarios
        if str(correo).strip()
    ]


def _preparar_adjuntos(
    adjuntos: list[dict] | None,
) -> list[dict]:
    """
    Convierte archivos locales/binarios a Base64
    para enviarlos mediante Resend.

    Formato esperado:

    {
        "filename": "boleta-123.pdf",
        "content": bytes_del_pdf,
    }
    """

    if not adjuntos:
        return []

    resultado = []

    for adjunto in adjuntos:

        filename = str(
            adjunto.get("filename") or ""
        ).strip()

        contenido = adjunto.get("content")

        if not filename:
            raise ValueError(
                "El adjunto debe tener filename."
            )

        if contenido is None:
            raise ValueError(
                f"El adjunto {filename} no tiene contenido."
            )

        # ---------------------------------------------------------
        # FILE-LIKE OBJECT
        # ---------------------------------------------------------

        if hasattr(contenido, "read"):
            contenido = contenido.read()

        # ---------------------------------------------------------
        # MEMORYVIEW
        # ---------------------------------------------------------

        if isinstance(contenido, memoryview):
            contenido = contenido.tobytes()

        # ---------------------------------------------------------
        # STRING
        # ---------------------------------------------------------

        if isinstance(contenido, str):
            contenido = contenido.encode("utf-8")

        # ---------------------------------------------------------
        # VALIDAR BYTES
        # ---------------------------------------------------------

        if not isinstance(
            contenido,
            (bytes, bytearray),
        ):
            raise TypeError(
                (
                    f"El contenido de {filename} "
                    "debe ser bytes o un archivo."
                )
            )

        contenido_base64 = (
            base64.b64encode(
                bytes(contenido)
            ).decode("ascii")
        )

        resultado.append(
            {
                "filename": filename,
                "content": contenido_base64,
            }
        )

    return resultado


def enviar_correo_resend(
    *,
    destinatarios: str | Sequence[str],
    asunto: str,
    html: str,
    remitente: str | None = None,
    texto: str | None = None,
    cc: str | Sequence[str] | None = None,
    bcc: str | Sequence[str] | None = None,
    reply_to: str | None = None,
    adjuntos: list[dict] | None = None,
):
    """
    Envía correo mediante la API HTTPS de Resend.

    Puede enviar:

    - HTML
    - texto plano
    - CC
    - BCC
    - Reply-To
    - adjuntos
    """

    api_key = getattr(
        settings,
        "RESEND_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise ResendEmailError(
            "RESEND_API_KEY no está configurada."
        )

    destinatarios = _normalizar_destinatarios(
        destinatarios
    )

    if not destinatarios:
        raise ValueError(
            "Debe existir al menos un destinatario."
        )

    if not asunto:
        raise ValueError(
            "El asunto es obligatorio."
        )

    if not html:
        raise ValueError(
            "El HTML del correo es obligatorio."
        )

    if not remitente:
        remitente = (
            settings.RESEND_FROM_NO_REPLY
        )

    resend.api_key = api_key

    params = {
        "from": remitente,
        "to": destinatarios,
        "subject": asunto,
        "html": html,
    }

    # =============================================================
    # TEXTO PLANO
    # =============================================================

    if texto:
        params["text"] = texto

    # =============================================================
    # CC
    # =============================================================

    destinatarios_cc = (
        _normalizar_destinatarios(cc)
    )

    if destinatarios_cc:
        params["cc"] = destinatarios_cc

    # =============================================================
    # BCC
    # =============================================================

    destinatarios_bcc = (
        _normalizar_destinatarios(bcc)
    )

    if destinatarios_bcc:
        params["bcc"] = destinatarios_bcc

    # =============================================================
    # REPLY TO
    # =============================================================

    if reply_to:
        params["reply_to"] = reply_to

    # =============================================================
    # ADJUNTOS
    # =============================================================

    adjuntos_preparados = (
        _preparar_adjuntos(
            adjuntos
        )
    )

    if adjuntos_preparados:
        params["attachments"] = (
            adjuntos_preparados
        )

    # =============================================================
    # ENVÍO
    # =============================================================

    try:

        respuesta = resend.Emails.send(
            params
        )

        logger.info(
            (
                "Correo enviado mediante Resend. "
                "Para=%s | Asunto=%s | "
                "Respuesta=%s"
            ),
            destinatarios,
            asunto,
            respuesta,
        )

        return respuesta

    except Exception as error:

        logger.exception(
            (
                "Error enviando correo mediante Resend. "
                "Para=%s | Asunto=%s"
            ),
            destinatarios,
            asunto,
        )

        raise ResendEmailError(
            (
                "No fue posible enviar el correo "
                f"mediante Resend: {error}"
            )
        ) from error