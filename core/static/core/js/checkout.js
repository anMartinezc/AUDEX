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

    // =========================================================================
    // VALIDAR RUT CHILENO
    // =========================================================================
    //
    // Valida el dígito verificador utilizando
    // el algoritmo oficial módulo 11.
    //
    // Ejemplos:
    //
    // 12.345.678-5 -> válido si el DV corresponde.
    // 12.345.678-1 -> inválido si el DV no corresponde.
    //
    // =========================================================================

    function validarRutChileno(
        valor
    ) {
        const rutLimpio = limpiarRut(
            valor
        );

        // El RUT debe tener:
        //
        // 7 u 8 dígitos de cuerpo
        // + 1 dígito verificador.
        //
        // Total limpio:
        // 8 o 9 caracteres.

        if (
            rutLimpio.length < 8
            || rutLimpio.length > 9
        ) {
            return false;
        }

        const cuerpo = rutLimpio.slice(
            0,
            -1
        );

        const dvIngresado = rutLimpio.slice(
            -1
        );

        if (!/^\d+$/.test(cuerpo)) {
            return false;
        }

        // Evitar cuerpos vacíos o compuestos
        // únicamente por ceros.

        if (
            Number(cuerpo) <= 0
        ) {
            return false;
        }

        let suma = 0;
        let multiplicador = 2;

        for (
            let i = cuerpo.length - 1;
            i >= 0;
            i -= 1
        ) {
            suma += (
                Number(
                    cuerpo[i]
                )
                * multiplicador
            );

            multiplicador += 1;

            if (multiplicador > 7) {
                multiplicador = 2;
            }
        }

        const resultado = (
            11 - (
                suma % 11
            )
        );

        let dvCalculado;

        if (resultado === 11) {
            dvCalculado = "0";

        } else if (resultado === 10) {
            dvCalculado = "K";

        } else {
            dvCalculado = String(
                resultado
            );
        }

        return (
            dvIngresado === dvCalculado
        );
    }

    // =========================================================================
    // EVENTOS DEL RUT
    // =========================================================================

    if (campoRut) {
        campoRut.addEventListener(
            "input",
            () => {
                // -------------------------------------------------------------
                // El usuario modificó el RUT.
                // Eliminamos cualquier error anterior.
                // -------------------------------------------------------------

                campoRut.setCustomValidity(
                    ""
                );

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

                if (!campoRut.value) {
                    campoRut.setCustomValidity(
                        ""
                    );

                    return;
                }

                if (
                    !validarRutChileno(
                        campoRut.value
                    )
                ) {
                    campoRut.setCustomValidity(
                        "El RUT ingresado no es válido."
                    );

                    return;
                }

                campoRut.setCustomValidity(
                    ""
                );
            }
        );

        // =====================================================================
        // RUT INICIAL
        // =====================================================================

        if (campoRut.value) {
            campoRut.value = formatearRut(
                campoRut.value
            );

            if (
                validarRutChileno(
                    campoRut.value
                )
            ) {
                campoRut.setCustomValidity(
                    ""
                );
            }
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

    /*
     * Para cotizar Blue Express basta
     * con conocer la región.
     *
     * Comuna, dirección y número siguen
     * siendo obligatorios para finalizar
     * la compra.
     */

    function despachoListoParaCotizar() {
        const region = obtenerRegionActual();

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
    // CONSTRUIR DATOS PARA EL RESUMEN
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
        // RUT
        // =====================================================================

        if (campoRut) {
            cuerpo.set(
                "rut",
                formatearRut(
                    campoRut.value
                )
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
    // SOLICITAR RESUMEN AL SERVIDOR
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

        const datos = await respuesta.json();

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

        const controlador = new AbortController();

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
                if (despachoElemento) {
                    despachoElemento.textContent = (
                        datos.mensaje_despacho
                        || datos.mensaje
                        || "No disponible"
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

                ultimaRegionAutocompletada = (
                    obtenerRegionActual()
                );

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

    // =========================================================================
    // COMUNA
    // =========================================================================

    if (comunaSelect) {
        comunaSelect.addEventListener(
            "change",
            () => {
                cancelarCotizacionPendiente();

                if (obtenerRegionActual()) {
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

        // =====================================================================
        // VALIDAR CÓDIGO
        // =====================================================================

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

        // =====================================================================
        // OBTENER RUT
        // =====================================================================

        const rutActual = campoRut
            ? limpiarRut(
                campoRut.value
            )
            : "";

        // =====================================================================
        // RUT VACÍO
        // =====================================================================

        if (!rutActual) {
            mostrarMensajeCupon(
                (
                    "Ingresa tu RUT antes "
                    + "de aplicar el código."
                ),
                "error"
            );

            if (campoRut) {
                campoRut.setCustomValidity(
                    ""
                );

                campoRut.focus();
            }

            return;
        }

        // =====================================================================
        // VALIDAR MATEMÁTICAMENTE EL RUT
        // =====================================================================

        if (
            !validarRutChileno(
                rutActual
            )
        ) {
            mostrarMensajeCupon(
                (
                    "El RUT ingresado "
                    + "no es válido."
                ),
                "error"
            );

            if (campoRut) {
                campoRut.setCustomValidity(
                    "El RUT ingresado no es válido."
                );

                campoRut.focus();
            }

            return;
        }

        // =====================================================================
        // RUT VÁLIDO
        // =====================================================================

        if (campoRut) {
            campoRut.setCustomValidity(
                ""
            );

            campoRut.value = formatearRut(
                campoRut.value
            );
        }

        // =====================================================================
        // INICIAR VALIDACIÓN DEL CÓDIGO
        // =====================================================================

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
    // DETECTAR AUTOCOMPLETADO DEL NAVEGADOR
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
            && regionActual !== ultimaRegionAutocompletada
        ) {
            cargarComunas(
                regionActual,
                comunaActual
            );

            ultimaRegionAutocompletada = (
                regionActual
            );
        }

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

    // =========================================================================
    // VOLVER ATRÁS / RESTAURACIÓN DEL NAVEGADOR
    // =========================================================================

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
            // =================================================================
            // NORMALIZAR CÓDIGO
            // =================================================================

            if (inputCupon) {
                inputCupon.value = (
                    normalizarCodigo(
                        inputCupon.value
                    )
                );
            }

            // =================================================================
            // VALIDAR Y NORMALIZAR RUT
            // =================================================================

            if (campoRut) {
                campoRut.value = formatearRut(
                    campoRut.value
                );

                if (
                    !validarRutChileno(
                        campoRut.value
                    )
                ) {
                    evento.preventDefault();

                    campoRut.setCustomValidity(
                        "El RUT ingresado no es válido."
                    );

                    campoRut.focus();

                    campoRut.reportValidity();

                    return;
                }

                campoRut.setCustomValidity(
                    ""
                );
            }

            // =================================================================
            // REGIÓN OBLIGATORIA
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
            // COMUNA OBLIGATORIA
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
            // DIRECCIÓN OBLIGATORIA
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
            // NÚMERO DE DIRECCIÓN OBLIGATORIO
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
            // VALIDACIÓN HTML DEL FORMULARIO
            // =================================================================

            if (!formulario.checkValidity()) {
                evento.preventDefault();

                formulario.reportValidity();

                return;
            }

            // =================================================================
            // ESTADO DE PROCESAMIENTO
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