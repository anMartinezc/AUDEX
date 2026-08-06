# core/services/descuentos.py

import hashlib
import hmac
import logging
import secrets

from dataclasses import dataclass
from datetime import timedelta
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from django.conf import settings
from django.db import (
    IntegrityError,
    transaction,
)
from django.db.models import Q
from django.utils import timezone

from core.models import (
    CodigoDescuento,
    ConfiguracionFidelidad,
    Pedido,
    SaldoFidelidad,
    UsoCodigoDescuento,
)


logger = logging.getLogger(__name__)


class DescuentoError(ValueError):
    pass


@dataclass
class ResultadoDescuento:
    codigo_objeto: CodigoDescuento | None
    codigo: str
    tipo: str
    porcentaje: Decimal
    descuento: Decimal
    cliente_clave: str


def normalizar_codigo(codigo):
    return (
        str(codigo or "")
        .strip()
        .upper()
    )


def normalizar_rut(rut):
    texto = (
        str(rut or "")
        .strip()
        .upper()
        .replace(".", "")
        .replace(" ", "")
    )

    if not texto:
        return ""

    if "-" not in texto and len(texto) > 1:
        texto = f"{texto[:-1]}-{texto[-1]}"

    return texto


def enmascarar_rut(rut):
    rut = normalizar_rut(rut)

    if not rut:
        return ""

    cuerpo, _, dv = rut.partition("-")

    return f"***{cuerpo[-4:]}-{dv}"


def crear_cliente_clave(rut):
    rut_normalizado = normalizar_rut(rut)

    if not rut_normalizado:
        raise DescuentoError(
            (
                "Ingresa un RUT válido antes de aplicar "
                "un código de descuento."
            )
        )

    digest = hmac.new(
        key=settings.SECRET_KEY.encode("utf-8"),
        msg=rut_normalizado.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return f"RUT:{digest}"


def resultado_sin_descuento(
    cliente_clave="",
):
    return ResultadoDescuento(
        codigo_objeto=None,
        codigo="",
        tipo=Pedido.TipoDescuento.NINGUNO,
        porcentaje=Decimal("0"),
        descuento=Decimal("0"),
        cliente_clave=cliente_clave,
    )


def calcular_importe_descuento(
    *,
    subtotal,
    porcentaje,
    monto_maximo=None,
):
    subtotal = Decimal(str(subtotal))
    porcentaje = Decimal(str(porcentaje))

    descuento = (
        subtotal
        * porcentaje
        / Decimal("100")
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    if monto_maximo is not None:
        descuento = min(
            descuento,
            Decimal(str(monto_maximo)),
        )

    return min(
        descuento,
        subtotal,
    )


def _validar_vigencia(codigo):
    ahora = timezone.now()

    if not codigo.activo:
        raise DescuentoError(
            "Este código está desactivado."
        )

    if (
        codigo.tipo
        == CodigoDescuento.Tipo.FIDELIDAD
        and codigo.consumido
    ):
        raise DescuentoError(
            "Este premio ya fue utilizado."
        )

    if (
        codigo.fecha_inicio
        and codigo.fecha_inicio > ahora
    ):
        raise DescuentoError(
            "Este código todavía no está vigente."
        )

    if (
        codigo.fecha_fin
        and codigo.fecha_fin <= ahora
    ):
        raise DescuentoError(
            "Este código ya venció."
        )


def _validar_propietario(
    *,
    codigo,
    usuario,
):
    if (
        codigo.tipo
        != CodigoDescuento.Tipo.FIDELIDAD
    ):
        return

    if not getattr(
        usuario,
        "is_authenticated",
        False,
    ):
        raise DescuentoError(
            (
                "Debes iniciar sesión para utilizar "
                "este premio."
            )
        )

    if codigo.usuario_exclusivo_id != usuario.pk:
        raise DescuentoError(
            "Este código pertenece a otro cliente."
        )


def _validar_uso_anterior(
    *,
    codigo,
    cliente_clave,
):
    ya_utilizado = (
        UsoCodigoDescuento.objects
        .filter(
            codigo=codigo,
            cliente_clave=cliente_clave,
            estado__in=[
                UsoCodigoDescuento.Estado.RESERVADO,
                UsoCodigoDescuento.Estado.CONFIRMADO,
            ],
        )
        .exists()
    )

    if ya_utilizado:
        raise DescuentoError(
            (
                "Este código ya fue utilizado o está "
                "reservado por este cliente."
            )
        )

    if codigo.tipo == CodigoDescuento.Tipo.FIDELIDAD:
        otro_uso = (
            UsoCodigoDescuento.objects
            .filter(
                codigo=codigo,
                estado__in=[
                    UsoCodigoDescuento.Estado.RESERVADO,
                    UsoCodigoDescuento.Estado.CONFIRMADO,
                ],
            )
            .exists()
        )

        if otro_uso:
            raise DescuentoError(
                "Este premio ya no está disponible."
            )


def resolver_descuento(
    *,
    usuario,
    rut,
    subtotal,
    codigo,
    bloquear=False,
):
    codigo_texto = normalizar_codigo(codigo)
    subtotal = Decimal(str(subtotal))

    if not codigo_texto:
        return resultado_sin_descuento()

    cliente_clave = crear_cliente_clave(rut)

    consulta = CodigoDescuento.objects.filter(
        codigo=codigo_texto,
    )

    if bloquear:
        consulta = consulta.select_for_update()

    codigo_objeto = consulta.first()

    if codigo_objeto is None:
        raise DescuentoError(
            "El código ingresado no existe."
        )

    _validar_vigencia(codigo_objeto)

    _validar_propietario(
        codigo=codigo_objeto,
        usuario=usuario,
    )

    _validar_uso_anterior(
        codigo=codigo_objeto,
        cliente_clave=cliente_clave,
    )

    if subtotal < codigo_objeto.monto_minimo:
        raise DescuentoError(
            (
                "Este código requiere una compra mínima "
                f"de ${codigo_objeto.monto_minimo:,.0f}."
            )
        )

    descuento = calcular_importe_descuento(
        subtotal=subtotal,
        porcentaje=codigo_objeto.porcentaje,
        monto_maximo=(
            codigo_objeto
            .monto_maximo_descuento
        ),
    )

    tipo_pedido = (
        Pedido.TipoDescuento.FIDELIDAD
        if codigo_objeto.tipo
        == CodigoDescuento.Tipo.FIDELIDAD
        else Pedido.TipoDescuento.GENERAL
    )

    return ResultadoDescuento(
        codigo_objeto=codigo_objeto,
        codigo=codigo_objeto.codigo,
        tipo=tipo_pedido,
        porcentaje=codigo_objeto.porcentaje,
        descuento=descuento,
        cliente_clave=cliente_clave,
    )


@transaction.atomic
def reservar_codigo_descuento(
    *,
    resultado,
    pedido,
    usuario,
    rut,
):
    if resultado.codigo_objeto is None:
        return None

    codigo = (
        CodigoDescuento.objects
        .select_for_update()
        .get(
            pk=resultado.codigo_objeto.pk,
        )
    )

    _validar_vigencia(codigo)

    _validar_propietario(
        codigo=codigo,
        usuario=usuario,
    )

    _validar_uso_anterior(
        codigo=codigo,
        cliente_clave=(
            resultado.cliente_clave
        ),
    )

    try:
        uso = UsoCodigoDescuento.objects.create(
            codigo=codigo,
            pedido=pedido,
            usuario=(
                usuario
                if getattr(
                    usuario,
                    "is_authenticated",
                    False,
                )
                else None
            ),
            cliente_clave=(
                resultado.cliente_clave
            ),
            rut_enmascarado=(
                enmascarar_rut(rut)
            ),
            estado=(
                UsoCodigoDescuento
                .Estado
                .RESERVADO
            ),
            subtotal_original=pedido.subtotal,
            descuento_aplicado=pedido.descuento,
            total_final=pedido.total,
        )

    except IntegrityError as error:
        raise DescuentoError(
            (
                "Este código ya fue utilizado o está "
                "reservado por este cliente."
            )
        ) from error

    return uso


@transaction.atomic
def confirmar_uso_codigo_pedido(pedido):
    uso = (
        UsoCodigoDescuento.objects
        .select_for_update()
        .select_related("codigo")
        .filter(
            pedido=pedido,
            estado=(
                UsoCodigoDescuento
                .Estado
                .RESERVADO
            ),
        )
        .first()
    )

    if uso is None:
        return False

    uso.estado = (
        UsoCodigoDescuento
        .Estado
        .CONFIRMADO
    )

    uso.confirmado_en = timezone.now()

    uso.save(
        update_fields=[
            "estado",
            "confirmado_en",
        ]
    )

    if (
        uso.codigo.tipo
        == CodigoDescuento.Tipo.FIDELIDAD
        and not uso.codigo.consumido
    ):
        uso.codigo.consumido = True

        uso.codigo.save(
            update_fields=[
                "consumido",
                "actualizado",
            ]
        )

    return True


@transaction.atomic
def liberar_uso_codigo_pedido(pedido):
    uso = (
        UsoCodigoDescuento.objects
        .select_for_update()
        .filter(
            pedido=pedido,
            estado=(
                UsoCodigoDescuento
                .Estado
                .RESERVADO
            ),
        )
        .first()
    )

    if uso is None:
        return False

    uso.estado = (
        UsoCodigoDescuento
        .Estado
        .LIBERADO
    )

    uso.liberado_en = timezone.now()

    uso.save(
        update_fields=[
            "estado",
            "liberado_en",
        ]
    )

    return True


def generar_codigo_fidelidad_unico(
    *,
    usuario,
    numero_meta,
    prefijo,
):
    prefijo = normalizar_codigo(prefijo)

    while True:
        token = secrets.token_hex(3).upper()

        codigo = (
            f"{prefijo}-{usuario.pk}-"
            f"M{numero_meta}-{token}"
        )

        if not CodigoDescuento.objects.filter(
            codigo=codigo,
        ).exists():
            return codigo


@transaction.atomic
def registrar_compra_fidelidad(pedido_id):
    pedido = (
        Pedido.objects
        .select_for_update()
        .select_related("usuario")
        .get(pk=pedido_id)
    )

    if pedido.fidelidad_contabilizada:
        return []

    if not pedido.pago_aprobado:
        return []

    configuracion = (
        ConfiguracionFidelidad.obtener()
    )

    if (
        not configuracion.activa
        or pedido.usuario_id is None
    ):
        pedido.fidelidad_contabilizada = True

        pedido.save(
            update_fields=[
                "fidelidad_contabilizada",
                "actualizado",
            ]
        )

        return []

    saldo, _ = (
        SaldoFidelidad.objects
        .get_or_create(
            usuario=pedido.usuario,
        )
    )

    saldo = (
        SaldoFidelidad.objects
        .select_for_update()
        .get(pk=saldo.pk)
    )

    monto_contabilizado = max(
        pedido.subtotal - pedido.descuento,
        Decimal("0"),
    )

    saldo.saldo_actual += monto_contabilizado
    saldo.total_historico += monto_contabilizado

    codigos_generados = []

    while saldo.saldo_actual >= configuracion.monto_objetivo:
        saldo.saldo_actual -= configuracion.monto_objetivo
        saldo.metas_cumplidas += 1

        codigo_texto = generar_codigo_fidelidad_unico(
            usuario=pedido.usuario,
            numero_meta=saldo.metas_cumplidas,
            prefijo=configuracion.prefijo_codigo,
        )

        codigo = CodigoDescuento.objects.create(
            tipo=CodigoDescuento.Tipo.FIDELIDAD,
            nombre=(
                "Premio de fidelidad "
                f"meta {saldo.metas_cumplidas}"
            ),
            codigo=codigo_texto,
            descripcion=(
                "Código generado automáticamente "
                "por cumplimiento de meta."
            ),
            activo=True,
            consumido=False,
            porcentaje=configuracion.porcentaje,
            monto_minimo=(
                configuracion
                .monto_minimo_compra
            ),
            monto_maximo_descuento=(
                configuracion
                .monto_maximo_descuento
            ),
            fecha_inicio=timezone.now(),
            fecha_fin=(
                timezone.now()
                + timedelta(
                    days=(
                        configuracion
                        .vigencia_dias
                    )
                )
            ),
            usuario_exclusivo=pedido.usuario,
            numero_meta=saldo.metas_cumplidas,
        )

        codigos_generados.append(codigo)

    saldo.save(
        update_fields=[
            "saldo_actual",
            "total_historico",
            "metas_cumplidas",
            "actualizado",
        ]
    )

    pedido.fidelidad_contabilizada = True

    pedido.save(
        update_fields=[
            "fidelidad_contabilizada",
            "actualizado",
        ]
    )

    return codigos_generados


def obtener_codigos_disponibles(usuario):
    if not getattr(
        usuario,
        "is_authenticated",
        False,
    ):
        return CodigoDescuento.objects.none()

    ahora = timezone.now()

    return (
        CodigoDescuento.objects
        .filter(
            tipo=CodigoDescuento.Tipo.FIDELIDAD,
            usuario_exclusivo=usuario,
            activo=True,
            consumido=False,
        )
        .filter(
            Q(fecha_inicio__isnull=True)
            | Q(fecha_inicio__lte=ahora)
        )
        .filter(
            Q(fecha_fin__isnull=True)
            | Q(fecha_fin__gt=ahora)
        )
        .order_by(
            "fecha_fin",
            "-creado",
        )
    )




def calcular_importe_descuento_fijo(
    *,
    subtotal,
    codigo,
):
    """
    Calcula un descuento fijo en CLP configurado
    completamente desde el administrador.

    Ejemplo configurado por el administrador:

    - monto_descuento: $38.000
    - monto_minimo: $313.000

    Resultado:

    - Compra de $300.000: no permite usar el código.
    - Compra de $313.000 o más: descuenta $38.000.
    """

    subtotal = Decimal(
        str(subtotal or 0)
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    monto_minimo = Decimal(
        str(
            codigo.monto_minimo
            or 0
        )
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    monto_descuento = Decimal(
        str(
            codigo.monto_descuento
            or 0
        )
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    if subtotal < Decimal("0"):
        raise DescuentoError(
            "El subtotal no puede ser negativo."
        )

    if monto_descuento <= Decimal("0"):
        raise DescuentoError(
            (
                "El código no tiene configurado "
                "un monto de descuento válido."
            )
        )

    if subtotal < monto_minimo:
        raise DescuentoError(
            (
                "Este código requiere una compra mínima "
                f"de ${monto_minimo:,.0f}."
            )
        )

    return min(
        monto_descuento,
        subtotal,
    )