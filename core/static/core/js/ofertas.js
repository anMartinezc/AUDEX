"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const pagina = document.getElementById(
        "ofertasPagina"
    );

    if (!pagina) {
        return;
    }

    const toast = document.getElementById(
        "ofertasToast"
    );

    const toastTexto = document.getElementById(
        "ofertasToastTexto"
    );

    const contadorHeader = document.getElementById(
        "carritoContador"
    );

    const botonAbrirCarrito = document.getElementById(
        "abrirCarrito"
    );

    const movimientoReducido = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    let temporizadorToast = null;
    let intervaloContador = null;

    // =================================================================
    // UTILIDADES
    // =================================================================

    function obtenerCookie(nombre) {
        const cookies = document.cookie
            ? document.cookie.split(";")
            : [];

        for (const cookie of cookies) {
            const cookieLimpia = cookie.trim();

            if (
                cookieLimpia.startsWith(
                    `${nombre}=`
                )
            ) {
                return decodeURIComponent(
                    cookieLimpia.substring(
                        nombre.length + 1
                    )
                );
            }
        }

        return "";
    }

    function mostrarToast(
        mensaje,
        esError = false
    ) {
        if (!toast || !toastTexto) {
            return;
        }

        toastTexto.textContent = String(
            mensaje || ""
        );

        toast.classList.toggle(
            "ofertas-toast--error",
            esError
        );

        toast.classList.add(
            "ofertas-toast--visible"
        );

        toast.setAttribute(
            "aria-hidden",
            "false"
        );

        window.clearTimeout(
            temporizadorToast
        );

        temporizadorToast = window.setTimeout(
            () => {
                toast.classList.remove(
                    "ofertas-toast--visible"
                );

                toast.setAttribute(
                    "aria-hidden",
                    "true"
                );
            },
            2800
        );
    }

    async function copiarTexto(texto) {
        const valor = String(
            texto || ""
        ).trim();

        if (!valor) {
            return false;
        }

        if (
            navigator.clipboard
            && window.isSecureContext
        ) {
            await navigator.clipboard.writeText(
                valor
            );

            return true;
        }

        const auxiliar = document.createElement(
            "textarea"
        );

        auxiliar.value = valor;
        auxiliar.setAttribute(
            "readonly",
            ""
        );

        auxiliar.style.position = "fixed";
        auxiliar.style.top = "-9999px";
        auxiliar.style.left = "-9999px";
        auxiliar.style.opacity = "0";

        document.body.appendChild(
            auxiliar
        );

        auxiliar.focus();
        auxiliar.select();
        auxiliar.setSelectionRange(
            0,
            auxiliar.value.length
        );

        const copiado = document.execCommand(
            "copy"
        );

        auxiliar.remove();

        return copiado;
    }

    async function leerRespuestaJson(
        respuesta
    ) {
        const texto = await respuesta.text();

        if (!texto) {
            return {};
        }

        try {
            return JSON.parse(
                texto
            );
        } catch (error) {
            return {
                ok: false,
                mensaje: (
                    "El servidor entregó una "
                    + "respuesta no válida."
                ),
            };
        }
    }

    // =================================================================
    // COPIAR CÓDIGOS
    // =================================================================

    document.querySelectorAll(
        ".js-copiar-codigo"
    ).forEach(
        (boton) => {
            boton.addEventListener(
                "click",
                async () => {
                    const codigo = String(
                        boton.dataset.codigo
                        || ""
                    ).trim();

                    if (!codigo) {
                        mostrarToast(
                            "El código no está disponible.",
                            true
                        );

                        return;
                    }

                    const textoElemento = boton.querySelector(
                        "span"
                    );

                    const textoOriginal = (
                        textoElemento?.textContent
                        || ""
                    ).trim();

                    boton.disabled = true;

                    try {
                        const copiado = await copiarTexto(
                            codigo
                        );

                        if (!copiado) {
                            throw new Error(
                                "No fue posible copiar el código."
                            );
                        }

                        if (textoElemento) {
                            textoElemento.textContent = (
                                "Copiado"
                            );
                        }

                        mostrarToast(
                            `Código ${codigo} copiado.`
                        );
                    } catch (error) {
                        mostrarToast(
                            (
                                error.message
                                || "No fue posible copiar el código."
                            ),
                            true
                        );
                    } finally {
                        window.setTimeout(
                            () => {
                                boton.disabled = false;

                                if (
                                    textoElemento
                                    && textoOriginal
                                ) {
                                    textoElemento.textContent = (
                                        textoOriginal
                                    );
                                }
                            },
                            900
                        );
                    }
                }
            );
        }
    );

    // =================================================================
    // CARRUSEL DE CUPONES CLP
    // =================================================================

    const rielCupones = document.querySelector(
        ".js-cupones-clp-riel"
    );

    const botonCuponAnterior = document.querySelector(
        ".js-cupones-anterior"
    );

    const botonCuponSiguiente = document.querySelector(
        ".js-cupones-siguiente"
    );

    function obtenerPasoCupones() {
        if (!rielCupones) {
            return 0;
        }

        const primerCupon = rielCupones.querySelector(
            ".cupon-clp"
        );

        if (!primerCupon) {
            return Math.max(
                rielCupones.clientWidth * 0.85,
                260
            );
        }

        const estilosRiel = window.getComputedStyle(
            rielCupones
        );

        const espacio = parseFloat(
            estilosRiel.columnGap
            || estilosRiel.gap
            || "0"
        );

        return (
            primerCupon.getBoundingClientRect().width
            + (
                Number.isFinite(espacio)
                    ? espacio
                    : 0
            )
        );
    }

    function actualizarControlesCupones() {
        if (
            !rielCupones
            || !botonCuponAnterior
            || !botonCuponSiguiente
        ) {
            return;
        }

        const tolerancia = 3;

        const puedeRetroceder = (
            rielCupones.scrollLeft
            > tolerancia
        );

        const puedeAvanzar = (
            rielCupones.scrollLeft
            + rielCupones.clientWidth
            < rielCupones.scrollWidth
            - tolerancia
        );

        botonCuponAnterior.disabled = (
            !puedeRetroceder
        );

        botonCuponSiguiente.disabled = (
            !puedeAvanzar
        );

        botonCuponAnterior.setAttribute(
            "aria-disabled",
            String(
                !puedeRetroceder
            )
        );

        botonCuponSiguiente.setAttribute(
            "aria-disabled",
            String(
                !puedeAvanzar
            )
        );
    }

    function desplazarCupones(
        direccion
    ) {
        if (!rielCupones) {
            return;
        }

        const paso = obtenerPasoCupones();

        rielCupones.scrollBy({
            left: paso * direccion,
            behavior: (
                movimientoReducido
                    ? "auto"
                    : "smooth"
            ),
        });
    }

    if (rielCupones) {
        botonCuponAnterior?.addEventListener(
            "click",
            () => {
                desplazarCupones(
                    -1
                );
            }
        );

        botonCuponSiguiente?.addEventListener(
            "click",
            () => {
                desplazarCupones(
                    1
                );
            }
        );

        rielCupones.addEventListener(
            "scroll",
            () => {
                window.requestAnimationFrame(
                    actualizarControlesCupones
                );
            },
            {
                passive: true,
            }
        );

        rielCupones.addEventListener(
            "keydown",
            (evento) => {
                if (evento.key === "ArrowLeft") {
                    evento.preventDefault();

                    desplazarCupones(
                        -1
                    );
                }

                if (evento.key === "ArrowRight") {
                    evento.preventDefault();

                    desplazarCupones(
                        1
                    );
                }

                if (evento.key === "Home") {
                    evento.preventDefault();

                    rielCupones.scrollTo({
                        left: 0,
                        behavior: (
                            movimientoReducido
                                ? "auto"
                                : "smooth"
                        ),
                    });
                }

                if (evento.key === "End") {
                    evento.preventDefault();

                    rielCupones.scrollTo({
                        left: rielCupones.scrollWidth,
                        behavior: (
                            movimientoReducido
                                ? "auto"
                                : "smooth"
                        ),
                    });
                }
            }
        );

        window.addEventListener(
            "resize",
            actualizarControlesCupones
        );

        actualizarControlesCupones();
    }

    // =================================================================
    // CUENTA REGRESIVA
    // =================================================================

    const fechaVencimientoTexto = String(
        pagina.dataset.venceEn
        || ""
    ).trim();

    const contador = document.getElementById(
        "contadorOferta"
    );

    const diasElemento = document.getElementById(
        "diasOferta"
    );

    const horasElemento = document.getElementById(
        "horasOferta"
    );

    const minutosElemento = document.getElementById(
        "minutosOferta"
    );

    const segundosElemento = document.getElementById(
        "segundosOferta"
    );

    function dosDigitos(numero) {
        return String(
            Math.max(
                0,
                numero
            )
        ).padStart(
            2,
            "0"
        );
    }

    function finalizarContador() {
        if (!contador) {
            return;
        }

        if (intervaloContador) {
            window.clearInterval(
                intervaloContador
            );

            intervaloContador = null;
        }

        contador.innerHTML = `
            <div class="contador-oferta__finalizado">
                Esta campaña finalizó
            </div>
        `;
    }

    function actualizarContador() {
        if (
            !fechaVencimientoTexto
            || !contador
        ) {
            return;
        }

        const fechaVencimiento = new Date(
            fechaVencimientoTexto
        );

        if (
            Number.isNaN(
                fechaVencimiento.getTime()
            )
        ) {
            finalizarContador();
            return;
        }

        const diferencia = (
            fechaVencimiento.getTime()
            - Date.now()
        );

        if (diferencia <= 0) {
            finalizarContador();
            return;
        }

        const segundosTotales = Math.floor(
            diferencia / 1000
        );

        const dias = Math.floor(
            segundosTotales / 86400
        );

        const horas = Math.floor(
            (
                segundosTotales % 86400
            )
            / 3600
        );

        const minutos = Math.floor(
            (
                segundosTotales % 3600
            )
            / 60
        );

        const segundos = (
            segundosTotales % 60
        );

        if (diasElemento) {
            diasElemento.textContent = (
                dosDigitos(
                    dias
                )
            );
        }

        if (horasElemento) {
            horasElemento.textContent = (
                dosDigitos(
                    horas
                )
            );
        }

        if (minutosElemento) {
            minutosElemento.textContent = (
                dosDigitos(
                    minutos
                )
            );
        }

        if (segundosElemento) {
            segundosElemento.textContent = (
                dosDigitos(
                    segundos
                )
            );
        }
    }

    if (
        fechaVencimientoTexto
        && contador
    ) {
        actualizarContador();

        intervaloContador = window.setInterval(
            actualizarContador,
            1000
        );
    }

    // =================================================================
    // AGREGAR PRODUCTOS AL CARRITO
    // =================================================================

    const urlAgregar = String(
        pagina.dataset.urlAgregar
        || ""
    ).trim();

    async function agregarAlCarrito(
        boton
    ) {
        const productoId = Number(
            boton.dataset.productoId
        );

        const nombreProducto = String(
            boton.dataset.producto
            || "El producto"
        ).trim();

        const stock = Number(
            boton.dataset.stock
            || 0
        );

        if (stock <= 0) {
            mostrarToast(
                "Este producto está agotado.",
                true
            );

            return;
        }

        if (
            !urlAgregar
            || !Number.isInteger(
                productoId
            )
            || productoId <= 0
        ) {
            mostrarToast(
                (
                    "No fue posible identificar "
                    + "el producto."
                ),
                true
            );

            return;
        }

        const texto = boton.querySelector(
            "span"
        );

        const textoOriginal = (
            texto?.textContent
            || "Agregar al carrito"
        ).trim();

        boton.disabled = true;
        boton.setAttribute(
            "aria-disabled",
            "true"
        );

        boton.classList.add(
            "comprar-oferta--cargando"
        );

        if (texto) {
            texto.textContent = (
                "Agregando..."
            );
        }

        try {
            const respuesta = await fetch(
                urlAgregar,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept": (
                            "application/json"
                        ),
                        "Content-Type": (
                            "application/json"
                        ),
                        "X-CSRFToken": (
                            obtenerCookie(
                                "csrftoken"
                            )
                        ),
                    },
                    body: JSON.stringify(
                        {
                            producto_id: productoId,
                            cantidad: 1,
                        }
                    ),
                }
            );

            const datos = await leerRespuestaJson(
                respuesta
            );

            if (
                !respuesta.ok
                || datos.ok === false
            ) {
                throw new Error(
                    datos.mensaje
                    || (
                        "No fue posible agregar "
                        + "el producto."
                    )
                );
            }

            if (
                contadorHeader
                && datos.carrito
            ) {
                contadorHeader.textContent = String(
                    datos.carrito.cantidad_total
                    || 0
                );
            }

            mostrarToast(
                datos.mensaje
                || (
                    `${nombreProducto} fue `
                    + "agregado al carrito."
                )
            );

            document.dispatchEvent(
                new CustomEvent(
                    "audex:carrito-actualizado",
                    {
                        detail: (
                            datos.carrito
                            || {}
                        ),
                    }
                )
            );

            window.setTimeout(
                () => {
                    botonAbrirCarrito?.click();
                },
                350
            );
        } catch (error) {
            mostrarToast(
                (
                    error.message
                    || (
                        "No fue posible agregar "
                        + "el producto."
                    )
                ),
                true
            );
        } finally {
            boton.classList.remove(
                "comprar-oferta--cargando"
            );

            boton.disabled = false;

            boton.setAttribute(
                "aria-disabled",
                "false"
            );

            if (texto) {
                texto.textContent = (
                    textoOriginal
                );
            }
        }
    }

    document.querySelectorAll(
        ".js-agregar-oferta"
    ).forEach(
        (boton) => {
            boton.addEventListener(
                "click",
                () => {
                    agregarAlCarrito(
                        boton
                    );
                }
            );
        }
    );
});