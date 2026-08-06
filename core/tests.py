from django.test import TestCase
from django.urls import reverse

from core.forms import CheckoutForm


class CoreViewsTest(TestCase):
    def test_pages_render_successfully(self):
        for name in ["inicio", "productos", "categorias", "ofertas", "nosotros"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_checkout_form_handles_discount_code_without_crashing(self):
        form = CheckoutForm(
            data={
                "codigo_descuento": "abc-123",
                "aceptar_terminos": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertNotIn("codigo_descuento", form.errors)
