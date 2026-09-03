import re

from django import forms
from django.core.exceptions import ValidationError
from .models import *
from django.forms import inlineformset_factory
from core.services.flujo_pedidos import (
    estados_permitidos,
)

from .models import (
    Categoria,
    Pedido,
    Producto,
)

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto

        fields = [
            "categoria",
            "nombre",
            "descripcion_corta",
            "descripcion",
            "imagen",
            "imagen_url",
            "precio",
            "precio_oferta",
            "stock",
            "caracteristica_1",
            "caracteristica_2",
            "caracteristica_3",
            "autonomia_horas",
            "bluetooth",
            "resistencia_agua",
            "cancelacion_ruido",
            "destacado",
            "activo",
        ]

        widgets = {
            "categoria": forms.Select(
                attrs={"class": "campo-formulario"}
            ),
            "nombre": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: EarFun Air Pro 4",
                }
            ),
            "descripcion_corta": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": (
                        "Resumen breve para la tarjeta del producto"
                    ),
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "campo-formulario",
                    "rows": 5,
                    "placeholder": (
                        "Descripción completa del producto"
                    ),
                }
            ),
            "imagen": forms.ClearableFileInput(
                attrs={
                    "class": "campo-formulario",
                    "accept": "image/*",
                }
            ),
            "imagen_url": forms.URLInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "https://...",
                }
            ),
            "precio": forms.NumberInput(
                attrs={
                    "class": "campo-formulario",
                    "min": 1,
                    "step": 1,
                }
            ),
            "precio_oferta": forms.NumberInput(
                attrs={
                    "class": "campo-formulario",
                    "min": 1,
                    "step": 1,
                    "placeholder": "Opcional",
                }
            ),
            "stock": forms.NumberInput(
                attrs={
                    "class": "campo-formulario",
                    "min": 0,
                }
            ),
            "caracteristica_1": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: Cancelación activa de ruido",
                }
            ),
            "caracteristica_2": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: Audio Hi-Res",
                }
            ),
            "caracteristica_3": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: Hasta 52 horas",
                }
            ),
            "autonomia_horas": forms.NumberInput(
                attrs={
                    "class": "campo-formulario",
                    "min": 0,
                }
            ),
            "bluetooth": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: 5.4",
                }
            ),
            "resistencia_agua": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: IPX5",
                }
            ),
        }


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria

        fields = [
            "nombre",
            "descripcion",
            "orden",
            "activa",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "campo-formulario",
                    "placeholder": "Ejemplo: Inalámbricos",
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "campo-formulario",
                    "rows": 4,
                }
            ),
            "orden": forms.NumberInput(
                attrs={
                    "class": "campo-formulario",
                    "min": 0,
                }
            ),
        }

# Las claves se guardan directamente en Pedido.region.
REGIONES_CHILE = [
    ("", "Selecciona una región"),
    ('Arica y Parinacota', 'Arica y Parinacota'),
    ('Tarapacá', 'Tarapacá'),
    ('Antofagasta', 'Antofagasta'),
    ('Atacama', 'Atacama'),
    ('Coquimbo', 'Coquimbo'),
    ('Valparaíso', 'Valparaíso'),
    ('Metropolitana', 'Región Metropolitana'),
    ('O’Higgins', 'O’Higgins'),
    ('Maule', 'Maule'),
    ('Ñuble', 'Ñuble'),
    ('Biobío', 'Biobío'),
    ('La Araucanía', 'La Araucanía'),
    ('Los Ríos', 'Los Ríos'),
    ('Los Lagos', 'Los Lagos'),
    ('Aysén', 'Aysén'),
    ('Magallanes', 'Magallanes'),
]


# 346 comunas agrupadas por las 16 regiones de Chile.
COMUNAS_POR_REGION = {
    'Arica y Parinacota': [
        'Arica',
        'Camarones',
        'General Lagos',
        'Putre',
    ],
    'Tarapacá': [
        'Alto Hospicio',
        'Camiña',
        'Colchane',
        'Huara',
        'Iquique',
        'Pica',
        'Pozo Almonte',
    ],
    'Antofagasta': [
        'Antofagasta',
        'Calama',
        'María Elena',
        'Mejillones',
        'Ollagüe',
        'San Pedro de Atacama',
        'Sierra Gorda',
        'Taltal',
        'Tocopilla',
    ],
    'Atacama': [
        'Alto del Carmen',
        'Caldera',
        'Chañaral',
        'Copiapó',
        'Diego de Almagro',
        'Freirina',
        'Huasco',
        'Tierra Amarilla',
        'Vallenar',
    ],
    'Coquimbo': [
        'Andacollo',
        'Canela',
        'Combarbalá',
        'Coquimbo',
        'Illapel',
        'La Higuera',
        'La Serena',
        'Los Vilos',
        'Monte Patria',
        'Ovalle',
        'Paihuano',
        'Punitaqui',
        'Río Hurtado',
        'Salamanca',
        'Vicuña',
    ],
    'Valparaíso': [
        'Algarrobo',
        'Cabildo',
        'Calle Larga',
        'Cartagena',
        'Casablanca',
        'Catemu',
        'Concón',
        'El Quisco',
        'El Tabo',
        'Hijuelas',
        'Isla de Pascua',
        'Juan Fernández',
        'La Calera',
        'La Cruz',
        'La Ligua',
        'Limache',
        'Llaillay',
        'Los Andes',
        'Nogales',
        'Olmué',
        'Panquehue',
        'Papudo',
        'Petorca',
        'Puchuncaví',
        'Putaendo',
        'Quillota',
        'Quilpué',
        'Quintero',
        'Rinconada',
        'San Antonio',
        'San Esteban',
        'San Felipe',
        'Santa María',
        'Santo Domingo',
        'Valparaíso',
        'Villa Alemana',
        'Viña del Mar',
        'Zapallar',
    ],
    'Metropolitana': [
        'Alhué',
        'Buin',
        'Calera de Tango',
        'Cerrillos',
        'Cerro Navia',
        'Colina',
        'Conchalí',
        'Curacaví',
        'El Bosque',
        'El Monte',
        'Estación Central',
        'Huechuraba',
        'Independencia',
        'Isla de Maipo',
        'La Cisterna',
        'La Florida',
        'La Granja',
        'Lampa',
        'La Pintana',
        'La Reina',
        'Las Condes',
        'Lo Barnechea',
        'Lo Espejo',
        'Lo Prado',
        'Macul',
        'Maipú',
        'María Pinto',
        'Melipilla',
        'Ñuñoa',
        'Padre Hurtado',
        'Paine',
        'Pedro Aguirre Cerda',
        'Peñaflor',
        'Peñalolén',
        'Pirque',
        'Providencia',
        'Pudahuel',
        'Puente Alto',
        'Quilicura',
        'Quinta Normal',
        'Recoleta',
        'Renca',
        'San Bernardo',
        'San Joaquín',
        'San José de Maipo',
        'San Miguel',
        'San Pedro',
        'San Ramón',
        'Santiago',
        'Talagante',
        'Tiltil',
        'Vitacura',
    ],
    'O’Higgins': [
        'Chépica',
        'Chimbarongo',
        'Codegua',
        'Coinco',
        'Coltauco',
        'Doñihue',
        'Graneros',
        'La Estrella',
        'Las Cabras',
        'Litueche',
        'Lolol',
        'Machalí',
        'Malloa',
        'Marchihue',
        'Mostazal',
        'Nancagua',
        'Navidad',
        'Olivar',
        'Palmilla',
        'Paredones',
        'Peralillo',
        'Peumo',
        'Pichidegua',
        'Pichilemu',
        'Placilla',
        'Pumanque',
        'Quinta de Tilcoco',
        'Rancagua',
        'Rengo',
        'Requínoa',
        'San Fernando',
        'Santa Cruz',
        'San Vicente',
    ],
    'Maule': [
        'Cauquenes',
        'Chanco',
        'Colbún',
        'Constitución',
        'Curepto',
        'Curicó',
        'Empedrado',
        'Hualañé',
        'Licantén',
        'Linares',
        'Longaví',
        'Maule',
        'Molina',
        'Parral',
        'Pelarco',
        'Pelluhue',
        'Pencahue',
        'Rauco',
        'Retiro',
        'Río Claro',
        'Romeral',
        'Sagrada Familia',
        'San Clemente',
        'San Javier',
        'San Rafael',
        'Talca',
        'Teno',
        'Vichuquén',
        'Villa Alegre',
        'Yerbas Buenas',
    ],
    'Ñuble': [
        'Bulnes',
        'Chillán',
        'Chillán Viejo',
        'Cobquecura',
        'Coelemu',
        'Coihueco',
        'El Carmen',
        'Ninhue',
        'Ñiquén',
        'Pemuco',
        'Pinto',
        'Portezuelo',
        'Quillón',
        'Quirihue',
        'Ránquil',
        'San Carlos',
        'San Fabián',
        'San Ignacio',
        'San Nicolás',
        'Treguaco',
        'Yungay',
    ],
    'Biobío': [
        'Alto Biobío',
        'Antuco',
        'Arauco',
        'Cabrero',
        'Cañete',
        'Chiguayante',
        'Concepción',
        'Contulmo',
        'Coronel',
        'Curanilahue',
        'Florida',
        'Hualpén',
        'Hualqui',
        'Laja',
        'Lebu',
        'Los Álamos',
        'Los Ángeles',
        'Lota',
        'Mulchén',
        'Nacimiento',
        'Negrete',
        'Penco',
        'Quilaco',
        'Quilleco',
        'San Pedro de la Paz',
        'San Rosendo',
        'Santa Bárbara',
        'Santa Juana',
        'Talcahuano',
        'Tirúa',
        'Tomé',
        'Tucapel',
        'Yumbel',
    ],
    'La Araucanía': [
        'Angol',
        'Carahue',
        'Cholchol',
        'Collipulli',
        'Cunco',
        'Curacautín',
        'Curarrehue',
        'Ercilla',
        'Freire',
        'Galvarino',
        'Gorbea',
        'Lautaro',
        'Loncoche',
        'Lonquimay',
        'Los Sauces',
        'Lumaco',
        'Melipeuco',
        'Nueva Imperial',
        'Padre Las Casas',
        'Perquenco',
        'Pitrufquén',
        'Pucón',
        'Purén',
        'Renaico',
        'Saavedra',
        'Temuco',
        'Teodoro Schmidt',
        'Toltén',
        'Traiguén',
        'Victoria',
        'Vilcún',
        'Villarrica',
    ],
    'Los Ríos': [
        'Corral',
        'Futrono',
        'Lago Ranco',
        'Lanco',
        'La Unión',
        'Los Lagos',
        'Máfil',
        'Mariquina',
        'Paillaco',
        'Panguipulli',
        'Río Bueno',
        'Valdivia',
    ],
    'Los Lagos': [
        'Ancud',
        'Calbuco',
        'Castro',
        'Chaitén',
        'Chonchi',
        'Cochamó',
        'Curaco de Vélez',
        'Dalcahue',
        'Fresia',
        'Frutillar',
        'Futaleufú',
        'Hualaihué',
        'Llanquihue',
        'Los Muermos',
        'Maullín',
        'Osorno',
        'Palena',
        'Puerto Montt',
        'Puerto Octay',
        'Puerto Varas',
        'Puqueldón',
        'Purranque',
        'Puyehue',
        'Queilén',
        'Quellón',
        'Quemchi',
        'Quinchao',
        'Río Negro',
        'San Juan de la Costa',
        'San Pablo',
    ],
    'Aysén': [
        'Aysén',
        'Chile Chico',
        'Cisnes',
        'Cochrane',
        'Coyhaique',
        'Guaitecas',
        'Lago Verde',
        "O'Higgins",
        'Río Ibáñez',
        'Tortel',
    ],
    'Magallanes': [
        'Antártica',
        'Cabo de Hornos',
        'Laguna Blanca',
        'Natales',
        'Porvenir',
        'Primavera',
        'Punta Arenas',
        'Río Verde',
        'San Gregorio',
        'Timaukel',
        'Torres del Paine',
    ],
}

def limpiar_rut(
    valor,
):
    """
    Elimina puntos, guion, espacios y cualquier carácter
    distinto de números o K.

    Ejemplo:
        12.345.678-5 -> 123456785
    """

    return re.sub(
        r"[^0-9Kk]",
        "",
        str(valor or ""),
    ).upper()


def formatear_rut(
    valor,
):
    """
    Formatea un RUT limpio.

    Ejemplo:
        123456785 -> 12.345.678-5
    """

    rut_limpio = limpiar_rut(
        valor
    )

    if len(rut_limpio) < 2:
        return rut_limpio

    cuerpo = rut_limpio[:-1]

    digito_verificador = (
        rut_limpio[-1]
    )

    grupos = []

    while cuerpo:
        grupos.insert(
            0,
            cuerpo[-3:],
        )

        cuerpo = cuerpo[:-3]

    cuerpo_formateado = ".".join(
        grupos
    )

    return (
        f"{cuerpo_formateado}-"
        f"{digito_verificador}"
    )


def calcular_digito_verificador_rut(
    cuerpo,
):
    suma = 0
    multiplicador = 2

    for caracter in reversed(
        cuerpo
    ):
        suma += (
            int(caracter)
            * multiplicador
        )

        multiplicador += 1

        if multiplicador > 7:
            multiplicador = 2

    resultado = (
        11 - (suma % 11)
    )

    if resultado == 11:
        return "0"

    if resultado == 10:
        return "K"

    return str(
        resultado
    )


def validar_rut_chileno(
    valor,
):
    """
    Acepta RUT de 8 o 9 caracteres sin formato:

    - 7 u 8 números para el cuerpo.
    - Un dígito verificador numérico o K.
    """

    rut_limpio = limpiar_rut(
        valor
    )

    if not re.fullmatch(
        r"\d{7,8}[0-9K]",
        rut_limpio,
    ):
        raise ValidationError(
            (
                "Ingresa un RUT válido de "
                "8 o 9 caracteres."
            ),
            code="rut_formato_invalido",
        )

    cuerpo = rut_limpio[:-1]

    digito_ingresado = (
        rut_limpio[-1]
    )

    digito_correcto = (
        calcular_digito_verificador_rut(
            cuerpo
        )
    )

    if (
        digito_ingresado
        != digito_correcto
    ):
        raise ValidationError(
            (
                "El dígito verificador "
                "del RUT no es válido."
            ),
            code="rut_dv_invalido",
        )




class CheckoutForm(
    forms.ModelForm
):
    """
    Formulario principal del checkout.

    Conserva los campos del Pedido y agrega:
    - RUT validado y formateado.
    - Región y comuna como desplegables.
    - Código de descuento.
    - Aceptación de términos.
    """

    rut = forms.CharField(
        label="RUT",
        required=True,
        min_length=8,
        max_length=12,
        validators=[
            validar_rut_chileno,
        ],
        widget=forms.TextInput(
            attrs={
                "id": "id_rut",
                "class": "checkout-control",
                "placeholder": (
                    "Ejemplo: 12.345.678-5"
                ),
                "maxlength": "12",
                "autocomplete": "off",
                "autocapitalize": (
                    "characters"
                ),
                "spellcheck": "false",
                "inputmode": "text",
            }
        ),
    )

    region = forms.ChoiceField(
        label="Región",
        required=True,
        choices=REGIONES_CHILE,
        help_text=(
            "Selecciona la región "
            "donde se realizará el despacho."
        ),
        widget=forms.Select(
            attrs={
                "id": "id_region",
                "class": (
                    "checkout-control "
                    "checkout-select"
                ),
                "autocomplete": (
                    "address-level1"
                ),
                "data-region-select": "true",
            }
        ),
    )

    comuna = forms.ChoiceField(
        label="Comuna",
        required=True,
        choices=[
            (
                "",
                (
                    "Selecciona primero "
                    "una región"
                ),
            ),
        ],
        help_text=(
            "Selecciona una región "
            "para cargar sus comunas."
        ),
        widget=forms.Select(
            attrs={
                "id": "id_comuna",
                "class": (
                    "checkout-control "
                    "checkout-select"
                ),
                "autocomplete": (
                    "address-level2"
                ),
                "data-comuna-select": "true",
            }
        ),
    )

    codigo_descuento = (
        forms.CharField(
            label="Código de descuento",
            required=False,
            max_length=64,
            help_text=(
                "Solo se permite un código "
                "de descuento por pedido."
            ),
            widget=forms.TextInput(
                attrs={
                    "id": (
                        "id_codigo_descuento"
                    ),
                    "class": (
                        "checkout-cupon__input"
                    ),
                    "placeholder": (
                        "Ingresa tu código"
                    ),
                    "maxlength": "64",
                    "autocomplete": "off",
                    "autocapitalize": (
                        "characters"
                    ),
                    "spellcheck": "false",
                }
            ),
        )
    )

    aceptar_terminos = (
        forms.BooleanField(
            label=(
                "Acepto los términos, "
                "condiciones y política "
                "de privacidad."
            ),
            required=True,
        )
    )

    class Meta:
        model = Pedido

        fields = [
            "nombre",
            "apellido",
            "rut",
            "telefono",
            "email",
            "region",
            "comuna",
            "direccion",
            "numero_direccion",
            "departamento",
            "referencia",
            "metodo_pago",
            "notas",
        ]

        widgets = {

            "nombre": forms.TextInput(
                attrs={
                    "id": "id_nombre",
                    "class": (
                        "checkout-control"
                    ),
                    "placeholder": (
                        "Ejemplo: Juan"
                    ),
                    "autocomplete": (
                        "given-name"
                    ),
                }
            ),

            "apellido": forms.TextInput(
                attrs={
                    "id": "id_apellido",
                    "class": (
                        "checkout-control"
                    ),
                    "placeholder": (
                        "Ejemplo: Pérez"
                    ),
                    "autocomplete": (
                        "family-name"
                    ),
                }
            ),

            "telefono": forms.TextInput(
                attrs={
                    "id": "id_telefono",
                    "class": (
                        "checkout-control"
                    ),
                    "placeholder": (
                        "Ejemplo: +56 9 1234 5678"
                    ),
                    "autocomplete": "tel",
                    "inputmode": "tel",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "id": "id_email",
                    "class": (
                        "checkout-control"
                    ),
                    "placeholder": (
                        "Ejemplo: cliente@correo.cl"
                    ),
                    "autocomplete": "email",
                }
            ),

            "direccion": forms.TextInput(
                attrs={
                    "id": "id_direccion",
                    "class": (
                        "checkout-control"
                    ),
                    "placeholder": (
                        "Ejemplo: Avenida Providencia"
                    ),
                    "autocomplete": (
                        "address-line1"
                    ),
                }
            ),

            "numero_direccion": (
                forms.TextInput(
                    attrs={
                        "id": (
                            "id_numero_direccion"
                        ),
                        "class": (
                            "checkout-control"
                        ),
                        "placeholder": (
                            "Ejemplo: 1234"
                        ),
                        "autocomplete": (
                            "address-line2"
                        ),
                    }
                )
            ),

            "departamento": (
                forms.TextInput(
                    attrs={
                        "id": (
                            "id_departamento"
                        ),
                        "class": (
                            "checkout-control"
                        ),
                        "placeholder": (
                            "Ejemplo: Depto. 201 "
                            "o casa B"
                        ),
                        "autocomplete": (
                            "address-line3"
                        ),
                    }
                )
            ),

            "referencia": forms.TextInput(
                attrs={
                    "id": "id_referencia",
                    "class": (
                        "checkout-control"
                    ),
                    "placeholder": (
                        "Ejemplo: Portón azul, "
                        "dejar en conserjería"
                    ),
                }
            ),

            "metodo_pago": (
                forms.RadioSelect()
            ),

            "notas": forms.Textarea(
                attrs={
                    "id": "id_notas",
                    "class": (
                        "checkout-control"
                    ),
                    "rows": 4,
                    "placeholder": (
                        "Ejemplo: Llamar antes "
                        "de entregar"
                    ),
                }
            ),
        }


    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        # ---------------------------------------------------------------------
        # AYUDAS DE LOS CAMPOS
        # ---------------------------------------------------------------------
        #
        # Los ejemplos visuales se muestran únicamente
        # mediante placeholder dentro de los inputs.
        #
        # Aquí dejamos solo textos de ayuda que aportan
        # información adicional al usuario.
        # ---------------------------------------------------------------------

        textos_ayuda = {

            "region": (
                "Selecciona la región "
                "donde se realizará el despacho."
            ),

            "comuna": (
                "Selecciona una región "
                "para cargar sus comunas."
            ),

            "codigo_descuento": (
                "Solo se permite un código "
                "de descuento por pedido."
            ),
        }


        for (
            nombre_campo,
            texto,
        ) in textos_ayuda.items():

            if (
                nombre_campo
                in self.fields
            ):

                self.fields[
                    nombre_campo
                ].help_text = texto


        # ---------------------------------------------------------------------
        # ELIMINAR HELP TEXT DUPLICADO
        # ---------------------------------------------------------------------
        #
        # Estos campos ya muestran su ejemplo mediante
        # placeholder dentro del input.
        # ---------------------------------------------------------------------

        campos_sin_ayuda = (
            "nombre",
            "apellido",
            "rut",
            "telefono",
            "email",
            "direccion",
            "numero_direccion",
            "departamento",
            "referencia",
            "notas",
        )


        for nombre_campo in campos_sin_ayuda:

            if (
                nombre_campo
                in self.fields
            ):

                self.fields[
                    nombre_campo
                ].help_text = ""


        # ---------------------------------------------------------------------
        # REGIÓN Y COMUNA SELECCIONADAS
        # ---------------------------------------------------------------------

        if self.is_bound:

            region_seleccionada = (
                self.data.get(
                    self.add_prefix(
                        "region"
                    ),
                    "",
                )
                or ""
            ).strip()

            comuna_seleccionada = (
                self.data.get(
                    self.add_prefix(
                        "comuna"
                    ),
                    "",
                )
                or ""
            ).strip()

        else:

            region_seleccionada = (
                self.initial.get(
                    "region"
                )
                or getattr(
                    self.instance,
                    "region",
                    "",
                )
                or ""
            ).strip()

            comuna_seleccionada = (
                self.initial.get(
                    "comuna"
                )
                or getattr(
                    self.instance,
                    "comuna",
                    "",
                )
                or ""
            ).strip()


        comunas_region = (
            COMUNAS_POR_REGION.get(
                region_seleccionada,
                [],
            )
        )


        if comunas_region:

            self.fields[
                "comuna"
            ].choices = [
                (
                    "",
                    (
                        "Selecciona "
                        "una comuna"
                    ),
                ),
                *[
                    (
                        comuna,
                        comuna,
                    )
                    for comuna
                    in comunas_region
                ],
            ]


            self.fields[
                "comuna"
            ].widget.attrs.pop(
                "disabled",
                None,
            )

        else:

            self.fields[
                "comuna"
            ].choices = [
                (
                    "",
                    (
                        "Selecciona primero "
                        "una región"
                    ),
                ),
            ]


            self.fields[
                "comuna"
            ].widget.attrs[
                "disabled"
            ] = "disabled"


        if comuna_seleccionada:

            self.initial[
                "comuna"
            ] = comuna_seleccionada


    def clean_rut(
        self,
    ):

        rut = (
            self.cleaned_data.get(
                "rut",
                "",
            )
            or ""
        )


        validar_rut_chileno(
            rut
        )


        return formatear_rut(
            rut
        )


    def clean_region(
        self,
    ):

        region = (
            self.cleaned_data.get(
                "region",
                "",
            )
            or ""
        ).strip()


        if (
            region
            not in COMUNAS_POR_REGION
        ):

            raise forms.ValidationError(
                (
                    "Selecciona una "
                    "región válida."
                )
            )


        return region


    def clean_comuna(
        self,
    ):

        comuna = (
            self.cleaned_data.get(
                "comuna",
                "",
            )
            or ""
        ).strip()


        if not comuna:

            raise forms.ValidationError(
                "Selecciona una comuna."
            )


        return comuna


    def clean_codigo_descuento(
        self,
    ):

        codigo = (
            self.cleaned_data.get(
                "codigo_descuento",
                "",
            )
            or ""
        ).strip().upper()


        if (
            codigo
            and not re.fullmatch(
                r"[A-Z0-9_-]+",
                codigo,
            )
        ):

            raise forms.ValidationError(
                (
                    "El código solo puede "
                    "contener letras, números, "
                    "guiones y guiones bajos."
                )
            )


        return codigo


    def clean(
        self,
    ):

        cleaned_data = (
            super().clean()
        )


        region = cleaned_data.get(
            "region"
        )


        comuna = cleaned_data.get(
            "comuna"
        )


        if (
            region
            and comuna
            and comuna
            not in COMUNAS_POR_REGION.get(
                region,
                [],
            )
        ):

            self.add_error(
                "comuna",
                (
                    "La comuna seleccionada "
                    "no pertenece a la "
                    "región indicada."
                ),
            )


        return cleaned_data







class BuscarPedidoForm(forms.Form):

    numero = forms.CharField(
        label="Número de pedido",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ejemplo: AUD-575FCB4D",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )

    rut = forms.CharField(
        label="RUT utilizado en la compra",
        max_length=12,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ejemplo: 12.345.678-9",
                "autocomplete": "off",
                "spellcheck": "false",
                "inputmode": "text",
                "maxlength": "12",
                "class": "js-rut",
            }
        ),
    )

    def clean_numero(self):

        numero = (
            self.cleaned_data["numero"]
            .strip()
            .upper()
        )

        if not numero.startswith("AUD-"):
            raise forms.ValidationError(
                "Ingresa un número de pedido válido."
            )

        return numero

    def clean_rut(self):

        rut = (
            self.cleaned_data["rut"]
            .strip()
            .upper()
            .replace(".", "")
            .replace(" ", "")
        )

        if "-" not in rut:
            raise forms.ValidationError(
                "Ingresa un RUT válido."
            )

        cuerpo, dv = rut.rsplit(
            "-",
            1,
        )

        # =========================================================
        # ESTRUCTURA
        # =========================================================

        if not cuerpo.isdigit():
            raise forms.ValidationError(
                "Ingresa un RUT válido."
            )

        # RUT chileno: cuerpo máximo de 8 dígitos
        if len(cuerpo) > 8:
            raise forms.ValidationError(
                "El RUT ingresado tiene demasiados dígitos."
            )

        if not dv or len(dv) != 1:
            raise forms.ValidationError(
                "Ingresa un RUT válido."
            )

        if not (
            dv.isdigit()
            or dv == "K"
        ):
            raise forms.ValidationError(
                "Ingresa un RUT válido."
            )

        # =========================================================
        # VALIDAR DÍGITO VERIFICADOR
        # =========================================================

        suma = 0
        multiplicador = 2

        for digito in reversed(cuerpo):

            suma += (
                int(digito)
                * multiplicador
            )

            multiplicador += 1

            if multiplicador > 7:
                multiplicador = 2

        resto = (
            11
            - (
                suma % 11
            )
        )

        if resto == 11:
            dv_correcto = "0"

        elif resto == 10:
            dv_correcto = "K"

        else:
            dv_correcto = str(
                resto
            )

        if dv != dv_correcto:
            raise forms.ValidationError(
                "El RUT ingresado no es válido."
            )

        # =========================================================
        # DEVOLVER NORMALIZADO
        # =========================================================

        return f"{cuerpo}-{dv}"
    
class ActualizarEstadoPedidoForm(forms.Form):
    nuevo_estado = forms.ChoiceField(
        label="Nuevo estado",
        choices=(),
    )

    comentario = forms.CharField(
        label="Comentario interno",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Ejemplo: pedido embalado "
                    "y listo para retiro."
                ),
            }
        ),
    )

    def __init__(
        self,
        *args,
        pedido: Pedido,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        etiquetas = dict(Pedido.ESTADOS)

        permitidos = estados_permitidos(
            pedido
        )

        self.fields[
            "nuevo_estado"
        ].choices = [
            (
                estado,
                etiquetas.get(estado, estado),
            )
            for estado in permitidos
        ]





class ProductoImagenForm(forms.ModelForm):
    class Meta:
        model = ProductoImagen

        fields = [
            "imagen",
            "texto_alt",
            "orden",
        ]


ProductoImagenFormSet = inlineformset_factory(
    Producto,
    ProductoImagen,
    form=ProductoImagenForm,
    extra=4,
    can_delete=True,
)