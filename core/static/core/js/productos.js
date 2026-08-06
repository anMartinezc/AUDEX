"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const formularioFiltros = document.getElementById(
        "formularioFiltros"
    );

    const selectorCategoria = document.getElementById(
        "categoriaProductos"
    );

    const selectorOrden = document.getElementById(
        "ordenProductos"
    );

    const buscador = document.getElementById(
        "buscadorProductos"
    );

    const tarjetas = document.querySelectorAll(
        ".producto-card"
    );

    let temporizadorBusqueda = null;

    /*
     * Los filtros son procesados por Django mediante GET.
     * Este archivo no controla el carrito ni modifica su contador.
     * Esa responsabilidad corresponde exclusivamente a carrito.js.
     */
    if (selectorCategoria && formularioFiltros) {
        selectorCategoria.addEventListener(
            "change",
            () => {
                formularioFiltros.requestSubmit();
            }
        );
    }

    if (selectorOrden && formularioFiltros) {
        selectorOrden.addEventListener(
            "change",
            () => {
                formularioFiltros.requestSubmit();
            }
        );
    }

    if (buscador && formularioFiltros) {
        buscador.addEventListener("input", () => {
            window.clearTimeout(
                temporizadorBusqueda
            );

            temporizadorBusqueda = window.setTimeout(
                () => {
                    formularioFiltros.requestSubmit();
                },
                650
            );
        });
    }

    /*
     * Reactiva solamente los botones con stock que no estén
     * procesando actualmente una solicitud del carrito.
     *
     * Esto corrige el estado deshabilitado que algunos navegadores
     * restauran al volver atrás o recuperar una página desde caché.
     */
    function restaurarBotonesAgregar() {
        document
            .querySelectorAll(".agregar-carrito")
            .forEach((boton) => {
                const stock = Number(
                    boton.dataset.stock || 0
                );

                const procesando =
                    boton.dataset.procesando === "true";

                if (stock > 0 && !procesando) {
                    boton.disabled = false;
                    boton.setAttribute(
                        "aria-disabled",
                        "false"
                    );
                }

                if (stock <= 0) {
                    boton.disabled = true;
                    boton.setAttribute(
                        "aria-disabled",
                        "true"
                    );
                }
            });
    }

    restaurarBotonesAgregar();

    window.addEventListener(
        "pageshow",
        restaurarBotonesAgregar
    );

    /*
     * Animación visual de las tarjetas.
     * No registra eventos sobre .agregar-carrito.
     */
    if (
        "IntersectionObserver" in window
        && tarjetas.length > 0
    ) {
        tarjetas.forEach((tarjeta, indice) => {
            tarjeta.style.opacity = "0";
            tarjeta.style.transform =
                "translateY(25px)";

            tarjeta.style.transition = `
                opacity 0.55s ease ${indice * 0.06}s,
                transform 0.55s ease ${indice * 0.06}s
            `;
        });

        const observador = new IntersectionObserver(
            (entradas, observer) => {
                entradas.forEach((entrada) => {
                    if (!entrada.isIntersecting) {
                        return;
                    }

                    entrada.target.style.opacity = "1";
                    entrada.target.style.transform =
                        "translateY(0)";

                    observer.unobserve(
                        entrada.target
                    );
                });
            },
            {
                threshold: 0.12,
            }
        );

        tarjetas.forEach((tarjeta) => {
            observador.observe(tarjeta);
        });
    }

    
    function restaurarBotonesAgregar() {
        document
            .querySelectorAll(".agregar-carrito")
            .forEach((boton) => {
                const stock = Number(
                    boton.dataset.stock || 0
                );

                const procesando =
                    boton.dataset.procesando === "true";

                if (stock > 0 && !procesando) {
                    boton.disabled = false;
                    boton.setAttribute(
                        "aria-disabled",
                        "false"
                    );
                }
            });
    }

    document.addEventListener(
        "DOMContentLoaded",
        restaurarBotonesAgregar
    );

    window.addEventListener(
        "pageshow",
        restaurarBotonesAgregar
    );
});