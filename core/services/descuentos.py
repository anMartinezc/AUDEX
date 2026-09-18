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

from core.models import *


logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPCIONES
# ============================================================================


class DescuentoError(ValueError):
    pass


# ============================================================================
# RESULTADO DEL DESCUENTO
# ============================================================================


@dataclass
class ResultadoDescuento:
    codigo_objeto: CodigoDescuento | None
    codigo: str
    tipo: str
    porcentaje: Decimal
    descuento: Decimal
    cliente_clave: str


# ============================================================================
# NORMALIZACIÓN
# ============================================================================


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

    if (
        "-" not in texto
        and len(texto) > 1
    ):
        texto = (
            f"{texto[:-1]}-"
            f"{texto[-1]}"
        )

    return texto


def enmascarar_rut(rut):
    rut = normalizar_rut(
        rut
    )

    if not rut:
        return ""

    cuerpo, _, dv = (
        rut.partition("-")
    )

    return (
        f"***{cuerpo[-4:]}-{dv}"
    )


# ============================================================================
# IDENTIFICACIÓN DEL CLIENTE
# ============================================================================

def crear_cliente_clave(
    *,
    usuario,
    rut,
):
    """
    Genera una clave privada basada exclusivamente
    en el RUT.

    La regla de códigos generales es:

        mismo RUT + mismo código = un solo uso

    Ejemplos:

        12.345.678-5 + AUDEX15   -> permitido una vez
        12.345.678-5 + AUDEX15   -> segundo uso bloqueado

        12.345.678-5 + VERANO10  -> permitido
        22.222.222-2 + AUDEX15   -> permitido

    El usuario autenticado NO modifica esta identidad.

    Esto evita que una misma persona pueda volver a utilizar
    el mismo código creando otra cuenta o comprando como invitado.
    """

    rut_normalizado = (
        normalizar_rut(
            rut
        )
    )

    if not rut_normalizado:
        raise DescuentoError(
            (
                "Debes ingresar un RUT válido "
                "para finalizar la compra con "
                "este código."
            )
        )

    digest = hmac.new(
        key=(
            settings.SECRET_KEY
            .encode(
                "utf-8"
            )
        ),
        msg=(
            rut_normalizado
            .encode(
                "utf-8"
            )
        ),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return (
        f"RUT:{digest}"
    )

# ============================================================================
# RESULTADO SIN DESCUENTO
# ============================================================================


def resultado_sin_descuento(
    cliente_clave="",
):
    return ResultadoDescuento(
        codigo_objeto=None,
        codigo="",
        tipo=(
            Pedido
            .TipoDescuento
            .NINGUNO
        ),
        porcentaje=Decimal("0"),
        descuento=Decimal("0"),
        cliente_clave=cliente_clave,
    )


# ============================================================================
# CÁLCULO PORCENTUAL
# ============================================================================


def calcular_importe_descuento(
    *,
    subtotal,
    porcentaje,
    monto_maximo=None,
):
    subtotal = Decimal(
        str(
            subtotal
            or 0
        )
    )

    porcentaje = Decimal(
        str(
            porcentaje
            or 0
        )
    )

    if subtotal < Decimal("0"):
        raise DescuentoError(
            (
                "El subtotal no puede "
                "ser negativo."
            )
        )

    if porcentaje <= Decimal("0"):
        raise DescuentoError(
            (
                "El código no tiene un "
                "porcentaje válido."
            )
        )

    descuento = (
        subtotal
        * porcentaje
        / Decimal("100")
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    if monto_maximo is not None:
        monto_maximo = Decimal(
            str(monto_maximo)
        )

        descuento = min(
            descuento,
            monto_maximo,
        )

    return max(
        Decimal("0"),
        min(
            descuento,
            subtotal,
        ),
    )


# ============================================================================
# CÁLCULO MONTO FIJO CLP
# ============================================================================


def calcular_importe_descuento_fijo(
    *,
    subtotal,
    codigo,
):
    """
    Calcula un descuento directo en CLP.

    Ejemplo:

    monto_descuento = 20000
    monto_minimo = 100000

    Compra $90.000:
        no aplica.

    Compra $120.000:
        descuento $20.000.
    """

    subtotal = Decimal(
        str(
            subtotal
            or 0
        )
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
            (
                "El subtotal no puede "
                "ser negativo."
            )
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
                "Este código requiere una "
                "compra mínima de "
                f"${monto_minimo:,.0f}."
            )
        )

    return max(
        Decimal("0"),
        min(
            monto_descuento,
            subtotal,
        ),
    )


# ============================================================================
# VALIDAR VIGENCIA
# ============================================================================


def _validar_vigencia(
    codigo,
):
    ahora = timezone.now()

    if not codigo.activo:
        raise DescuentoError(
            (
                "Este código está "
                "desactivado."
            )
        )

    if (
        codigo.tipo
        == CodigoDescuento
        .Tipo
        .FIDELIDAD
        and codigo.consumido
    ):
        raise DescuentoError(
            (
                "Este premio ya fue "
                "utilizado."
            )
        )

    if (
        codigo.fecha_inicio
        and codigo.fecha_inicio > ahora
    ):
        raise DescuentoError(
            (
                "Este código todavía "
                "no está vigente."
            )
        )

    if (
        codigo.fecha_fin
        and codigo.fecha_fin <= ahora
    ):
        raise DescuentoError(
            (
                "Este código ya venció."
            )
        )


# ============================================================================
# VALIDAR PROPIETARIO
# ============================================================================


def _validar_propietario(
    *,
    codigo,
    usuario,
):
    """
    Solo los códigos de fidelidad tienen
    propietario.

    Los códigos generales son públicos.
    """

    if (
        codigo.tipo
        != CodigoDescuento
        .Tipo
        .FIDELIDAD
    ):
        return

    if not getattr(
        usuario,
        "is_authenticated",
        False,
    ):
        raise DescuentoError(
            (
                "Debes iniciar sesión para "
                "utilizar este premio."
            )
        )

    if (
        codigo.usuario_exclusivo_id
        != usuario.pk
    ):
        raise DescuentoError(
            (
                "Este código pertenece "
                "a otro cliente."
            )
        )


# ============================================================================
# VALIDAR USO ANTERIOR
# ============================================================================


def _validar_uso_anterior(
    *,
    codigo,
    cliente_clave,
):
    """
    Un cliente puede utilizar cada código
    solamente una vez.

    General:
        mismo código para todos,
        un uso por cliente.

    Fidelidad:
        código personal y además de un solo uso.
    """

    ya_utilizado = (
        UsoCodigoDescuento.objects
        .filter(
            codigo=codigo,
            cliente_clave=(
                cliente_clave
            ),
            estado__in=[
                (
                    UsoCodigoDescuento
                    .Estado
                    .RESERVADO
                ),
                (
                    UsoCodigoDescuento
                    .Estado
                    .CONFIRMADO
                ),
            ],
        )
        .exists()
    )

    if ya_utilizado:
        raise DescuentoError(
            (
                "Este código de descuento ya fue "
                "utilizado con este RUT."
            )
        )

    # El premio de fidelidad es un código
    # individual. Si ya tiene cualquier uso
    # reservado o confirmado, no puede volver
    # a utilizarse.
    if (
        codigo.tipo
        == CodigoDescuento
        .Tipo
        .FIDELIDAD
    ):
        otro_uso = (
            UsoCodigoDescuento.objects
            .filter(
                codigo=codigo,
                estado__in=[
                    (
                        UsoCodigoDescuento
                        .Estado
                        .RESERVADO
                    ),
                    (
                        UsoCodigoDescuento
                        .Estado
                        .CONFIRMADO
                    ),
                ],
            )
            .exists()
        )

        if otro_uso:
            raise DescuentoError(
                (
                    "Este premio ya no "
                    "está disponible."
                )
            )


# ============================================================================
# RESOLVER DESCUENTO
# ============================================================================

def resolver_descuento(
    *,
    usuario,
    rut,
    subtotal,
    codigo,
    bloquear=False,
):
    """
    Resuelve un código de descuento.

    COMPORTAMIENTO:

    1. Sin código:
       devuelve resultado sin descuento.

    2. Código + sin RUT + bloquear=False:
       permite calcular el descuento provisionalmente.

       Esto se utiliza en el resumen AJAX del checkout.

    3. Código + RUT:
       comprueba si la combinación:

           RUT + CÓDIGO

       ya fue utilizada o está reservada.

    4. bloquear=True:
       corresponde al flujo definitivo de compra.
       En ese caso el RUT es obligatorio.

    La reserva definitiva vuelve a ser validada posteriormente
    por reservar_codigo_descuento().
    """

    # ========================================================================
    # NORMALIZAR
    # ========================================================================

    codigo_texto = (
        normalizar_codigo(
            codigo
        )
    )

    subtotal = Decimal(
        str(
            subtotal
            or 0
        )
    )

    rut_normalizado = (
        normalizar_rut(
            rut
        )
    )

    # ========================================================================
    # SIN CÓDIGO
    # ========================================================================

    if not codigo_texto:
        return (
            resultado_sin_descuento()
        )

    # ========================================================================
    # BUSCAR CÓDIGO
    # ========================================================================

    consulta = (
        CodigoDescuento.objects
        .filter(
            codigo=codigo_texto,
        )
    )

    if bloquear:
        consulta = (
            consulta
            .select_for_update()
        )

    codigo_objeto = (
        consulta.first()
    )

    if codigo_objeto is None:
        raise DescuentoError(
            (
                "El código ingresado "
                "no existe."
            )
        )

    # ========================================================================
    # VALIDAR VIGENCIA
    # ========================================================================

    _validar_vigencia(
        codigo_objeto
    )

    # ========================================================================
    # VALIDAR PROPIETARIO
    # ========================================================================
    #
    # Los códigos de fidelidad continúan perteneciendo
    # exclusivamente al usuario que los recibió.
    # ========================================================================

    _validar_propietario(
        codigo=codigo_objeto,
        usuario=usuario,
    )

    # ========================================================================
    # IDENTIFICACIÓN DEL CLIENTE
    # ========================================================================
    #
    # SIN RUT:
    #
    # Si bloquear=False estamos solamente mostrando
    # una previsualización del descuento.
    #
    # En esa etapa NO impedimos aplicar el código.
    #
    # CON RUT:
    #
    # generamos la clave RUT:<HMAC> y comprobamos
    # la combinación RUT + código.
    # ========================================================================

    cliente_clave = ""

    if rut_normalizado:

        cliente_clave = (
            crear_cliente_clave(
                usuario=usuario,
                rut=rut_normalizado,
            )
        )

        # --------------------------------------------------------------------
        # COMPROBAR:
        #
        # mismo RUT + mismo código
        # --------------------------------------------------------------------

        _validar_uso_anterior(
            codigo=codigo_objeto,
            cliente_clave=cliente_clave,
        )

    elif bloquear:

        # --------------------------------------------------------------------
        # En una operación definitiva nunca permitimos
        # utilizar un código sin RUT.
        # --------------------------------------------------------------------

        raise DescuentoError(
            (
                "Debes ingresar un RUT válido "
                "para utilizar este código."
            )
        )

    # ========================================================================
    # MONTO MÍNIMO
    # ========================================================================

    monto_minimo = (
        codigo_objeto.monto_minimo
        or Decimal(
            "0"
        )
    )

    if subtotal < monto_minimo:
        raise DescuentoError(
            (
                "Este código requiere una "
                "compra mínima de "
                f"${monto_minimo:,.0f}."
            )
        )

    # ========================================================================
    # MODALIDAD
    # ========================================================================

    if (
        codigo_objeto.modalidad
        == CodigoDescuento
        .Modalidad
        .MONTO_FIJO
    ):

        descuento = (
            calcular_importe_descuento_fijo(
                subtotal=subtotal,
                codigo=codigo_objeto,
            )
        )

        porcentaje_resultado = (
            Decimal(
                "0"
            )
        )

    else:

        descuento = (
            calcular_importe_descuento(
                subtotal=subtotal,

                porcentaje=(
                    codigo_objeto
                    .porcentaje
                    or Decimal(
                        "0"
                    )
                ),

                monto_maximo=(
                    codigo_objeto
                    .monto_maximo_descuento
                ),
            )
        )

        porcentaje_resultado = (
            codigo_objeto
            .porcentaje
            or Decimal(
                "0"
            )
        )

    # ========================================================================
    # TIPO DEL DESCUENTO
    # ========================================================================

    if (
        codigo_objeto.tipo
        == CodigoDescuento
        .Tipo
        .FIDELIDAD
    ):

        tipo_pedido = (
            Pedido
            .TipoDescuento
            .FIDELIDAD
        )

    else:

        tipo_pedido = (
            Pedido
            .TipoDescuento
            .GENERAL
        )

    # ========================================================================
    # RESULTADO
    # ========================================================================

    return ResultadoDescuento(
        codigo_objeto=(
            codigo_objeto
        ),

        codigo=(
            codigo_objeto.codigo
        ),

        tipo=(
            tipo_pedido
        ),

        porcentaje=(
            porcentaje_resultado
        ),

        descuento=(
            descuento
        ),

        cliente_clave=(
            cliente_clave
        ),
    )
# ============================================================================
# RESERVAR USO DEL CÓDIGO
# ============================================================================


@transaction.atomic
def reservar_codigo_descuento(
    *,
    resultado,
    pedido,
    usuario,
    rut,
):
    if (
        resultado.codigo_objeto
        is None
    ):
        return None

    codigo = (
        CodigoDescuento.objects
        .select_for_update()
        .get(
            pk=(
                resultado
                .codigo_objeto
                .pk
            )
        )
    )

    _validar_vigencia(
        codigo
    )

    _validar_propietario(
        codigo=codigo,
        usuario=usuario,
    )

    # Se vuelve a calcular para no confiar
    # únicamente en el resultado recibido.
    cliente_clave = (
        crear_cliente_clave(
            usuario=usuario,
            rut=rut,
        )
    )

    _validar_uso_anterior(
        codigo=codigo,
        cliente_clave=cliente_clave,
    )

    try:
        uso = (
            UsoCodigoDescuento.objects
            .create(
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
                    cliente_clave
                ),

                rut_enmascarado=(
                    enmascarar_rut(
                        rut
                    )
                ),

                estado=(
                    UsoCodigoDescuento
                    .Estado
                    .RESERVADO
                ),

                subtotal_original=(
                    pedido.subtotal
                ),

                descuento_aplicado=(
                    pedido.descuento
                ),

                total_final=(
                    pedido.total
                ),
            )
        )

    except IntegrityError as error:
        raise DescuentoError(
            (
                "Este código de descuento ya fue "
                "utilizado con este RUT."
            )
        ) from error

    return uso


# ============================================================================
# CONFIRMAR USO DEL CÓDIGO
# ============================================================================


@transaction.atomic
def confirmar_uso_codigo_pedido(
    pedido,
):
    uso = (
        UsoCodigoDescuento.objects
        .select_for_update()
        .select_related(
            "codigo"
        )
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

    uso.confirmado_en = (
        timezone.now()
    )

    uso.save(
        update_fields=[
            "estado",
            "confirmado_en",
        ]
    )

    # Los códigos de fidelidad son personales
    # y de un solo uso.
    if (
        uso.codigo.tipo
        == CodigoDescuento
        .Tipo
        .FIDELIDAD
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


# ============================================================================
# LIBERAR RESERVA DEL CÓDIGO
# ============================================================================


@transaction.atomic
def liberar_uso_codigo_pedido(
    pedido,
):
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

    uso.liberado_en = (
        timezone.now()
    )

    uso.save(
        update_fields=[
            "estado",
            "liberado_en",
        ]
    )

    return True


# ============================================================================
# GENERAR CÓDIGO PERSONAL DE FIDELIDAD
# ============================================================================


def generar_codigo_fidelidad_unico(
    *,
    usuario,
    meta,
):
    """
    Cada cliente recibe un código diferente.

    Ejemplo:

    FIEL10-25-M3-A8CF21

    25:
        ID del usuario.

    M3:
        ID de la meta.

    A8CF21:
        fragmento aleatorio.
    """

    prefijo = normalizar_codigo(
        meta.prefijo_codigo
    )

    if not prefijo:
        prefijo = "AUDEXFIEL"

    while True:
        token = (
            secrets
            .token_hex(3)
            .upper()
        )

        codigo = (
            f"{prefijo}-"
            f"{usuario.pk}-"
            f"M{meta.pk}-"
            f"{token}"
        )

        existe = (
            CodigoDescuento.objects
            .filter(
                codigo=codigo,
            )
            .exists()
        )

        if not existe:
            return codigo


# ============================================================================
# REGISTRAR COMPRA EN FIDELIDAD
# ============================================================================
@transaction.atomic
def registrar_compra_fidelidad(
    pedido_id,
):
    """
    Contabiliza una compra aprobada en el programa
    de fidelidad y genera los premios correspondientes.

    Reglas:

    - Solo cuenta pedidos pagados y aprobados.
    - Solo cuenta Webpay y Mercado Pago.
    - Solo cuenta pedidos asociados a un usuario.
    - Cada pedido se contabiliza una sola vez.
    - El despacho NO suma fidelidad.
    - Se acumula subtotal - descuento.
    - El acumulado es histórico.
    - Cada MetaFidelidad se entrega una sola vez
      por usuario.
    - Soporta premios porcentuales y premios CLP.
    """

    # ==================================================================
    # PEDIDO
    # ==================================================================

    pedido = (
        Pedido.objects
        .select_for_update()
        .select_related(
            "usuario",
        )
        .get(
            pk=pedido_id,
        )
    )

    # ==================================================================
    # EL PAGO DEBE ESTAR APROBADO
    # ==================================================================

    if not pedido.pago_aprobado:
        return []

    # ==================================================================
    # MÉTODO DE PAGO VÁLIDO PARA FIDELIDAD
    # ==================================================================
    #
    # Solamente:
    #
    # - Webpay
    # - Mercado Pago
    #
    # Transferencias y otros métodos no generan fidelidad.
    # ==================================================================

    if pedido.metodo_pago not in {
        Pedido.MetodoPago.WEBPAY,
        Pedido.MetodoPago.MERCADOPAGO,
    }:
        return []

    # ==================================================================
    # SOLO CLIENTES CON CUENTA
    # ==================================================================

    if pedido.usuario_id is None:
        return []

    # ==================================================================
    # SALDO DEL CLIENTE
    # ==================================================================

    saldo, _ = (
        SaldoFidelidad.objects
        .get_or_create(
            usuario=pedido.usuario,
        )
    )

    saldo = (
        SaldoFidelidad.objects
        .select_for_update()
        .get(
            pk=saldo.pk,
        )
    )

    # ==================================================================
    # CONTABILIZAR PEDIDO
    # ==================================================================

    if not pedido.fidelidad_contabilizada:

        subtotal = Decimal(
            str(
                pedido.subtotal
                or 0
            )
        )

        descuento = Decimal(
            str(
                pedido.descuento
                or 0
            )
        )

        # --------------------------------------------------------------
        # IMPORTE QUE SUMA A FIDELIDAD
        # --------------------------------------------------------------
        #
        # No utilizamos pedido.total porque incluye despacho.
        #
        # Fidelidad:
        #
        #     subtotal - descuento
        #
        # --------------------------------------------------------------

        monto_contabilizado = max(
            subtotal - descuento,
            Decimal("0"),
        )

        saldo.total_historico = (
            Decimal(
                str(
                    saldo.total_historico
                    or 0
                )
            )
            + monto_contabilizado
        )

        # --------------------------------------------------------------
        # SALDO ACTUAL
        # --------------------------------------------------------------

        saldo.saldo_actual = (
            saldo.total_historico
        )

        # --------------------------------------------------------------
        # MARCAR PEDIDO COMO CONTABILIZADO
        # --------------------------------------------------------------

        pedido.fidelidad_contabilizada = (
            True
        )

        pedido.save(
            update_fields=[
                "fidelidad_contabilizada",
                "actualizado",
            ]
        )

    # ==================================================================
    # TOTAL ACUMULADO
    # ==================================================================

    total_historico = Decimal(
        str(
            saldo.total_historico
            or 0
        )
    )

    # ==================================================================
    # METAS ALCANZADAS
    # ==================================================================

    metas_alcanzadas = (
        MetaFidelidad.objects
        .filter(
            activa=True,
            monto_objetivo__lte=(
                total_historico
            ),
        )
        .order_by(
            "monto_objetivo",
            "orden",
            "pk",
        )
    )

    codigos_generados = []

    ahora = timezone.now()

    # ==================================================================
    # GENERAR UN PREMIO POR CADA META ALCANZADA
    # ==================================================================

    for meta in metas_alcanzadas:

        # --------------------------------------------------------------
        # ESTA META YA FUE ENTREGADA AL CLIENTE
        # --------------------------------------------------------------
        #
        # Buscamos incluso códigos:
        #
        # - usados;
        # - vencidos;
        # - desactivados.
        #
        # Si la meta ya entregó un código, no generamos otro.
        # --------------------------------------------------------------

        ya_generado = (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                usuario_exclusivo=(
                    pedido.usuario
                ),
                meta_fidelidad=meta,
            )
            .exists()
        )

        if ya_generado:
            continue

        # --------------------------------------------------------------
        # CÓDIGO ÚNICO
        # --------------------------------------------------------------

        codigo_texto = (
            generar_codigo_fidelidad_unico(
                usuario=pedido.usuario,
                meta=meta,
            )
        )

        # --------------------------------------------------------------
        # DATOS BASE
        # --------------------------------------------------------------

        datos_codigo = {
            "tipo": (
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),

            "modalidad": (
                meta.modalidad
            ),

            "nombre": (
                f"Premio · {meta.nombre}"
            ),

            "codigo": (
                codigo_texto
            ),

            "descripcion": (
                "Premio personal generado "
                f"por alcanzar la meta "
                f"«{meta.nombre}»."
            ),

            "activo": True,

            "consumido": False,

            "monto_minimo": (
                meta.monto_minimo_compra
                or Decimal("0")
            ),

            "fecha_inicio": (
                ahora
            ),

            "fecha_fin": (
                ahora
                + timedelta(
                    days=(
                        meta.vigencia_dias
                    )
                )
            ),

            "usuario_exclusivo": (
                pedido.usuario
            ),

            "meta_fidelidad": (
                meta
            ),

            "numero_meta": (
                meta.pk
            ),
        }

        # --------------------------------------------------------------
        # PREMIO PORCENTUAL
        # --------------------------------------------------------------

        if (
            meta.modalidad
            == CodigoDescuento
            .Modalidad
            .PORCENTAJE
        ):

            datos_codigo[
                "porcentaje"
            ] = (
                meta.porcentaje
            )

            datos_codigo[
                "monto_descuento"
            ] = None

            datos_codigo[
                "monto_maximo_descuento"
            ] = (
                meta.monto_maximo_descuento
            )

        # --------------------------------------------------------------
        # PREMIO MONTO FIJO
        # --------------------------------------------------------------

        else:

            datos_codigo[
                "porcentaje"
            ] = None

            datos_codigo[
                "monto_descuento"
            ] = (
                meta.monto_descuento
            )

            datos_codigo[
                "monto_maximo_descuento"
            ] = None

        # --------------------------------------------------------------
        # CREAR PREMIO
        # --------------------------------------------------------------

        codigo = (
            CodigoDescuento.objects
            .create(
                **datos_codigo
            )
        )

        codigos_generados.append(
            codigo
        )

    # ==================================================================
    # METAS CUMPLIDAS
    # ==================================================================
    #
    # Una meta continúa contando históricamente aunque su código:
    #
    # - haya sido utilizado;
    # - esté vencido;
    # - haya sido desactivado.
    # ==================================================================

    saldo.metas_cumplidas = (
        CodigoDescuento.objects
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),
            usuario_exclusivo=(
                pedido.usuario
            ),
            meta_fidelidad__isnull=False,
        )
        .values(
            "meta_fidelidad_id"
        )
        .distinct()
        .count()
    )

    saldo.saldo_actual = (
        saldo.total_historico
    )

    saldo.save(
        update_fields=[
            "saldo_actual",
            "total_historico",
            "metas_cumplidas",
            "actualizado",
        ]
    )

    return codigos_generados


@transaction.atomic
def sincronizar_fidelidad_usuario(
    usuario,
):
    """
    Reconstruye completamente la fidelidad del usuario
    utilizando los pedidos realmente válidos.

    Reglas:

    - Solo Webpay y Mercado Pago.
    - Solo pagos aprobados.
    - Solo pedidos marcados como pagados.
    - No incluye despacho.
    - Acumula subtotal - descuento.
    - Corrige pedidos antiguos incorrectamente marcados.
    - Genera premios faltantes.
    - Nunca vuelve a generar una recompensa de una meta
      que ya entregó anteriormente un código.
    """

    # ==================================================================
    # USUARIO
    # ==================================================================

    if not getattr(
        usuario,
        "is_authenticated",
        False,
    ):
        return []

    # ==================================================================
    # PEDIDOS REALMENTE VÁLIDOS PARA FIDELIDAD
    # ==================================================================

    pedidos = list(
        Pedido.objects
        .select_for_update()
        .filter(
            usuario=usuario,

            pagado=True,

            estado_pago=(
                Pedido
                .EstadoPago
                .APROBADO
            ),

            metodo_pago__in=[
                Pedido
                .MetodoPago
                .WEBPAY,

                Pedido
                .MetodoPago
                .MERCADOPAGO,
            ],
        )
        .order_by(
            "creado",
            "pk",
        )
    )

    # ==================================================================
    # RECALCULAR ACUMULADO DESDE CERO
    # ==================================================================

    total_historico = Decimal(
        "0"
    )

    for pedido in pedidos:

        subtotal = Decimal(
            str(
                pedido.subtotal
                or 0
            )
        )

        descuento = Decimal(
            str(
                pedido.descuento
                or 0
            )
        )

        # --------------------------------------------------------------
        # NO INCLUIR DESPACHO
        # --------------------------------------------------------------

        monto = max(
            subtotal - descuento,
            Decimal("0"),
        )

        total_historico += (
            monto
        )

    # ==================================================================
    # SALDO
    # ==================================================================

    saldo, _ = (
        SaldoFidelidad.objects
        .get_or_create(
            usuario=usuario,
        )
    )

    saldo = (
        SaldoFidelidad.objects
        .select_for_update()
        .get(
            pk=saldo.pk,
        )
    )

    saldo.total_historico = (
        total_historico
    )

    saldo.saldo_actual = (
        total_historico
    )

    # ==================================================================
    # IDS DE PEDIDOS VÁLIDOS
    # ==================================================================

    pedidos_validos_ids = [
        pedido.pk
        for pedido
        in pedidos
    ]

    # ==================================================================
    # MARCAR PEDIDOS VÁLIDOS COMO CONTABILIZADOS
    # ==================================================================

    if pedidos_validos_ids:

        (
            Pedido.objects
            .filter(
                pk__in=(
                    pedidos_validos_ids
                )
            )
            .update(
                fidelidad_contabilizada=True,
            )
        )

    # ==================================================================
    # LIMPIAR PEDIDOS QUE YA NO DEBEN CONTAR
    # ==================================================================
    #
    # Esto corrige pedidos antiguos que hayan quedado marcados
    # fidelidad_contabilizada=True aunque actualmente:
    #
    # - estén rechazados;
    # - estén cancelados;
    # - estén reembolsados;
    # - sean transferencias;
    # - no estén pagados;
    # - ya no tengan estado APROBADO.
    # ==================================================================

    pedidos_no_validos = (
        Pedido.objects
        .filter(
            usuario=usuario,
            fidelidad_contabilizada=True,
        )
    )

    if pedidos_validos_ids:

        pedidos_no_validos = (
            pedidos_no_validos
            .exclude(
                pk__in=(
                    pedidos_validos_ids
                )
            )
        )

    pedidos_no_validos.update(
        fidelidad_contabilizada=False,
    )

    # ==================================================================
    # METAS ALCANZADAS
    # ==================================================================

    metas = (
        MetaFidelidad.objects
        .filter(
            activa=True,

            monto_objetivo__lte=(
                total_historico
            ),
        )
        .order_by(
            "monto_objetivo",
            "orden",
            "pk",
        )
    )

    codigos_generados = []

    ahora = timezone.now()

    # ==================================================================
    # GENERAR PREMIOS FALTANTES
    # ==================================================================

    for meta in metas:

        # --------------------------------------------------------------
        # COMPROBAR SI ESTA META YA ENTREGÓ UN PREMIO
        # --------------------------------------------------------------

        existente = (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),

                usuario_exclusivo=(
                    usuario
                ),

                meta_fidelidad=(
                    meta
                ),
            )
            .first()
        )

        if existente:
            continue

        # --------------------------------------------------------------
        # CÓDIGO ÚNICO
        # --------------------------------------------------------------

        codigo_texto = (
            generar_codigo_fidelidad_unico(
                usuario=usuario,
                meta=meta,
            )
        )

        # --------------------------------------------------------------
        # DATOS BASE
        # --------------------------------------------------------------

        datos = {
            "tipo": (
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),

            "modalidad": (
                meta.modalidad
            ),

            "nombre": (
                f"Premio · {meta.nombre}"
            ),

            "codigo": (
                codigo_texto
            ),

            "descripcion": (
                "Premio personal generado "
                "automáticamente por fidelidad."
            ),

            "activo": True,

            "consumido": False,

            "monto_minimo": (
                meta.monto_minimo_compra
                or Decimal("0")
            ),

            "fecha_inicio": (
                ahora
            ),

            "fecha_fin": (
                ahora
                + timedelta(
                    days=(
                        meta.vigencia_dias
                    )
                )
            ),

            "usuario_exclusivo": (
                usuario
            ),

            "meta_fidelidad": (
                meta
            ),

            "numero_meta": (
                meta.pk
            ),
        }

        # --------------------------------------------------------------
        # PREMIO PORCENTUAL
        # --------------------------------------------------------------

        if (
            meta.modalidad
            == CodigoDescuento
            .Modalidad
            .PORCENTAJE
        ):

            datos[
                "porcentaje"
            ] = (
                meta.porcentaje
            )

            datos[
                "monto_descuento"
            ] = None

            datos[
                "monto_maximo_descuento"
            ] = (
                meta.monto_maximo_descuento
            )

        # --------------------------------------------------------------
        # PREMIO MONTO FIJO
        # --------------------------------------------------------------

        else:

            datos[
                "porcentaje"
            ] = None

            datos[
                "monto_descuento"
            ] = (
                meta.monto_descuento
            )

            datos[
                "monto_maximo_descuento"
            ] = None

        # --------------------------------------------------------------
        # CREAR CÓDIGO
        # --------------------------------------------------------------

        codigo = (
            CodigoDescuento.objects
            .create(
                **datos
            )
        )

        codigos_generados.append(
            codigo
        )

    # ==================================================================
    # METAS CUMPLIDAS
    # ==================================================================

    saldo.metas_cumplidas = (
        CodigoDescuento.objects
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),

            usuario_exclusivo=(
                usuario
            ),

            meta_fidelidad__isnull=False,
        )
        .values(
            "meta_fidelidad_id"
        )
        .distinct()
        .count()
    )

    # ==================================================================
    # GUARDAR SALDO
    # ==================================================================

    saldo.save(
        update_fields=[
            "saldo_actual",
            "total_historico",
            "metas_cumplidas",
            "actualizado",
        ]
    )

    return codigos_generados
# ============================================================================
# OBTENER PREMIOS PERSONALES DISPONIBLES
# ============================================================================


def obtener_codigos_disponibles(
    usuario,
):
    """
    Devuelve exclusivamente los premios
    de fidelidad del usuario autenticado
    que todavía pueden utilizarse.
    """

    if not getattr(
        usuario,
        "is_authenticated",
        False,
    ):
        return (
            CodigoDescuento.objects
            .none()
        )

    ahora = timezone.now()

    return (
        CodigoDescuento.objects
        .select_related(
            "meta_fidelidad"
        )
        .filter(
            tipo=(
                CodigoDescuento
                .Tipo
                .FIDELIDAD
            ),
            usuario_exclusivo=usuario,
            activo=True,
            consumido=False,
        )
        .filter(
            Q(
                fecha_inicio__isnull=True
            )
            |
            Q(
                fecha_inicio__lte=ahora
            )
        )
        .filter(
            Q(
                fecha_fin__isnull=True
            )
            |
            Q(
                fecha_fin__gt=ahora
            )
        )
        .order_by(
            "meta_fidelidad__monto_objetivo",
            "fecha_fin",
            "-creado",
        )
    )


# ============================================================================
# OBTENER METAS Y PROGRESO DEL USUARIO
# ============================================================================


def obtener_progreso_fidelidad(
    usuario,
):
    """
    Devuelve las metas activas junto al estado
    actual del cliente.

    Esta función sirve para construir la página
    pública de ofertas.
    """

    if not getattr(
        usuario,
        "is_authenticated",
        False,
    ):
        return []

    saldo, _ = (
        SaldoFidelidad.objects
        .get_or_create(
            usuario=usuario,
        )
    )

    acumulado = (
        saldo.total_historico
        or Decimal("0")
    )

    metas = (
        MetaFidelidad.objects
        .filter(
            activa=True
        )
        .order_by(
            "monto_objetivo",
            "orden",
            "pk",
        )
    )

    metas_usuario = []

    for meta in metas:
        objetivo = (
            meta.monto_objetivo
            or Decimal("1")
        )

        if objetivo <= Decimal("0"):
            objetivo = Decimal("1")

        progreso = min(
            max(
                int(
                    acumulado
                    * Decimal("100")
                    / objetivo
                ),
                0,
            ),
            100,
        )

        faltante = max(
            objetivo - acumulado,
            Decimal("0"),
        )

        codigo_generado = (
            CodigoDescuento.objects
            .filter(
                tipo=(
                    CodigoDescuento
                    .Tipo
                    .FIDELIDAD
                ),
                usuario_exclusivo=usuario,
                meta_fidelidad=meta,
            )
            .order_by(
                "-creado"
            )
            .first()
        )

        metas_usuario.append(
            {
                "meta": meta,
                "monto_objetivo": (
                    objetivo
                ),
                "acumulado": (
                    acumulado
                ),
                "faltante": (
                    faltante
                ),
                "progreso": (
                    progreso
                ),
                "alcanzada": (
                    acumulado >= objetivo
                ),
                "codigo_generado": (
                    codigo_generado
                ),
                "premio_disponible": (
                    codigo_generado
                    is not None
                    and codigo_generado.activo
                    and not codigo_generado.consumido
                    and codigo_generado.vigente
                ),
            }
        )

    return metas_usuario