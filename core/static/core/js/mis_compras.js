/* =========================================================
   MIS COMPRAS — NAVEGACIÓN SIN RECARGA
   Archivo:
   core/static/core/js/mis_compras.js

   Funciones:
   - Cambiar filtros sin recargar la página.
   - Avanzar/retroceder paginación sin recargar.
   - Mantener la URL actualizada.
   - Soportar atrás/adelante del navegador.
   - Evitar dobles clics.
   - Scroll suave al listado.
========================================================= */

(() => {
    "use strict";


    /* =====================================================
       CONFIGURACIÓN
    ====================================================== */

    const SELECTORES = {
        controles: ".mis-compras-controles",
        listado: ".pedidos-lista--compras",
        paginacion: ".paginacion",
        filtros: ".mis-compras-filtros",
        contenedor: ".mis-compras",
    };


    let cargando = false;
    let controlador = null;


    /* =====================================================
       OBTENER CONTENEDOR PRINCIPAL
    ====================================================== */

    function obtenerPagina() {
        return document.querySelector(
            SELECTORES.contenedor
        );
    }


    /* =====================================================
       COMPROBAR ENLACE AJAX
    ====================================================== */

    function esEnlaceNavegable(enlace) {
        if (!enlace) {
            return false;
        }

        if (
            enlace.target === "_blank"
            || enlace.hasAttribute("download")
        ) {
            return false;
        }

        const url = new URL(
            enlace.href,
            window.location.href
        );

        /*
         * Solo interceptamos enlaces del mismo sitio.
         */
        if (url.origin !== window.location.origin) {
            return false;
        }

        /*
         * Solo filtros y paginación.
         */
        const estaEnFiltros = enlace.closest(
            SELECTORES.filtros
        );

        const estaEnPaginacion = enlace.closest(
            SELECTORES.paginacion
        );

        return Boolean(
            estaEnFiltros
            || estaEnPaginacion
        );
    }


    /* =====================================================
       ESTADO DE CARGA
    ====================================================== */

    function activarCarga() {
        const pagina = obtenerPagina();

        if (!pagina) {
            return;
        }

        pagina.classList.add(
            "mis-compras--cargando"
        );

        pagina.setAttribute(
            "aria-busy",
            "true"
        );
    }


    function desactivarCarga() {
        const pagina = obtenerPagina();

        if (!pagina) {
            return;
        }

        pagina.classList.remove(
            "mis-compras--cargando"
        );

        pagina.removeAttribute(
            "aria-busy"
        );
    }


    /* =====================================================
       REEMPLAZAR ELEMENTO
    ====================================================== */

    function reemplazarElemento(
        documentoNuevo,
        selector
    ) {
        const actual = document.querySelector(
            selector
        );

        const nuevo = documentoNuevo.querySelector(
            selector
        );

        /*
         * Si ambos existen, reemplazamos.
         */
        if (actual && nuevo) {
            actual.replaceWith(
                nuevo
            );

            return;
        }

        /*
         * Si el actual existe pero en la nueva página
         * desapareció, lo eliminamos.
         *
         * Ejemplo:
         * paginación de página 2 -> filtro con una sola página.
         */
        if (actual && !nuevo) {
            actual.remove();
            return;
        }

        /*
         * Caso especial:
         * no existía paginación pero ahora sí.
         */
        if (
            !actual
            && nuevo
            && selector === SELECTORES.paginacion
        ) {
            const listado = document.querySelector(
                SELECTORES.listado
            );

            if (listado) {
                listado.insertAdjacentElement(
                    "afterend",
                    nuevo
                );
            }
        }
    }


    /* =====================================================
       ACTUALIZAR DOCUMENTO
    ====================================================== */

    function actualizarContenido(
        html,
        url,
        guardarHistorial = true
    ) {
        const parser = new DOMParser();

        const documentoNuevo = parser.parseFromString(
            html,
            "text/html"
        );


        /*
         * Actualizamos bloque de filtros/contador.
         */
        reemplazarElemento(
            documentoNuevo,
            SELECTORES.controles
        );


        /*
         * Actualizamos las compras.
         */
        reemplazarElemento(
            documentoNuevo,
            SELECTORES.listado
        );


        /*
         * Actualizamos el paginador.
         */
        reemplazarElemento(
            documentoNuevo,
            SELECTORES.paginacion
        );


        /*
         * Actualizamos título del navegador
         * por si en algún momento cambia.
         */
        if (documentoNuevo.title) {
            document.title = documentoNuevo.title;
        }


        /*
         * URL sin recargar.
         */
        if (guardarHistorial) {
            window.history.pushState(
                {
                    misComprasAjax: true,
                },
                "",
                url
            );
        }


        /*
         * Reactivamos eventos después de reemplazar HTML.
         */
        inicializarEventos();


        desactivarCarga();
    }


    /* =====================================================
       CARGAR URL
    ====================================================== */

    async function cargarUrl(
        url,
        {
            guardarHistorial = true,
            hacerScroll = true,
        } = {}
    ) {
        if (cargando) {
            /*
             * Cancelamos petición anterior.
             */
            if (controlador) {
                controlador.abort();
            }
        }


        cargando = true;

        controlador = new AbortController();


        activarCarga();


        try {
            const respuesta = await fetch(
                url,
                {
                    method: "GET",

                    headers: {
                        "X-Requested-With":
                            "XMLHttpRequest",
                    },

                    credentials:
                        "same-origin",

                    signal:
                        controlador.signal,
                }
            );


            if (!respuesta.ok) {
                throw new Error(
                    `HTTP ${respuesta.status}`
                );
            }


            const html = await respuesta.text();


            actualizarContenido(
                html,
                url,
                guardarHistorial
            );


            /*
             * Si cambió filtro o página,
             * volvemos suavemente al listado.
             */
            if (hacerScroll) {
                scrollListado();
            }

        } catch (error) {

            /*
             * AbortError ocurre cuando el usuario
             * hace clic rápidamente en otro filtro.
             */
            if (
                error.name === "AbortError"
            ) {
                return;
            }


            console.error(
                "Error cargando Mis compras:",
                error
            );


            /*
             * Fallback:
             * si AJAX falla usamos navegación normal.
             */
            window.location.href = url;

        } finally {

            cargando = false;

            controlador = null;

            desactivarCarga();
        }
    }


    /* =====================================================
       SCROLL SUAVE
    ====================================================== */

    function scrollListado() {
        const controles = document.querySelector(
            SELECTORES.controles
        );

        if (!controles) {
            return;
        }


        const rect = controles.getBoundingClientRect();

        const offset = 110;


        /*
         * Si el usuario ya está aproximadamente
         * en esa zona, no hacemos scroll innecesario.
         */
        if (
            rect.top > -100
            && rect.top < 250
        ) {
            return;
        }


        const posicion =
            window.scrollY
            + rect.top
            - offset;


        window.scrollTo({
            top: Math.max(
                posicion,
                0
            ),
            behavior: "smooth",
        });
    }


    /* =====================================================
       CLIC EN FILTROS / PAGINADOR
    ====================================================== */

    function manejarClick(evento) {
        const enlace = evento.target.closest(
            "a"
        );


        if (!esEnlaceNavegable(enlace)) {
            return;
        }


        /*
         * Respetamos:
         * Cmd + click
         * Ctrl + click
         * Shift + click
         * Alt + click
         */
        if (
            evento.metaKey
            || evento.ctrlKey
            || evento.shiftKey
            || evento.altKey
        ) {
            return;
        }


        evento.preventDefault();


        cargarUrl(
            enlace.href,
            {
                guardarHistorial: true,
                hacerScroll: true,
            }
        );
    }


    /* =====================================================
       NAVEGACIÓN ATRÁS / ADELANTE
    ====================================================== */

    function manejarPopState() {
        cargarUrl(
            window.location.href,
            {
                guardarHistorial: false,
                hacerScroll: false,
            }
        );
    }


    /* =====================================================
       INICIALIZAR EVENTOS
    ====================================================== */

    function inicializarEventos() {
        /*
         * Usamos delegación de eventos.
         *
         * Por eso realmente basta registrarlo
         * una vez en document.
         */
    }


    /* =====================================================
       INICIALIZACIÓN
    ====================================================== */

    function inicializar() {
        const pagina = obtenerPagina();

        if (!pagina) {
            return;
        }


        document.addEventListener(
            "click",
            manejarClick
        );


        window.addEventListener(
            "popstate",
            manejarPopState
        );


        /*
         * Marcamos el primer estado del historial.
         */
        window.history.replaceState(
            {
                misComprasAjax: true,
            },
            "",
            window.location.href
        );
    }


    /* =====================================================
       DOM READY
    ====================================================== */

    if (
        document.readyState
        === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            inicializar
        );

    } else {

        inicializar();
    }

})();