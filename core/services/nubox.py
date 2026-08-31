# core/services/nubox.py

import json
import logging
import re
import uuid

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

import requests

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPCIONES
# =============================================================================


class NuboxError(Exception):
    """
    Error controlado durante una operación
    con la API de Nubox.
    """


# =============================================================================
# CONSTANTES
# =============================================================================


IVA = Decimal("0.19")
FACTOR_IVA = Decimal("1.19")

NUBOX_BOLETA_AFECTA = "39"

NUBOX_IVA_LEGAL_CODE = "14"

NUBOX_UNIDAD = "UNID"

NUBOX_TIPO_VENTA_NORMAL = 1

NUBOX_PAGO_CONTADO = 1


# =============================================================================
# REGIONES
# =============================================================================


REGIONES_NUBOX = {
    "tarapaca": "01",
    "i tarapaca": "01",
    "antofagasta": "02",
    "ii antofagasta": "02",
    "atacama": "03",
    "iii atacama": "03",
    "coquimbo": "04",
    "iv coquimbo": "04",
    "valparaiso": "05",
    "v valparaiso": "05",
    "ohiggins": "06",
    "o'higgins": "06",
    "libertador general bernardo ohiggins": "06",
    "libertador general bernardo o'higgins": "06",
    "maule": "07",
    "biobio": "08",
    "biobío": "08",
    "la araucania": "09",
    "la araucanía": "09",
    "los lagos": "10",
    "aysen": "11",
    "aysén": "11",
    "magallanes": "12",
    "metropolitana": "13",
    "region metropolitana": "13",
    "región metropolitana": "13",
    "metropolitana de santiago": "13",
    "los rios": "14",
    "los ríos": "14",
    "arica y parinacota": "15",
    "nuble": "16",
    "ñuble": "16",
}


# =============================================================================
# COMUNAS
# =============================================================================


# Códigos legalCode publicados por Nubox para
# client.territorialDivisionL2LegalCode.
#
# Las claves están normalizadas con el mismo criterio
# utilizado por _normalizar_texto().
COMUNAS_NUBOX = {
    # 01 - Tarapacá
    "iquique": "01101",
    "alto hospicio": "01107",
    "pozo almonte": "01401",
    "camina": "01402",
    "colchane": "01403",
    "huara": "01404",
    "pica": "01405",

    # 02 - Antofagasta
    "antofagasta": "02101",
    "mejillones": "02102",
    "sierra gorda": "02103",
    "taltal": "02104",
    "calama": "02201",
    "ollague": "02202",
    "san pedro de atacama": "02203",
    "tocopilla": "02301",
    "maria elena": "02302",

    # 03 - Atacama
    "copiapo": "03101",
    "caldera": "03102",
    "tierra amarilla": "03103",
    "chanaral": "03201",
    "diego de almagro": "03202",
    "vallenar": "03301",
    "alto del carmen": "03302",
    "freirina": "03303",
    "huasco": "03304",

    # 04 - Coquimbo
    "la serena": "04101",
    "coquimbo": "04102",
    "andacollo": "04103",
    "la higuera": "04104",
    "paiguano": "04105",
    "vicuna": "04106",
    "illapel": "04201",
    "canela": "04202",
    "los vilos": "04203",
    "salamanca": "04204",
    "ovalle": "04301",
    "combarbala": "04302",
    "monte patria": "04303",
    "punitaqui": "04304",
    "rio hurtado": "04305",

    # 05 - Valparaíso
    "valparaiso": "05101",
    "casablanca": "05102",
    "concon": "05103",
    "juan fernandez": "05104",
    "puchuncavi": "05105",
    "quintero": "05107",
    "vina del mar": "05109",
    "isla de pascua": "05201",
    "los andes": "05301",
    "calle larga": "05302",
    "rinconada": "05303",
    "san esteban": "05304",
    "la ligua": "05401",
    "cabildo": "05402",
    "papudo": "05403",
    "petorca": "05404",
    "zapallar": "05405",
    "quillota": "05501",
    "calera": "05502",
    "hijuelas": "05503",
    "la cruz": "05504",
    "nogales": "05506",
    "san antonio": "05601",
    "algarrobo": "05602",
    "cartagena": "05603",
    "el quisco": "05604",
    "el tabo": "05605",
    "santo domingo": "05606",
    "san felipe": "05701",
    "catemu": "05702",
    "llaillay": "05703",
    "panquehue": "05704",
    "putaendo": "05705",
    "santa maria": "05706",
    "quilpue": "05801",
    "limache": "05802",
    "olmue": "05803",
    "villa alemana": "05804",

    # 06 - O'Higgins
    "rancagua": "06101",
    "codegua": "06102",
    "coinco": "06103",
    "coltauco": "06104",
    "donihue": "06105",
    "graneros": "06106",
    "las cabras": "06107",
    "machali": "06108",
    "malloa": "06109",
    "mostazal": "06110",
    "olivar": "06111",
    "peumo": "06112",
    "pichidegua": "06113",
    "quinta de tilcoco": "06114",
    "rengo": "06115",
    "requinoa": "06116",
    "san vicente": "06117",
    "pichilemu": "06201",
    "la estrella": "06202",
    "litueche": "06203",
    "marchihue": "06204",
    "navidad": "06205",
    "paredones": "06206",
    "san fernando": "06301",
    "chepica": "06302",
    "chimbarongo": "06303",
    "lolol": "06304",
    "nancagua": "06305",
    "palmilla": "06306",
    "peralillo": "06307",
    "placilla": "06308",
    "pumanque": "06309",
    "santa cruz": "06310",

    # 07 - Maule
    "talca": "07101",
    "constitucion": "07102",
    "curepto": "07103",
    "empedrado": "07104",
    "maule": "07105",
    "pelarco": "07106",
    "pencahue": "07107",
    "rio claro": "07108",
    "san clemente": "07109",
    "san rafael": "07110",
    "cauquenes": "07201",
    "chanco": "07202",
    "pelluhue": "07203",
    "curico": "07301",
    "hualane": "07302",
    "licanten": "07303",
    "molina": "07304",
    "rauco": "07305",
    "romeral": "07306",
    "sagrada familia": "07307",
    "teno": "07308",
    "vichuquen": "07309",
    "linares": "07401",
    "colbun": "07402",
    "longavi": "07403",
    "parral": "07404",
    "retiro": "07405",
    "san javier": "07406",
    "villa alegre": "07407",
    "yerbas buenas": "07408",

    # 08 - Biobío
    "concepcion": "08101",
    "coronel": "08102",
    "chiguayante": "08103",
    "florida": "08104",
    "hualqui": "08105",
    "lota": "08106",
    "penco": "08107",
    "san pedro de la paz": "08108",
    "santa juana": "08109",
    "talcahuano": "08110",
    "tome": "08111",
    "hualpen": "08112",
    "lebu": "08201",
    "arauco": "08202",
    "canete": "08203",
    "contulmo": "08204",
    "curanilahue": "08205",
    "los alamos": "08206",
    "tirua": "08207",
    "los angeles": "08301",
    "antuco": "08302",
    "cabrero": "08303",
    "laja": "08304",
    "mulchen": "08305",
    "nacimiento": "08306",
    "negrete": "08307",
    "quilaco": "08308",
    "quilleco": "08309",
    "san rosendo": "08310",
    "santa barbara": "08311",
    "tucapel": "08312",
    "yumbel": "08313",
    "alto biobio": "08314",

    # 09 - La Araucanía
    "temuco": "09101",
    "carahue": "09102",
    "cunco": "09103",
    "curarrehue": "09104",
    "freire": "09105",
    "galvarino": "09106",
    "gorbea": "09107",
    "lautaro": "09108",
    "loncoche": "09109",
    "melipeuco": "09110",
    "nueva imperial": "09111",
    "padre las casas": "09112",
    "perquenco": "09113",
    "pitrufquen": "09114",
    "pucon": "09115",
    "saavedra": "09116",
    "teodoro schmidt": "09117",
    "tolten": "09118",
    "vilcun": "09119",
    "villarrica": "09120",
    "cholchol": "09121",
    "angol": "09201",
    "collipulli": "09202",
    "curacautin": "09203",
    "ercilla": "09204",
    "lonquimay": "09205",
    "los sauces": "09206",
    "lumaco": "09207",
    "puren": "09208",
    "renaico": "09209",
    "traiguen": "09210",
    "victoria": "09211",

    # 10 - Los Lagos
    "puerto montt": "10101",
    "calbuco": "10102",
    "cochamo": "10103",
    "fresia": "10104",
    "frutillar": "10105",
    "los muermos": "10106",
    "llanquihue": "10107",
    "maullin": "10108",
    "puerto varas": "10109",
    "castro": "10201",
    "ancud": "10202",
    "chonchi": "10203",
    "curaco de velez": "10204",
    "dalcahue": "10205",
    "puqueldon": "10206",
    "queilen": "10207",
    "quellon": "10208",
    "quemchi": "10209",
    "quinchao": "10210",
    "osorno": "10301",
    "puerto octay": "10302",
    "purranque": "10303",
    "puyehue": "10304",
    "rio negro": "10305",
    "san juan de la costa": "10306",
    "san pablo": "10307",
    "chaiten": "10401",
    "futaleufu": "10402",
    "hualaihue": "10403",
    "palena": "10404",

    # 11 - Aysén
    "coyhaique": "11101",
    "lago verde": "11102",
    "aisen": "11201",
    "cisnes": "11202",
    "guaitecas": "11203",
    "cochrane": "11301",
    "o'higgins": "11302",
    "tortel": "11303",
    "chile chico": "11401",
    "rio ibanez": "11402",

    # 12 - Magallanes
    "punta arenas": "12101",
    "laguna blanca": "12102",
    "rio verde": "12103",
    "san gregorio": "12104",
    "cabo de hornos": "12201",
    "antartica": "12202",
    "porvenir": "12301",
    "primavera": "12302",
    "timaukel": "12303",
    "natales": "12401",
    "torres del paine": "12402",

    # 13 - Metropolitana
    "santiago": "13101",
    "cerrillos": "13102",
    "cerro navia": "13103",
    "conchali": "13104",
    "el bosque": "13105",
    "estacion central": "13106",
    "huechuraba": "13107",
    "independencia": "13108",
    "la cisterna": "13109",
    "la florida": "13110",
    "la granja": "13111",
    "la pintana": "13112",
    "la reina": "13113",
    "las condes": "13114",
    "lo barnechea": "13115",
    "lo espejo": "13116",
    "lo prado": "13117",
    "macul": "13118",
    "maipu": "13119",
    "nunoa": "13120",
    "pedro aguirre cerda": "13121",
    "penalolen": "13122",
    "providencia": "13123",
    "pudahuel": "13124",
    "quilicura": "13125",
    "quinta normal": "13126",
    "recoleta": "13127",
    "renca": "13128",
    "san joaquin": "13129",
    "san miguel": "13130",
    "san ramon": "13131",
    "vitacura": "13132",
    "puente alto": "13201",
    "pirque": "13202",
    "san jose de maipo": "13203",
    "colina": "13301",
    "lampa": "13302",
    "tiltil": "13303",
    "san bernardo": "13401",
    "buin": "13402",
    "calera de tango": "13403",
    "paine": "13404",
    "melipilla": "13501",
    "alhue": "13502",
    "curacavi": "13503",
    "maria pinto": "13504",
    "san pedro": "13505",
    "talagante": "13601",
    "el monte": "13602",
    "isla de maipo": "13603",
    "padre hurtado": "13604",
    "penaflor": "13605",

    # 14 - Los Ríos
    "valdivia": "14101",
    "corral": "14102",
    "lanco": "14103",
    "los lagos": "14104",
    "mafil": "14105",
    "mariquina": "14106",
    "paillaco": "14107",
    "panguipulli": "14108",
    "la union": "14201",
    "futrono": "14202",
    "lago ranco": "14203",
    "rio bueno": "14204",

    # 15 - Arica y Parinacota
    "arica": "15101",
    "camarones": "15102",
    "putre": "15201",
    "general lagos": "15202",

    # 16 - Ñuble
    "chillan": "16101",
    "bulnes": "16102",
    "chillan viejo": "16103",
    "el carmen": "16104",
    "pemuco": "16105",
    "pinto": "16106",
    "quillon": "16107",
    "san ignacio": "16108",
    "yungay": "16109",
    "quirihue": "16201",
    "cobquecura": "16202",
    "coelemu": "16203",
    "ninhue": "16204",
    "portezuelo": "16205",
    "ranquil": "16206",
    "treguaco": "16207",
    "san carlos": "16301",
    "coihueco": "16302",
    "niquen": "16303",
    "san fabian": "16304",
    "san nicolas": "16305",

}


# Alias habituales que pueden venir desde formularios,
# proveedores de despacho o bases históricas.
COMUNAS_NUBOX_ALIASES = {
    "la calera": "05502",
    "paihuano": "04105",
    "san vicente de tagua tagua": "06117",
    "san vicente tagua tagua": "06117",
    "aysen": "11201",
    "coihaique": "11101",
    "o higgins": "11302",
    "ohiggins": "11302",
    "rapa nui": "05201",
}

# =============================================================================
# UTILIDADES
# =============================================================================


def _texto(
    valor,
    *,
    max_length=None,
):
    texto = str(
        valor
        or ""
    ).strip()

    if (
        max_length
        and len(texto) > max_length
    ):
        texto = texto[:max_length]

    return texto


def _normalizar_texto(
    valor,
):
    texto = _texto(
        valor
    ).lower()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "’": "'",
        "´": "'",
        "`": "'",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(
            origen,
            destino,
        )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    return texto


def _mapping_desde_settings(
    nombre,
):
    """
    Obtiene un mapping desde settings.

    Acepta:
    - dict ya parseado;
    - JSON en texto, útil cuando el valor
      viene directamente desde .env.
    """

    valor = getattr(
        settings,
        nombre,
        {},
    )

    if not valor:
        return {}

    if isinstance(
        valor,
        dict,
    ):
        return valor

    if isinstance(
        valor,
        str,
    ):
        try:
            data = json.loads(
                valor
            )

        except json.JSONDecodeError as error:
            raise NuboxError(
                (
                    f"{nombre} debe contener "
                    "un objeto JSON válido."
                )
            ) from error

        if not isinstance(
            data,
            dict,
        ):
            raise NuboxError(
                (
                    f"{nombre} debe ser "
                    "un objeto JSON."
                )
            )

        return data

    raise NuboxError(
        (
            f"{nombre} debe ser un dict "
            "o un objeto JSON."
        )
    )


def _decimal(
    valor,
):
    try:
        return Decimal(
            str(
                valor
                or 0
            )
        )

    except Exception as error:
        raise NuboxError(
            f"Monto inválido: {valor}"
        ) from error


def _redondear_peso(
    valor,
):
    """
    Nubox trabaja con montos CLP.

    Los dejamos expresados como enteros,
    redondeados al peso.
    """

    return int(
        _decimal(
            valor
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _numero_nubox(
    valor,
):
    """
    Convierte Decimal a un número compatible
    con JSON manteniendo la precisión necesaria
    para Nubox.
    """

    return float(
        _decimal(
            valor
        )
    )


def _precio_neto_desde_bruto(
    precio_bruto,
):
    precio_bruto = _decimal(
        precio_bruto
    )

    if precio_bruto < 0:
        raise NuboxError(
            (
                "No se pueden enviar "
                "montos negativos a Nubox."
            )
        )

    return (
        precio_bruto
        / FACTOR_IVA
    )





def _separar_neto_iva(
    precio_bruto,
):
    """
    Separa un monto bruto IVA incluido en neto e IVA.

    Conservamos precisión decimal para que Nubox
    pueda recalcular el IVA sin generar diferencias
    de $1 por redondeo anticipado.
    """

    bruto = _decimal(
        precio_bruto
    )

    if bruto < 0:
        raise NuboxError(
            (
                "No se pueden enviar "
                "montos negativos a Nubox."
            )
        )

    precision = Decimal(
        "0.000001"
    )

    neto = (
        bruto
        / FACTOR_IVA
    ).quantize(
        precision,
        rounding=ROUND_HALF_UP,
    )

    iva = (
        bruto
        - neto
    ).quantize(
        precision,
        rounding=ROUND_HALF_UP,
    )

    return (
        neto,
        iva,
    )
# =============================================================================
# CONFIGURACIÓN
# =============================================================================


def _configuracion():
    """
    Resuelve la configuración Nubox.

    Compatibilidad:

    URL:
    - NUBOX_API_URL
    - NUBOX_BASE_URL
    - NUBOX_UAT_BASE_URL
    - NUBOX_PRODUCTION_BASE_URL

    API Key:
    - NUBOX_API_KEY
    - NUBOX_COMPANY_API_KEY

    De esta forma el servicio funciona tanto
    con la configuración anterior como con
    el .env nuevo por ambientes.
    """

    enabled = getattr(
        settings,
        "NUBOX_ENABLED",
        True,
    )

    if isinstance(
        enabled,
        str,
    ):
        enabled = (
            enabled.strip().lower()
            in {
                "1",
                "true",
                "yes",
                "si",
                "sí",
                "on",
            }
        )

    if not enabled:
        raise NuboxError(
            (
                "La integración Nubox "
                "está deshabilitada."
            )
        )

    environment = _texto(
        getattr(
            settings,
            "NUBOX_ENV",
            "uat",
        )
    ).lower()

    ambientes_uat = {
        "uat",
        "test",
        "testing",
        "certificacion",
        "certificación",
    }

    ambientes_produccion = {
        "prod",
        "production",
        "produccion",
        "producción",
    }

    if (
        environment
        not in (
            ambientes_uat
            | ambientes_produccion
        )
    ):
        raise NuboxError(
            (
                "NUBOX_ENV inválido. "
                "Usa 'uat' o 'production'."
            )
        )

    # Primero respetamos una URL ya resuelta
    # desde settings.py para mantener
    # compatibilidad con configuraciones
    # anteriores.
    base_url = (
        getattr(
            settings,
            "NUBOX_API_URL",
            "",
        )
        or getattr(
            settings,
            "NUBOX_BASE_URL",
            "",
        )
        or ""
    )

    if not _texto(
        base_url
    ):
        if (
            environment
            in ambientes_produccion
        ):
            base_url = getattr(
                settings,
                "NUBOX_PRODUCTION_BASE_URL",
                "",
            )

        else:
            base_url = getattr(
                settings,
                "NUBOX_UAT_BASE_URL",
                "",
            )

    base_url = (
        _texto(
            base_url
        )
        .rstrip("/?")
    )

    partner_token = _texto(
        getattr(
            settings,
            "NUBOX_PARTNER_TOKEN",
            "",
        )
    )

    # Si por error se configuró con "Bearer ",
    # lo limpiamos para no duplicarlo en headers.
    if (
        partner_token.lower()
        .startswith(
            "bearer "
        )
    ):
        partner_token = (
            partner_token[7:]
            .strip()
        )

    company_api_key = _texto(
        getattr(
            settings,
            "NUBOX_API_KEY",
            "",
        )
        or getattr(
            settings,
            "NUBOX_COMPANY_API_KEY",
            "",
        )
    )

    timeout_valor = getattr(
        settings,
        "NUBOX_TIMEOUT",
        30,
    )

    try:
        timeout = float(
            timeout_valor
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise NuboxError(
            (
                "NUBOX_TIMEOUT debe ser "
                "un número válido."
            )
        ) from error

    if timeout <= 0:
        raise NuboxError(
            (
                "NUBOX_TIMEOUT debe ser "
                "mayor que cero."
            )
        )

    if not base_url:
        raise NuboxError(
            (
                "No existe URL base Nubox. "
                "Configura NUBOX_API_URL, "
                "NUBOX_BASE_URL o la URL "
                "del ambiente correspondiente."
            )
        )

    if not partner_token:
        raise NuboxError(
            (
                "NUBOX_PARTNER_TOKEN "
                "no está configurado."
            )
        )

    if not company_api_key:
        raise NuboxError(
            (
                "NUBOX_API_KEY / "
                "NUBOX_COMPANY_API_KEY "
                "no está configurado."
            )
        )

    return {
        "base_url": base_url,
        "partner_token": (
            partner_token
        ),
        "company_api_key": (
            company_api_key
        ),
        "timeout": timeout,
        "environment": (
            environment
        ),
    }


# =============================================================================
# HEADERS
# =============================================================================


def _headers(
    *,
    idempotence_id=None,
    accept="application/json",
):
    config = _configuracion()

    headers = {
        "Authorization": (
            f"Bearer "
            f"{config['partner_token']}"
        ),
        "X-Api-Key": (
            config[
                "company_api_key"
            ]
        ),
        "Content-Type": (
            "application/json"
        ),
        "Accept": accept,
    }

    if idempotence_id:
        headers[
            "X-Idempotence-id"
        ] = str(
            idempotence_id
        )

    return headers


# =============================================================================
# MANEJO DE ERRORES HTTP
# =============================================================================


def _extraer_mensaje_error(
    response,
):
    try:
        data = response.json()

    except ValueError:
        texto = (
            response.text
            or ""
        ).strip()

        return (
            texto[:2000]
            or "Respuesta inválida de Nubox."
        )

    if isinstance(
        data,
        dict,
    ):
        mensaje = (
            data.get(
                "message"
            )
            or data.get(
                "error"
            )
            or data.get(
                "code"
            )
        )

        errores = (
            data.get(
                "errors"
            )
            or []
        )

        mensajes_errores = []

        if isinstance(
            errores,
            list,
        ):
            for error in errores:

                if not isinstance(
                    error,
                    dict,
                ):
                    continue

                campo = (
                    error.get(
                        "field"
                    )
                    or ""
                )

                detalle = (
                    error.get(
                        "message"
                    )
                    or ""
                )

                if campo and detalle:
                    mensajes_errores.append(
                        f"{campo}: {detalle}"
                    )

                elif detalle:
                    mensajes_errores.append(
                        detalle
                    )

        partes = []

        if mensaje:
            partes.append(
                str(mensaje)
            )

        partes.extend(
            mensajes_errores
        )

        if partes:
            return " | ".join(
                partes
            )[:2000]

    return str(
        data
    )[:2000]


# =============================================================================
# GET
# =============================================================================


def _get(
    endpoint,
    *,
    params=None,
    accept="application/json",
    devolver_bytes=False,
):
    config = _configuracion()

    url = (
        f"{config['base_url']}/"
        f"{endpoint.lstrip('/')}"
    )

    try:
        response = requests.get(
            url,
            headers=_headers(
                accept=accept,
            ),
            params=(
                params
                or {}
            ),
            timeout=config[
                "timeout"
            ],
        )

    except requests.RequestException as error:
        raise NuboxError(
            (
                "No fue posible conectar "
                f"con Nubox: {error}"
            )
        ) from error

    if not response.ok:
        raise NuboxError(
            (
                f"Nubox HTTP "
                f"{response.status_code}: "
                f"{_extraer_mensaje_error(response)}"
            )
        )

    if devolver_bytes:
        return response.content

    try:
        return response.json()

    except ValueError as error:
        raise NuboxError(
            (
                "Nubox respondió con "
                "contenido JSON no válido."
            )
        ) from error


# =============================================================================
# POST
# =============================================================================


def _post(
    endpoint,
    payload,
    *,
    idempotence_id,
):
    config = _configuracion()

    url = (
        f"{config['base_url']}/"
        f"{endpoint.lstrip('/')}"
    )

    try:
        response = requests.post(
            url,
            headers=_headers(
                idempotence_id=(
                    idempotence_id
                ),
            ),
            json=payload,
            timeout=config[
                "timeout"
            ],
        )

    except requests.RequestException as error:
        raise NuboxError(
            (
                "No fue posible conectar "
                f"con Nubox: {error}"
            )
        ) from error

    try:
        data = response.json()

    except ValueError as error:
        raise NuboxError(
            (
                "Nubox respondió con "
                "contenido no válido."
            )
        ) from error

    # Nubox utiliza 207 Multi-Status
    # como respuesta válida del endpoint
    # de emisión.
    if not (
        response.ok
        or response.status_code == 207
    ):
        raise NuboxError(
            (
                f"Nubox HTTP "
                f"{response.status_code}: "
                f"{_extraer_mensaje_error(response)}"
            )
        )

    return data


# =============================================================================
# CÓDIGO REGIÓN
# =============================================================================


def _codigo_region_nubox(
    pedido,
):
    """
    Nubox requiere territorialDivisionLegalCode.

    Prioridad:

    1. pedido.nubox_region_codigo
    2. pedido.region_codigo
    3. NUBOX_REGION_CODES en settings
    4. mapping interno de regiones chilenas
    """

    for atributo in (
        "nubox_region_codigo",
        "region_codigo",
        "codigo_region",
    ):
        valor = getattr(
            pedido,
            atributo,
            None,
        )

        if valor:
            return str(
                valor
            ).zfill(2)

    region = _texto(
        getattr(
            pedido,
            "region",
            "",
        )
    )

    if not region:
        raise NuboxError(
            (
                "El pedido no contiene "
                "región."
            )
        )

    mappings = (
        _mapping_desde_settings(
            "NUBOX_REGION_CODES"
        )
    )

    if isinstance(
        mappings,
        dict,
    ):
        for nombre, codigo in mappings.items():

            if (
                _normalizar_texto(nombre)
                == _normalizar_texto(region)
            ):
                return str(
                    codigo
                ).zfill(2)

    normalizada = (
        _normalizar_texto(
            region
        )
    )

    codigo = (
        REGIONES_NUBOX.get(
            normalizada
        )
    )

    if codigo:
        return codigo

    raise NuboxError(
        (
            "No fue posible determinar "
            "el código Nubox/SII de la región "
            f"'{region}'."
        )
    )


# =============================================================================
# CÓDIGO COMUNA
# =============================================================================


def _codigo_comuna_nubox(
    pedido,
):
    """
    Obtiene el legalCode de comuna requerido
    por Nubox.

    Prioridad:

    1. Código guardado directamente en Pedido.
    2. Si pedido.comuna ya contiene un código
       de 5 dígitos, se utiliza directamente.
    3. NUBOX_COMUNA_CODES en settings/.env.
    4. Catálogo oficial de comunas incluido
       en este servicio.
    5. Alias habituales.

    El catálogo interno evita tener que
    mantener las 346 comunas dentro del .env.
    """

    for atributo in (
        "nubox_comuna_codigo",
        "comuna_codigo",
        "codigo_comuna",
    ):
        valor = getattr(
            pedido,
            atributo,
            None,
        )

        if valor:
            codigo = str(
                valor
            ).strip()

            if not re.fullmatch(
                r"\d{1,5}",
                codigo,
            ):
                raise NuboxError(
                    (
                        f"El código de comuna "
                        f"'{codigo}' guardado "
                        "en el Pedido no es válido."
                    )
                )

            return codigo.zfill(
                5
            )

    comuna = _texto(
        getattr(
            pedido,
            "comuna",
            "",
        )
    )

    if not comuna:
        raise NuboxError(
            (
                "El pedido no contiene "
                "comuna."
            )
        )

    # También aceptamos que pedido.comuna
    # venga directamente con el código SII.
    if re.fullmatch(
        r"\d{5}",
        comuna,
    ):
        return comuna

    normalizada = (
        _normalizar_texto(
            comuna
        )
    )

    # Permite sobrescribir o agregar códigos
    # sin tocar el código fuente.
    mappings = (
        _mapping_desde_settings(
            "NUBOX_COMUNA_CODES"
        )
    )

    for nombre, codigo in mappings.items():

        if (
            _normalizar_texto(
                nombre
            )
            == normalizada
        ):
            codigo = str(
                codigo
            ).strip()

            if not re.fullmatch(
                r"\d{1,5}",
                codigo,
            ):
                raise NuboxError(
                    (
                        "Código inválido en "
                        "NUBOX_COMUNA_CODES para "
                        f"'{nombre}': '{codigo}'."
                    )
                )

            return codigo.zfill(
                5
            )

    codigo = (
        COMUNAS_NUBOX.get(
            normalizada
        )
        or COMUNAS_NUBOX_ALIASES.get(
            normalizada
        )
    )

    if codigo:
        return codigo

    raise NuboxError(
        (
            "No fue posible determinar "
            "el código Nubox/SII de la comuna "
            f"'{comuna}'. "
            "Revisa el nombre recibido desde "
            "checkout o agrega un alias en "
            "NUBOX_COMUNA_CODES."
        )
    )







def _guardar_codigos_territoriales_nubox(
    pedido,
):
    """
    Resuelve y guarda en el Pedido los códigos
    territoriales utilizados por Nubox.
    """

    codigo_region = _codigo_region_nubox(
        pedido
    )

    codigo_comuna = _codigo_comuna_nubox(
        pedido
    )

    campos_update = []

    if hasattr(
        pedido,
        "nubox_region_codigo",
    ):
        pedido.nubox_region_codigo = (
            codigo_region
        )

        campos_update.append(
            "nubox_region_codigo"
        )

    if hasattr(
        pedido,
        "nubox_comuna_codigo",
    ):
        pedido.nubox_comuna_codigo = (
            codigo_comuna
        )

        campos_update.append(
            "nubox_comuna_codigo"
        )

    if campos_update:

        if hasattr(
            pedido,
            "actualizado",
        ):
            campos_update.append(
                "actualizado"
            )

        pedido.save(
            update_fields=list(
                dict.fromkeys(
                    campos_update
                )
            )
        )

    return (
        codigo_region,
        codigo_comuna,
    )
# =============================================================================
# CLIENTE
# =============================================================================


def _crear_cliente_nubox(
    pedido,
):
    rut = (
        _texto(
            getattr(
                pedido,
                "rut",
                "",
            )
        )
        .upper()
        .replace(
            ".",
            "",
        )
    )

    nombre = _texto(
        getattr(
            pedido,
            "nombre",
            "",
        ),
        max_length=50,
    )

    apellido = _texto(
        getattr(
            pedido,
            "apellido",
            "",
        ),
        max_length=50,
    )

    nombre_completo = (
        f"{nombre} {apellido}"
    ).strip()

    email = _texto(
        getattr(
            pedido,
            "email",
            "",
        ),
        max_length=100,
    ).lower()

    telefono = _texto(
        getattr(
            pedido,
            "telefono",
            "",
        ),
        max_length=30,
    )

    direccion = _texto(
        getattr(
            pedido,
            "direccion_completa",
            "",
        ),
        max_length=200,
    )

    comuna = _texto(
        getattr(
            pedido,
            "comuna",
            "",
        ),
        max_length=50,
    )

    if not rut:
        raise NuboxError(
            (
                "El pedido no tiene RUT "
                "para emitir la boleta."
            )
        )

    if not nombre_completo:
        raise NuboxError(
            (
                "El pedido no tiene "
                "nombre del cliente."
            )
        )

    if not email:
        raise NuboxError(
            (
                "El pedido no tiene "
                "correo electrónico."
            )
        )

    actividad = _texto(
        getattr(
            settings,
            "NUBOX_CLIENT_MAIN_ACTIVITY",
            "Consumidor final",
        ),
        max_length=40,
    )

    cliente = {
        "tradeName": (
            nombre_completo[:100]
        ),

        "identification": {
            "type": 1,
            "value": rut,
        },

        "mainActivity": (
            actividad
        ),

        "email": email,

        "contactName": (
            nombre_completo[:100]
        ),

        "address": direccion,

        "city": comuna,

        "territorialDivisionLegalCode": (
            _codigo_region_nubox(
                pedido
            )
        ),

        "territorialDivisionL2LegalCode": (
            _codigo_comuna_nubox(
                pedido
            )
        ),
    }

    if telefono:
        cliente[
            "phone"
        ] = telefono

    return cliente


# =============================================================================
# PRODUCT CODE
# =============================================================================


def _codigo_producto_nubox(
    item,
    *,
    indice,
):
    """
    Nubox limita productCode a determinados
    caracteres y máximo 35 caracteres.
    """

    producto = getattr(
        item,
        "producto",
        None,
    )

    posibles = [
        getattr(
            producto,
            "sku",
            None,
        ),
        getattr(
            producto,
            "codigo",
            None,
        ),
        getattr(
            producto,
            "id",
            None,
        ),
        getattr(
            item,
            "producto_id",
            None,
        ),
    ]

    codigo = ""

    for valor in posibles:

        if valor:
            codigo = str(
                valor
            )
            break

    if not codigo:
        codigo = (
            f"AUDEX-{indice}"
        )

    codigo = re.sub(
        r"[^A-Za-z0-9\-_\.#@\[\]\(\)\{\}]",
        "-",
        codigo,
    )

    return codigo[:35]


# =============================================================================
# DETALLES
# =============================================================================


def _crear_detalles_nubox(
    pedido,
):
    """
    Genera los detalles para Nubox desde
    PedidoItem.

    En la integración Nubox,
    usamos total_final porque contempla:

    - precio/oferta;
    - cantidad;
    - descuento por código.

    Cada PedidoItem se envía como una línea
    económica completa quantity=1 para que
    el total emitido coincida exactamente
    con el pedido.
    """

    detalles = []

    items = list(
        pedido.items.all()
    )

    if not items:
        raise NuboxError(
            (
                "El pedido no contiene "
                "productos."
            )
        )

    total_productos = Decimal(
        "0"
    )

    orden = 1

    for item in items:

        cantidad_real = int(
            getattr(
                item,
                "cantidad",
                0,
            )
            or 0
        )

        if cantidad_real <= 0:
            raise NuboxError(
                (
                    "Existe un ítem con "
                    "cantidad inválida."
                )
            )

        total_final = _decimal(
            getattr(
                item,
                "total_final",
                0,
            )
        )

        # Compatibilidad con pedidos
        # históricos.
        if total_final <= 0:

            total_original = _decimal(
                getattr(
                    item,
                    "total",
                    0,
                )
            )

            descuento_codigo = _decimal(
                getattr(
                    item,
                    "descuento_codigo",
                    0,
                )
            )

            if total_original > 0:
                total_final = max(
                    (
                        total_original
                        - descuento_codigo
                    ),
                    Decimal("0"),
                )

        if total_final <= 0:
            continue

        total_productos += (
            total_final
        )

        (
            neto,
            iva,
        ) = _separar_neto_iva(
            total_final
        )

        nombre_producto = _texto(
            getattr(
                item,
                "nombre_producto",
                "",
            )
            or "Producto Audex",
            max_length=80,
        )

        descripcion_extendida = (
            f"{nombre_producto} "
            f"x {cantidad_real}"
        )

        detalles.append(
            {
                "order": orden,

                "productCode": (
                    _codigo_producto_nubox(
                        item,
                        indice=orden,
                    )
                ),

                # Se envía como línea
                # económica completa.
                "quantity": 1,

                "productDescription": (
                    nombre_producto
                ),

                "productDescriptionExtended": (
                    descripcion_extendida[:1000]
                ),

                "subjectToTax": True,

                "uom": {
                    "code": (
                        NUBOX_UNIDAD
                    )
                },

                # Precio NETO con precisión decimal
                # compatible con JSON/Nubox.
                "price": _numero_nubox(
                    neto
                ),

                "taxes": [
                    {
                        "legalCode": (
                            NUBOX_IVA_LEGAL_CODE
                        ),
                        "amount": _numero_nubox(
                            iva
                        ),
                    }
                ],

                "discountsAndSurcharges": [],
            }
        )

        orden += 1

    if not detalles:
        raise NuboxError(
            (
                "No existen productos "
                "válidos para emitir."
            )
        )

    return (
        detalles,
        total_productos,
    )


# =============================================================================
# DESPACHO
# =============================================================================


def _agregar_despacho_nubox(
    *,
    pedido,
    detalles,
):
    despacho = _decimal(
        getattr(
            pedido,
            "despacho",
            0,
        )
    )

    if despacho <= 0:
        return Decimal(
            "0"
        )

    (
        neto,
        iva,
    ) = _separar_neto_iva(
        despacho
    )

    detalles.append(
        {
            "order": (
                len(detalles)
                + 1
            ),

            "productCode": (
                "DESPACHO"
            ),

            "quantity": 1,

            "productDescription": (
                "Despacho Blue Express"
            ),

            "productDescriptionExtended": (
                "Servicio de despacho "
                "pedido Audex"
            ),

            "subjectToTax": True,

            "uom": {
                "code": (
                    NUBOX_UNIDAD
                )
            },

            "price": _numero_nubox(
                neto
            ),

            "taxes": [
                {
                    "legalCode": (
                        NUBOX_IVA_LEGAL_CODE
                    ),
                    "amount": _numero_nubox(
                        iva
                    ),
                }
            ],

            "discountsAndSurcharges": [],
        }
    )

    return despacho


# =============================================================================
# PAYLOAD
# =============================================================================


def _crear_payload_nubox(
    pedido,
):
    cliente = (
        _crear_cliente_nubox(
            pedido
        )
    )

    (
        detalles,
        total_productos,
    ) = (
        _crear_detalles_nubox(
            pedido
        )
    )

    despacho = (
        _agregar_despacho_nubox(
            pedido=pedido,
            detalles=detalles,
        )
    )

    total_esperado = (
        total_productos
        + despacho
    )

    total_pedido = _decimal(
        getattr(
            pedido,
            "total",
            0,
        )
    )

    if (
        _redondear_peso(
            total_esperado
        )
        !=
        _redondear_peso(
            total_pedido
        )
    ):
        raise NuboxError(
            (
                "El total que se enviará "
                "a Nubox no coincide con "
                "el pedido. "
                f"Productos+despacho="
                f"{total_esperado}, "
                f"Pedido={total_pedido}, "
                f"Número={pedido.numero}."
            )
        )

    fecha_pago = (
        timezone.localdate()
        .isoformat()
    )

    documento = {
        "sequence": 1,

        "type": {
            "legalCode": (
                str(
                    getattr(
                        settings,
                        "NUBOX_BOLETA_LEGAL_CODE",
                        NUBOX_BOLETA_AFECTA,
                    )
                )
            )
        },

        "client": cliente,

        "saleType": {
            "id": (
                int(
                    getattr(
                        settings,
                        "NUBOX_SALE_TYPE_ID",
                        NUBOX_TIPO_VENTA_NORMAL,
                    )
                )
            )
        },

        "paymentForm": {
            "id": (
                int(
                    getattr(
                        settings,
                        "NUBOX_PAYMENT_FORM_ID",
                        NUBOX_PAGO_CONTADO,
                    )
                )
            )
        },

        "paymentDate": (
            fecha_pago
        ),

        "comment": (
            f"Pedido Audex "
            f"{pedido.numero}"
        )[:500],

        "details": detalles,

        "references": [],
    }

    # La API de emisión recibe un ARRAY
    # incluso cuando se envía una sola boleta.
    return [
        documento
    ]


# =============================================================================
# VALIDAR RESPUESTA EMISIÓN
# =============================================================================


def _procesar_respuesta_emision(
    data,
):
    if not isinstance(
        data,
        list,
    ):
        raise NuboxError(
            (
                "Nubox respondió con un "
                "formato inesperado al emitir."
            )
        )

    if not data:
        raise NuboxError(
            (
                "Nubox respondió sin "
                "documentos."
            )
        )

    resultado = data[0]

    if not isinstance(
        resultado,
        dict,
    ):
        raise NuboxError(
            (
                "Respuesta de emisión "
                "Nubox inválida."
            )
        )

    errores = (
        resultado.get(
            "errors"
        )
        or []
    )

    if errores:

        mensajes = []

        for error in errores:

            if not isinstance(
                error,
                dict,
            ):
                mensajes.append(
                    str(error)
                )
                continue

            campo = (
                error.get(
                    "field"
                )
                or ""
            )

            mensaje = (
                error.get(
                    "message"
                )
                or "Error de validación."
            )

            if campo:
                mensajes.append(
                    f"{campo}: {mensaje}"
                )

            else:
                mensajes.append(
                    mensaje
                )

        raise NuboxError(
            (
                "Nubox rechazó la boleta: "
                + " | ".join(
                    mensajes
                )
            )
        )

    document_id = (
        resultado.get(
            "id"
        )
    )

    if not document_id:
        raise NuboxError(
            (
                "Nubox aceptó la solicitud "
                "pero respondió sin ID "
                "de documento."
            )
        )

    return resultado


# =============================================================================
# EMITIR BOLETA
# =============================================================================
def emitir_boleta_nubox(
    pedido,
):
    """
    Envía la boleta a la cola de emisión
    de Nubox.

    IMPORTANTE:

    Esta función NO significa que la boleta
    ya haya sido aceptada por el SII.

    La API Nubox es asíncrona.

    Antes de emitir:

    - valida que el pedido esté pagado;
    - evita duplicados mediante document_id;
    - genera/conserva X-Idempotence-id;
    - resuelve y guarda los códigos territoriales
      de región y comuna.

    Después se debe consultar:

        GET /v1/sales/{document_id}
    """

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not (
        pedido.pagado
        and pedido.estado_pago
        == pedido.EstadoPago.APROBADO
    ):
        raise NuboxError(
            (
                "No se puede emitir una "
                "boleta para un pedido "
                "no pagado."
            )
        )

    # =========================================================================
    # IDEMPOTENCIA LOCAL
    # =========================================================================

    document_id_existente = (
        getattr(
            pedido,
            "nubox_document_id",
            None,
        )
    )

    if document_id_existente:

        logger.info(
            (
                "Pedido %s ya posee "
                "documento Nubox %s. "
                "No se volverá a emitir."
            ),
            pedido.numero,
            document_id_existente,
        )

        return {
            "id": (
                document_id_existente
            ),
            "already_created": True,
        }

    # =========================================================================
    # X-IDEMPOTENCE-ID
    # =========================================================================

    idempotence_id = (
        getattr(
            pedido,
            "nubox_idempotence_id",
            None,
        )
    )

    if not idempotence_id:

        idempotence_id = (
            str(
                uuid.uuid4()
            )
        )

        if hasattr(
            pedido,
            "nubox_idempotence_id",
        ):

            pedido.nubox_idempotence_id = (
                idempotence_id
            )

            campos_idempotencia = [
                "nubox_idempotence_id",
            ]

            if hasattr(
                pedido,
                "actualizado",
            ):
                campos_idempotencia.append(
                    "actualizado"
                )

            pedido.save(
                update_fields=(
                    campos_idempotencia
                )
            )

    else:

        idempotence_id = str(
            idempotence_id
        )

    # =========================================================================
    # CÓDIGOS TERRITORIALES NUBOX
    # =========================================================================
    #
    # Resuelve:
    #
    #     pedido.region
    #         ↓
    #     nubox_region_codigo
    #
    #     pedido.comuna
    #         ↓
    #     nubox_comuna_codigo
    #
    # Ejemplo:
    #
    # Metropolitana -> 13
    # Las Condes     -> 13114
    #
    # Los códigos quedan guardados en el Pedido
    # antes de realizar la petición a Nubox.
    # =========================================================================

    (
        codigo_region,
        codigo_comuna,
    ) = (
        _guardar_codigos_territoriales_nubox(
            pedido
        )
    )

    logger.info(
        (
            "Códigos territoriales Nubox "
            "resueltos. "
            "Pedido=%s "
            "region=%s "
            "comuna=%s"
        ),
        pedido.numero,
        codigo_region,
        codigo_comuna,
    )

    # =========================================================================
    # PAYLOAD
    # =========================================================================

    payload = (
        _crear_payload_nubox(
            pedido
        )
    )

    logger.info(
        (
            "Enviando boleta Nubox "
            "para pedido %s. "
            "Idempotence=%s"
        ),
        pedido.numero,
        idempotence_id,
    )

    # =========================================================================
    # EMITIR
    # =========================================================================

    data = _post(
        "v1/sales/issuance",
        payload,
        idempotence_id=(
            idempotence_id
        ),
    )

    # =========================================================================
    # PROCESAR RESPUESTA
    # =========================================================================

    resultado = (
        _procesar_respuesta_emision(
            data
        )
    )

    document_id = (
        resultado.get(
            "id"
        )
    )

    if not document_id:
        raise NuboxError(
            (
                "Nubox respondió sin "
                "identificador de documento."
            )
        )

    # =========================================================================
    # GUARDAR DOCUMENTO NUBOX
    # =========================================================================

    campos_update = []

    if hasattr(
        pedido,
        "nubox_document_id",
    ):

        pedido.nubox_document_id = (
            str(
                document_id
            )
        )

        campos_update.append(
            "nubox_document_id"
        )

    if hasattr(
        pedido,
        "nubox_estado",
    ):

        pedido.nubox_estado = (
            "PENDIENTE"
        )

        campos_update.append(
            "nubox_estado"
        )

    if hasattr(
        pedido,
        "nubox_emitido",
    ):

        # Nubox recibió la solicitud,
        # pero todavía no significa
        # que el DTE esté emitido.
        pedido.nubox_emitido = False

        campos_update.append(
            "nubox_emitido"
        )

    if hasattr(
        pedido,
        "nubox_ultimo_error",
    ):

        # Si anteriormente hubo un error,
        # se elimina después de que Nubox
        # recibe correctamente el documento.
        pedido.nubox_ultimo_error = ""

        campos_update.append(
            "nubox_ultimo_error"
        )

    if campos_update:

        if hasattr(
            pedido,
            "actualizado",
        ):
            campos_update.append(
                "actualizado"
            )

        pedido.save(
            update_fields=list(
                dict.fromkeys(
                    campos_update
                )
            )
        )

    # =========================================================================
    # LOG
    # =========================================================================

    logger.info(
        (
            "Solicitud de emisión Nubox "
            "recibida correctamente. "
            "Pedido=%s "
            "documentId=%s "
            "region=%s "
            "comuna=%s."
        ),
        pedido.numero,
        document_id,
        codigo_region,
        codigo_comuna,
    )

    return resultado
# =============================================================================
# CONSULTAR DOCUMENTO
# =============================================================================


def consultar_documento_nubox(
    document_id,
):
    if not document_id:
        raise NuboxError(
            (
                "document_id es obligatorio "
                "para consultar Nubox."
            )
        )

    return _get(
        (
            f"v1/sales/"
            f"{document_id}"
        )
    )


# =============================================================================
# SINCRONIZAR ESTADO
# =============================================================================


def sincronizar_estado_nubox(
    pedido,
):
    document_id = (
        getattr(
            pedido,
            "nubox_document_id",
            None,
        )
    )

    if not document_id:
        raise NuboxError(
            (
                "El pedido no posee "
                "nubox_document_id."
            )
        )

    data = (
        consultar_documento_nubox(
            document_id
        )
    )

    # Nubox puede devolver la estructura
    # del estado con campos adicionales.
    #
    # Dejamos extracción tolerante para
    # no romper la integración si cambia
    # la representación secundaria.

    estado = (
        data.get(
            "status"
        )
        or data.get(
            "state"
        )
        or data.get(
            "emissionStatus"
        )
        or {}
    )

    if isinstance(
        estado,
        dict,
    ):
        estado_nombre = (
            estado.get(
                "name"
            )
            or estado.get(
                "description"
            )
            or estado.get(
                "code"
            )
            or ""
        )

    else:
        estado_nombre = str(
            estado
            or ""
        )

    folio = (
        data.get(
            "number"
        )
        or data.get(
            "folio"
        )
        or ""
    )

    campos_update = []

    if hasattr(
        pedido,
        "nubox_folio",
    ) and folio:

        pedido.nubox_folio = (
            str(
                folio
            )
        )

        campos_update.append(
            "nubox_folio"
        )

    if hasattr(
        pedido,
        "nubox_estado",
    ):

        pedido.nubox_estado = (
            estado_nombre[:100]
            or "PROCESANDO"
        )

        campos_update.append(
            "nubox_estado"
        )

    estado_normalizado = (
        _normalizar_texto(
            estado_nombre
        )
    )

    emitido = (
        estado_normalizado
        in {
            "emitido",
            "aceptado",
            "accepted",
            "issued",
        }
    )

    if (
        emitido
        and hasattr(
            pedido,
            "nubox_emitido",
        )
    ):
        pedido.nubox_emitido = True

        campos_update.append(
            "nubox_emitido"
        )

        if hasattr(
            pedido,
            "nubox_emitido_en",
        ):
            if not (
                pedido.nubox_emitido_en
            ):
                pedido.nubox_emitido_en = (
                    timezone.now()
                )

                campos_update.append(
                    "nubox_emitido_en"
                )

    if campos_update:

        campos_update.append(
            "actualizado"
        )

        pedido.save(
            update_fields=list(
                dict.fromkeys(
                    campos_update
                )
            )
        )

    return data


# =============================================================================
# PDF
# =============================================================================


def obtener_pdf_nubox(
    document_id,
    *,
    formato="A4",
):
    """
    Retorna los bytes del PDF.

    formato:
        A4
        80MM
    """

    formato = (
        str(
            formato
            or "A4"
        )
        .strip()
        .upper()
    )

    templates = {
        "A4": "TEMPLATE_A4",
        "80MM": "TEMPLATE_80MM",
    }

    template = (
        templates.get(
            formato
        )
    )

    if not template:
        raise NuboxError(
            (
                "Formato PDF Nubox "
                "no válido."
            )
        )

    return _get(
        (
            f"v1/sales/"
            f"{document_id}/pdf"
        ),
        params={
            "template": template,
        },
        accept="application/pdf",
        devolver_bytes=True,
    )


# =============================================================================
# XML
# =============================================================================


def obtener_xml_nubox(
    document_id,
):
    """
    Retorna los bytes del XML tributario.
    """

    return _get(
        (
            f"v1/sales/"
            f"{document_id}/xml"
        ),
        accept="application/xml",
        devolver_bytes=True,
    )


# =============================================================================
# PUNTO DE ENTRADA POR PEDIDO
# =============================================================================


def emitir_boleta_nubox_por_pedido(
    *,
    pedido_id,
):
    """
    Carga nuevamente el Pedido desde
    base de datos después del commit.

    Este es el punto de entrada utilizado
    desde core/services/pagos.py para emitir
    la boleta Nubox después del commit.
    """

    from core.models import Pedido

    # =========================================================================
    # OBTENER PEDIDO
    # =========================================================================

    try:
        pedido = (
            Pedido.objects
            .select_related(
                "usuario",
            )
            .prefetch_related(
                "items__producto",
            )
            .get(
                pk=pedido_id,
            )
        )

    except Pedido.DoesNotExist:

        logger.error(
            (
                "No existe pedido_id=%s "
                "para emitir Nubox."
            ),
            pedido_id,
        )

        return None

    # =========================================================================
    # VALIDAR PAGO
    # =========================================================================

    if not pedido.pago_aprobado:

        logger.warning(
            (
                "Pedido %s no tiene "
                "pago aprobado. "
                "No se emitirá Nubox."
            ),
            pedido.numero,
        )

        return None

    # =========================================================================
    # YA ENVIADO
    # =========================================================================

    document_id = (
        getattr(
            pedido,
            "nubox_document_id",
            None,
        )
    )

    if document_id:

        logger.info(
            (
                "Pedido %s ya posee "
                "documento Nubox %s."
            ),
            pedido.numero,
            document_id,
        )

        return {
            "id": document_id,
            "already_created": True,
        }

    # =========================================================================
    # EMITIR
    # =========================================================================

    try:

        return emitir_boleta_nubox(
            pedido
        )

    except NuboxError as error:

        logger.exception(
            (
                "Error Nubox en pedido "
                "%s: %s"
            ),
            pedido.numero,
            error,
        )

        if hasattr(
            pedido,
            "nubox_ultimo_error",
        ):
            Pedido.objects.filter(
                pk=pedido.pk
            ).update(
                nubox_ultimo_error=(
                    str(error)[:2000]
                )
            )

        return None

    except Exception as error:

        logger.exception(
            (
                "Error inesperado Nubox "
                "en pedido %s: %s"
            ),
            pedido.numero,
            error,
        )

        if hasattr(
            pedido,
            "nubox_ultimo_error",
        ):
            Pedido.objects.filter(
                pk=pedido.pk
            ).update(
                nubox_ultimo_error=(
                    str(error)[:2000]
                )
            )

        return None

