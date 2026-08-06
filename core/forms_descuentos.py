# core/forms_descuentos.py

from django import forms

from core.models import (
    CodigoDescuento,
    ConfiguracionFidelidad,
)


class CodigoGeneralForm(forms.ModelForm):
    class Meta:
        model = CodigoDescuento

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

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ejemplo: Campaña fin de semana",
                }
            ),
            "codigo": forms.TextInput(
                attrs={
                    "placeholder": "Ejemplo: FINDE15",
                    "autocomplete": "off",
                }
            ),
            "descripcion": forms.TextInput(
                attrs={
                    "placeholder": "Descripción interna de la campaña",
                }
            ),
            "porcentaje": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "max": "100",
                    "step": "0.01",
                }
            ),
            "monto_minimo": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "1",
                }
            ),
            "monto_maximo_descuento": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "placeholder": "Sin límite",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.instance.tipo = CodigoDescuento.Tipo.GENERAL

        self.fields["fecha_inicio"].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        self.fields["fecha_fin"].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

    def save(self, commit=True):
        instancia = super().save(commit=False)

        instancia.tipo = CodigoDescuento.Tipo.GENERAL
        instancia.usuario_exclusivo = None
        instancia.numero_meta = None
        instancia.consumido = False

        if commit:
            instancia.save()

        return instancia


class ConfiguracionFidelidadForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionFidelidad

        fields = [
            "activa",
            "monto_objetivo",
            "porcentaje",
            "monto_minimo_compra",
            "monto_maximo_descuento",
            "vigencia_dias",
            "prefijo_codigo",
        ]

        widgets = {
            "monto_objetivo": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                }
            ),
            "porcentaje": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "max": "100",
                    "step": "0.01",
                }
            ),
            "monto_minimo_compra": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "1",
                }
            ),
            "monto_maximo_descuento": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "placeholder": "Sin límite",
                }
            ),
            "vigencia_dias": forms.NumberInput(
                attrs={
                    "min": "1",
                    "max": "730",
                }
            ),
            "prefijo_codigo": forms.TextInput(
                attrs={
                    "placeholder": "Ejemplo: AUDEXFIEL",
                    "autocomplete": "off",
                }
            ),
        }