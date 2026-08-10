"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const checkout = document.getElementById(
        "checkout"
    );

    const formulario = document.getElementById(
        "checkoutFormulario"
    );

    if (!checkout || !formulario) {
        return;
    }

    // =========================================================================
    // ELEMENTOS GENERALES
    // =========================================================================

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

    // =========================================================================
    // CÓDIGO DE DESCUENTO Y RESUMEN
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
            mensaje
            || ""
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

    function actualizarResumen(
        datos
    ) {
        const descuento = Number(
            datos.descuento
            || 0
        );

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

        if (codigoAplicadoElemento) {
            codigoAplicadoElemento.textContent = (
                datos.codigo_aplicado
                || ""
            );
        }

        if (despachoElemento) {
            despachoElemento.textContent = (
                datos.despacho_formateado
                || "$0"
            );

            despachoElemento.removeAttribute(
                "aria-busy"
            );
        }

        if (totalElemento) {
            totalElemento.textContent = (
                datos.total_formateado
                || "$0"
            );
        }
    }

    // =========================================================================
    // COTIZACIÓN BLUE EXPRESS
    // =========================================================================

    let temporizadorCotizacionEnvio = null;
    let solicitudEnvioActual = null;

    const RETARDO_COTIZACION_ENVIO = 900;

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

    function despachoListoParaCotizar() {
        const region = obtenerRegionActual();
        const comuna = obtenerComunaActual();
        const direccion = obtenerDireccionActual();
        const numero = obtenerNumeroDireccionActual();

        return (
            Boolean(region)
            && Boolean(comuna)
            && direccion.length >= 5
            && numero.length >= 1
        );
    }

    function cancelarCotizacionPendiente() {
        if (temporizadorCotizacionEnvio) {
            clearTimeout(
                temporizadorCotizacionEnvio
            );

            temporizadorCotizacionEnvio = null;
        }

        if (solicitudEnvioActual) {
            solicitudEnvioActual.abort();
            solicitudEnvioActual = null;
        }
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

    function mostrarEnvioCalculando() {
        if (!despachoElemento) {
            return;
        }

        despachoElemento.textContent = (
            "Cotizando..."
        );

        despachoElemento.setAttribute(
            "aria-busy",
            "true"
        );
    }

    function mostrarEnvioError() {
        if (!despachoElemento) {
            return;
        }

        despachoElemento.textContent = (
            "No disponible"
        );

        despachoElemento.removeAttribute(
            "aria-busy"
        );
    }

    function crearCuerpoResumen() {
        const cuerpo = new URLSearchParams();

        cuerpo.set(
            "codigo_descuento",
            normalizarCodigo(
                inputCupon?.value
                || ""
            )
        );

        cuerpo.set(
            "rut",
            limpiarRut(
                campoRut?.value
                || ""
            )
        );

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

    async function solicitarResumenCheckout(
        {
            signal = undefined,
        } = {}
    ) {
        if (!resumenUrl) {
            throw new Error(
                (
                    "No se configuró la URL "
                    + "del resumen del checkout."
                )
            );
        }

        if (!csrfInput) {
            throw new Error(
                (
                    "No se encontró el token "
                    + "CSRF del formulario."
                )
            );
        }

        const cuerpo = crearCuerpoResumen();

        const respuesta = await fetch(
            resumenUrl,
            {
                method: "POST",

                credentials: "same-origin",

                signal,

                headers: {
                    "Accept": (
                        "application/json"
                    ),

                    "Content-Type": (
                        "application/"
                        + "x-www-form-urlencoded; "
                        + "charset=UTF-8"
                    ),

                    "X-CSRFToken": (
                        csrfInput.value
                    ),

                    "X-Requested-With": (
                        "XMLHttpRequest"
                    ),
                },

                body: cuerpo.toString(),
            }
        );

        let datos = {};

        try {
            datos = await respuesta.json();
        } catch (error) {
            throw new Error(
                (
                    "El servidor no devolvió "
                    + "una respuesta JSON válida."
                )
            );
        }

        return {
            respuesta,
            datos,
        };
    }

    async function cotizarEnvioBlueExpress() {
        if (!despachoListoParaCotizar()) {
            mostrarEnvioPendiente();
            return;
        }

        if (!resumenUrl || !csrfInput) {
            console.error(
                (
                    "No existe configuración "
                    + "para cotizar el despacho."
                )
            );

            mostrarEnvioError();

            return;
        }

        if (solicitudEnvioActual) {
            solicitudEnvioActual.abort();
        }

        const controlador = (
            new AbortController()
        );

        solicitudEnvioActual = controlador;

        mostrarEnvioCalculando();

        try {
            const {
                respuesta,
                datos,
            } = await solicitarResumenCheckout(
                {
                    signal: controlador.signal,
                }
            );

            if (
                !respuesta.ok
                || datos.ok === false
            ) {
                throw new Error(
                    datos.mensaje
                    || (
                        "No fue posible calcular "
                        + "el despacho."
                    )
                );
            }

            actualizarResumen(
                datos
            );

        } catch (error) {
            if (
                error.name
                === "AbortError"
            ) {
                return;
            }

            console.error(
                (
                    "Error calculando "
                    + "Blue Express:"
                ),
                error
            );

            mostrarEnvioError();

        } finally {
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
            clearTimeout(
                temporizadorCotizacionEnvio
            );

            temporizadorCotizacionEnvio = null;
        }

        if (!despachoListoParaCotizar()) {
            mostrarEnvioPendiente();
            return;
        }

        mostrarEnvioCalculando();

        temporizadorCotizacionEnvio = (
            setTimeout(
                () => {
                    temporizadorCotizacionEnvio = null;

                    cotizarEnvioBlueExpress();
                },
                RETARDO_COTIZACION_ENVIO
            )
        );
    }

    // =========================================================================
    // EVENTOS REGIÓN / COMUNA / DIRECCIÓN
    // =========================================================================

    if (
        regionSelect
        && comunaSelect
        && comunasScript
    ) {
        const comunaInicial = (
            comunaSelect.value
            || ""
        ).trim();

        cargarComunas(
            regionSelect.value,
            comunaInicial
        );

        regionSelect.addEventListener(
            "change",
            () => {
                cancelarCotizacionPendiente();

                cargarComunas(
                    regionSelect.value,
                    ""
                );

                mostrarEnvioPendiente();

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

                mostrarEnvioPendiente();

                if (
                    comunaSelect.value
                    && direccionInput
                ) {
                    direccionInput.focus();
                }
            }
        );
    }

    if (direccionInput) {
        direccionInput.addEventListener(
            "input",
            () => {
                programarCotizacionEnvio();
            }
        );

        direccionInput.addEventListener(
            "blur",
            () => {
                programarCotizacionEnvio();
            }
        );
    }

    if (numeroDireccionInput) {
        numeroDireccionInput.addEventListener(
            "input",
            () => {
                programarCotizacionEnvio();
            }
        );

        numeroDireccionInput.addEventListener(
            "blur",
            () => {
                programarCotizacionEnvio();
            }
        );
    }

    // =========================================================================
    // CÓDIGO DE DESCUENTO
    // =========================================================================

    async function aplicarCupon(
        codigoForzado = null
    ) {
        if (!inputCupon) {
            console.error(
                (
                    "No existe el input "
                    + "#id_codigo_descuento. "
                    + "Revisa CheckoutForm y "
                    + "checkout.html."
                )
            );

            return;
        }

        if (!botonCupon || !csrfInput) {
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

        if (!codigo) {
            mostrarMensajeCupon(
                (
                    "Ingresa un código "
                    + "de descuento."
                ),
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

            actualizarResumen(
                datos
            );

            if (
                !respuesta.ok
                || datos.ok === false
            ) {
                mostrarMensajeCupon(
                    (
                        datos.mensaje
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

            mostrarMensajeCupon(
                "No hay un código aplicado."
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
                if (evento.key !== "Enter") {
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

                    const codigo = (
                        normalizarCodigo(
                            boton.dataset.codigo
                        )
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
    // ESTADO INICIAL DEL DESPACHO
    // =========================================================================

    if (despachoListoParaCotizar()) {
        programarCotizacionEnvio();
    } else {
        mostrarEnvioPendiente();
    }

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
    // ENVÍO DEL FORMULARIO
    // =========================================================================

    formulario.addEventListener(
        "submit",
        (evento) => {
            if (inputCupon) {
                inputCupon.value = (
                    normalizarCodigo(
                        inputCupon.value
                    )
                );
            }

            if (campoRut) {
                campoRut.value = formatearRut(
                    campoRut.value
                );
            }

            if (
                regionSelect
                && !regionSelect.value
            ) {
                evento.preventDefault();

                regionSelect.focus();

                return;
            }

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

            if (!formulario.checkValidity()) {
                evento.preventDefault();

                formulario.reportValidity();

                return;
            }

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