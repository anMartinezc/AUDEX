"use strict";

document.addEventListener(
    "DOMContentLoaded",
    () => {
        const pagina = document.getElementById(
            "favoritosPagina"
        );

        if (!pagina) {
            return;
        }

        const grid = document.getElementById(
            "favoritosPaginaGrid"
        );

        const estadoVacio = document.getElementById(
            "favoritosPaginaVacio"
        );

        const cantidadElemento = document.getElementById(
            "favoritosPaginaCantidad"
        );

        const URL_ALTERNAR =
            pagina.dataset.urlAlternar;

        let solicitudEnCurso = false;


        function obtenerCookie(nombre) {
            const cookies = document.cookie
                ? document.cookie.split(";")
                : [];

            for (const cookieTexto of cookies) {
                const cookie =
                    cookieTexto.trim();

                if (
                    cookie.startsWith(
                        `${nombre}=`
                    )
                ) {
                    return decodeURIComponent(
                        cookie.substring(
                            nombre.length + 1
                        )
                    );
                }
            }

            return "";
        }


        function obtenerCantidadActual() {
            return document.querySelectorAll(
                "[data-favorito-item]"
            ).length;
        }


        function actualizarEstadoPagina() {
            const cantidad =
                obtenerCantidadActual();

            if (cantidadElemento) {
                cantidadElemento.textContent =
                    String(cantidad);
            }

            if (estadoVacio) {
                estadoVacio.hidden =
                    cantidad > 0;
            }

            if (grid) {
                grid.hidden =
                    cantidad === 0;
            }
        }


        function mostrarAviso(
            mensaje,
            esError = false
        ) {
            let aviso = document.getElementById(
                "favoritosPaginaAviso"
            );

            if (!aviso) {
                aviso = document.createElement(
                    "div"
                );

                aviso.id =
                    "favoritosPaginaAviso";

                aviso.className =
                    "favoritos-aviso";

                document.body.appendChild(
                    aviso
                );
            }

            aviso.classList.toggle(
                "favoritos-aviso--error",
                esError
            );

            aviso.textContent = mensaje;

            aviso.classList.add(
                "favoritos-aviso--visible"
            );

            window.clearTimeout(
                aviso._temporizador
            );

            aviso._temporizador =
                window.setTimeout(
                    () => {
                        aviso.classList.remove(
                            "favoritos-aviso--visible"
                        );
                    },
                    2600
                );
        }


        async function eliminarFavorito(
            boton
        ) {
            if (solicitudEnCurso) {
                return;
            }

            const productoId = Number(
                boton.dataset.productoId
            );

            const tarjeta = boton.closest(
                "[data-favorito-item]"
            );

            if (
                !productoId
                || !tarjeta
            ) {
                return;
            }

            solicitudEnCurso = true;
            boton.disabled = true;

            try {
                const respuesta = await fetch(
                    URL_ALTERNAR,
                    {
                        method: "POST",
                        credentials: "same-origin",
                        cache: "no-store",
                        headers: {
                            Accept: "application/json",
                            "Content-Type":
                                "application/json",
                            "X-CSRFToken":
                                obtenerCookie(
                                    "csrftoken"
                                ),
                            "X-Requested-With":
                                "XMLHttpRequest",
                        },
                        body: JSON.stringify(
                            {
                                producto_id:
                                    productoId,
                            }
                        ),
                    }
                );

                const datos =
                    await respuesta.json();

                if (
                    !respuesta.ok
                    || datos.ok === false
                ) {
                    throw new Error(
                        datos.mensaje
                        || (
                            "No fue posible "
                            + "eliminar el favorito."
                        )
                    );
                }

                if (datos.favorito === false) {
                    tarjeta.classList.add(
                        "favorito-card--eliminando"
                    );

                    window.setTimeout(
                        () => {
                            tarjeta.remove();

                            actualizarEstadoPagina();
                        },
                        260
                    );

                    mostrarAviso(
                        datos.mensaje
                    );

                    return;
                }

                mostrarAviso(
                    "El producto continúa en favoritos."
                );

            } catch (error) {
                mostrarAviso(
                    error.message,
                    true
                );

            } finally {
                solicitudEnCurso = false;

                if (document.body.contains(boton)) {
                    boton.disabled = false;
                }
            }
        }


        document.addEventListener(
            "click",
            (evento) => {
                const boton = evento.target.closest(
                    ".js-quitar-favorito-pagina"
                );

                if (!boton) {
                    return;
                }

                evento.preventDefault();

                eliminarFavorito(
                    boton
                );
            }
        );


        actualizarEstadoPagina();
    }
);