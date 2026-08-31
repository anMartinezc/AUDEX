(function () {
    "use strict";

    const CLAVE_CONSENTIMIENTO =
        "audex_cookie_consent_v1";


    const aviso =
        document.getElementById(
            "cookieAviso"
        );


    const botonAceptar =
        document.getElementById(
            "cookiesAceptarTodas"
        );


    const botonEsenciales =
        document.getElementById(
            "cookiesSoloEsenciales"
        );


    const botonPreferencias =
        document.getElementById(
            "abrirPreferenciasCookies"
        );


    if (
        !aviso
        || !botonAceptar
        || !botonEsenciales
    ) {
        return;
    }


    /* =====================================================
       OBTENER CONSENTIMIENTO
    ====================================================== */

    function obtenerConsentimiento() {

        try {

            const guardado =
                localStorage.getItem(
                    CLAVE_CONSENTIMIENTO
                );


            return guardado
                ? JSON.parse(guardado)
                : null;

        } catch (error) {

            return null;

        }

    }


    /* =====================================================
       GUARDAR CONSENTIMIENTO
    ====================================================== */

    function guardarConsentimiento(
        analytics,
        marketing
    ) {

        const consentimiento = {

            essential: true,

            analytics:
                Boolean(
                    analytics
                ),

            marketing:
                Boolean(
                    marketing
                ),

            updated_at:
                new Date()
                    .toISOString()

        };


        try {

            localStorage.setItem(
                CLAVE_CONSENTIMIENTO,
                JSON.stringify(
                    consentimiento
                )
            );

        } catch (error) {

            /*
             * Si localStorage está deshabilitado,
             * Audex debe seguir funcionando.
             */

        }


        aplicarConsentimiento(
            consentimiento
        );


        ocultarAviso();

    }


    /* =====================================================
       APLICAR CONSENTIMIENTO
    ====================================================== */

    function aplicarConsentimiento(
        consentimiento
    ) {

        /*
         * Las cookies esenciales de Django siguen
         * funcionando siempre.
         *
         * Ejemplos:
         *
         * - csrftoken
         * - sessionid
         *
         *
         * FUTURO:
         *
         * if (consentimiento.analytics) {
         *     cargarGoogleAnalytics();
         * }
         *
         *
         * if (consentimiento.marketing) {
         *     cargarMetaPixel();
         * }
         */

        document.documentElement.dataset
            .cookieAnalytics =
                consentimiento.analytics
                    ? "true"
                    : "false";


        document.documentElement.dataset
            .cookieMarketing =
                consentimiento.marketing
                    ? "true"
                    : "false";

    }


    /* =====================================================
       MOSTRAR AVISO
    ====================================================== */

    function mostrarAviso() {

        aviso.classList.add(
            "cookie-aviso--visible"
        );

    }


    /* =====================================================
       OCULTAR AVISO
    ====================================================== */

    function ocultarAviso() {

        aviso.classList.remove(
            "cookie-aviso--visible"
        );

    }


    /* =====================================================
       ACEPTAR TODAS
    ====================================================== */

    botonAceptar.addEventListener(
        "click",
        function () {

            guardarConsentimiento(
                true,
                true
            );

        }
    );


    /* =====================================================
       SOLO ESENCIALES
    ====================================================== */

    botonEsenciales.addEventListener(
        "click",
        function () {

            guardarConsentimiento(
                false,
                false
            );

        }
    );


    /* =====================================================
       ABRIR PREFERENCIAS DESDE EL FOOTER
    ====================================================== */

    if (botonPreferencias) {

        botonPreferencias.addEventListener(
            "click",
            function () {

                mostrarAviso();

            }
        );

    }


    /* =====================================================
       CARGA INICIAL
    ====================================================== */

    const consentimiento =
        obtenerConsentimiento();


    if (consentimiento) {

        aplicarConsentimiento(
            consentimiento
        );

    } else {

        window.setTimeout(
            mostrarAviso,
            450
        );

    }

})();