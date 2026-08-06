"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const cantidadInput = document.getElementById(
        "cantidadProducto"
    );

    const botonRestar = document.getElementById(
        "restarCantidad"
    );

    const botonSumar = document.getElementById(
        "sumarCantidad"
    );

    const botonAgregar = document.getElementById(
        "agregarCarritoDetalle"
    );

    const imagenPrincipal = document.getElementById(
        "imagenProductoPrincipal"
    );

    const miniaturas = [
        ...document.querySelectorAll(
            ".detalle-miniatura[data-imagen-url]"
        ),
    ];

    const botonAbrirZoom = document.getElementById(
        "abrirZoomProducto"
    );

    const modal = document.getElementById(
        "modalImagenProducto"
    );

    const imagenModal = document.getElementById(
        "imagenModalProducto"
    );

    const botonCerrarZoom = document.getElementById(
        "cerrarZoomProducto"
    );

    const botonImagenAnterior = document.getElementById(
        "imagenAnteriorProducto"
    );

    const botonImagenSiguiente = document.getElementById(
        "imagenSiguienteProducto"
    );

    const botonFavorito = document.getElementById(
        "favoritoDetalle"
    );

    const FAVORITOS_KEY = "audex_favoritos";

    let indiceImagenActual = 0;

    function numeroSeguro(valor, respaldo = 0) {
        const numero = Number(valor);

        return Number.isFinite(numero)
            ? numero
            : respaldo;
    }

    function obtenerStock() {
        return Math.max(
            0,
            numeroSeguro(
                botonAgregar?.dataset.stock
                ?? cantidadInput?.max,
                0
            )
        );
    }

    function obtenerCantidad() {
        return numeroSeguro(
            cantidadInput?.value,
            obtenerStock() > 0 ? 1 : 0
        );
    }

    function establecerCantidad(nuevaCantidad) {
        if (!cantidadInput) {
            return;
        }

        const stock = obtenerStock();

        if (stock <= 0) {
            cantidadInput.value = "0";

            if (botonRestar) {
                botonRestar.disabled = true;
            }

            if (botonSumar) {
                botonSumar.disabled = true;
            }

            if (botonAgregar) {
                botonAgregar.disabled = true;
                botonAgregar.dataset.cantidad = "0";
                botonAgregar.setAttribute(
                    "aria-disabled",
                    "true"
                );
            }

            return;
        }

        const cantidad = Math.min(
            stock,
            Math.max(
                1,
                numeroSeguro(nuevaCantidad, 1)
            )
        );

        cantidadInput.value = String(cantidad);

        if (botonRestar) {
            botonRestar.disabled =
                cantidad <= 1;
        }

        if (botonSumar) {
            botonSumar.disabled =
                cantidad >= stock;
        }

        if (botonAgregar) {
            botonAgregar.dataset.cantidad =
                String(cantidad);

            const procesando =
                botonAgregar.dataset.procesando === "true";

            if (!procesando) {
                botonAgregar.disabled = false;

                botonAgregar.setAttribute(
                    "aria-disabled",
                    "false"
                );
            }
        }
    }

    botonRestar?.addEventListener(
        "click",
        () => {
            establecerCantidad(
                obtenerCantidad() - 1
            );
        }
    );

    botonSumar?.addEventListener(
        "click",
        () => {
            establecerCantidad(
                obtenerCantidad() + 1
            );
        }
    );

    /*
     * Mantiene data-cantidad sincronizado para que carrito.js
     * reciba la cantidad elegida sin registrar un segundo evento
     * de agregado al carrito.
     */
    botonAgregar?.addEventListener(
        "pointerdown",
        () => {
            botonAgregar.dataset.cantidad =
                String(obtenerCantidad());
        },
        {
            capture: true,
        }
    );

    establecerCantidad(
        obtenerStock() > 0 ? 1 : 0
    );

    function obtenerImagenes() {
        return miniaturas
            .map((miniatura) => ({
                url: miniatura.dataset.imagenUrl || "",
                alt:
                    miniatura.dataset.imagenAlt
                    || imagenPrincipal?.alt
                    || "Imagen del producto",
            }))
            .filter((imagen) => imagen.url);
    }

    function marcarMiniaturaActiva(indice) {
        miniaturas.forEach(
            (miniatura, posicion) => {
                const activa = posicion === indice;

                miniatura.classList.toggle(
                    "detalle-miniatura--activa",
                    activa
                );

                miniatura.setAttribute(
                    "aria-pressed",
                    activa ? "true" : "false"
                );
            }
        );
    }

    function mostrarImagen(indice) {
        const imagenes = obtenerImagenes();

        if (
            !imagenes.length
            || !imagenPrincipal
        ) {
            return;
        }

        const indiceNormalizado =
            (indice + imagenes.length)
            % imagenes.length;

        indiceImagenActual =
            indiceNormalizado;

        const imagen =
            imagenes[indiceNormalizado];

        imagenPrincipal.src = imagen.url;
        imagenPrincipal.alt = imagen.alt;
        imagenPrincipal.dataset.indice =
            String(indiceNormalizado);

        marcarMiniaturaActiva(
            indiceNormalizado
        );

        if (
            modal?.getAttribute("aria-hidden")
            === "false"
        ) {
            actualizarImagenModal();
        }
    }

    miniaturas.forEach(
        (miniatura, indice) => {
            miniatura.addEventListener(
                "click",
                () => {
                    mostrarImagen(indice);
                }
            );
        }
    );

    function actualizarImagenModal() {
        const imagenes = obtenerImagenes();

        if (
            !imagenModal
            || !imagenes.length
        ) {
            return;
        }

        const imagen =
            imagenes[indiceImagenActual];

        imagenModal.src = imagen.url;
        imagenModal.alt = imagen.alt;

        const hayVarias =
            imagenes.length > 1;

        if (botonImagenAnterior) {
            botonImagenAnterior.hidden =
                !hayVarias;
        }

        if (botonImagenSiguiente) {
            botonImagenSiguiente.hidden =
                !hayVarias;
        }
    }

    function abrirModal() {
        if (
            !modal
            || !imagenPrincipal?.src
        ) {
            return;
        }

        indiceImagenActual = Math.max(
            0,
            numeroSeguro(
                imagenPrincipal.dataset.indice,
                0
            )
        );

        actualizarImagenModal();

        modal.classList.add(
            "detalle-modal--activo"
        );

        modal.setAttribute(
            "aria-hidden",
            "false"
        );

        botonAbrirZoom?.setAttribute(
            "aria-expanded",
            "true"
        );

        document.body.classList.add(
            "no-scroll"
        );

        botonCerrarZoom?.focus();
    }

    function cerrarModal() {
        if (!modal) {
            return;
        }

        modal.classList.remove(
            "detalle-modal--activo"
        );

        modal.setAttribute(
            "aria-hidden",
            "true"
        );

        botonAbrirZoom?.setAttribute(
            "aria-expanded",
            "false"
        );

        document.body.classList.remove(
            "no-scroll"
        );

        botonAbrirZoom?.focus();
    }

    botonAbrirZoom?.addEventListener(
        "click",
        abrirModal
    );

    botonCerrarZoom?.addEventListener(
        "click",
        cerrarModal
    );

    botonImagenAnterior?.addEventListener(
        "click",
        () => {
            mostrarImagen(
                indiceImagenActual - 1
            );
        }
    );

    botonImagenSiguiente?.addEventListener(
        "click",
        () => {
            mostrarImagen(
                indiceImagenActual + 1
            );
        }
    );

    modal?.addEventListener(
        "click",
        (evento) => {
            if (evento.target === modal) {
                cerrarModal();
            }
        }
    );

    document.addEventListener(
        "keydown",
        (evento) => {
            const modalAbierto =
                modal?.getAttribute("aria-hidden")
                === "false";

            if (!modalAbierto) {
                return;
            }

            if (evento.key === "Escape") {
                cerrarModal();
            }

            if (evento.key === "ArrowLeft") {
                mostrarImagen(
                    indiceImagenActual - 1
                );
            }

            if (evento.key === "ArrowRight") {
                mostrarImagen(
                    indiceImagenActual + 1
                );
            }
        }
    );

    function leerFavoritos() {
        try {
            const valor = localStorage.getItem(
                FAVORITOS_KEY
            );

            const favoritos = JSON.parse(
                valor || "[]"
            );

            return Array.isArray(favoritos)
                ? favoritos.map(String)
                : [];
        } catch {
            return [];
        }
    }

    function guardarFavoritos(favoritos) {
        localStorage.setItem(
            FAVORITOS_KEY,
            JSON.stringify(favoritos)
        );
    }

    function actualizarFavoritoVisual(
        esFavorito
    ) {
        if (!botonFavorito) {
            return;
        }

        const icono =
            botonFavorito.querySelector("i");

        const texto =
            botonFavorito.querySelector("span");

        botonFavorito.classList.toggle(
            "detalle-favorito--activo",
            esFavorito
        );

        botonFavorito.setAttribute(
            "aria-pressed",
            esFavorito ? "true" : "false"
        );

        if (icono) {
            icono.classList.toggle(
                "bi-heart",
                !esFavorito
            );

            icono.classList.toggle(
                "bi-heart-fill",
                esFavorito
            );
        }

        if (texto) {
            texto.textContent = esFavorito
                ? "Guardado en favoritos"
                : "Guardar en favoritos";
        }
    }

    function iniciarFavorito() {
        if (!botonFavorito) {
            return;
        }

        const productoId = String(
            botonFavorito.dataset.productoId
            || ""
        );

        if (!productoId) {
            botonFavorito.disabled = true;
            return;
        }

        const favoritos = leerFavoritos();

        actualizarFavoritoVisual(
            favoritos.includes(productoId)
        );
    }

    botonFavorito?.addEventListener(
        "click",
        () => {
            const productoId = String(
                botonFavorito.dataset.productoId
                || ""
            );

            if (!productoId) {
                return;
            }

            const favoritos =
                leerFavoritos();

            const yaExiste =
                favoritos.includes(productoId);

            const nuevosFavoritos = yaExiste
                ? favoritos.filter(
                    (id) => id !== productoId
                )
                : [...favoritos, productoId];

            guardarFavoritos(
                nuevosFavoritos
            );

            actualizarFavoritoVisual(
                !yaExiste
            );
        }
    );

    iniciarFavorito();

    /*
     * Chrome puede restaurar botones deshabilitados al volver
     * desde la caché de navegación. Recalculamos el estado.
     */
    window.addEventListener(
        "pageshow",
        () => {
            establecerCantidad(
                obtenerCantidad()
            );

            iniciarFavorito();
        }
    );
});