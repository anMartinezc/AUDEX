(function () {
    "use strict";


    /* =====================================================
       FORMATO MONETARIO CHILENO DEL CARRITO
    ====================================================== */

    function formatearMontoCLP(texto) {

        if (!texto) {
            return texto;
        }


        return texto.replace(
            /(-?\$)\s*([\d\s.,]+)(?:\s*CLP)?/gi,
            function (
                coincidencia,
                simbolo,
                numero
            ) {

                const soloDigitos =
                    numero.replace(
                        /[^\d]/g,
                        ""
                    );


                if (!soloDigitos) {
                    return coincidencia;
                }


                const valor =
                    Number.parseInt(
                        soloDigitos,
                        10
                    );


                if (
                    Number.isNaN(valor)
                ) {
                    return coincidencia;
                }


                const numeroFormateado =
                    new Intl.NumberFormat(
                        "es-CL",
                        {
                            maximumFractionDigits: 0
                        }
                    ).format(valor);


                return (
                    `${simbolo}` +
                    `${numeroFormateado} CLP`
                );

            }
        );

    }


    /* =====================================================
       PROCESAR NODOS DE TEXTO
    ====================================================== */

    function procesarNodoTexto(
        nodo
    ) {

        if (
            !nodo
            || nodo.nodeType
            !== Node.TEXT_NODE
        ) {
            return;
        }


        const textoOriginal =
            nodo.nodeValue;


        if (
            !textoOriginal
            || !textoOriginal.includes("$")
        ) {
            return;
        }


        const textoNuevo =
            formatearMontoCLP(
                textoOriginal
            );


        if (
            textoNuevo !== textoOriginal
        ) {

            nodo.nodeValue =
                textoNuevo;

        }

    }


    /* =====================================================
       RECORRER EL CONTENIDO DEL CARRITO
    ====================================================== */

    function procesarContenedor(
        contenedor
    ) {

        if (!contenedor) {
            return;
        }


        const walker =
            document.createTreeWalker(
                contenedor,
                NodeFilter.SHOW_TEXT
            );


        const nodos = [];


        while (
            walker.nextNode()
        ) {

            nodos.push(
                walker.currentNode
            );

        }


        nodos.forEach(
            procesarNodoTexto
        );

    }


    /* =====================================================
       APLICAR FORMATO
    ====================================================== */

    function aplicarFormatoCarrito() {

        const productos =
            document.getElementById(
                "carritoProductos"
            );


        const subtotal =
            document.getElementById(
                "carritoSubtotal"
            );


        procesarContenedor(
            productos
        );


        procesarContenedor(
            subtotal
        );

    }


    /* =====================================================
       CARGA INICIAL
    ====================================================== */

    if (
        document.readyState
        === "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            aplicarFormatoCarrito
        );

    } else {

        aplicarFormatoCarrito();

    }


    /* =====================================================
       ACTUALIZACIONES DINÁMICAS DEL CARRITO
    ====================================================== */

    const carritoLateral =
        document.getElementById(
            "carritoLateral"
        );


    if (carritoLateral) {

        let pendiente = false;


        const observer =
            new MutationObserver(
                function () {

                    if (pendiente) {
                        return;
                    }


                    pendiente = true;


                    requestAnimationFrame(
                        function () {

                            aplicarFormatoCarrito();

                            pendiente = false;

                        }
                    );

                }
            );


        observer.observe(
            carritoLateral,
            {
                childList: true,
                subtree: true,
                characterData: true
            }
        );

    }

})();