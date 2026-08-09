"use strict";

document.addEventListener("DOMContentLoaded", () => {

    // =====================================================================
    // CONFIGURACIÓN GENERAL
    // =====================================================================

    const SELECTOR_CONTENEDOR = ".gd__contenedor";

    const formateadorClp = new Intl.NumberFormat(
        "es-CL",
        {
            maximumFractionDigits: 0,
        }
    );


    // =====================================================================
    // SWEETALERT2
    // =====================================================================

    let promesaSweetAlert = null;


    function asegurarSweetAlert() {

        if (
            typeof window.Swal !== "undefined"
            && typeof window.Swal.fire === "function"
        ) {
            return Promise.resolve(
                window.Swal
            );
        }


        if (promesaSweetAlert) {
            return promesaSweetAlert;
        }


        promesaSweetAlert = new Promise(
            (resolve, reject) => {

                // ---------------------------------------------------------
                // CSS
                // ---------------------------------------------------------

                if (
                    !document.querySelector(
                        'link[data-sweetalert-audex="true"]'
                    )
                ) {
                    const enlace = (
                        document.createElement(
                            "link"
                        )
                    );

                    enlace.rel = "stylesheet";

                    enlace.href = (
                        "https://cdn.jsdelivr.net/npm/"
                        + "sweetalert2@11/dist/"
                        + "sweetalert2.min.css"
                    );

                    enlace.dataset.sweetalertAudex = (
                        "true"
                    );

                    document.head.appendChild(
                        enlace
                    );
                }


                // ---------------------------------------------------------
                // JS
                // ---------------------------------------------------------

                const scriptExistente = (
                    document.querySelector(
                        'script[data-sweetalert-audex="true"]'
                    )
                );

                if (scriptExistente) {

                    scriptExistente.addEventListener(
                        "load",
                        () => {
                            resolve(
                                window.Swal
                            );
                        },
                        {
                            once: true,
                        }
                    );

                    scriptExistente.addEventListener(
                        "error",
                        reject,
                        {
                            once: true,
                        }
                    );

                    return;
                }


                const script = (
                    document.createElement(
                        "script"
                    )
                );

                script.src = (
                    "https://cdn.jsdelivr.net/npm/"
                    + "sweetalert2@11"
                );

                script.async = true;

                script.dataset.sweetalertAudex = (
                    "true"
                );


                script.addEventListener(
                    "load",
                    () => {

                        if (
                            typeof window.Swal !== "undefined"
                        ) {
                            resolve(
                                window.Swal
                            );

                            return;
                        }

                        reject(
                            new Error(
                                "SweetAlert2 no quedó disponible."
                            )
                        );
                    },
                    {
                        once: true,
                    }
                );


                script.addEventListener(
                    "error",
                    reject,
                    {
                        once: true,
                    }
                );


                document.head.appendChild(
                    script
                );
            }
        );


        return promesaSweetAlert;
    }


    async function alerta({
        titulo,
        texto = "",
        icono = "info",
        boton = "Aceptar",
    }) {

        try {

            const Swal = await asegurarSweetAlert();

            return Swal.fire({
                title: titulo,
                text: texto,
                icon: icono,
                confirmButtonText: boton,
                allowOutsideClick: false,
            });

        } catch (error) {

            window.alert(
                `${titulo}\n\n${texto}`
            );

            return null;
        }
    }


    async function confirmarAccion({
        titulo,
        texto,
        icono = "question",
        confirmar = "Confirmar",
        cancelar = "Cancelar",
    }) {

        try {

            const Swal = await asegurarSweetAlert();

            const resultado = await Swal.fire({
                title: titulo,
                text: texto,
                icon: icono,

                showCancelButton: true,

                confirmButtonText: confirmar,
                cancelButtonText: cancelar,

                reverseButtons: true,
                focusCancel: true,

                allowOutsideClick: false,
                allowEscapeKey: true,
            });

            return Boolean(
                resultado.isConfirmed
            );

        } catch (error) {

            return window.confirm(
                `${titulo}\n\n${texto}`
            );
        }
    }


    async function mostrarToast(
        mensaje,
        tipo = "success"
    ) {

        if (!mensaje) {
            return;
        }

        try {

            const Swal = await asegurarSweetAlert();

            await Swal.fire({
                toast: true,
                position: "top-end",

                icon: tipo,
                title: mensaje,

                showConfirmButton: false,

                timer: 2600,
                timerProgressBar: true,

                didOpen: (toast) => {

                    toast.addEventListener(
                        "mouseenter",
                        Swal.stopTimer
                    );

                    toast.addEventListener(
                        "mouseleave",
                        Swal.resumeTimer
                    );
                },
            });

        } catch (error) {

            console.info(
                mensaje
            );
        }
    }


    // Precarga SweetAlert.
    asegurarSweetAlert().catch(
        () => {
            /*
             * Si falla el CDN se utilizarán
             * alert/confirm como respaldo.
             */
        }
    );


    // =====================================================================
    // UTILIDADES
    // =====================================================================

    function convertirNumero(valor) {

        const texto = String(
            valor ?? ""
        )
            .trim()
            .replace(/\s/g, "")
            .replace(/\$/g, "")
            .replace(/\./g, "")
            .replace(",", ".");


        if (!texto) {
            return 0;
        }


        const resultado = Number(
            texto
        );


        if (!Number.isFinite(resultado)) {
            return 0;
        }


        return Math.max(
            resultado,
            0
        );
    }


    function formatearClp(valor) {

        const numero = convertirNumero(
            valor
        );

        return (
            `$${formateadorClp.format(
                Math.round(numero)
            )}`
        );
    }


    function obtenerCampo(
        formulario,
        nombre
    ) {

        if (!formulario) {
            return null;
        }

        return formulario.querySelector(
            `[name="${nombre}"]`
        );
    }


    function limpiarValidez(
        ...campos
    ) {

        campos.forEach(
            (campo) => {

                if (campo) {
                    campo.setCustomValidity(
                        ""
                    );
                }
            }
        );
    }


    function normalizarCodigo(
        campo
    ) {

        if (!campo) {
            return;
        }


        const inicio = (
            campo.selectionStart
        );

        const fin = (
            campo.selectionEnd
        );


        campo.value = String(
            campo.value || ""
        )
            .trimStart()
            .toUpperCase()
            .replace(
                /[^A-Z0-9_-]/g,
                ""
            );


        if (
            inicio !== null
            && fin !== null
            && typeof campo.setSelectionRange
            === "function"
        ) {

            try {

                campo.setSelectionRange(
                    inicio,
                    fin
                );

            } catch (error) {

                /*
                 * Algunos inputs no permiten
                 * cambiar manualmente el cursor.
                 */
            }
        }
    }


    function normalizarTextoFinal(
        campo
    ) {

        if (!campo) {
            return;
        }


        campo.value = String(
            campo.value || ""
        )
            .trim()
            .toUpperCase()
            .replace(
                /[^A-Z0-9_-]/g,
                ""
            );
    }


    function obtenerFechaLocal(valor) {

        if (!valor) {
            return null;
        }


        const fecha = new Date(
            valor
        );


        if (
            Number.isNaN(
                fecha.getTime()
            )
        ) {
            return null;
        }


        return fecha;
    }


    function escucharCampos(
        campos,
        callback
    ) {

        campos.forEach(
            (campo) => {

                if (!campo) {
                    return;
                }


                campo.addEventListener(
                    "input",
                    callback
                );

                campo.addEventListener(
                    "change",
                    callback
                );
            }
        );
    }


    function obtenerNombreElemento(
        boton
    ) {

        return String(
            boton?.dataset?.codigo
            || ""
        ).trim();
    }


    function obtenerTextoBoton(
        boton
    ) {

        return String(
            boton?.textContent
            || ""
        )
            .trim()
            .replace(
                /\s+/g,
                " "
            );
    }


    // =====================================================================
    // BLOQUEO DE BOTONES
    // =====================================================================

    function bloquearBoton(
        boton,
        textoTemporal = "Procesando..."
    ) {

        if (!boton) {
            return;
        }


        boton.disabled = true;

        boton.setAttribute(
            "aria-disabled",
            "true"
        );


        const span = (
            boton.querySelector(
                "span"
            )
        );


        if (span) {

            if (
                !span.dataset.textoOriginal
            ) {
                span.dataset.textoOriginal = (
                    span.textContent.trim()
                );
            }

            span.textContent = (
                textoTemporal
            );

            return;
        }


        if (
            !boton.dataset.textoOriginal
        ) {
            boton.dataset.textoOriginal = (
                boton.textContent.trim()
            );
        }
    }


    function desbloquearBoton(
        boton
    ) {

        if (!boton) {
            return;
        }


        boton.disabled = false;

        boton.removeAttribute(
            "aria-disabled"
        );


        const span = (
            boton.querySelector(
                "span"
            )
        );


        if (
            span
            && span.dataset.textoOriginal
        ) {

            span.textContent = (
                span.dataset.textoOriginal
            );

            delete span.dataset.textoOriginal;
        }


        if (
            boton.dataset.textoOriginal
        ) {
            delete boton.dataset.textoOriginal;
        }
    }


    // =====================================================================
    // MENSAJES DJANGO
    // =====================================================================

    function extraerMensajesDjango(
        documento
    ) {

        const mensajes = [];


        documento.querySelectorAll(
            ".gd__mensaje"
        ).forEach(
            (elemento) => {

                const texto = String(
                    elemento.textContent
                    || ""
                )
                    .trim()
                    .replace(
                        /\s+/g,
                        " "
                    );


                if (!texto) {
                    return;
                }


                let tipo = "info";


                if (
                    elemento.classList.contains(
                        "gd__mensaje--success"
                    )
                ) {
                    tipo = "success";
                }

                else if (
                    elemento.classList.contains(
                        "gd__mensaje--error"
                    )
                    || elemento.classList.contains(
                        "gd__mensaje--danger"
                    )
                ) {
                    tipo = "error";
                }

                else if (
                    elemento.classList.contains(
                        "gd__mensaje--warning"
                    )
                ) {
                    tipo = "warning";
                }


                mensajes.push({
                    texto,
                    tipo,
                });
            }
        );


        return mensajes;
    }


    // =====================================================================
    // ESTADO VISUAL ANTES DE ACTUALIZAR EL PANEL
    // =====================================================================

    function obtenerArchivosAbiertos() {

        return Array.from(
            document.querySelectorAll(
                ".gd__archivo[open]"
            )
        ).map(
            (detalle) => {

                const titulo = (
                    detalle.querySelector(
                        "summary strong"
                    )
                );

                return String(
                    titulo?.textContent
                    || ""
                ).trim();
            }
        ).filter(
            Boolean
        );
    }


    function restaurarArchivosAbiertos(
        titulos
    ) {

        if (!titulos.length) {
            return;
        }


        document.querySelectorAll(
            ".gd__archivo"
        ).forEach(
            (detalle) => {

                const titulo = String(
                    detalle.querySelector(
                        "summary strong"
                    )?.textContent
                    || ""
                ).trim();


                if (
                    titulos.includes(
                        titulo
                    )
                ) {
                    detalle.open = true;
                }
            }
        );
    }


    // =====================================================================
    // REEMPLAZAR EL PANEL SIN RECARGAR PÁGINA
    // =====================================================================

    function reemplazarPanelDesdeHtml(
        html,
        {
            cambiarUrl = null,
            agregarHistorial = false,
        } = {}
    ) {

        const parser = new DOMParser();

        const documento = (
            parser.parseFromString(
                html,
                "text/html"
            )
        );


        const nuevoContenedor = (
            documento.querySelector(
                SELECTOR_CONTENEDOR
            )
        );

        const contenedorActual = (
            document.querySelector(
                SELECTOR_CONTENEDOR
            )
        );


        if (
            !nuevoContenedor
            || !contenedorActual
        ) {
            throw new Error(
                "No fue posible actualizar el panel."
            );
        }


        const posicionScroll = (
            window.scrollY
        );

        const archivosAbiertos = (
            obtenerArchivosAbiertos()
        );

        const mensajes = (
            extraerMensajesDjango(
                documento
            )
        );


        contenedorActual.replaceWith(
            nuevoContenedor
        );


        restaurarArchivosAbiertos(
            archivosAbiertos
        );


        inicializarContenidoDinamico();


        if (cambiarUrl) {

            if (agregarHistorial) {

                window.history.pushState(
                    {},
                    "",
                    cambiarUrl
                );

            } else {

                window.history.replaceState(
                    {},
                    "",
                    cambiarUrl
                );
            }
        }


        window.scrollTo({
            top: posicionScroll,
            behavior: "instant",
        });


        return mensajes;
    }


    // =====================================================================
    // FETCH / AJAX
    // =====================================================================

    async function enviarFormularioAjax(
        formulario,
        boton = null
    ) {

        const metodo = String(
            formulario.method
            || "POST"
        ).toUpperCase();


        const datos = new FormData(
            formulario
        );


        const opciones = {
            method: metodo,

            headers: {
                "X-Requested-With": (
                    "XMLHttpRequest"
                ),
            },

            credentials: "same-origin",
        };


        if (
            metodo !== "GET"
            && metodo !== "HEAD"
        ) {
            opciones.body = datos;
        }


        let url = (
            formulario.action
            || window.location.href
        );


        if (metodo === "GET") {

            const urlObjeto = new URL(
                url,
                window.location.origin
            );

            urlObjeto.search = "";

            datos.forEach(
                (valor, clave) => {

                    if (
                        String(valor).trim() !== ""
                    ) {
                        urlObjeto.searchParams.append(
                            clave,
                            valor
                        );
                    }
                }
            );

            url = urlObjeto.toString();
        }


        if (boton) {
            bloquearBoton(
                boton
            );
        }


        try {

            const respuesta = await fetch(
                url,
                opciones
            );


            const html = await respuesta.text();


            let mensajes = [];


            try {

                mensajes = (
                    reemplazarPanelDesdeHtml(
                        html,
                        {
                            cambiarUrl: (
                                metodo === "GET"
                                    ? respuesta.url
                                    : null
                            ),

                            agregarHistorial: (
                                metodo === "GET"
                            ),
                        }
                    )
                );

            } catch (error) {

                if (!respuesta.ok) {
                    throw error;
                }

                throw new Error(
                    "El servidor respondió correctamente, "
                    + "pero no fue posible actualizar el panel."
                );
            }


            const mensajePrincipal = (
                mensajes.length
                    ? mensajes[0]
                    : null
            );


            if (!respuesta.ok) {

                await alerta({
                    titulo: "No fue posible completar la acción",
                    texto: (
                        mensajePrincipal?.texto
                        || "Revisa los datos ingresados."
                    ),
                    icono: "error",
                });

                return {
                    ok: false,
                    mensajes,
                    respuesta,
                };
            }


            if (mensajePrincipal) {

                await mostrarToast(
                    mensajePrincipal.texto,
                    mensajePrincipal.tipo
                );
            }


            return {
                ok: true,
                mensajes,
                respuesta,
            };

        } catch (error) {

            console.error(
                error
            );


            desbloquearBoton(
                boton
            );


            await alerta({
                titulo: "Ocurrió un problema",
                texto: (
                    "No fue posible comunicarse "
                    + "correctamente con el servidor. "
                    + "Intenta nuevamente."
                ),
                icono: "error",
            });


            return {
                ok: false,
                mensajes: [],
                respuesta: null,
            };
        }
    }


    async function cargarUrlAjax(
        url,
        {
            agregarHistorial = true,
        } = {}
    ) {

        try {

            const respuesta = await fetch(
                url,
                {
                    method: "GET",

                    headers: {
                        "X-Requested-With": (
                            "XMLHttpRequest"
                        ),
                    },

                    credentials: "same-origin",
                }
            );


            const html = await respuesta.text();


            if (!respuesta.ok) {
                throw new Error(
                    "No fue posible cargar el contenido."
                );
            }


            reemplazarPanelDesdeHtml(
                html,
                {
                    cambiarUrl: respuesta.url,
                    agregarHistorial,
                }
            );


            return true;

        } catch (error) {

            console.error(
                error
            );


            await alerta({
                titulo: "No fue posible actualizar",
                texto: (
                    "Intenta nuevamente en unos segundos."
                ),
                icono: "error",
            });


            return false;
        }
    }


    // =====================================================================
    // VISTA PREVIA
    // =====================================================================

    function prepararVistaPrevia(
        formulario,
        titulo
    ) {

        let contenedor = (
            formulario.querySelector(
                ".gd__vista-previa"
            )
        );


        const botonEnviar = (
            formulario.querySelector(
                'button[type="submit"]'
            )
        );


        if (!contenedor) {

            contenedor = (
                document.createElement(
                    "div"
                )
            );


            contenedor.className = (
                "gd__vista-previa"
            );


            contenedor.setAttribute(
                "aria-live",
                "polite"
            );


            contenedor.innerHTML = `
                <span data-vista-titulo>
                    ${titulo}
                </span>

                <strong data-vista-beneficio>
                    Configura el beneficio
                </strong>

                <small data-vista-condicion>
                    Completa las condiciones.
                </small>

                <small data-vista-extra></small>
            `;


            if (botonEnviar) {

                formulario.insertBefore(
                    contenedor,
                    botonEnviar
                );

            } else {

                formulario.appendChild(
                    contenedor
                );
            }
        }


        return {
            contenedor,

            titulo: (
                contenedor.querySelector(
                    "[data-vista-titulo]"
                )
            ),

            beneficio: (
                contenedor.querySelector(
                    "[data-vista-beneficio]"
                )
            ),

            condicion: (
                contenedor.querySelector(
                    "[data-vista-condicion]"
                )
            ),

            extra: (
                contenedor.querySelector(
                    "[data-vista-extra]"
                )
            ),
        };
    }


    // =====================================================================
    // VALIDACIÓN DE FECHAS
    // =====================================================================

    function validarFechas(
        fechaInicio,
        fechaFin
    ) {

        if (!fechaFin) {
            return true;
        }


        fechaFin.setCustomValidity(
            ""
        );


        const inicio = obtenerFechaLocal(
            fechaInicio?.value
        );

        const fin = obtenerFechaLocal(
            fechaFin?.value
        );


        if (
            inicio
            && fin
            && fin <= inicio
        ) {

            fechaFin.setCustomValidity(
                (
                    "La fecha de término debe "
                    + "ser posterior a la fecha "
                    + "de inicio."
                )
            );

            return false;
        }


        return true;
    }


    // =====================================================================
    // FORMULARIOS GENERALES
    // =====================================================================

    function configurarFormularioGeneral(
        formulario
    ) {

        if (
            formulario.dataset.gdConfigurado
            === "true"
        ) {
            return;
        }


        formulario.dataset.gdConfigurado = (
            "true"
        );


        const codigo = obtenerCampo(
            formulario,
            "codigo"
        );


        if (!codigo) {
            return;
        }


        const nombre = obtenerCampo(
            formulario,
            "nombre"
        );

        const porcentaje = obtenerCampo(
            formulario,
            "porcentaje"
        );

        const montoDescuento = obtenerCampo(
            formulario,
            "monto_descuento"
        );

        const montoMinimo = obtenerCampo(
            formulario,
            "monto_minimo"
        );

        const montoMaximo = obtenerCampo(
            formulario,
            "monto_maximo_descuento"
        );

        const fechaInicio = obtenerCampo(
            formulario,
            "fecha_inicio"
        );

        const fechaFin = obtenerCampo(
            formulario,
            "fecha_fin"
        );


        const esMontoFijo = Boolean(
            montoDescuento
            && !porcentaje
        );


        const vistaPrevia = prepararVistaPrevia(
            formulario,
            "Vista previa de la campaña"
        );


        // -----------------------------------------------------------------
        // VALIDACIÓN
        // -----------------------------------------------------------------

        function validarFormulario() {

            limpiarValidez(
                porcentaje,
                montoDescuento,
                montoMinimo,
                montoMaximo,
                fechaFin
            );


            let valido = true;


            const minimo = convertirNumero(
                montoMinimo?.value
            );


            if (esMontoFijo) {

                const descuento = convertirNumero(
                    montoDescuento?.value
                );


                if (descuento <= 0) {

                    montoDescuento?.setCustomValidity(
                        (
                            "Debes indicar un monto "
                            + "de descuento mayor que cero."
                        )
                    );

                    valido = false;
                }


                if (minimo <= 0) {

                    montoMinimo?.setCustomValidity(
                        (
                            "Un descuento en CLP "
                            + "debe tener una compra "
                            + "mínima mayor que cero."
                        )
                    );

                    valido = false;
                }


                if (
                    descuento > 0
                    && minimo > 0
                    && descuento > minimo
                ) {

                    montoDescuento?.setCustomValidity(
                        (
                            "El monto del descuento "
                            + "no puede superar la "
                            + "compra mínima."
                        )
                    );

                    valido = false;
                }

            } else {

                const valorPorcentaje = (
                    convertirNumero(
                        porcentaje?.value
                    )
                );


                if (
                    valorPorcentaje <= 0
                    || valorPorcentaje > 100
                ) {

                    porcentaje?.setCustomValidity(
                        (
                            "El porcentaje debe ser "
                            + "mayor que 0 y no puede "
                            + "superar 100."
                        )
                    );

                    valido = false;
                }


                if (
                    montoMaximo
                    && montoMaximo.value
                ) {

                    const maximo = convertirNumero(
                        montoMaximo.value
                    );


                    if (maximo <= 0) {

                        montoMaximo.setCustomValidity(
                            (
                                "El descuento máximo "
                                + "debe ser mayor que cero."
                            )
                        );

                        valido = false;
                    }
                }
            }


            if (
                !validarFechas(
                    fechaInicio,
                    fechaFin
                )
            ) {
                valido = false;
            }


            return valido;
        }


        // -----------------------------------------------------------------
        // VISTA PREVIA
        // -----------------------------------------------------------------

        function actualizarVistaPrevia() {

            validarFormulario();


            const minimo = convertirNumero(
                montoMinimo?.value
            );


            if (esMontoFijo) {

                const descuento = convertirNumero(
                    montoDescuento?.value
                );


                if (vistaPrevia.beneficio) {

                    vistaPrevia.beneficio.textContent = (
                        descuento > 0
                            ? `-${formatearClp(
                                descuento
                            )}`
                            : (
                                "Indica el monto "
                                + "del descuento"
                            )
                    );
                }

            } else {

                const valorPorcentaje = (
                    convertirNumero(
                        porcentaje?.value
                    )
                );


                if (vistaPrevia.beneficio) {

                    vistaPrevia.beneficio.textContent = (
                        valorPorcentaje > 0
                            ? (
                                `${valorPorcentaje}% `
                                + "de descuento"
                            )
                            : "Indica el porcentaje"
                    );
                }
            }


            if (vistaPrevia.condicion) {

                vistaPrevia.condicion.textContent = (
                    minimo > 0
                        ? (
                            "Compra mínima: "
                            + formatearClp(
                                minimo
                            )
                        )
                        : "Sin compra mínima"
                );
            }


            if (vistaPrevia.extra) {

                if (
                    !esMontoFijo
                    && montoMaximo?.value
                    && convertirNumero(
                        montoMaximo.value
                    ) > 0
                ) {

                    vistaPrevia.extra.textContent = (
                        "Tope máximo de descuento: "
                        + formatearClp(
                            montoMaximo.value
                        )
                    );

                } else {

                    vistaPrevia.extra.textContent = (
                        "Código público · un uso por cliente"
                    );
                }
            }


            if (
                nombre?.value
                && vistaPrevia.contenedor
            ) {

                vistaPrevia.contenedor.setAttribute(
                    "aria-label",
                    (
                        "Vista previa de "
                        + nombre.value.trim()
                    )
                );
            }
        }


        // -----------------------------------------------------------------
        // NORMALIZAR CÓDIGO
        // -----------------------------------------------------------------

        codigo.addEventListener(
            "input",
            () => {

                normalizarCodigo(
                    codigo
                );
            }
        );


        codigo.addEventListener(
            "blur",
            () => {

                normalizarTextoFinal(
                    codigo
                );
            }
        );


        escucharCampos(
            [
                nombre,
                porcentaje,
                montoDescuento,
                montoMinimo,
                montoMaximo,
                fechaInicio,
                fechaFin,
            ],
            actualizarVistaPrevia
        );


        // -----------------------------------------------------------------
        // SUBMIT AJAX
        // -----------------------------------------------------------------

        formulario.addEventListener(
            "submit",
            async (evento) => {

                evento.preventDefault();


                normalizarTextoFinal(
                    codigo
                );


                actualizarVistaPrevia();


                const valido = (
                    validarFormulario()
                    && formulario.checkValidity()
                );


                if (!valido) {

                    formulario.reportValidity();

                    return;
                }


                const boton = (
                    evento.submitter
                    || formulario.querySelector(
                        'button[type="submit"]'
                    )
                );


                bloquearBoton(
                    boton,
                    "Creando..."
                );


                const resultado = (
                    await enviarFormularioAjax(
                        formulario
                    )
                );


                if (!resultado.ok) {

                    desbloquearBoton(
                        boton
                    );
                }
            }
        );


        actualizarVistaPrevia();
    }


    // =====================================================================
    // FORMULARIOS META FIDELIDAD
    // =====================================================================

    function configurarFormularioMeta(
        formulario
    ) {

        if (
            formulario.dataset.gdConfigurado
            === "true"
        ) {
            return;
        }


        formulario.dataset.gdConfigurado = (
            "true"
        );


        const montoObjetivo = obtenerCampo(
            formulario,
            "monto_objetivo"
        );


        if (!montoObjetivo) {
            return;
        }


        const nombre = obtenerCampo(
            formulario,
            "nombre"
        );

        const porcentaje = obtenerCampo(
            formulario,
            "porcentaje"
        );

        const montoPremio = obtenerCampo(
            formulario,
            "monto_descuento"
        );

        const montoMinimoCompra = obtenerCampo(
            formulario,
            "monto_minimo_compra"
        );

        const montoMaximo = obtenerCampo(
            formulario,
            "monto_maximo_descuento"
        );

        const vigenciaDias = obtenerCampo(
            formulario,
            "vigencia_dias"
        );

        const prefijoCodigo = obtenerCampo(
            formulario,
            "prefijo_codigo"
        );

        const orden = obtenerCampo(
            formulario,
            "orden"
        );


        const esMontoFijo = Boolean(
            montoPremio
            && !porcentaje
        );


        const vistaPrevia = prepararVistaPrevia(
            formulario,
            "Vista previa de la meta"
        );


        // -----------------------------------------------------------------
        // VALIDACIÓN
        // -----------------------------------------------------------------

        function validarFormulario() {

            limpiarValidez(
                montoObjetivo,
                porcentaje,
                montoPremio,
                montoMinimoCompra,
                montoMaximo,
                vigenciaDias,
                orden
            );


            let valido = true;


            const objetivo = convertirNumero(
                montoObjetivo?.value
            );

            const minimoCompra = convertirNumero(
                montoMinimoCompra?.value
            );

            const vigencia = convertirNumero(
                vigenciaDias?.value
            );


            if (objetivo <= 0) {

                montoObjetivo?.setCustomValidity(
                    (
                        "El monto de la meta "
                        + "debe ser mayor que cero."
                    )
                );

                valido = false;
            }


            if (vigencia <= 0) {

                vigenciaDias?.setCustomValidity(
                    (
                        "La vigencia debe ser "
                        + "de al menos 1 día."
                    )
                );

                valido = false;
            }


            if (
                orden
                && orden.value
                && convertirNumero(
                    orden.value
                ) < 0
            ) {

                orden.setCustomValidity(
                    "El orden no puede ser negativo."
                );

                valido = false;
            }


            if (esMontoFijo) {

                const premio = convertirNumero(
                    montoPremio?.value
                );


                if (premio <= 0) {

                    montoPremio?.setCustomValidity(
                        (
                            "El premio en CLP debe "
                            + "ser mayor que cero."
                        )
                    );

                    valido = false;
                }


                if (minimoCompra <= 0) {

                    montoMinimoCompra?.setCustomValidity(
                        (
                            "Un premio en CLP debe "
                            + "tener una compra mínima "
                            + "mayor que cero."
                        )
                    );

                    valido = false;
                }


                if (
                    premio > 0
                    && minimoCompra > 0
                    && premio > minimoCompra
                ) {

                    montoPremio?.setCustomValidity(
                        (
                            "El premio no puede "
                            + "superar la compra mínima."
                        )
                    );

                    valido = false;
                }

            } else {

                const valorPorcentaje = (
                    convertirNumero(
                        porcentaje?.value
                    )
                );


                if (
                    valorPorcentaje <= 0
                    || valorPorcentaje > 100
                ) {

                    porcentaje?.setCustomValidity(
                        (
                            "El porcentaje del premio "
                            + "debe ser mayor que 0 "
                            + "y máximo 100."
                        )
                    );

                    valido = false;
                }


                if (
                    montoMaximo
                    && montoMaximo.value
                ) {

                    const maximo = convertirNumero(
                        montoMaximo.value
                    );


                    if (maximo <= 0) {

                        montoMaximo.setCustomValidity(
                            (
                                "El descuento máximo "
                                + "debe ser mayor que cero."
                            )
                        );

                        valido = false;
                    }
                }
            }


            return valido;
        }


        // -----------------------------------------------------------------
        // VISTA PREVIA
        // -----------------------------------------------------------------

        function actualizarVistaPrevia() {

            validarFormulario();


            const objetivo = convertirNumero(
                montoObjetivo?.value
            );

            const minimoCompra = convertirNumero(
                montoMinimoCompra?.value
            );


            if (esMontoFijo) {

                const premio = convertirNumero(
                    montoPremio?.value
                );


                if (vistaPrevia.beneficio) {

                    vistaPrevia.beneficio.textContent = (
                        premio > 0
                            ? (
                                "Premio: "
                                + formatearClp(
                                    premio
                                )
                            )
                            : "Indica el premio en CLP"
                    );
                }

            } else {

                const valorPorcentaje = (
                    convertirNumero(
                        porcentaje?.value
                    )
                );


                if (vistaPrevia.beneficio) {

                    vistaPrevia.beneficio.textContent = (
                        valorPorcentaje > 0
                            ? (
                                `Premio: `
                                + `${valorPorcentaje}%`
                            )
                            : (
                                "Indica el porcentaje "
                                + "del premio"
                            )
                    );
                }
            }


            if (vistaPrevia.condicion) {

                vistaPrevia.condicion.textContent = (
                    objetivo > 0
                        ? (
                            "Se desbloquea al acumular "
                            + formatearClp(
                                objetivo
                            )
                        )
                        : (
                            "Indica el monto acumulado "
                            + "de la meta"
                        )
                );
            }


            if (vistaPrevia.extra) {

                let texto = (
                    "Código personal · único · un solo uso"
                );


                if (minimoCompra > 0) {

                    texto += (
                        " · compra mínima "
                        + formatearClp(
                            minimoCompra
                        )
                    );
                }


                const dias = convertirNumero(
                    vigenciaDias?.value
                );


                if (dias > 0) {

                    texto += (
                        ` · ${Math.round(
                            dias
                        )} días`
                    );
                }


                vistaPrevia.extra.textContent = (
                    texto
                );
            }


            if (
                nombre?.value
                && vistaPrevia.contenedor
            ) {

                vistaPrevia.contenedor.setAttribute(
                    "aria-label",
                    (
                        "Vista previa de la meta "
                        + nombre.value.trim()
                    )
                );
            }
        }


        // -----------------------------------------------------------------
        // PREFIJO
        // -----------------------------------------------------------------

        if (prefijoCodigo) {

            prefijoCodigo.addEventListener(
                "input",
                () => {

                    normalizarCodigo(
                        prefijoCodigo
                    );
                }
            );


            prefijoCodigo.addEventListener(
                "blur",
                () => {

                    normalizarTextoFinal(
                        prefijoCodigo
                    );
                }
            );
        }


        escucharCampos(
            [
                nombre,
                montoObjetivo,
                porcentaje,
                montoPremio,
                montoMinimoCompra,
                montoMaximo,
                vigenciaDias,
                orden,
            ],
            actualizarVistaPrevia
        );


        // -----------------------------------------------------------------
        // SUBMIT AJAX
        // -----------------------------------------------------------------

        formulario.addEventListener(
            "submit",
            async (evento) => {

                evento.preventDefault();


                normalizarTextoFinal(
                    prefijoCodigo
                );


                actualizarVistaPrevia();


                const valido = (
                    validarFormulario()
                    && formulario.checkValidity()
                );


                if (!valido) {

                    formulario.reportValidity();

                    return;
                }


                const boton = (
                    evento.submitter
                    || formulario.querySelector(
                        'button[type="submit"]'
                    )
                );


                bloquearBoton(
                    boton,
                    "Creando..."
                );


                const resultado = (
                    await enviarFormularioAjax(
                        formulario
                    )
                );


                if (!resultado.ok) {

                    desbloquearBoton(
                        boton
                    );
                }
            }
        );


        actualizarVistaPrevia();
    }


    // =====================================================================
    // CONFIGURACIÓN SWEETALERT SEGÚN ACCIÓN
    // =====================================================================

    function obtenerConfiguracionAccion(
        boton
    ) {

        const accion = String(
            boton.dataset.accion
            || ""
        )
            .trim()
            .toLowerCase();


        const textoBoton = (
            obtenerTextoBoton(
                boton
            )
            .toLowerCase()
        );


        const nombre = (
            obtenerNombreElemento(
                boton
            )
            || "este elemento"
        );


        // -----------------------------------------------------------------
        // ELIMINAR
        // -----------------------------------------------------------------

        if (
            accion === "eliminar"
            || textoBoton.includes(
                "eliminar"
            )
        ) {

            return {
                titulo: "¿Eliminar definitivamente?",

                texto: (
                    `Vas a eliminar "${nombre}". `
                    + "Esta acción no se puede deshacer."
                ),

                icono: "warning",

                confirmar: "Sí, eliminar",
                cancelar: "Cancelar",
            };
        }


        // -----------------------------------------------------------------
        // OCULTAR
        // -----------------------------------------------------------------

        if (
            accion === "ocultar"
            || textoBoton.includes(
                "ocultar"
            )
        ) {

            return {
                titulo: "¿Ocultar del listado?",

                texto: (
                    `"${nombre}" será movido a la `
                    + "sección de ocultos. "
                    + "No será eliminado y continuará "
                    + "desactivado."
                ),

                icono: "question",

                confirmar: "Sí, ocultar",
                cancelar: "Cancelar",
            };
        }


        // -----------------------------------------------------------------
        // MOSTRAR
        // -----------------------------------------------------------------

        if (
            accion === "mostrar"
            || textoBoton.includes(
                "mostrar"
            )
        ) {

            return {
                titulo: "¿Volver a mostrar?",

                texto: (
                    `"${nombre}" volverá al listado `
                    + "principal y continuará "
                    + "desactivado hasta que lo actives."
                ),

                icono: "question",

                confirmar: "Sí, mostrar",
                cancelar: "Cancelar",
            };
        }


        // -----------------------------------------------------------------
        // DESACTIVAR
        // -----------------------------------------------------------------

        if (
            textoBoton.includes(
                "desactivar"
            )
        ) {

            return {
                titulo: "¿Desactivar?",

                texto: (
                    `"${nombre}" dejará de estar `
                    + "disponible para nuevas compras. "
                    + "Podrás volver a activarlo después."
                ),

                icono: "warning",

                confirmar: "Sí, desactivar",
                cancelar: "Cancelar",
            };
        }


        // -----------------------------------------------------------------
        // ACTIVAR
        // -----------------------------------------------------------------

        if (
            textoBoton.includes(
                "activar"
            )
            && !textoBoton.includes(
                "desactivar"
            )
        ) {

            return {
                titulo: "¿Activar?",

                texto: (
                    `"${nombre}" volverá a estar `
                    + "habilitado para su uso."
                ),

                icono: "question",

                confirmar: "Sí, activar",
                cancelar: "Cancelar",
            };
        }


        return {
            titulo: "¿Confirmar acción?",
            texto: `¿Deseas continuar con "${nombre}"?`,
            icono: "question",
            confirmar: "Sí, continuar",
            cancelar: "Cancelar",
        };
    }


    // =====================================================================
    // SUBMIT GLOBAL:
    // ACTIVAR / DESACTIVAR / OCULTAR / MOSTRAR / ELIMINAR
    // =====================================================================

    document.addEventListener(
        "submit",
        async (evento) => {

            const formulario = (
                evento.target
            );


            if (
                !(formulario instanceof HTMLFormElement)
            ) {
                return;
            }


            // Los formularios de creación tienen
            // su propio controlador.
            if (
                formulario.matches(
                    "form.gd__formulario"
                )
            ) {
                return;
            }


            // -------------------------------------------------------------
            // FILTROS AJAX
            // -------------------------------------------------------------

            if (
                formulario.matches(
                    "form.gd__filtros"
                )
            ) {

                evento.preventDefault();


                const datos = new FormData(
                    formulario
                );


                const url = new URL(
                    formulario.action
                    || window.location.href,
                    window.location.origin
                );


                url.search = "";


                datos.forEach(
                    (valor, clave) => {

                        if (
                            String(valor).trim() !== ""
                        ) {

                            url.searchParams.append(
                                clave,
                                valor
                            );
                        }
                    }
                );


                await cargarUrlAjax(
                    url.toString(),
                    {
                        agregarHistorial: true,
                    }
                );


                return;
            }


            // -------------------------------------------------------------
            // ACCIONES DE ADMINISTRACIÓN
            // -------------------------------------------------------------

            const boton = (
                evento.submitter
                || formulario.querySelector(
                    "button.gd__accion"
                )
            );


            if (
                !boton
                || !boton.classList.contains(
                    "gd__accion"
                )
            ) {
                return;
            }


            evento.preventDefault();


            const configuracion = (
                obtenerConfiguracionAccion(
                    boton
                )
            );


            const confirmado = (
                await confirmarAccion(
                    configuracion
                )
            );


            if (!confirmado) {
                return;
            }


            bloquearBoton(
                boton
            );


            const resultado = (
                await enviarFormularioAjax(
                    formulario
                )
            );


            if (!resultado.ok) {

                desbloquearBoton(
                    boton
                );
            }
        }
    );


    // =====================================================================
    // PAGINACIÓN Y LIMPIAR FILTROS SIN RECARGAR
    // =====================================================================

    document.addEventListener(
        "click",
        async (evento) => {

            const enlace = (
                evento.target.closest(
                    ".gd__paginacion a, "
                    + ".gd__limpiar-filtros"
                )
            );


            if (!enlace) {
                return;
            }


            if (
                evento.ctrlKey
                || evento.metaKey
                || evento.shiftKey
                || evento.altKey
            ) {
                return;
            }


            evento.preventDefault();


            await cargarUrlAjax(
                enlace.href,
                {
                    agregarHistorial: true,
                }
            );
        }
    );


    // =====================================================================
    // BUSCADOR
    // =====================================================================

    function configurarFiltros() {

        document.querySelectorAll(
            "form.gd__filtros"
        ).forEach(
            (formulario) => {

                if (
                    formulario.dataset.gdConfigurado
                    === "true"
                ) {
                    return;
                }


                formulario.dataset.gdConfigurado = (
                    "true"
                );


                const buscador = (
                    formulario.querySelector(
                        'input[name="q"]'
                    )
                );


                if (!buscador) {
                    return;
                }


                buscador.addEventListener(
                    "keydown",
                    (evento) => {

                        if (
                            evento.key === "Escape"
                        ) {

                            buscador.value = "";
                        }
                    }
                );
            }
        );
    }


    // =====================================================================
    // HISTORIAL
    // =====================================================================

    function configurarHistorial() {

        document.querySelectorAll(
            ".gd__uso"
        ).forEach(
            (detalle) => {

                if (
                    detalle.dataset.gdConfigurado
                    === "true"
                ) {
                    return;
                }


                detalle.dataset.gdConfigurado = (
                    "true"
                );


                detalle.addEventListener(
                    "toggle",
                    () => {

                        if (!detalle.open) {
                            return;
                        }


                        document.querySelectorAll(
                            ".gd__uso[open]"
                        ).forEach(
                            (otro) => {

                                if (
                                    otro !== detalle
                                ) {

                                    otro.open = false;
                                }
                            }
                        );
                    }
                );
            }
        );
    }


    // =====================================================================
    // INICIALIZACIÓN DEL CONTENIDO DINÁMICO
    // =====================================================================

    function inicializarContenidoDinamico() {

        document.querySelectorAll(
            "form.gd__formulario"
        ).forEach(
            (formulario) => {

                const tipoFormulario = (
                    formulario.dataset
                        .tipoFormulario
                    || ""
                );


                // ---------------------------------------------------------
                // GENERAL
                // ---------------------------------------------------------

                if (
                    tipoFormulario === "general"
                    || obtenerCampo(
                        formulario,
                        "codigo"
                    )
                ) {

                    configurarFormularioGeneral(
                        formulario
                    );

                    return;
                }


                // ---------------------------------------------------------
                // META DE FIDELIDAD
                // ---------------------------------------------------------

                if (
                    tipoFormulario === "meta"
                    || obtenerCampo(
                        formulario,
                        "monto_objetivo"
                    )
                ) {

                    configurarFormularioMeta(
                        formulario
                    );
                }
            }
        );


        configurarFiltros();

        configurarHistorial();
    }


    // =====================================================================
    // BOTÓN ATRÁS / ADELANTE DEL NAVEGADOR
    // =====================================================================

    window.addEventListener(
        "popstate",
        async () => {

            await cargarUrlAjax(
                window.location.href,
                {
                    agregarHistorial: false,
                }
            );
        }
    );


    // =====================================================================
    // INICIALIZACIÓN
    // =====================================================================

    inicializarContenidoDinamico();

});