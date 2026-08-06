"use strict";

/* =========================================================
   AUDEX ECOMMERCE
   Archivo: core/static/core/js/app.js
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;

    const header = document.getElementById("header");
    const overlay = document.getElementById("overlay");

    const abrirMenu = document.getElementById("abrirMenu");
    const cerrarMenu = document.getElementById("cerrarMenu");
    const menuMovil = document.getElementById("menuMovil");

    const abrirCarrito = document.getElementById("abrirCarrito");
    const cerrarCarrito = document.getElementById("cerrarCarrito");
    const carritoLateral = document.getElementById("carritoLateral");
    const irProductos = document.getElementById("irProductos");

    const abrirBusqueda = document.getElementById("abrirBusqueda");
    const cerrarBusqueda = document.getElementById("cerrarBusqueda");
    const buscadorModal = document.getElementById("buscadorModal");
    const busquedaProducto = document.getElementById(
        "busquedaProducto"
    );

    const volverArriba = document.getElementById("volverArriba");

    const newsletterFormulario = document.querySelector(
        ".newsletter__formulario"
    );


    const existe = (elemento) => elemento !== null;


    const bloquearPantalla = () => {
        body.classList.add("no-scroll");
    };


    const desbloquearPantalla = () => {
        body.classList.remove("no-scroll");
    };


    const mostrarOverlay = () => {
        if (existe(overlay)) {
            overlay.classList.add("overlay--activo");
        }

        bloquearPantalla();
    };


    const ocultarOverlay = () => {
        if (existe(overlay)) {
            overlay.classList.remove("overlay--activo");
        }

        desbloquearPantalla();
    };


    const cerrarTodosLosPaneles = () => {
        if (existe(menuMovil)) {
            menuMovil.classList.remove(
                "menu-movil--activo"
            );

            menuMovil.setAttribute(
                "aria-hidden",
                "true"
            );
        }

        if (existe(carritoLateral)) {
            carritoLateral.classList.remove(
                "carrito-lateral--activo"
            );

            carritoLateral.setAttribute(
                "aria-hidden",
                "true"
            );
        }

        if (existe(buscadorModal)) {
            buscadorModal.classList.remove(
                "buscador-modal--activo"
            );

            buscadorModal.setAttribute(
                "aria-hidden",
                "true"
            );
        }

        if (existe(abrirMenu)) {
            abrirMenu.setAttribute(
                "aria-expanded",
                "false"
            );
        }

        ocultarOverlay();
    };


    /* Header al hacer scroll */

    const controlarHeader = () => {
        if (!existe(header)) {
            return;
        }

        header.classList.toggle(
            "header--scroll",
            window.scrollY > 30
        );
    };

    controlarHeader();

    window.addEventListener(
        "scroll",
        controlarHeader
    );


    /* Menú móvil */

    if (
        existe(abrirMenu) &&
        existe(cerrarMenu) &&
        existe(menuMovil)
    ) {
        abrirMenu.addEventListener("click", () => {
            cerrarTodosLosPaneles();

            menuMovil.classList.add(
                "menu-movil--activo"
            );

            menuMovil.setAttribute(
                "aria-hidden",
                "false"
            );

            abrirMenu.setAttribute(
                "aria-expanded",
                "true"
            );

            mostrarOverlay();
        });

        cerrarMenu.addEventListener(
            "click",
            cerrarTodosLosPaneles
        );

        menuMovil
            .querySelectorAll("a")
            .forEach((enlace) => {
                enlace.addEventListener(
                    "click",
                    cerrarTodosLosPaneles
                );
            });
    }


    /* Carrito lateral */

    if (
        existe(abrirCarrito) &&
        existe(cerrarCarrito) &&
        existe(carritoLateral)
    ) {
        abrirCarrito.addEventListener("click", () => {
            cerrarTodosLosPaneles();

            carritoLateral.classList.add(
                "carrito-lateral--activo"
            );

            carritoLateral.setAttribute(
                "aria-hidden",
                "false"
            );

            mostrarOverlay();
        });

        cerrarCarrito.addEventListener(
            "click",
            cerrarTodosLosPaneles
        );
    }


    if (existe(irProductos)) {
        irProductos.addEventListener("click", () => {
            cerrarTodosLosPaneles();

            const productos = document.getElementById(
                "productos"
            );

            if (productos) {
                productos.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }
        });
    }


    /* Buscador */

    if (
        existe(abrirBusqueda) &&
        existe(cerrarBusqueda) &&
        existe(buscadorModal)
    ) {
        abrirBusqueda.addEventListener("click", () => {
            cerrarTodosLosPaneles();

            buscadorModal.classList.add(
                "buscador-modal--activo"
            );

            buscadorModal.setAttribute(
                "aria-hidden",
                "false"
            );

            bloquearPantalla();

            window.setTimeout(() => {
                if (existe(busquedaProducto)) {
                    busquedaProducto.focus();
                }
            }, 200);
        });

        cerrarBusqueda.addEventListener(
            "click",
            cerrarTodosLosPaneles
        );
    }


    /* Overlay */

    if (existe(overlay)) {
        overlay.addEventListener(
            "click",
            cerrarTodosLosPaneles
        );
    }


    /* Cerrar paneles con Escape */

    document.addEventListener("keydown", (evento) => {
        if (evento.key !== "Escape") {
            return;
        }

        const logoutModal = document.getElementById(
            "logoutModal"
        );

        if (
            logoutModal &&
            !logoutModal.hidden
        ) {
            return;
        }

        cerrarTodosLosPaneles();
    });


    /* Volver arriba */

    const controlarBotonArriba = () => {
        if (!existe(volverArriba)) {
            return;
        }

        volverArriba.classList.toggle(
            "volver-arriba--visible",
            window.scrollY > 450
        );
    };

    controlarBotonArriba();

    window.addEventListener(
        "scroll",
        controlarBotonArriba
    );

    if (existe(volverArriba)) {
        volverArriba.addEventListener("click", () => {
            window.scrollTo({
                top: 0,
                behavior: "smooth",
            });
        });
    }


    /* Newsletter */

    if (existe(newsletterFormulario)) {
        newsletterFormulario.addEventListener(
            "submit",
            (evento) => {
                evento.preventDefault();

                const email = newsletterFormulario.querySelector(
                    'input[type="email"]'
                );

                if (
                    !email ||
                    !email.value.trim()
                ) {
                    mostrarNotificacion(
                        "Ingresa un correo electrónico válido.",
                        "error"
                    );

                    return;
                }

                mostrarNotificacion(
                    "¡Gracias por suscribirte a Audex!",
                    "success"
                );

                newsletterFormulario.reset();
            }
        );
    }


    /* Mensajes Django */

    document
        .querySelectorAll(".mensaje__cerrar")
        .forEach((boton) => {
            boton.addEventListener("click", () => {
                const mensaje = boton.closest(
                    ".mensaje"
                );

                if (mensaje) {
                    mensaje.remove();
                }
            });
        });


    document
        .querySelectorAll(".mensaje")
        .forEach((mensaje) => {
            window.setTimeout(() => {
                mensaje.style.opacity = "0";
                mensaje.style.transform =
                    "translateX(20px)";

                window.setTimeout(() => {
                    mensaje.remove();
                }, 300);
            }, 5000);
        });


    /* Notificaciones dinámicas */

    function mostrarNotificacion(
        texto,
        tipo = "success"
    ) {
        let contenedor = document.querySelector(
            ".mensajes-django"
        );

        if (!contenedor) {
            contenedor = document.createElement(
                "div"
            );

            contenedor.className =
                "mensajes-django";

            document.body.appendChild(
                contenedor
            );
        }

        const mensaje = document.createElement(
            "div"
        );

        mensaje.className =
            `mensaje mensaje--${tipo}`;

        mensaje.innerHTML = `
            <span>${texto}</span>

            <button
                type="button"
                class="mensaje__cerrar"
                aria-label="Cerrar mensaje"
            >
                Cerrar
            </button>
        `;

        contenedor.appendChild(mensaje);

        const botonCerrar = mensaje.querySelector(
            ".mensaje__cerrar"
        );

        if (botonCerrar) {
            botonCerrar.addEventListener(
                "click",
                () => {
                    mensaje.remove();
                }
            );
        }

        window.setTimeout(() => {
            mensaje.style.opacity = "0";
            mensaje.style.transform =
                "translateX(20px)";
            mensaje.style.transition =
                "0.3s ease";

            window.setTimeout(() => {
                mensaje.remove();
            }, 300);
        }, 4500);
    }


    /* Animaciones de entrada */

    const elementosAnimados =
        document.querySelectorAll(
            ".beneficio, " +
            ".newsletter__contenido, " +
            ".footer__grid"
        );

    if ("IntersectionObserver" in window) {
        elementosAnimados.forEach((elemento) => {
            elemento.style.opacity = "0";
            elemento.style.transform =
                "translateY(25px)";
            elemento.style.transition =
                "opacity 0.65s ease, " +
                "transform 0.65s ease";
        });

        const observador = new IntersectionObserver(
            (entradas, observer) => {
                entradas.forEach((entrada) => {
                    if (entrada.isIntersecting) {
                        entrada.target.style.opacity =
                            "1";

                        entrada.target.style.transform =
                            "translateY(0)";

                        observer.unobserve(
                            entrada.target
                        );
                    }
                });
            },
            {
                threshold: 0.12,
            }
        );

        elementosAnimados.forEach((elemento) => {
            observador.observe(elemento);
        });
    }


    console.log(
        "Audex Ecommerce cargado correctamente."
    );
});



