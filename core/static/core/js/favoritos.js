"use strict";

document.addEventListener(
    "DOMContentLoaded",
    () => {
        const botones = document.querySelectorAll(
            ".js-favorito"
        );

        if (botones.length === 0) {
            return;
        }

        const primerBoton = botones[0];

        const URL_ESTADO =
            primerBoton.dataset.urlEstado;

        const URL_ALTERNAR =
            primerBoton.dataset.urlAlternar;

        let idsFavoritos = new Set();


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


        async function solicitar(
            url,
            opciones = {}
        ) {
            const metodo =
                opciones.method || "GET";

            const configuracion = {
                method: metodo,
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    Accept: "application/json",
                },
            };

            if (metodo !== "GET") {
                configuracion.headers[
                    "Content-Type"
                ] = "application/json";

                configuracion.headers[
                    "X-CSRFToken"
                ] = obtenerCookie(
                    "csrftoken"
                );

                configuracion.headers[
                    "X-Requested-With"
                ] = "XMLHttpRequest";

                configuracion.body =
                    JSON.stringify(
                        opciones.body || {}
                    );
            }

            const respuesta = await fetch(
                url,
                configuracion
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
                        + "actualizar favoritos."
                    )
                );
            }

            return datos;
        }


        function actualizarBoton(
            boton,
            activo
        ) {
            const icono =
                boton.querySelector("i");

            boton.classList.toggle(
                "boton-favorito--activo",
                activo
            );

            boton.setAttribute(
                "aria-pressed",
                String(activo)
            );

            const texto = activo
                ? "Eliminar de favoritos"
                : "Guardar en favoritos";

            boton.setAttribute(
                "aria-label",
                texto
            );

            boton.setAttribute(
                "title",
                texto
            );

            if (icono) {
                icono.className = activo
                    ? "bi bi-heart-fill"
                    : "bi bi-heart";
            }
        }


        function actualizarTodosLosBotones() {
            document
                .querySelectorAll(
                    ".js-favorito"
                )
                .forEach((boton) => {
                    const productoId = Number(
                        boton.dataset.productoId
                    );

                    actualizarBoton(
                        boton,
                        idsFavoritos.has(
                            productoId
                        )
                    );
                });
        }


        function mostrarAviso(
            mensaje,
            esError = false
        ) {
            let aviso =
                document.getElementById(
                    "favoritosAviso"
                );

            if (!aviso) {
                aviso =
                    document.createElement(
                        "div"
                    );

                aviso.id =
                    "favoritosAviso";

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
                    2800
                );
        }


        async function cargarFavoritos() {
            try {
                const datos =
                    await solicitar(
                        URL_ESTADO
                    );

                idsFavoritos = new Set(
                    (
                        datos.favoritos?.ids
                        || []
                    ).map(Number)
                );

                actualizarTodosLosBotones();

            } catch (error) {
                console.error(
                    error
                );
            }
        }


        document.addEventListener(
            "click",
            async (evento) => {
                const boton =
                    evento.target.closest(
                        ".js-favorito"
                    );

                if (!boton) {
                    return;
                }

                evento.preventDefault();

                if (
                    boton.dataset.cargando
                    === "true"
                ) {
                    return;
                }

                const productoId = Number(
                    boton.dataset.productoId
                );

                boton.dataset.cargando =
                    "true";

                boton.disabled = true;

                try {
                    const datos =
                        await solicitar(
                            URL_ALTERNAR,
                            {
                                method: "POST",
                                body: {
                                    producto_id:
                                        productoId,
                                },
                            }
                        );

                    idsFavoritos = new Set(
                        (
                            datos.favoritos?.ids
                            || []
                        ).map(Number)
                    );

                    actualizarTodosLosBotones();

                    mostrarAviso(
                        datos.mensaje
                    );

                } catch (error) {
                    mostrarAviso(
                        error.message,
                        true
                    );

                } finally {
                    boton.disabled = false;

                    boton.dataset.cargando =
                        "false";
                }
            }
        );


        cargarFavoritos();
    }
);