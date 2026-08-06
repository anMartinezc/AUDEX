import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


VALIDADOR_CODIGO_DESCUENTO = RegexValidator(
    regex=r"^[A-Z0-9_-]+$",
    message=(
        "El código solo puede contener letras, "
        "números, guiones y guiones bajos."
    ),
)


class Categoria(models.Model):
    nombre = models.CharField(
        max_length=80,
        unique=True,
        verbose_name="Nombre",
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
    )

    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )

    activa = models.BooleanField(
        default=True,
        verbose_name="Categoría activa",
    )

    orden = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden",
    )

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = [
            "orden",
            "nombre",
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            slug_base = slugify(
                self.nombre
            )

            slug = slug_base
            contador = 1

            while (
                Categoria.objects
                .filter(
                    slug=slug,
                )
                .exclude(
                    pk=self.pk,
                )
                .exists()
            ):
                slug = (
                    f"{slug_base}-{contador}"
                )

                contador += 1

            self.slug = slug

        super().save(
            *args,
            **kwargs,
        )


class Producto(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="productos",
        verbose_name="Categoría",
    )

    nombre = models.CharField(
        max_length=150,
        verbose_name="Nombre",
    )

    slug = models.SlugField(
        max_length=180,
        unique=True,
        blank=True,
    )

    descripcion_corta = models.CharField(
        max_length=220,
        verbose_name="Descripción corta",
    )

    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción completa",
    )

    imagen = models.ImageField(
        upload_to="productos/",
        blank=True,
        null=True,
        verbose_name="Imagen principal",
    )

    imagen_url = models.URLField(
        blank=True,
        verbose_name="URL externa de imagen",
        help_text=(
            "Opcional. Se utiliza cuando no se "
            "carga una imagen local."
        ),
    )

    precio = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name="Precio normal",
    )

    precio_oferta = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        blank=True,
        null=True,
        verbose_name="Precio oferta",
    )

    stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Stock",
    )

    stock_reservado = (
        models.PositiveIntegerField(
            default=0,
            verbose_name="Stock reservado",
        )
    )

    caracteristica_1 = models.CharField(
        max_length=120,
        verbose_name="Característica 1",
    )

    caracteristica_2 = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Característica 2",
    )

    caracteristica_3 = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Característica 3",
    )

    autonomia_horas = (
        models.PositiveIntegerField(
            blank=True,
            null=True,
            verbose_name="Autonomía en horas",
        )
    )

    bluetooth = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Versión Bluetooth",
    )

    resistencia_agua = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Resistencia al agua",
    )

    cancelacion_ruido = (
        models.BooleanField(
            default=False,
            verbose_name="Cancelación de ruido",
        )
    )

    destacado = models.BooleanField(
        default=False,
        verbose_name="Producto destacado",
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="Producto visible",
    )

    creado = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

        ordering = [
            "-destacado",
            "-creado",
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()

        errores = {}

        if self.precio <= Decimal("0"):
            errores["precio"] = (
                "El precio debe ser mayor que cero."
            )

        if self.precio_oferta is not None:
            if (
                self.precio_oferta
                <= Decimal("0")
            ):
                errores["precio_oferta"] = (
                    "El precio de oferta debe ser "
                    "mayor que cero."
                )

            elif (
                self.precio_oferta
                >= self.precio
            ):
                errores["precio_oferta"] = (
                    "El precio de oferta debe ser "
                    "menor que el precio normal."
                )

        if (
            not self.imagen
            and not self.imagen_url
        ):
            errores["imagen"] = (
                "Carga una imagen o ingresa "
                "una URL externa."
            )

        if (
            self.stock_reservado
            > self.stock
        ):
            errores["stock_reservado"] = (
                "El stock reservado no puede "
                "superar el stock total."
            )

        if errores:
            raise ValidationError(
                errores
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            slug_base = slugify(
                self.nombre
            )

            slug = slug_base
            contador = 1

            while (
                Producto.objects
                .filter(
                    slug=slug,
                )
                .exclude(
                    pk=self.pk,
                )
                .exists()
            ):
                slug = (
                    f"{slug_base}-{contador}"
                )

                contador += 1

            self.slug = slug

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    @property
    def en_oferta(self):
        return (
            self.precio_oferta is not None
            and self.precio_oferta > 0
            and self.precio_oferta
            < self.precio
        )

    @property
    def precio_actual(self):
        if self.en_oferta:
            return self.precio_oferta

        return self.precio

    @property
    def porcentaje_descuento(self):
        if not self.en_oferta:
            return 0

        descuento = (
            (
                self.precio
                - self.precio_oferta
            )
            / self.precio
            * Decimal("100")
        )

        return round(
            descuento
        )

    @property
    def imagen_mostrable(self):
        if self.imagen:
            return self.imagen.url

        return self.imagen_url

    @property
    def stock_disponible(self):
        return max(
            self.stock
            - self.stock_reservado,
            0,
        )

    @property
    def disponible(self):
        return (
            self.activo
            and self.stock_disponible > 0
        )

    def get_absolute_url(self):
        return reverse(
            "core:producto_detalle",
            kwargs={
                "slug": self.slug,
            },
        )


class Pedido(models.Model):
    # -------------------------------------------------------------------------
    # ESTADOS DEL PEDIDO
    # -------------------------------------------------------------------------

    class EstadoPedido(
        models.TextChoices
    ):
        PENDIENTE = (
            "pendiente",
            "Pendiente de pago",
        )

        CONFIRMADO = (
            "confirmado",
            "Pago confirmado",
        )

        PREPARACION = (
            "preparacion",
            "En preparación",
        )

        LISTO = (
            "listo",
            "Listo para despacho",
        )

        ENVIADO = (
            "enviado",
            "Enviado",
        )

        ENTREGADO = (
            "entregado",
            "Entregado",
        )

        CANCELADO = (
            "cancelado",
            "Cancelado",
        )

    # -------------------------------------------------------------------------
    # MÉTODOS DE PAGO
    # -------------------------------------------------------------------------

    class MetodoPago(
        models.TextChoices
    ):
        WEBPAY = (
            "webpay",
            "Webpay",
        )

        MERCADOPAGO = (
            "mercadopago",
            "Mercado Pago",
        )

        TRANSFERENCIA = (
            "transferencia",
            "Transferencia bancaria",
        )

    # -------------------------------------------------------------------------
    # ESTADOS DEL PAGO
    # -------------------------------------------------------------------------

    class EstadoPago(
        models.TextChoices
    ):
        PENDIENTE = (
            "pendiente",
            "Pendiente",
        )

        INICIADO = (
            "iniciado",
            "Iniciado",
        )

        APROBADO = (
            "aprobado",
            "Aprobado",
        )

        RECHAZADO = (
            "rechazado",
            "Rechazado",
        )

        CANCELADO = (
            "cancelado",
            "Cancelado",
        )

        REEMBOLSADO = (
            "reembolsado",
            "Reembolsado",
        )

        REVISION = (
            "revision",
            "En revisión",
        )

    # -------------------------------------------------------------------------
    # TIPOS DE DESCUENTO
    # -------------------------------------------------------------------------

    class TipoDescuento(
        models.TextChoices
    ):
        NINGUNO = (
            "ninguno",
            "Sin descuento",
        )

        GENERAL = (
            "general",
            "Código general",
        )

        FIDELIDAD = (
            "fidelidad",
            "Premio de fidelidad",
        )

    # -------------------------------------------------------------------------
    # COMPATIBILIDAD CON CÓDIGO ANTERIOR
    # -------------------------------------------------------------------------

    ESTADOS = EstadoPedido.choices
    METODOS_PAGO = MetodoPago.choices
    ESTADOS_PAGO = EstadoPago.choices

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    numero = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos",
    )

    # -------------------------------------------------------------------------
    # DATOS DEL CLIENTE
    # -------------------------------------------------------------------------

    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre",
    )

    apellido = models.CharField(
        max_length=100,
        verbose_name="Apellido",
    )

    rut = models.CharField(
        max_length=20,
        verbose_name="RUT",
        db_index=True,
    )

    email = models.EmailField(
        verbose_name=(
            "Correo electrónico del checkout"
        ),
        db_index=True,
    )

    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono",
    )

    # -------------------------------------------------------------------------
    # DIRECCIÓN
    # -------------------------------------------------------------------------

    region = models.CharField(
        max_length=100,
        verbose_name="Región",
    )

    comuna = models.CharField(
        max_length=100,
        verbose_name="Comuna",
    )

    direccion = models.CharField(
        max_length=180,
        verbose_name="Dirección",
    )

    numero_direccion = models.CharField(
        max_length=20,
        verbose_name="Número",
    )

    departamento = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=(
            "Departamento, casa u oficina"
        ),
    )

    referencia = models.CharField(
        max_length=220,
        blank=True,
        verbose_name="Referencia",
    )

    # -------------------------------------------------------------------------
    # ESTADO Y MÉTODO DE PAGO
    # -------------------------------------------------------------------------

    metodo_pago = models.CharField(
        max_length=30,
        choices=MetodoPago.choices,
        default=MetodoPago.WEBPAY,
        db_index=True,
    )

    estado = models.CharField(
        max_length=30,
        choices=EstadoPedido.choices,
        default=EstadoPedido.PENDIENTE,
        db_index=True,
    )

    estado_pago = models.CharField(
        max_length=20,
        choices=EstadoPago.choices,
        default=EstadoPago.PENDIENTE,
        db_index=True,
    )

    # -------------------------------------------------------------------------
    # DATOS GENERALES DEL PAGO
    # -------------------------------------------------------------------------

    pagado = models.BooleanField(
        default=False,
        db_index=True,
    )

    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
    )

    stock_descontado = (
        models.BooleanField(
            default=False,
            db_index=True,
        )
    )

    correo_confirmacion_enviado = (
        models.BooleanField(
            default=False,
            db_index=True,
        )
    )

    fecha_correo_confirmacion = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    # -------------------------------------------------------------------------
    # WEBPAY
    # -------------------------------------------------------------------------

    webpay_token = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    webpay_buy_order = (
        models.CharField(
            max_length=100,
            blank=True,
            db_index=True,
        )
    )

    webpay_authorization_code = (
        models.CharField(
            max_length=100,
            blank=True,
        )
    )

    webpay_response_code = (
        models.IntegerField(
            null=True,
            blank=True,
        )
    )

    webpay_payment_type_code = (
        models.CharField(
            max_length=20,
            blank=True,
        )
    )

    webpay_installments_number = (
        models.PositiveIntegerField(
            null=True,
            blank=True,
        )
    )

    webpay_transaction_date = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    # -------------------------------------------------------------------------
    # MERCADO PAGO
    # -------------------------------------------------------------------------

    mercadopago_preference_id = (
        models.CharField(
            max_length=150,
            blank=True,
            db_index=True,
        )
    )

    mercadopago_payment_id = (
        models.CharField(
            max_length=100,
            blank=True,
            db_index=True,
        )
    )

    mercadopago_status = (
        models.CharField(
            max_length=50,
            blank=True,
        )
    )

    mercadopago_status_detail = (
        models.CharField(
            max_length=100,
            blank=True,
        )
    )

    mercadopago_payment_type = (
        models.CharField(
            max_length=50,
            blank=True,
        )
    )

    mercadopago_transaction_amount = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            null=True,
            blank=True,
        )
    )

    # -------------------------------------------------------------------------
    # DESCUENTOS
    # -------------------------------------------------------------------------

    codigo_descuento_obj = (
        models.ForeignKey(
            "CodigoDescuento",
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name="pedidos",
            verbose_name=(
                "Código de descuento aplicado"
            ),
        )
    )

    codigo_descuento = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
    )

    tipo_descuento = (
        models.CharField(
            max_length=20,
            choices=(
                TipoDescuento.choices
            ),
            default=(
                TipoDescuento.NINGUNO
            ),
            db_index=True,
        )
    )

    porcentaje_descuento = (
        models.DecimalField(
            max_digits=5,
            decimal_places=2,
            default=0,
            validators=[
                MinValueValidator(
                    Decimal("0")
                ),
                MaxValueValidator(
                    Decimal("100")
                ),
            ],
        )
    )

    fidelidad_contabilizada = (
        models.BooleanField(
            default=False,
            db_index=True,
        )
    )

    # -------------------------------------------------------------------------
    # MONTOS
    # -------------------------------------------------------------------------

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
    )

    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
    )

    despacho = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
    )

    # -------------------------------------------------------------------------
    # INFORMACIÓN ADICIONAL
    # -------------------------------------------------------------------------

    notas = models.TextField(
        blank=True,
        verbose_name="Notas del pedido",
    )

    creado = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-creado",
        ]

        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

        indexes = [
            models.Index(
                fields=[
                    "estado_pago",
                    "creado",
                ],
                name=(
                    "pedido_pago_creado_idx"
                ),
            ),
            models.Index(
                fields=[
                    "metodo_pago",
                    "estado_pago",
                ],
                name=(
                    "pedido_metodo_pago_idx"
                ),
            ),
            models.Index(
                fields=[
                    "tipo_descuento",
                    "creado",
                ],
                name=(
                    "pedido_desc_tipo_idx"
                ),
            ),
            models.Index(
                fields=[
                    "usuario",
                    "fidelidad_contabilizada",
                ],
                name=(
                    "pedido_fidelidad_idx"
                ),
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    subtotal__gte=0,
                ),
                name=(
                    "pedido_subtotal_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    descuento__gte=0,
                ),
                name=(
                    "pedido_descuento_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    despacho__gte=0,
                ),
                name=(
                    "pedido_despacho_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    total__gte=0,
                ),
                name=(
                    "pedido_total_gte_0"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.numero} - "
            f"{self.nombre_completo}"
        )

    @property
    def nombre_completo(self):
        return (
            f"{self.nombre} "
            f"{self.apellido}"
        ).strip()

    @property
    def direccion_completa(self):
        partes = [
            self.direccion,
            self.numero_direccion,
            self.departamento,
            self.comuna,
            self.region,
        ]

        return ", ".join(
            str(parte).strip()
            for parte in partes
            if (
                parte
                and str(parte).strip()
            )
        )

    @property
    def pago_aprobado(self):
        return (
            self.estado_pago
            == self.EstadoPago.APROBADO
            and self.pagado
        )

    @property
    def puede_confirmarse(self):
        return (
            self.estado
            != self.EstadoPedido.CANCELADO
            and self.estado_pago
            == self.EstadoPago.APROBADO
            and self.pagado
        )

    @property
    def tiene_descuento(self):
        return (
            self.descuento > 0
            and self.tipo_descuento
            != self.TipoDescuento.NINGUNO
        )

    @property
    def email_usuario(self):
        if not self.usuario_id:
            return ""

        return self.normalizar_email(
            getattr(
                self.usuario,
                "email",
                "",
            )
        )

    @property
    def emails_confirmacion(self):
        emails = []
        emails_vistos = set()

        candidatos = [
            self.email,
            self.email_usuario,
        ]

        for candidato in candidatos:
            email_normalizado = (
                self.normalizar_email(
                    candidato
                )
            )

            if not email_normalizado:
                continue

            if (
                email_normalizado
                in emails_vistos
            ):
                continue

            emails_vistos.add(
                email_normalizado
            )

            emails.append(
                email_normalizado
            )

        return emails

    @staticmethod
    def normalizar_email(email):
        if not email:
            return ""

        return (
            str(email)
            .strip()
            .casefold()
        )

    def save(
        self,
        *args,
        **kwargs,
    ):
        if not self.numero:
            self.numero = (
                self._generar_numero_unico()
            )

        if self.email:
            self.email = (
                self.email.strip()
            )

        if self.rut:
            self.rut = (
                str(self.rut)
                .strip()
                .upper()
            )

        if self.codigo_descuento:
            self.codigo_descuento = (
                self.codigo_descuento
                .strip()
                .upper()
            )

        super().save(
            *args,
            **kwargs,
        )

    @classmethod
    def _generar_numero_unico(cls):
        while True:
            codigo = (
                uuid.uuid4()
                .hex[:8]
                .upper()
            )

            numero = (
                f"AUD-{codigo}"
            )

            existe = (
                cls.objects
                .filter(
                    numero=numero,
                )
                .exists()
            )

            if not existe:
                return numero


class PedidoItem(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="items",
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items_pedido",
    )

    nombre_producto = models.CharField(
        max_length=150,
    )

    precio_lista_unitario = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
            help_text=(
                "Precio normal del producto "
                "al momento de la compra."
            ),
        )
    )

    precio_unitario = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
        )
    )

    descuento_producto_unitario = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
            help_text=(
                "Descuento propio de la oferta "
                "del producto por unidad."
            ),
        )
    )

    cantidad = models.PositiveIntegerField(
        default=1,
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        help_text=(
            "Total de la línea antes del "
            "código de descuento."
        ),
    )

    descuento_codigo = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
            help_text=(
                "Parte proporcional del cupón "
                "asignada a esta línea."
            ),
        )
    )

    total_final = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
            help_text=(
                "Total de la línea después del "
                "código de descuento."
            ),
        )
    )

    class Meta:
        ordering = [
            "pk",
        ]

        verbose_name = "Ítem de pedido"
        verbose_name_plural = (
            "Ítems de pedido"
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    cantidad__gt=0,
                ),
                name=(
                    "pedido_item_cantidad_gt_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    precio_unitario__gte=0,
                ),
                name=(
                    "pedido_item_precio_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    total__gte=0,
                ),
                name=(
                    "pedido_item_total_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    descuento_codigo__gte=0,
                ),
                name=(
                    "pedido_item_desc_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    total_final__gte=0,
                ),
                name=(
                    "pedido_item_final_gte_0"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.nombre_producto} "
            f"x {self.cantidad}"
        )

    @property
    def total_precio_lista(self):
        return (
            self.precio_lista_unitario
            * self.cantidad
        )

    @property
    def descuento_producto_total(self):
        return (
            self.descuento_producto_unitario
            * self.cantidad
        )


class CodigoDescuento(models.Model):
    class Tipo(
        models.TextChoices
    ):
        GENERAL = (
            "general",
            "Código general",
        )

        FIDELIDAD = (
            "fidelidad",
            "Premio de fidelidad",
        )

    class Modalidad(
        models.TextChoices
    ):
        PORCENTAJE = (
            "porcentaje",
            "Porcentaje",
        )

        MONTO_FIJO = (
            "monto_fijo",
            "Monto fijo en CLP",
        )

    # ------------------------------------------------------------------
    # CLASIFICACIÓN
    # ------------------------------------------------------------------

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.GENERAL,
        db_index=True,
        verbose_name="Tipo de código",
    )

    modalidad = models.CharField(
        max_length=20,
        choices=Modalidad.choices,
        default=Modalidad.PORCENTAJE,
        db_index=True,
        verbose_name="Modalidad del descuento",
        help_text=(
            "Selecciona si el código descontará "
            "un porcentaje o un monto fijo en CLP."
        ),
    )

    # ------------------------------------------------------------------
    # INFORMACIÓN DEL CÓDIGO
    # ------------------------------------------------------------------

    nombre = models.CharField(
        max_length=120,
        verbose_name="Nombre interno",
    )

    codigo = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        validators=[
            VALIDADOR_CODIGO_DESCUENTO,
        ],
        verbose_name="Código",
    )

    descripcion = models.CharField(
        max_length=220,
        blank=True,
        verbose_name="Descripción",
    )

    activo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Código activo",
    )

    consumido = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Código consumido",
        help_text=(
            "Solo se utiliza para premios "
            "personales de fidelidad."
        ),
    )

    # ------------------------------------------------------------------
    # VALOR DEL DESCUENTO
    # ------------------------------------------------------------------

    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
            MaxValueValidator(
                Decimal("100")
            ),
        ],
        verbose_name="Porcentaje de descuento",
        help_text=(
            "Completar solamente cuando la modalidad "
            "sea porcentaje. Ejemplo: 15 para un 15%."
        ),
    )

    monto_descuento = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            null=True,
            blank=True,
            validators=[
                MinValueValidator(
                    Decimal("1")
                ),
            ],
            verbose_name=(
                "Monto fijo de descuento"
            ),
            help_text=(
                "Completar solamente cuando la modalidad "
                "sea monto fijo en CLP. Ejemplo: 38000."
            ),
        )
    )

    monto_minimo = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
            validators=[
                MinValueValidator(
                    Decimal("0")
                ),
            ],
            verbose_name="Compra mínima",
            help_text=(
                "Subtotal mínimo que debe alcanzar el "
                "cliente para utilizar este código."
            ),
        )
    )

    monto_maximo_descuento = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            null=True,
            blank=True,
            validators=[
                MinValueValidator(
                    Decimal("1")
                ),
            ],
            verbose_name=(
                "Descuento máximo"
            ),
            help_text=(
                "Opcional. Solo se utiliza en descuentos "
                "porcentuales para limitar el monto máximo "
                "que puede descontarse."
            ),
        )
    )

    # ------------------------------------------------------------------
    # VIGENCIA
    # ------------------------------------------------------------------

    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Fecha de inicio",
    )

    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Fecha de término",
    )

    # ------------------------------------------------------------------
    # CÓDIGOS PERSONALES
    # ------------------------------------------------------------------

    usuario_exclusivo = (
        models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE,
            null=True,
            blank=True,
            related_name=(
                "codigos_descuento_exclusivos"
            ),
            verbose_name="Usuario exclusivo",
        )
    )

    numero_meta = (
        models.PositiveIntegerField(
            null=True,
            blank=True,
            verbose_name="Número de meta",
            help_text=(
                "Número de meta que originó "
                "el premio personal."
            ),
        )
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "codigos_descuento_creados"
        ),
        verbose_name="Creado por",
    )

    # ------------------------------------------------------------------
    # AUDITORÍA
    # ------------------------------------------------------------------

    creado = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-creado",
        ]

        verbose_name = (
            "Código de descuento"
        )

        verbose_name_plural = (
            "Códigos de descuento"
        )

        indexes = [
            models.Index(
                fields=[
                    "tipo",
                    "activo",
                ],
                name=(
                    "codigo_tipo_activo_idx"
                ),
            ),
            models.Index(
                fields=[
                    "modalidad",
                    "activo",
                ],
                name=(
                    "codigo_modal_activo_idx"
                ),
            ),
            models.Index(
                fields=[
                    "usuario_exclusivo",
                    "consumido",
                ],
                name=(
                    "codigo_usuario_consum_idx"
                ),
            ),
            models.Index(
                fields=[
                    "activo",
                    "fecha_inicio",
                    "fecha_fin",
                ],
                name=(
                    "codigo_vigencia_idx"
                ),
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        modalidad="porcentaje",
                        porcentaje__gt=0,
                        monto_descuento__isnull=True,
                    )
                    |
                    Q(
                        modalidad="monto_fijo",
                        monto_descuento__gt=0,
                        porcentaje__isnull=True,
                    )
                ),
                name=(
                    "codigo_modalidad_valida"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    monto_minimo__gte=0,
                ),
                name=(
                    "codigo_min_gte_0"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.codigo} · "
            f"{self.nombre}"
        )

    def clean(self):
        super().clean()

        self.codigo = (
            self.codigo
            or ""
        ).strip().upper()

        errores = {}

        # --------------------------------------------------------------
        # VALIDACIÓN DE FECHAS
        # --------------------------------------------------------------

        if (
            self.fecha_inicio
            and self.fecha_fin
            and self.fecha_fin
            <= self.fecha_inicio
        ):
            errores["fecha_fin"] = (
                "La fecha de término debe ser "
                "posterior a la fecha de inicio."
            )

        # --------------------------------------------------------------
        # VALIDACIÓN DEL MONTO MÍNIMO
        # --------------------------------------------------------------

        if (
            self.monto_minimo is not None
            and self.monto_minimo
            < Decimal("0")
        ):
            errores["monto_minimo"] = (
                "La compra mínima no puede "
                "ser negativa."
            )

        # --------------------------------------------------------------
        # DESCUENTO PORCENTUAL
        # --------------------------------------------------------------

        if (
            self.modalidad
            == self.Modalidad.PORCENTAJE
        ):
            self.monto_descuento = None

            if (
                self.porcentaje is None
                or self.porcentaje
                <= Decimal("0")
            ):
                errores["porcentaje"] = (
                    "Debes indicar un porcentaje "
                    "mayor que cero."
                )

            elif (
                self.porcentaje
                > Decimal("100")
            ):
                errores["porcentaje"] = (
                    "El porcentaje no puede "
                    "ser superior a 100."
                )

        # --------------------------------------------------------------
        # DESCUENTO FIJO EN CLP
        # --------------------------------------------------------------

        elif (
            self.modalidad
            == self.Modalidad.MONTO_FIJO
        ):
            self.porcentaje = None
            self.monto_maximo_descuento = None

            if (
                self.monto_descuento is None
                or self.monto_descuento
                <= Decimal("0")
            ):
                errores["monto_descuento"] = (
                    "Debes indicar un monto fijo "
                    "de descuento mayor que cero."
                )

        else:
            errores["modalidad"] = (
                "Selecciona una modalidad "
                "de descuento válida."
            )

        # --------------------------------------------------------------
        # CÓDIGOS GENERALES
        # --------------------------------------------------------------

        if self.tipo == self.Tipo.GENERAL:
            self.usuario_exclusivo = None
            self.numero_meta = None
            self.consumido = False

        # --------------------------------------------------------------
        # CÓDIGOS DE FIDELIDAD
        # --------------------------------------------------------------

        if self.tipo == self.Tipo.FIDELIDAD:
            # La configuración de fidelidad actual
            # genera premios porcentuales.
            self.modalidad = (
                self.Modalidad.PORCENTAJE
            )

            self.monto_descuento = None

            if not self.usuario_exclusivo_id:
                errores["usuario_exclusivo"] = (
                    "Un código de fidelidad debe "
                    "pertenecer a un usuario."
                )

            if (
                self.porcentaje is None
                or self.porcentaje
                <= Decimal("0")
            ):
                errores["porcentaje"] = (
                    "Un premio de fidelidad debe "
                    "tener un porcentaje válido."
                )

        if errores:
            raise ValidationError(
                errores
            )

    def save(
        self,
        *args,
        **kwargs,
    ):
        self.codigo = (
            self.codigo
            or ""
        ).strip().upper()

        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )

    @property
    def vigente(self):
        ahora = timezone.now()

        if not self.activo:
            return False

        if (
            self.tipo
            == self.Tipo.FIDELIDAD
            and self.consumido
        ):
            return False

        if (
            self.fecha_inicio
            and self.fecha_inicio > ahora
        ):
            return False

        if (
            self.fecha_fin
            and self.fecha_fin <= ahora
        ):
            return False

        return True

    @property
    def es_porcentaje(self):
        return (
            self.modalidad
            == self.Modalidad.PORCENTAJE
        )

    @property
    def es_monto_fijo(self):
        return (
            self.modalidad
            == self.Modalidad.MONTO_FIJO
        )

    @property
    def valor_descuento(self):
        if self.es_monto_fijo:
            return (
                self.monto_descuento
                or Decimal("0")
            )

        return (
            self.porcentaje
            or Decimal("0")
        )

    @property
    def nombre_modalidad(self):
        return self.get_modalidad_display()

class ConfiguracionFidelidad(
    models.Model
):
    SINGLETON_PK = 1

    activa = models.BooleanField(
        default=False,
        verbose_name=(
            "Activar programa de fidelidad"
        ),
    )

    monto_objetivo = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=100000,
            validators=[
                MinValueValidator(
                    Decimal("1")
                ),
            ],
            verbose_name=(
                "Monto para cumplir una meta"
            ),
        )
    )

    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
            MaxValueValidator(
                Decimal("100")
            ),
        ],
        verbose_name=(
            "Porcentaje del premio"
        ),
    )

    monto_minimo_compra = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
            validators=[
                MinValueValidator(
                    Decimal("0")
                ),
            ],
            verbose_name=(
                "Compra mínima para utilizar "
                "el premio"
            ),
        )
    )

    monto_maximo_descuento = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            null=True,
            blank=True,
            validators=[
                MinValueValidator(
                    Decimal("1")
                ),
            ],
            verbose_name=(
                "Descuento máximo del premio"
            ),
        )
    )

    vigencia_dias = (
        models.PositiveIntegerField(
            default=60,
            validators=[
                MinValueValidator(1),
                MaxValueValidator(730),
            ],
            verbose_name=(
                "Vigencia del código en días"
            ),
        )
    )

    prefijo_codigo = models.CharField(
        max_length=24,
        default="AUDEXFIEL",
        validators=[
            VALIDADOR_CODIGO_DESCUENTO,
        ],
        verbose_name=(
            "Prefijo de los códigos de premio"
        ),
        help_text=(
            "Ejemplo: AUDEXFIEL. El sistema "
            "agregará el usuario, la meta y "
            "un fragmento aleatorio."
        ),
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "configuraciones_fidelidad_actualizadas"
        ),
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = (
            "Configuración de fidelidad"
        )

        verbose_name_plural = (
            "Configuración de fidelidad"
        )

    def __str__(self):
        return (
            "Configuración de fidelidad Audex"
        )

    def clean(self):
        super().clean()

        self.prefijo_codigo = (
            self.prefijo_codigo
            or ""
        ).strip().upper()

        errores = {}

        if (
            self.activa
            and self.monto_objetivo
            <= Decimal("0")
        ):
            errores["monto_objetivo"] = (
                "El monto objetivo debe ser "
                "mayor que cero."
            )

        if (
            self.activa
            and self.porcentaje
            <= Decimal("0")
        ):
            errores["porcentaje"] = (
                "El porcentaje debe ser "
                "mayor que cero."
            )

        if not self.prefijo_codigo:
            errores["prefijo_codigo"] = (
                "Debes indicar un prefijo "
                "para los premios."
            )

        if errores:
            raise ValidationError(
                errores
            )

    def save(
        self,
        *args,
        **kwargs,
    ):
        self.pk = self.SINGLETON_PK

        self.prefijo_codigo = (
            self.prefijo_codigo
            or ""
        ).strip().upper()

        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )

    def delete(
        self,
        *args,
        **kwargs,
    ):
        raise ValidationError(
            (
                "La configuración de fidelidad "
                "no puede eliminarse."
            )
        )

    @classmethod
    def obtener(cls):
        configuracion, _ = (
            cls.objects.get_or_create(
                pk=cls.SINGLETON_PK,
            )
        )

        return configuracion


class SaldoFidelidad(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saldo_fidelidad",
    )

    saldo_actual = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0,
    )

    total_historico = (
        models.DecimalField(
            max_digits=14,
            decimal_places=0,
            default=0,
        )
    )

    metas_cumplidas = (
        models.PositiveIntegerField(
            default=0,
        )
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-saldo_actual",
        ]

        verbose_name = (
            "Saldo de fidelidad"
        )

        verbose_name_plural = (
            "Saldos de fidelidad"
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    saldo_actual__gte=0,
                ),
                name=(
                    "saldo_fid_actual_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    total_historico__gte=0,
                ),
                name=(
                    "saldo_fid_total_gte_0"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.usuario} · "
            f"${self.saldo_actual}"
        )

    @property
    def premios_generados(self):
        """
        Alias de compatibilidad para templates
        o código anterior.
        """

        return self.metas_cumplidas


class UsoCodigoDescuento(
    models.Model
):
    class Estado(
        models.TextChoices
    ):
        RESERVADO = (
            "reservado",
            "Reservado",
        )

        CONFIRMADO = (
            "confirmado",
            "Confirmado",
        )

        LIBERADO = (
            "liberado",
            "Liberado",
        )

    codigo = models.ForeignKey(
        CodigoDescuento,
        on_delete=models.PROTECT,
        related_name="usos",
    )

    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.CASCADE,
        related_name=(
            "uso_codigo_descuento"
        ),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "usos_codigos_descuento"
        ),
    )

    cliente_clave = models.CharField(
        max_length=80,
        db_index=True,
        help_text=(
            "Identificador HMAC generado "
            "a partir del RUT normalizado."
        ),
    )

    rut_enmascarado = models.CharField(
        max_length=20,
        blank=True,
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.RESERVADO,
        db_index=True,
    )

    subtotal_original = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
        )
    )

    descuento_aplicado = (
        models.DecimalField(
            max_digits=12,
            decimal_places=0,
            default=0,
        )
    )

    total_final = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
    )

    reservado_en = (
        models.DateTimeField(
            auto_now_add=True,
        )
    )

    confirmado_en = (
        models.DateTimeField(
            null=True,
            blank=True,
            db_index=True,
        )
    )

    liberado_en = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    class Meta:
        ordering = [
            "-reservado_en",
        ]

        verbose_name = (
            "Uso de código de descuento"
        )

        verbose_name_plural = (
            "Usos de códigos de descuento"
        )

        indexes = [
            models.Index(
                fields=[
                    "codigo",
                    "estado",
                ],
                name=(
                    "uso_codigo_estado_idx"
                ),
            ),
            models.Index(
                fields=[
                    "cliente_clave",
                    "estado",
                ],
                name=(
                    "uso_cliente_estado_idx"
                ),
            ),
            models.Index(
                fields=[
                    "confirmado_en",
                ],
                name=(
                    "uso_confirmado_fecha_idx"
                ),
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "codigo",
                    "cliente_clave",
                ],
                condition=Q(
                    estado__in=[
                        "reservado",
                        "confirmado",
                    ],
                ),
                name=(
                    "codigo_un_uso_por_cliente"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    subtotal_original__gte=0,
                ),
                name=(
                    "uso_subtotal_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    descuento_aplicado__gte=0,
                ),
                name=(
                    "uso_descuento_gte_0"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    total_final__gte=0,
                ),
                name=(
                    "uso_total_gte_0"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.codigo.codigo} · "
            f"{self.pedido.numero} · "
            f"{self.get_estado_display()}"
        )


class PedidoHistorialEstado(
    models.Model
):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "cambios_estado_pedidos"
        ),
    )

    estado_anterior = (
        models.CharField(
            max_length=30,
            choices=(
                Pedido.EstadoPedido.choices
            ),
            blank=True,
            default="",
            verbose_name="Estado anterior",
        )
    )

    estado_nuevo = models.CharField(
        max_length=30,
        choices=(
            Pedido.EstadoPedido.choices
        ),
        verbose_name="Estado nuevo",
        db_index=True,
    )

    comentario = models.TextField(
        blank=True,
        verbose_name="Comentario",
    )

    creado = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = [
            "creado",
        ]

        verbose_name = (
            "Historial de estado"
        )

        verbose_name_plural = (
            "Historial de estados"
        )

        indexes = [
            models.Index(
                fields=[
                    "pedido",
                    "creado",
                ],
                name=(
                    "historial_pedido_fecha_idx"
                ),
            ),
            models.Index(
                fields=[
                    "pedido",
                    "estado_nuevo",
                ],
                name=(
                    "historial_pedido_estado_idx"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.pedido.numero}: "
            f"{self.nombre_estado_anterior} "
            f"→ "
            f"{self.get_estado_nuevo_display()}"
        )

    @property
    def nombre_estado_anterior(self):
        if not self.estado_anterior:
            return "Inicio"

        return (
            self.get_estado_anterior_display()
        )

    @property
    def realizado_por(self):
        if not self.usuario_id:
            return "Sistema"

        nombre_completo = (
            self.usuario
            .get_full_name()
            .strip()
        )

        return (
            nombre_completo
            or getattr(
                self.usuario,
                "email",
                "",
            )
            or getattr(
                self.usuario,
                "username",
                "",
            )
            or str(
                self.usuario
            )
        )


class CarritoUsuario(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carrito_audex",
    )

    contenido = models.JSONField(
        default=dict,
        blank=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = (
            "carrito de usuario"
        )

        verbose_name_plural = (
            "carritos de usuarios"
        )

    def __str__(self):
        return (
            f"Carrito de {self.usuario}"
        )


class Favorito(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favoritos_audex",
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name=(
            "usuarios_favoritos"
        ),
    )

    creado = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "favorito"
        verbose_name_plural = "favoritos"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "usuario",
                    "producto",
                ],
                name=(
                    "favorito_usuario_producto_unico"
                ),
            ),
        ]

        ordering = [
            "-creado",
        ]

    def __str__(self):
        return (
            f"{self.usuario} - "
            f"{self.producto}"
        )


class CorreoPedido(models.Model):
    TIPO_CONFIRMACION_PAGO = (
        "confirmacion_pago"
    )

    TIPOS = [
        (
            TIPO_CONFIRMACION_PAGO,
            "Confirmación de pago",
        ),
    ]

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_ENVIANDO = "enviando"
    ESTADO_ENVIADO = "enviado"
    ESTADO_ERROR = "error"

    ESTADOS = [
        (
            ESTADO_PENDIENTE,
            "Pendiente",
        ),
        (
            ESTADO_ENVIANDO,
            "Enviando",
        ),
        (
            ESTADO_ENVIADO,
            "Enviado",
        ),
        (
            ESTADO_ERROR,
            "Error",
        ),
    ]

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="correos_enviados",
    )

    email = models.EmailField()

    tipo = models.CharField(
        max_length=40,
        choices=TIPOS,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE,
    )

    enviado_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    ultimo_error = models.TextField(
        blank=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "pedido",
                    "email",
                    "tipo",
                ],
                name=(
                    "correo_unico_por_pedido_email_tipo"
                ),
            ),
        ]

        ordering = [
            "-creado_en",
        ]

    def __str__(self):
        return (
            f"{self.pedido.numero} · "
            f"{self.email} · "
            f"{self.get_tipo_display()}"
        )