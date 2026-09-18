"use strict";

document.addEventListener("DOMContentLoaded", () => {
    // =========================================================================
    // ELEMENTOS PRINCIPALES
    // =========================================================================

    const checkout = document.getElementById(
        "checkout"
    );

    const formulario = document.getElementById(
        "checkoutFormulario"
    );

    if (!checkout || !formulario) {
        return;
    }

    const botonConfirmar = document.getElementById(
        "checkoutConfirmar"
    );

    const metodoPagoTarjetas = (
        document.querySelectorAll(
            ".checkout-metodo"
        )
    );

    // =========================================================================
    // RUT
    // =========================================================================
    //
    // JavaScript solamente:
    //
    // - limpia;
    // - formatea visualmente.
    //
    // NO se exige el RUT para aplicar un código.
    //
    // La validación definitiva del RUT debe realizarla Django.
    // =========================================================================

    const campoRut = document.getElementById(
        "id_rut"
    );

    function limpiarRut(
        valor
    ) {
        return String(
            valor || ""
        )
            .replace(
                /[^0-9kK]/g,
                ""
            )
            .toUpperCase()
            .slice(
                0,
                9
            );
    }

    function formatearRut(
        valor
    ) {
        const rutLimpio = limpiarRut(
            valor
        );

        if (rutLimpio.length <= 1) {
            return rutLimpio;
        }

        const cuerpo = rutLimpio.slice(
            0,
            -1
        );

        const digitoVerificador = (
            rutLimpio.slice(-1)
        );

        const cuerpoFormateado = (
            cuerpo.replace(
                /\B(?=(\d{3})+(?!\d))/g,
                "."
            )
        );

        return (
            `${cuerpoFormateado}-`
            + digitoVerificador
        );
    }

    if (campoRut) {
        campoRut.addEventListener(
            "input",
            () => {
                campoRut.value = formatearRut(
                    campoRut.value
                );
            }
        );

        campoRut.addEventListener(
            "blur",
            () => {
                campoRut.value = formatearRut(
                    campoRut.value
                );
            }
        );

        if (campoRut.value) {
            campoRut.value = formatearRut(
                campoRut.value
            );
        }
    }

    // =========================================================================
    // TELÉFONO CHILENO
    // =========================================================================
    //
    // Visualmente:
    //
    // +56 | 912345678
    //
    // Django recibe solamente:
    //
    // 912345678
    // =========================================================================

    const telefonoInput = document.getElementById(
        "id_telefono"
    );

    const PREFIJO_TELEFONO = "+56";

    function obtenerDigitosTelefono(
        valor
    ) {
        let texto = String(
            valor || ""
        ).trim();

        if (
            texto.startsWith(
                PREFIJO_TELEFONO
            )
        ) {
            texto = texto.substring(
                PREFIJO_TELEFONO.length
            );
        }

        let digitos = texto.replace(
            /\D/g,
            ""
        );

        /*
         * Permitir también:
         *
         * 56912345678
         */

        if (
            digitos.length === 11
            && digitos.startsWith(
                "56"
            )
        ) {
            digitos = digitos.substring(
                2
            );
        }

        return digitos.substring(
            0,
            9
        );
    }

    function crearControlTelefono() {
        if (!telefonoInput) {
            return;
        }

        if (
            telefonoInput.closest(
                ".checkout-telefono-control"
            )
        ) {
            return;
        }

        const padre = telefonoInput.parentNode;

        if (!padre) {
            return;
        }

        const contenedorTelefono = (
            document.createElement(
                "div"
            )
        );

        contenedorTelefono.className = (
            "checkout-telefono-control"
        );

        const prefijoTelefono = (
            document.createElement(
                "span"
            )
        );

        prefijoTelefono.className = (
            "checkout-telefono-prefijo"
        );

        prefijoTelefono.textContent = (
            PREFIJO_TELEFONO
        );

        prefijoTelefono.setAttribute(
            "aria-hidden",
            "true"
        );

        padre.insertBefore(
            contenedorTelefono,
            telefonoInput
        );

        contenedorTelefono.appendChild(
            prefijoTelefono
        );

        contenedorTelefono.appendChild(
            telefonoInput
        );
    }

    function normalizarTelefonoChile() {
        if (!telefonoInput) {
            return;
        }

        telefonoInput.value = (
            obtenerDigitosTelefono(
                telefonoInput.value
            )
        );
    }

    if (telefonoInput) {
        const numeroInicial = (
            obtenerDigitosTelefono(
                telefonoInput.value
            )
        );

        crearControlTelefono();

        telefonoInput.setAttribute(
            "maxlength",
            "9"
        );

        telefonoInput.setAttribute(
            "inputmode",
            "numeric"
        );

        telefonoInput.setAttribute(
            "autocomplete",
            "tel-national"
        );

        telefonoInput.setAttribute(
            "pattern",
            "[0-9]{9}"
        );

        telefonoInput.setAttribute(
            "placeholder",
            "912345678"
        );

        telefonoInput.setAttribute(
            "title",
            (
                "Ingresa un número de "
                + "teléfono de 9 dígitos."
            )
        );

        telefonoInput.value = numeroInicial;

        telefonoInput.addEventListener(
            "input",
            () => {
                telefonoInput.setCustomValidity(
                    ""
                );

                normalizarTelefonoChile();
            }
        );

        telefonoInput.addEventListener(
            "paste",
            (evento) => {
                evento.preventDefault();

                const portapapeles = (
                    evento.clipboardData
                    || window.clipboardData
                );

                const textoPegado = portapapeles
                    ? portapapeles.getData(
                        "text"
                    )
                    : "";

                telefonoInput.value = (
                    obtenerDigitosTelefono(
                        textoPegado
                    )
                );

                telefonoInput.setCustomValidity(
                    ""
                );
            }
        );
    }

    // =========================================================================
    // LIMPIAR EJEMPLOS VISUALES
    // =========================================================================
    //
    // Conserva la lógica que anteriormente
    // estaba dentro de checkout.html.
    // =========================================================================

    formulario
        .querySelectorAll(
            "input[placeholder], textarea[placeholder]"
        )
        .forEach(
            (campo) => {
                const placeholder = String(
                    campo.getAttribute(
                        "placeholder"
                    )
                    || ""
                );

                if (
                    /antonio/i.test(
                        placeholder
                    )
                ) {
                    campo.removeAttribute(
                        "placeholder"
                    );
                }
            }
        );

    formulario
        .querySelectorAll(
            ".helptext, small"
        )
        .forEach(
            (elemento) => {
                const texto = String(
                    elemento.textContent
                    || ""
                ).trim();

                if (
                    /^ejemplo\s*:/i.test(
                        texto
                    )
                    || /ejemplo.*antonio/i.test(
                        texto
                    )
                ) {
                    elemento.remove();
                }
            }
        );

    // =========================================================================
    // REGIONES, COMUNAS Y DIRECCIÓN
    // =========================================================================

    const regionSelect = document.getElementById(
        "id_region"
    );

    const comunaSelect = document.getElementById(
        "id_comuna"
    );

    const direccionInput = document.getElementById(
        "id_direccion"
    );

    const numeroDireccionInput = document.getElementById(
        "id_numero_direccion"
    );

    const comunasScript = document.getElementById(
        "comunas-por-region"
    );

    let comunasPorRegion = {};

    if (comunasScript) {
        try {
            comunasPorRegion = JSON.parse(
                comunasScript.textContent
            );
        } catch (error) {
            console.error(
                (
                    "No fue posible cargar las "
                    + "comunas de Chile."
                ),
                error
            );
        }
    }

    function crearOpcion(
        valor,
        texto,
        seleccionada = false
    ) {
        const opcion = document.createElement(
            "option"
        );

        opcion.value = valor;
        opcion.textContent = texto;
        opcion.selected = seleccionada;

        return opcion;
    }

    function cargarComunas(
        region,
        comunaSeleccionada = ""
    ) {
        if (!comunaSelect) {
            return;
        }

        const comunas = Array.isArray(
            comunasPorRegion[region]
        )
            ? comunasPorRegion[region]
            : [];

        comunaSelect.replaceChildren();

        if (
            !region
            || comunas.length === 0
        ) {
            comunaSelect.appendChild(
                crearOpcion(
                    "",
                    (
                        "Selecciona primero "
                        + "una región"
                    ),
                    true
                )
            );

            comunaSelect.value = "";
            comunaSelect.disabled = true;

            comunaSelect.setAttribute(
                "aria-disabled",
                "true"
            );

            return;
        }

        comunaSelect.appendChild(
            crearOpcion(
                "",
                "Selecciona una comuna"
            )
        );

        comunas.forEach(
            (comuna) => {
                comunaSelect.appendChild(
                    crearOpcion(
                        comuna,
                        comuna,
                        (
                            comuna
                            === comunaSeleccionada
                        )
                    )
                );
            }
        );

        comunaSelect.disabled = false;

        comunaSelect.removeAttribute(
            "aria-disabled"
        );

        if (
            comunaSeleccionada
            && comunas.includes(
                comunaSeleccionada
            )
        ) {
            comunaSelect.value = (
                comunaSeleccionada
            );
        } else {
            comunaSelect.value = "";
        }
    }

    function obtenerRegionActual() {
        return String(
            regionSelect?.value
            || ""
        ).trim();
    }

    function obtenerComunaActual() {
        return String(
            comunaSelect?.value
            || ""
        ).trim();
    }

    function obtenerDireccionActual() {
        return String(
            direccionInput?.value
            || ""
        ).trim();
    }

    function obtenerNumeroDireccionActual() {
        return String(
            numeroDireccionInput?.value
            || ""
        ).trim();
    }

    // =========================================================================
    // TIEMPO ESTIMADO BLUE EXPRESS
    // =========================================================================

    const tiempoEstimadoElemento = (
        document.getElementById(
            "checkoutTiempoEstimado"
        )
    );

    const REGION_SANTIAGO = new Set([
        "Metropolitana",
    ]);

    const REGIONES_CENTRO = new Set([
        "Coquimbo",
        "Valparaíso",
        "O’Higgins",
        "O'Higgins",
        "Maule",
        "Ñuble",
        "Biobío",
        "La Araucanía",
        "Los Ríos",
        "Los Lagos",
    ]);

    const REGIONES_EXTREMO = new Set([
        "Arica y Parinacota",
        "Tarapacá",
        "Antofagasta",
        "Atacama",
        "Aysén",
        "Magallanes",
    ]);

    function obtenerTiempoEntrega(
        region
    ) {
        const regionNormalizada = String(
            region || ""
        ).trim();

        if (
            REGION_SANTIAGO.has(
                regionNormalizada
            )
        ) {
            return 48;
        }

        if (
            REGIONES_CENTRO.has(
                regionNormalizada
            )
            || REGIONES_EXTREMO.has(
                regionNormalizada
            )
        ) {
            return 72;
        }

        return null;
    }

    function actualizarTiempoEntrega() {
        if (
            !regionSelect
            || !tiempoEstimadoElemento
        ) {
            return;
        }

        const horas = obtenerTiempoEntrega(
            regionSelect.value
        );

        const textoNuevo = horas
            ? `${horas} hrs`
            : "Selecciona una región";

        /*
         * Evita mutaciones innecesarias y,
         * por lo tanto, ciclos del MutationObserver.
         */

        if (
            tiempoEstimadoElemento
                .textContent
                .trim()
            !== textoNuevo
        ) {
            tiempoEstimadoElemento.textContent = (
                textoNuevo
            );
        }
    }

    // =========================================================================
    // CÓDIGO DE DESCUENTO
    // =========================================================================

    const inputCupon = document.getElementById(
        "id_codigo_descuento"
    );

    const botonCupon = document.getElementById(
        "checkoutAplicarCupon"
    );

    const mensajeCupon = document.getElementById(
        "checkoutMensajeCupon"
    );

    const filaDescuento = document.getElementById(
        "checkoutFilaDescuento"
    );

    const descuentoElemento = document.getElementById(
        "checkoutDescuento"
    );

    const codigoAplicadoElemento = (
        document.getElementById(
            "checkoutCodigoAplicado"
        )
    );

    const filaSubtotalConDescuento = (
        document.getElementById(
            "checkoutFilaSubtotalConDescuento"
        )
    );

    const subtotalConDescuentoElemento = (
        document.getElementById(
            "checkoutSubtotalConDescuento"
        )
    );

    const tipoDescuentoElemento = (
        document.getElementById(
            "checkoutTipoDescuentoAplicado"
        )
    );

    const despachoElemento = document.getElementById(
        "checkoutDespacho"
    );

    const totalElemento = document.getElementById(
        "checkoutTotal"
    );

    const resumenUrl = String(
        checkout.dataset.resumenUrl
        || ""
    ).trim();

    const csrfInput = formulario.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    );

    function normalizarCodigo(
        codigo
    ) {
        return String(
            codigo || ""
        )
            .trim()
            .toUpperCase()
            .replace(
                /[^A-Z0-9_-]/g,
                ""
            )
            .slice(
                0,
                64
            );
    }

    function mostrarMensajeCupon(
        mensaje,
        tipo = ""
    ) {
        if (!mensajeCupon) {
            return;
        }

        mensajeCupon.textContent = (
            mensaje || ""
        );

        mensajeCupon.classList.remove(
            "checkout-cupon__mensaje--error",
            "checkout-cupon__mensaje--exito"
        );

        if (tipo === "error") {
            mensajeCupon.classList.add(
                "checkout-cupon__mensaje--error"
            );
        }

        if (tipo === "exito") {
            mensajeCupon.classList.add(
                "checkout-cupon__mensaje--exito"
            );
        }
    }

    function establecerEstadoBotonCupon(
        cargando
    ) {
        if (!botonCupon) {
            return;
        }

        botonCupon.disabled = cargando;

        const texto = botonCupon.querySelector(
            "span"
        );

        if (texto) {
            texto.textContent = cargando
                ? "Validando..."
                : "Aplicar";
        }
    }

    // =========================================================================
    // FORMATO MONETARIO CHILENO
    // =========================================================================

    const selectoresMonetarios = [
        ".checkout-producto__precio-original",
        ".checkout-producto__precio-oferta",
        ".checkout-producto__precio-normal",
        ".checkout-producto__ahorro-unitario",
        ".checkout-producto__precio-cada-uno",
        ".checkout-producto__total-original",
        ".checkout-producto__total > strong",
        "#checkoutTotalProductosOriginal",
        "#checkoutAhorroOfertas",
        "#checkoutSubtotal",
        "#checkoutDescuento",
        "#checkoutSubtotalConDescuento",
        "#checkoutDespacho",
        "#checkoutTotal",
    ];

    function normalizarMilesChile(
        texto
    ) {
        if (!texto) {
            return texto;
        }

        return texto.replace(
            /(-?\$)\s*([\d.,]+)/g,
            (
                coincidencia,
                simbolo,
                numero
            ) => {
                const soloDigitos = (
                    numero.replace(
                        /[^\d]/g,
                        ""
                    )
                );

                if (!soloDigitos) {
                    return coincidencia;
                }

                const numeroEntero = parseInt(
                    soloDigitos,
                    10
                );

                if (
                    Number.isNaN(
                        numeroEntero
                    )
                ) {
                    return coincidencia;
                }

                const formateado = (
                    new Intl.NumberFormat(
                        "es-CL",
                        {
                            maximumFractionDigits: 0,
                        }
                    ).format(
                        numeroEntero
                    )
                );

                return (
                    `${simbolo}${formateado}`
                );
            }
        );
    }

    function contieneMonto(
        texto
    ) {
        return (
            /-?\$\s*[\d.,]+/.test(
                texto
            )
        );
    }

    function formatearElemento(
        elemento
    ) {
        if (!elemento) {
            return;
        }

        const textoOriginal = String(
            elemento.textContent
            || ""
        ).trim();

        if (!textoOriginal) {
            return;
        }

        if (
            !contieneMonto(
                textoOriginal
            )
        ) {
            return;
        }

        let textoNuevo = normalizarMilesChile(
            textoOriginal
        );

        textoNuevo = textoNuevo.replace(
            /\s+CLP\b/gi,
            ""
        );

        textoNuevo = (
            `${textoNuevo} CLP`
        );

        /*
         * Solo modificamos el DOM si realmente
         * cambió el contenido.
         */

        if (
            textoNuevo !== textoOriginal
        ) {
            elemento.textContent = textoNuevo;
        }
    }

    function aplicarFormatoMonetario() {
        selectoresMonetarios.forEach(
            (selector) => {
                document
                    .querySelectorAll(
                        selector
                    )
                    .forEach(
                        formatearElemento
                    );
            }
        );
    }

    // =========================================================================
    // ACTUALIZAR RESUMEN
    // =========================================================================

    function actualizarResumen(
        datos
    ) {
        if (!datos) {
            return;
        }

        const descuento = Number(
            datos.descuento
            || 0
        );

        // =====================================================================
        // FILA DESCUENTO
        // =====================================================================

        if (filaDescuento) {
            filaDescuento.hidden = (
                descuento <= 0
            );
        }

        if (descuentoElemento) {
            const textoDescuento = String(
                datos.descuento_formateado
                || "$0"
            );

            descuentoElemento.textContent = (
                textoDescuento.startsWith("-")
                    ? textoDescuento
                    : `-${textoDescuento}`
            );
        }

        // =====================================================================
        // CÓDIGO APLICADO
        // =====================================================================

        if (codigoAplicadoElemento) {
            codigoAplicadoElemento.textContent = (
                datos.codigo_aplicado
                || ""
            );
        }

        // =====================================================================
        // SUBTOTAL DESPUÉS DEL DESCUENTO
        // =====================================================================

        if (filaSubtotalConDescuento) {
            filaSubtotalConDescuento.hidden = (
                descuento <= 0
            );
        }

        if (
            subtotalConDescuentoElemento
            && datos.subtotal_con_descuento_formateado
        ) {
            subtotalConDescuentoElemento.textContent = (
                datos.subtotal_con_descuento_formateado
            );
        }

        // =====================================================================
        // TIPO DE DESCUENTO
        // =====================================================================

        if (tipoDescuentoElemento) {
            const porcentaje = Number(
                datos.porcentaje_descuento
                || 0
            );

            if (descuento <= 0) {
                tipoDescuentoElemento.textContent = "";

            } else if (porcentaje > 0) {
                tipoDescuentoElemento.textContent = (
                    `${porcentaje}% aplicado al subtotal`
                );

            } else {
                tipoDescuentoElemento.textContent = (
                    "Descuento de monto fijo"
                );
            }
        }

        // =====================================================================
        // DESPACHO
        // =====================================================================

        if (
            despachoElemento
            && datos.despacho_formateado
        ) {
            despachoElemento.textContent = (
                datos.despacho_formateado
            );

            despachoElemento.removeAttribute(
                "aria-busy"
            );
        }

        // =====================================================================
        // TOTAL
        // =====================================================================

        if (
            totalElemento
            && datos.total_formateado
        ) {
            totalElemento.textContent = (
                datos.total_formateado
            );
        }

        aplicarFormatoMonetario();
    }

    // =========================================================================
    // COTIZACIÓN BLUE EXPRESS
    // =========================================================================

    let temporizadorCotizacionEnvio = null;
    let solicitudEnvioActual = null;

    const RETARDO_COTIZACION_ENVIO = 900;

    function despachoListoParaCotizar() {
        const region = obtenerRegionActual();

        /*
         * La tarifa depende de la región/zona.
         *
         * La comuna, calle y número siguen siendo
         * obligatorios para finalizar el checkout,
         * pero no para visualizar la tarifa.
         */

        return Boolean(
            region
        );
    }

    function mostrarEnvioPendiente() {
        if (!despachoElemento) {
            return;
        }

        despachoElemento.textContent = (
            "Completa los datos de envío"
        );

        despachoElemento.removeAttribute(
            "aria-busy"
        );
    }

    function mostrarEnvioCotizando() {
        if (!despachoElemento) {
            return;
        }

        despachoElemento.textContent = (
            "Calculando..."
        );

        despachoElemento.setAttribute(
            "aria-busy",
            "true"
        );
    }

    function cancelarCotizacionPendiente() {
        if (temporizadorCotizacionEnvio) {
            window.clearTimeout(
                temporizadorCotizacionEnvio
            );

            temporizadorCotizacionEnvio = null;
        }

        if (solicitudEnvioActual) {
            solicitudEnvioActual.abort();

            solicitudEnvioActual = null;
        }
    }

    // =========================================================================
    // CONSTRUIR DATOS PARA AJAX
    // =========================================================================

    function construirDatosResumen() {
        const cuerpo = new URLSearchParams();

        if (csrfInput) {
            cuerpo.set(
                "csrfmiddlewaretoken",
                csrfInput.value
            );
        }

        // =====================================================================
        // RUT OPCIONAL
        // =====================================================================
        //
        // MUY IMPORTANTE:
        //
        // Un RUT vacío NO bloquea la solicitud.
        //
        // El usuario puede aplicar el código antes
        // de completar sus datos personales.
        // =====================================================================

        if (campoRut) {
            const rutActual = String(
                campoRut.value
                || ""
            ).trim();

            cuerpo.set(
                "rut",
                rutActual
                    ? formatearRut(
                        rutActual
                    )
                    : ""
            );

        } else {
            cuerpo.set(
                "rut",
                ""
            );
        }

        // =====================================================================
        // CÓDIGO DE DESCUENTO
        // =====================================================================

        if (inputCupon) {
            cuerpo.set(
                "codigo_descuento",
                normalizarCodigo(
                    inputCupon.value
                )
            );
        } else {
            cuerpo.set(
                "codigo_descuento",
                ""
            );
        }

        // =====================================================================
        // DATOS DE ENVÍO
        // =====================================================================

        cuerpo.set(
            "region",
            obtenerRegionActual()
        );

        cuerpo.set(
            "comuna",
            obtenerComunaActual()
        );

        cuerpo.set(
            "direccion",
            obtenerDireccionActual()
        );

        cuerpo.set(
            "numero_direccion",
            obtenerNumeroDireccionActual()
        );

        return cuerpo;
    }

    // =========================================================================
    // SOLICITAR RESUMEN
    // =========================================================================

    async function solicitarResumenCheckout(
        signal = undefined
    ) {
        if (!resumenUrl) {
            throw new Error(
                (
                    "No se configuró la URL "
                    + "del resumen del checkout."
                )
            );
        }

        const respuesta = await fetch(
            resumenUrl,
            {
                method: "POST",

                headers: {
                    "Content-Type": (
                        "application/x-www-form-urlencoded"
                    ),

                    "X-Requested-With": (
                        "XMLHttpRequest"
                    ),
                },

                body: construirDatosResumen(),

                signal,
            }
        );

        /*
         * Primero leemos como texto para poder
         * mostrar un error más claro si Django
         * devuelve HTML inesperadamente.
         */

        const textoRespuesta = await respuesta.text();

        let datos;

        try {
            datos = textoRespuesta
                ? JSON.parse(
                    textoRespuesta
                )
                : {};

        } catch (error) {
            console.error(
                (
                    "El endpoint del resumen "
                    + "no devolvió JSON válido."
                ),
                textoRespuesta
            );

            throw new Error(
                (
                    "El servidor no entregó "
                    + "una respuesta válida."
                )
            );
        }

        return {
            respuesta,
            datos,
        };
    }

    // =========================================================================
    // COTIZAR ENVÍO
    // =========================================================================

    async function cotizarEnvio() {
        if (!despachoListoParaCotizar()) {
            mostrarEnvioPendiente();

            return;
        }

        if (!resumenUrl) {
            return;
        }

        if (solicitudEnvioActual) {
            solicitudEnvioActual.abort();
        }

        const controlador = (
            new AbortController()
        );

        solicitudEnvioActual = controlador;

        mostrarEnvioCotizando();

        try {
            const {
                respuesta,
                datos,
            } = await solicitarResumenCheckout(
                controlador.signal
            );

            if (
                !respuesta.ok
                || datos.ok === false
            ) {
                /*
                 * MUY IMPORTANTE:
                 *
                 * NO utilizamos datos.mensaje aquí.
                 *
                 * datos.mensaje puede ser:
                 *
                 * "Ingresa tu RUT..."
                 * "Código inválido..."
                 *
                 * y ese mensaje NO debe aparecer
                 * dentro de la fila "Despacho".
                 */

                if (despachoElemento) {
                    despachoElemento.textContent = (
                        datos.mensaje_despacho
                        || (
                            despachoListoParaCotizar()
                                ? (
                                    "No fue posible "
                                    + "calcular el despacho"
                                )
                                : (
                                    "Completa los "
                                    + "datos de envío"
                                )
                        )
                    );

                    despachoElemento.removeAttribute(
                        "aria-busy"
                    );
                }

                return;
            }

            actualizarResumen(
                datos
            );

            actualizarTiempoEntrega();

        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }

            console.error(
                "Error cotizando despacho:",
                error
            );

            if (despachoElemento) {
                despachoElemento.textContent = (
                    "No disponible"
                );

                despachoElemento.removeAttribute(
                    "aria-busy"
                );
            }

        } finally {
            /*
             * Evita que una solicitud antigua
             * borre la referencia de una nueva.
             */

            if (
                solicitudEnvioActual
                === controlador
            ) {
                solicitudEnvioActual = null;
            }
        }
    }

    function programarCotizacionEnvio() {
        if (temporizadorCotizacionEnvio) {
            window.clearTimeout(
                temporizadorCotizacionEnvio
            );

            temporizadorCotizacionEnvio = null;
        }

        if (!despachoListoParaCotizar()) {
            mostrarEnvioPendiente();

            return;
        }

        mostrarEnvioCotizando();

        temporizadorCotizacionEnvio = (
            window.setTimeout(
                () => {
                    temporizadorCotizacionEnvio = null;

                    cotizarEnvio();
                },
                RETARDO_COTIZACION_ENVIO
            )
        );
    }

    // =========================================================================
    // REGIÓN Y COMUNA
    // =========================================================================

    let ultimaRegionAutocompletada = (
        obtenerRegionActual()
    );

    if (
        regionSelect
        && comunaSelect
        && comunasScript
    ) {
        const regionInicial = (
            obtenerRegionActual()
            || String(
                checkout.dataset.regionSeleccionada
                || ""
            ).trim()
        );

        const comunaInicial = (
            String(
                comunaSelect.value
                || checkout.dataset.comunaSeleccionada
                || ""
            ).trim()
        );

        cargarComunas(
            regionInicial,
            comunaInicial
        );

        if (
            regionInicial
            && !regionSelect.value
        ) {
            regionSelect.value = regionInicial;
        }

        ultimaRegionAutocompletada = (
            obtenerRegionActual()
        );

        regionSelect.addEventListener(
            "change",
            () => {
                cancelarCotizacionPendiente();

                cargarComunas(
                    regionSelect.value,
                    ""
                );

                ultimaRegionAutocompletada = (
                    obtenerRegionActual()
                );

                actualizarTiempoEntrega();

                if (regionSelect.value) {
                    programarCotizacionEnvio();

                } else {
                    mostrarEnvioPendiente();
                }

                if (!comunaSelect.disabled) {
                    comunaSelect.focus();
                }
            }
        );
    }

    if (comunaSelect) {
        comunaSelect.addEventListener(
            "change",
            () => {
                cancelarCotizacionPendiente();

                if (
                    obtenerRegionActual()
                ) {
                    programarCotizacionEnvio();

                } else {
                    mostrarEnvioPendiente();
                }

                if (
                    comunaSelect.value
                    && direccionInput
                ) {
                    direccionInput.focus();
                }
            }
        );
    }

    // =========================================================================
    // APLICAR CÓDIGO DE DESCUENTO
    // =========================================================================

    async function aplicarCupon(
        codigoForzado = null
    ) {
        if (!inputCupon) {
            console.error(
                (
                    "No existe el input "
                    + "#id_codigo_descuento."
                )
            );

            return;
        }

        if (
            !botonCupon
            || !csrfInput
        ) {
            return;
        }

        if (!resumenUrl) {
            mostrarMensajeCupon(
                (
                    "No se configuró la URL "
                    + "para validar descuentos."
                ),
                "error"
            );

            return;
        }

        const codigo = normalizarCodigo(
            codigoForzado !== null
                ? codigoForzado
                : inputCupon.value
        );

        inputCupon.value = codigo;

        // =====================================================================
        // ÚNICA VALIDACIÓN DEL FRONTEND:
        // DEBE EXISTIR UN CÓDIGO
        // =====================================================================
        //
        // NO pedimos RUT aquí.
        //
        // El RUT podrá estar completamente vacío.
        // =====================================================================

        if (!codigo) {
            mostrarMensajeCupon(
                "Ingresa un código de descuento.",
                "error"
            );

            inputCupon.focus();

            return;
        }

        establecerEstadoBotonCupon(
            true
        );

        mostrarMensajeCupon(
            "Validando código..."
        );

        try {
            const {
                respuesta,
                datos,
            } = await solicitarResumenCheckout();

            /*
             * Solo actualizamos los montos si el
             * servidor entregó información utilizable.
             */

            if (
                datos
                && typeof datos === "object"
            ) {
                actualizarResumen(
                    datos
                );
            }

            if (
                !respuesta.ok
                || datos.ok === false
            ) {
                mostrarMensajeCupon(
                    (
                        datos.mensaje
                        || datos.error_descuento
                        || (
                            "El código no pudo "
                            + "aplicarse."
                        )
                    ),
                    "error"
                );

                return;
            }

            if (datos.codigo_aplicado) {
                mostrarMensajeCupon(
                    (
                        datos.mensaje
                        || (
                            `Código ${
                                datos.codigo_aplicado
                            } aplicado.`
                        )
                    ),
                    "exito"
                );

                return;
            }

            if (
                Number(
                    datos.descuento
                    || 0
                ) > 0
            ) {
                mostrarMensajeCupon(
                    (
                        datos.mensaje
                        || "Código aplicado correctamente."
                    ),
                    "exito"
                );

                return;
            }

            mostrarMensajeCupon(
                (
                    datos.mensaje
                    || "No hay un código aplicado."
                )
            );

        } catch (error) {
            console.error(
                (
                    "Error validando "
                    + "el descuento:"
                ),
                error
            );

            mostrarMensajeCupon(
                (
                    "No fue posible validar "
                    + "el código. Intenta "
                    + "nuevamente."
                ),
                "error"
            );

        } finally {
            establecerEstadoBotonCupon(
                false
            );
        }
    }

    // =========================================================================
    // EVENTOS DEL CÓDIGO
    // =========================================================================

    if (!inputCupon) {
        console.error(
            (
                "El formulario Django no renderizó "
                + "codigo_descuento."
            )
        );
    }

    if (
        inputCupon
        && botonCupon
    ) {
        inputCupon.addEventListener(
            "input",
            () => {
                inputCupon.value = (
                    normalizarCodigo(
                        inputCupon.value
                    )
                );
            }
        );

        inputCupon.addEventListener(
            "keydown",
            (evento) => {
                if (
                    evento.key !== "Enter"
                ) {
                    return;
                }

                evento.preventDefault();

                aplicarCupon();
            }
        );

        botonCupon.addEventListener(
            "click",
            () => {
                aplicarCupon();
            }
        );
    }

    // =========================================================================
    // CÓDIGOS PERSONALES / PREMIOS
    // =========================================================================

    document.querySelectorAll(
        (
            ".checkout-premio, "
            + ".checkout-codigo-personal"
        )
    ).forEach(
        (boton) => {
            boton.addEventListener(
                "click",
                () => {
                    if (!inputCupon) {
                        return;
                    }

                    const codigo = normalizarCodigo(
                        boton.dataset.codigo
                    );

                    if (!codigo) {
                        return;
                    }

                    inputCupon.value = codigo;

                    aplicarCupon(
                        codigo
                    );
                }
            );
        }
    );

    // =========================================================================
    // AUTOCOMPLETADO DEL NAVEGADOR
    // =========================================================================
    //
    // Chrome y Safari pueden completar los campos
    // después de DOMContentLoaded sin lanzar change.
    // =========================================================================

    function sincronizarAutocompletadoEnvio() {
        const regionActual = (
            obtenerRegionActual()
        );

        const comunaActual = (
            obtenerComunaActual()
        );

        if (!regionActual) {
            return;
        }

        if (
            regionSelect
            && comunaSelect
            && regionActual
                !== ultimaRegionAutocompletada
        ) {
            cargarComunas(
                regionActual,
                comunaActual
            );

            ultimaRegionAutocompletada = (
                regionActual
            );
        }

        actualizarTiempoEntrega();

        programarCotizacionEnvio();
    }

    [
        150,
        500,
        1000,
        1800,
    ].forEach(
        (tiempo) => {
            window.setTimeout(
                sincronizarAutocompletadoEnvio,
                tiempo
            );
        }
    );

    window.addEventListener(
        "pageshow",
        () => {
            window.setTimeout(
                sincronizarAutocompletadoEnvio,
                200
            );
        }
    );

    // =========================================================================
    // MÉTODOS DE PAGO
    // =========================================================================

    metodoPagoTarjetas.forEach(
        (metodo) => {
            metodo.addEventListener(
                "click",
                () => {
                    const radio = metodo.querySelector(
                        'input[type="radio"]'
                    );

                    if (
                        radio
                        && !radio.disabled
                    ) {
                        radio.checked = true;

                        radio.dispatchEvent(
                            new Event(
                                "change",
                                {
                                    bubbles: true,
                                }
                            )
                        );
                    }
                }
            );
        }
    );

    // =========================================================================
    // ESTADO INICIAL
    // =========================================================================

    actualizarTiempoEntrega();

    aplicarFormatoMonetario();

    if (
        despachoListoParaCotizar()
    ) {
        programarCotizacionEnvio();

    } else {
        mostrarEnvioPendiente();
    }

    // =========================================================================
    // MUTATION OBSERVER
    // =========================================================================
    //
    // Mantiene el formato CLP después de actualizaciones
    // AJAX del resumen.
    // =========================================================================

    let formatoPendiente = false;

    const observer = new MutationObserver(
        () => {
            if (formatoPendiente) {
                return;
            }

            formatoPendiente = true;

            window.requestAnimationFrame(
                () => {
                    aplicarFormatoMonetario();

                    actualizarTiempoEntrega();

                    formatoPendiente = false;
                }
            );
        }
    );

    observer.observe(
        checkout,
        {
            childList: true,
            subtree: true,
            characterData: true,
        }
    );

    // =========================================================================
    // ENVÍO FINAL DEL FORMULARIO
    // =========================================================================

    formulario.addEventListener(
        "submit",
        (evento) => {
            // =================================================================
            // CÓDIGO
            // =================================================================

            if (inputCupon) {
                inputCupon.value = (
                    normalizarCodigo(
                        inputCupon.value
                    )
                );
            }

            // =================================================================
            // RUT
            // =================================================================
            //
            // Solo formateamos.
            //
            // Django valida su autenticidad.
            // =================================================================

            if (campoRut) {
                campoRut.value = formatearRut(
                    campoRut.value
                );
            }

            // =================================================================
            // TELÉFONO
            // =================================================================

            if (telefonoInput) {
                const digitosTelefono = (
                    obtenerDigitosTelefono(
                        telefonoInput.value
                    )
                );

                if (
                    digitosTelefono.length
                    !== 9
                ) {
                    evento.preventDefault();

                    telefonoInput.setCustomValidity(
                        (
                            "Ingresa un número de "
                            + "teléfono válido de "
                            + "9 dígitos."
                        )
                    );

                    telefonoInput.reportValidity();

                    telefonoInput.focus();

                    return;
                }

                telefonoInput.setCustomValidity(
                    ""
                );

                /*
                 * Django recibe solamente
                 * los 9 dígitos nacionales.
                 */

                telefonoInput.value = (
                    digitosTelefono
                );
            }

            // =================================================================
            // REGIÓN
            // =================================================================

            if (
                regionSelect
                && !regionSelect.value
            ) {
                evento.preventDefault();

                regionSelect.focus();

                return;
            }

            // =================================================================
            // COMUNA
            // =================================================================

            if (
                comunaSelect
                && (
                    comunaSelect.disabled
                    || !comunaSelect.value
                )
            ) {
                evento.preventDefault();

                comunaSelect.focus();

                return;
            }

            // =================================================================
            // DIRECCIÓN
            // =================================================================

            if (
                direccionInput
                && !String(
                    direccionInput.value
                    || ""
                ).trim()
            ) {
                evento.preventDefault();

                direccionInput.focus();

                return;
            }

            // =================================================================
            // NÚMERO
            // =================================================================

            if (
                numeroDireccionInput
                && !String(
                    numeroDireccionInput.value
                    || ""
                ).trim()
            ) {
                evento.preventDefault();

                numeroDireccionInput.focus();

                return;
            }

            // =================================================================
            // VALIDACIÓN HTML
            // =================================================================

            if (
                !formulario.checkValidity()
            ) {
                evento.preventDefault();

                formulario.reportValidity();

                return;
            }

            // =================================================================
            // PROCESANDO PEDIDO
            // =================================================================

            if (!botonConfirmar) {
                return;
            }

            botonConfirmar.disabled = true;

            botonConfirmar.classList.add(
                "checkout-confirmar--cargando"
            );

            botonConfirmar.innerHTML = `
                <span>
                    Procesando pedido...
                </span>

                <span
                    class="carrito-spinner"
                    aria-hidden="true"
                ></span>
            `;
        }
    );
});