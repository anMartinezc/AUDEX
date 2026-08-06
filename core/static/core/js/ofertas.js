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

    let temporizadorToast = null;

    function obtenerCookie(
        nombre
    ) {
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

        toastTexto.textContent = mensaje;

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

    // =========================================================================
    // COPIAR CÓDIGOS
    // =========================================================================

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
                        return;
                    }

                    try {
                        await navigator.clipboard.writeText(
                            codigo
                        );

                        mostrarToast(
                            (
                                `Código ${codigo} `
                                + "copiado."
                            )
                        );
                    } catch (error) {
                        const auxiliar = (
                            document.createElement(
                                "textarea"
                            )
                        );

                        auxiliar.value = codigo;

                        auxiliar.setAttribute(
                            "readonly",
                            ""
                        );

                        auxiliar.style.position = (
                            "fixed"
                        );

                        auxiliar.style.opacity = "0";

                        document.body.appendChild(
                            auxiliar
                        );

                        auxiliar.select();

                        document.execCommand(
                            "copy"
                        );

                        auxiliar.remove();

                        mostrarToast(
                            (
                                `Código ${codigo} `
                                + "copiado."
                            )
                        );
                    }
                }
            );
        }
    );

    // =========================================================================
    // CUENTA REGRESIVA
    // =========================================================================

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

    function dosDigitos(
        numero
    ) {
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

        const diferencia = (
            fechaVencimiento.getTime()
            - Date.now()
        );

        if (
            Number.isNaN(
                fechaVencimiento.getTime()
            )
            || diferencia <= 0
        ) {
            contador.innerHTML = `
                <div class="contador-oferta__finalizado">
                    Esta campaña finalizó
                </div>
            `;

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

        window.setInterval(
            actualizarContador,
            1000
        );
    }

    // =========================================================================
    // AGREGAR PRODUCTOS AL CARRITO
    // =========================================================================

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
        );

        if (
            !urlAgregar
            || !Number.isInteger(
                productoId
            )
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

        boton.disabled = true;
        boton.classList.add(
            "comprar-oferta--cargando"
        );

        const texto = boton.querySelector(
            "span"
        );

        const textoOriginal = (
            texto?.textContent
            || "Agregar al carrito"
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
                            producto_id: (
                                productoId
                            ),
                            cantidad: 1,
                        }
                    ),
                }
            );

            const datos = await respuesta.json();

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
                        detail: datos.carrito,
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
                error.message,
                true
            );
        } finally {
            boton.classList.remove(
                "comprar-oferta--cargando"
            );

            boton.disabled = false;

            if (texto) {
                texto.textContent = (
                    textoOriginal.trim()
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