# core/forms_descuentos.py

from decimal import Decimal

from django import forms

from core.models import (
    CodigoDescuento,
    MetaFidelidad,
)


# ============================================================================
# UTILIDADES
# ============================================================================


def _normalizar_texto_codigo(valor):
    return (
        str(valor or "")
        .strip()
        .upper()
    )


# ============================================================================
# BASE PARA CÓDIGOS GENERALES
# ============================================================================


class CodigoGeneralBaseForm(forms.ModelForm):
    modalidad_codigo = None
    prefijo_html = "general"

    class Meta:
        model = CodigoDescuento

        fields = [
            "nombre",
            "codigo",
            "descripcion",
            "activo",
            "monto_minimo",
            "fecha_inicio",
            "fecha_fin",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ejemplo: Campaña fin de semana"
                    ),
                    "autocomplete": "off",
                }
            ),

            "codigo": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ejemplo: FINDE15"
                    ),
                    "autocomplete": "off",
                    "spellcheck": "false",
                }
            ),

            "descripcion": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Descripción visible "
                        "para el cliente"
                    ),
                    "autocomplete": "off",
                }
            ),

            "activo": forms.CheckboxInput(),

            "monto_minimo": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "1",
                    "inputmode": "numeric",
                    "placeholder": "0",
                }
            ),

            "fecha_inicio": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),

            "fecha_fin": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
        }

        labels = {
            "nombre": (
                "Nombre de la campaña"
            ),

            "codigo": (
                "Código del cupón"
            ),

            "descripcion": (
                "Descripción"
            ),

            "activo": (
                "Código activo"
            ),

            "monto_minimo": (
                "Compra mínima"
            ),

            "fecha_inicio": (
                "Fecha de inicio"
            ),

            "fecha_fin": (
                "Fecha de término"
            ),
        }

        help_texts = {
            "monto_minimo": (
                "Subtotal mínimo necesario "
                "para utilizar el código."
            ),

            "fecha_inicio": (
                "Déjala vacía para activar "
                "el código inmediatamente."
            ),

            "fecha_fin": (
                "Déjala vacía si el código "
                "no tendrá vencimiento."
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

        if self.modalidad_codigo is None:
            raise ValueError(
                (
                    "El formulario debe definir "
                    "modalidad_codigo."
                )
            )

        self.auto_id = (
            f"id_{self.prefijo_html}_%s"
        )

        self.instance.tipo = (
            CodigoDescuento
            .Tipo
            .GENERAL
        )

        self.instance.modalidad = (
            self.modalidad_codigo
        )

        self.fields[
            "fecha_inicio"
        ].required = False

        self.fields[
            "fecha_fin"
        ].required = False

        self.fields[
            "fecha_inicio"
        ].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        self.fields[
            "fecha_fin"
        ].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        if (
            not self.is_bound
            and not self.instance.pk
        ):
            self.fields[
                "activo"
            ].initial = True

            self.fields[
                "monto_minimo"
            ].initial = Decimal("0")

    def clean_codigo(self):
        return _normalizar_texto_codigo(
            self.cleaned_data.get(
                "codigo"
            )
        )

    def clean(self):
        datos = super().clean()

        fecha_inicio = datos.get(
            "fecha_inicio"
        )

        fecha_fin = datos.get(
            "fecha_fin"
        )

        monto_minimo = (
            datos.get(
                "monto_minimo"
            )
            or Decimal("0")
        )

        if (
            fecha_inicio
            and fecha_fin
            and fecha_fin <= fecha_inicio
        ):
            self.add_error(
                "fecha_fin",
                (
                    "La fecha de término debe "
                    "ser posterior a la fecha "
                    "de inicio."
                ),
            )

        if monto_minimo < Decimal("0"):
            self.add_error(
                "monto_minimo",
                (
                    "La compra mínima no puede "
                    "ser negativa."
                ),
            )

        return datos

    def save(
        self,
        commit=True,
    ):
        instancia = super().save(
            commit=False
        )

        instancia.tipo = (
            CodigoDescuento
            .Tipo
            .GENERAL
        )

        instancia.modalidad = (
            self.modalidad_codigo
        )

        instancia.usuario_exclusivo = None
        instancia.meta_fidelidad = None
        instancia.numero_meta = None
        instancia.consumido = False

        if commit:
            instancia.save()

        return instancia


# ============================================================================
# 1. DESCUENTO GENERAL PORCENTUAL
# ============================================================================


class CodigoGeneralPorcentajeForm(
    CodigoGeneralBaseForm
):
    modalidad_codigo = (
        CodigoDescuento
        .Modalidad
        .PORCENTAJE
    )

    prefijo_html = (
        "general_porcentaje"
    )

    porcentaje = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_value=Decimal("100"),
        decimal_places=2,
        max_digits=5,
        label=(
            "Porcentaje de descuento"
        ),
        help_text=(
            "Ejemplo: 15 corresponde "
            "a un 15% de descuento."
        ),
        widget=forms.NumberInput(
            attrs={
                "min": "0.01",
                "max": "100",
                "step": "0.01",
                "inputmode": "decimal",
                "placeholder": "15",
            }
        ),
    )

    monto_maximo_descuento = (
        forms.DecimalField(
            required=False,
            min_value=Decimal("1"),
            decimal_places=0,
            max_digits=12,
            label=(
                "Descuento máximo"
            ),
            help_text=(
                "Opcional. Máximo de CLP "
                "que se podrá descontar."
            ),
            widget=forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "inputmode": "numeric",
                    "placeholder": (
                        "Sin límite"
                    ),
                }
            ),
        )
    )

    class Meta(
        CodigoGeneralBaseForm.Meta
    ):
        fields = [
            "nombre",
            "codigo",
            "descripcion",
            "activo",
            "porcentaje",
            "monto_minimo",
            "monto_maximo_descuento",
            "fecha_inicio",
            "fecha_fin",
        ]

        widgets = (
            CodigoGeneralBaseForm
            .Meta
            .widgets
        )

        labels = (
            CodigoGeneralBaseForm
            .Meta
            .labels
        )

        help_texts = (
            CodigoGeneralBaseForm
            .Meta
            .help_texts
        )

    def clean(self):
        datos = super().clean()

        porcentaje = datos.get(
            "porcentaje"
        )

        monto_maximo = datos.get(
            "monto_maximo_descuento"
        )

        if (
            porcentaje is None
            or porcentaje <= Decimal("0")
        ):
            self.add_error(
                "porcentaje",
                (
                    "Debes indicar un porcentaje "
                    "mayor que cero."
                ),
            )

        if (
            monto_maximo is not None
            and monto_maximo
            <= Decimal("0")
        ):
            self.add_error(
                "monto_maximo_descuento",
                (
                    "El descuento máximo debe "
                    "ser mayor que cero."
                ),
            )

        return datos

    def save(
        self,
        commit=True,
    ):
        instancia = super().save(
            commit=False
        )

        instancia.modalidad = (
            CodigoDescuento
            .Modalidad
            .PORCENTAJE
        )

        instancia.porcentaje = (
            self.cleaned_data.get(
                "porcentaje"
            )
        )

        instancia.monto_descuento = None

        instancia.monto_maximo_descuento = (
            self.cleaned_data.get(
                "monto_maximo_descuento"
            )
        )

        if commit:
            instancia.save()

        return instancia


# ============================================================================
# 2. DESCUENTO GENERAL EN CLP
# ============================================================================


class CodigoGeneralMontoFijoForm(
    CodigoGeneralBaseForm
):
    modalidad_codigo = (
        CodigoDescuento
        .Modalidad
        .MONTO_FIJO
    )

    prefijo_html = (
        "general_clp"
    )

    monto_descuento = (
        forms.DecimalField(
            min_value=Decimal("1"),
            decimal_places=0,
            max_digits=12,
            label=(
                "Monto de descuento en CLP"
            ),
            help_text=(
                "Cantidad exacta que se "
                "descontará de la compra."
            ),
            widget=forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "inputmode": "numeric",
                    "placeholder": "20000",
                }
            ),
        )
    )

    class Meta(
        CodigoGeneralBaseForm.Meta
    ):
        fields = [
            "nombre",
            "codigo",
            "descripcion",
            "activo",
            "monto_descuento",
            "monto_minimo",
            "fecha_inicio",
            "fecha_fin",
        ]

        widgets = (
            CodigoGeneralBaseForm
            .Meta
            .widgets
        )

        labels = (
            CodigoGeneralBaseForm
            .Meta
            .labels
        )

        help_texts = (
            CodigoGeneralBaseForm
            .Meta
            .help_texts
        )

    def clean(self):
        datos = super().clean()

        monto_descuento = datos.get(
            "monto_descuento"
        )

        monto_minimo = (
            datos.get(
                "monto_minimo"
            )
            or Decimal("0")
        )

        if (
            monto_descuento is None
            or monto_descuento
            <= Decimal("0")
        ):
            self.add_error(
                "monto_descuento",
                (
                    "Debes indicar el monto "
                    "que se descontará."
                ),
            )

        if monto_minimo <= Decimal("0"):
            self.add_error(
                "monto_minimo",
                (
                    "Un descuento en CLP debe "
                    "tener una compra mínima "
                    "mayor que cero."
                ),
            )

        if (
            monto_descuento is not None
            and monto_minimo > Decimal("0")
            and monto_descuento
            > monto_minimo
        ):
            self.add_error(
                "monto_descuento",
                (
                    "El descuento no puede ser "
                    "mayor que la compra mínima."
                ),
            )

        return datos

    def save(
        self,
        commit=True,
    ):
        instancia = super().save(
            commit=False
        )

        instancia.modalidad = (
            CodigoDescuento
            .Modalidad
            .MONTO_FIJO
        )

        instancia.porcentaje = None

        instancia.monto_descuento = (
            self.cleaned_data.get(
                "monto_descuento"
            )
        )

        instancia.monto_maximo_descuento = (
            None
        )

        if commit:
            instancia.save()

        return instancia


# ============================================================================
# BASE PARA METAS DE FIDELIDAD
# ============================================================================


class MetaFidelidadBaseForm(
    forms.ModelForm
):
    modalidad_meta = None
    prefijo_html = "meta"

    class Meta:
        model = MetaFidelidad

        fields = [
            "nombre",
            "activa",
            "monto_objetivo",
            "monto_minimo_compra",
            "vigencia_dias",
            "prefijo_codigo",
            "orden",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ejemplo: Cliente Plata"
                    ),
                    "autocomplete": "off",
                }
            ),

            "activa": (
                forms.CheckboxInput()
            ),

            "monto_objetivo": (
                forms.NumberInput(
                    attrs={
                        "min": "1",
                        "step": "1",
                        "inputmode": "numeric",
                        "placeholder": "100000",
                    }
                )
            ),

            "monto_minimo_compra": (
                forms.NumberInput(
                    attrs={
                        "min": "0",
                        "step": "1",
                        "inputmode": "numeric",
                        "placeholder": "0",
                    }
                )
            ),

            "vigencia_dias": (
                forms.NumberInput(
                    attrs={
                        "min": "1",
                        "max": "730",
                        "step": "1",
                        "inputmode": "numeric",
                        "placeholder": "60",
                    }
                )
            ),

            "prefijo_codigo": (
                forms.TextInput(
                    attrs={
                        "placeholder": (
                            "Ejemplo: AUDEXFIEL"
                        ),
                        "autocomplete": "off",
                        "spellcheck": "false",
                    }
                )
            ),

            "orden": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "1",
                    "inputmode": "numeric",
                }
            ),
        }

        labels = {
            "nombre": (
                "Nombre de la meta"
            ),

            "activa": (
                "Meta activa"
            ),

            "monto_objetivo": (
                "Monto acumulado para "
                "alcanzar la meta"
            ),

            "monto_minimo_compra": (
                "Compra mínima para "
                "usar el premio"
            ),

            "vigencia_dias": (
                "Vigencia del premio "
                "en días"
            ),

            "prefijo_codigo": (
                "Prefijo del código"
            ),

            "orden": (
                "Orden"
            ),
        }

        help_texts = {
            "monto_objetivo": (
                "Monto total acumulado que "
                "debe alcanzar el cliente."
            ),

            "monto_minimo_compra": (
                "Compra mínima necesaria "
                "cuando utilice el premio."
            ),

            "vigencia_dias": (
                "Días durante los cuales "
                "el código personal podrá "
                "utilizarse."
            ),

            "prefijo_codigo": (
                "El sistema agregará "
                "automáticamente el usuario, "
                "la meta y un código aleatorio."
            ),

            "orden": (
                "Sirve para ordenar metas "
                "que tengan importes similares."
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

        if self.modalidad_meta is None:
            raise ValueError(
                (
                    "El formulario debe definir "
                    "modalidad_meta."
                )
            )

        self.auto_id = (
            f"id_{self.prefijo_html}_%s"
        )

        self.instance.modalidad = (
            self.modalidad_meta
        )

        if (
            not self.is_bound
            and not self.instance.pk
        ):
            self.fields[
                "activa"
            ].initial = True

            self.fields[
                "monto_minimo_compra"
            ].initial = Decimal("0")

            self.fields[
                "vigencia_dias"
            ].initial = 60

            self.fields[
                "orden"
            ].initial = 0

    def clean_prefijo_codigo(self):
        return _normalizar_texto_codigo(
            self.cleaned_data.get(
                "prefijo_codigo"
            )
        )

    def clean(self):
        datos = super().clean()

        monto_objetivo = datos.get(
            "monto_objetivo"
        )

        monto_minimo = (
            datos.get(
                "monto_minimo_compra"
            )
            or Decimal("0")
        )

        if (
            monto_objetivo is None
            or monto_objetivo
            <= Decimal("0")
        ):
            self.add_error(
                "monto_objetivo",
                (
                    "La meta debe ser mayor "
                    "que cero."
                ),
            )

        if monto_minimo < Decimal("0"):
            self.add_error(
                "monto_minimo_compra",
                (
                    "La compra mínima no "
                    "puede ser negativa."
                ),
            )

        return datos

    def save(
        self,
        commit=True,
    ):
        instancia = super().save(
            commit=False
        )

        instancia.modalidad = (
            self.modalidad_meta
        )

        if commit:
            instancia.save()

        return instancia


# ============================================================================
# 3. META DE FIDELIDAD PORCENTUAL
# ============================================================================


class MetaFidelidadPorcentajeForm(
    MetaFidelidadBaseForm
):
    modalidad_meta = (
        MetaFidelidad
        .Modalidad
        .PORCENTAJE
    )

    prefijo_html = (
        "fidelidad_porcentaje"
    )

    porcentaje = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_value=Decimal("100"),
        decimal_places=2,
        max_digits=5,
        label=(
            "Porcentaje del premio"
        ),
        help_text=(
            "Porcentaje que recibirá "
            "automáticamente el cliente "
            "al alcanzar esta meta."
        ),
        widget=forms.NumberInput(
            attrs={
                "min": "0.01",
                "max": "100",
                "step": "0.01",
                "inputmode": "decimal",
                "placeholder": "10",
            }
        ),
    )

    monto_maximo_descuento = (
        forms.DecimalField(
            required=False,
            min_value=Decimal("1"),
            decimal_places=0,
            max_digits=12,
            label=(
                "Descuento máximo"
            ),
            help_text=(
                "Opcional. Máximo de CLP "
                "que podrá descontar el premio."
            ),
            widget=forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "inputmode": "numeric",
                    "placeholder": (
                        "Sin límite"
                    ),
                }
            ),
        )
    )

    class Meta(
        MetaFidelidadBaseForm.Meta
    ):
        fields = [
            "nombre",
            "activa",
            "monto_objetivo",
            "porcentaje",
            "monto_minimo_compra",
            "monto_maximo_descuento",
            "vigencia_dias",
            "prefijo_codigo",
            "orden",
        ]

        widgets = (
            MetaFidelidadBaseForm
            .Meta
            .widgets
        )

        labels = (
            MetaFidelidadBaseForm
            .Meta
            .labels
        )

        help_texts = (
            MetaFidelidadBaseForm
            .Meta
            .help_texts
        )

    def clean(self):
        datos = super().clean()

        porcentaje = datos.get(
            "porcentaje"
        )

        if (
            porcentaje is None
            or porcentaje
            <= Decimal("0")
        ):
            self.add_error(
                "porcentaje",
                (
                    "Debes indicar un porcentaje "
                    "de premio mayor que cero."
                ),
            )

        return datos

    def save(
        self,
        commit=True,
    ):
        instancia = super().save(
            commit=False
        )

        instancia.modalidad = (
            MetaFidelidad
            .Modalidad
            .PORCENTAJE
        )

        instancia.porcentaje = (
            self.cleaned_data.get(
                "porcentaje"
            )
        )

        instancia.monto_descuento = None

        instancia.monto_maximo_descuento = (
            self.cleaned_data.get(
                "monto_maximo_descuento"
            )
        )

        if commit:
            instancia.save()

        return instancia


# ============================================================================
# 4. META DE FIDELIDAD EN CLP
# ============================================================================


class MetaFidelidadMontoFijoForm(
    MetaFidelidadBaseForm
):
    modalidad_meta = (
        MetaFidelidad
        .Modalidad
        .MONTO_FIJO
    )

    prefijo_html = (
        "fidelidad_clp"
    )

    monto_descuento = (
        forms.DecimalField(
            min_value=Decimal("1"),
            decimal_places=0,
            max_digits=12,
            label=(
                "Premio en CLP"
            ),
            help_text=(
                "Cantidad exacta de pesos "
                "que recibirá el cliente "
                "al alcanzar esta meta."
            ),
            widget=forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "inputmode": "numeric",
                    "placeholder": "20000",
                }
            ),
        )
    )

    class Meta(
        MetaFidelidadBaseForm.Meta
    ):
        fields = [
            "nombre",
            "activa",
            "monto_objetivo",
            "monto_descuento",
            "monto_minimo_compra",
            "vigencia_dias",
            "prefijo_codigo",
            "orden",
        ]

        widgets = (
            MetaFidelidadBaseForm
            .Meta
            .widgets
        )

        labels = (
            MetaFidelidadBaseForm
            .Meta
            .labels
        )

        help_texts = (
            MetaFidelidadBaseForm
            .Meta
            .help_texts
        )

    def clean(self):
        datos = super().clean()

        monto_descuento = datos.get(
            "monto_descuento"
        )

        monto_minimo = (
            datos.get(
                "monto_minimo_compra"
            )
            or Decimal("0")
        )

        if (
            monto_descuento is None
            or monto_descuento
            <= Decimal("0")
        ):
            self.add_error(
                "monto_descuento",
                (
                    "Debes indicar el monto "
                    "del premio."
                ),
            )

        if monto_minimo <= Decimal("0"):
            self.add_error(
                "monto_minimo_compra",
                (
                    "Un premio en CLP debe "
                    "tener una compra mínima "
                    "mayor que cero."
                ),
            )

        if (
            monto_descuento is not None
            and monto_minimo > Decimal("0")
            and monto_descuento
            > monto_minimo
        ):
            self.add_error(
                "monto_descuento",
                (
                    "El premio no puede ser "
                    "mayor que la compra mínima."
                ),
            )

        return datos

    def save(
        self,
        commit=True,
    ):
        instancia = super().save(
            commit=False
        )

        instancia.modalidad = (
            MetaFidelidad
            .Modalidad
            .MONTO_FIJO
        )

        instancia.porcentaje = None

        instancia.monto_descuento = (
            self.cleaned_data.get(
                "monto_descuento"
            )
        )

        instancia.monto_maximo_descuento = (
            None
        )

        if commit:
            instancia.save()

        return instancia