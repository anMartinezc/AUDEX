"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const pagina = document.getElementById("carritoPagina");

    if (!pagina) {
        return;
    }

    const productosContenedor = document.getElementById(
        "carritoPaginaProductos"
    );

    const cantidadElemento = document.getElementById(
        "carritoPaginaCantidad"
    );

    const subtotalElemento = document.getElementById(
        "carritoPaginaSubtotal"
    );

    const totalElemento = document.getElementById(
        "carritoPaginaTotal"
    );

    const contadorHeader = document.getElementById(
        "carritoContador"
    );

    const botonVaciar = document.getElementById(
        "carritoPaginaVaciar"
    );

    const botonContinuar = document.getElementById(
        "continuarCompra"
    );

    const mensajeEnvio = document.getElementById(
        "carritoPaginaMensajeEnvio"
    );

    const progresoEnvio = document.getElementById(
        "carritoPaginaProgreso"
    );

    const codigoInput = document.getElementById(
        "codigoDescuento"
    );

    const botonCodigo = document.getElementById(
        "aplicarCodigoDescuento"
    );

    const mensajeCodigo = document.getElementById(
        "mensajeCodigoDescuento"
    );

    const filaDescuento = document.getElementById(
        "filaDescuento"
    );

    const descuentoElemento = document.getElementById(
        "carritoPaginaDescuento"
    );

    const toast = document.getElementById(
        "carritoPaginaToast"
    );

    const toastTexto = document.getElementById(
        "carritoPaginaToastTexto"
    );

    const urls = {
        estado: pagina.dataset.urlEstado,
        actualizar: pagina.dataset.urlActualizar,
        eliminar: pagina.dataset.urlEliminar,
        vaciar: pagina.dataset.urlVaciar,
    };

    const META_ENVIO_GRATIS = 50000;

    let carritoActual = null;
    let porcentajeDescuento = 0;
    let temporizadorToast = null;

    function obtenerCookie(nombre) {
        const cookies = document.cookie
            ? document.cookie.split(";")
            : [];

        for (const cookie of cookies) {
            const limpia = cookie.trim();

            if (limpia.startsWith(`${nombre}=`)) {
                return decodeURIComponent(
                    limpia.substring(nombre.length + 1)
                );
            }
        }

        return "";
    }

    async function solicitar(url, cuerpo = null) {
        const esGet = cuerpo === null;

        const configuracion = {
            method: esGet ? "GET" : "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        };

        if (!esGet) {
            configuracion.headers["Content-Type"] =
                "application/json";

            configuracion.headers["X-CSRFToken"] =
                obtenerCookie("csrftoken");

            configuracion.body = JSON.stringify(cuerpo);
        }

        const respuesta = await fetch(url, configuracion);
        const datos = await respuesta.json();

        if (!respuesta.ok || datos.ok === false) {
            throw new Error(
                datos.mensaje ||
                "No fue posible completar la operación."
            );
        }

        return datos;
    }

    function escaparHTML(valor) {
        const elemento = document.createElement("div");
        elemento.textContent = String(valor ?? "");

        return elemento.innerHTML;
    }

    function mostrarToast(texto) {
        if (!toast) {
            return;
        }

        toastTexto.textContent = texto;

        toast.classList.add(
            "carrito-pagina-toast--visible"
        );

        toast.setAttribute("aria-hidden", "false");

        window.clearTimeout(temporizadorToast);

        temporizadorToast = window.setTimeout(() => {
            toast.classList.remove(
                "carrito-pagina-toast--visible"
            );

            toast.setAttribute("aria-hidden", "true");
        }, 2500);
    }

    function actualizarEnvio(subtotal) {
        const porcentaje = Math.min(
            subtotal / META_ENVIO_GRATIS * 100,
            100
        );

        progresoEnvio.style.width = `${porcentaje}%`;

        if (subtotal >= META_ENVIO_GRATIS) {
            mensajeEnvio.innerHTML = `
                <i class="bi bi-check-circle-fill"></i>
                ¡Tienes despacho gratis!
            `;

            return;
        }

        const faltante = META_ENVIO_GRATIS - subtotal;

        mensajeEnvio.textContent =
            `Te faltan $${faltante.toLocaleString(
                "es-CL"
            )} para despacho gratis.`;
    }

    function actualizarResumen(carrito) {
        const descuento = Math.round(
            carrito.subtotal * porcentajeDescuento
        );

        const total = carrito.subtotal - descuento;

        subtotalElemento.textContent =
            carrito.subtotal_formateado;

        totalElemento.textContent =
            `$${total.toLocaleString("es-CL")}`;

        contadorHeader.textContent =
            carrito.cantidad_total;

        cantidadElemento.textContent =
            `${carrito.cantidad_total} ${
                carrito.cantidad_total === 1
                    ? "producto"
                    : "productos"
            }`;

        botonVaciar.hidden = carrito.vacio;
        botonContinuar.disabled = carrito.vacio;

        if (descuento > 0) {
            filaDescuento.hidden = false;

            descuentoElemento.textContent =
                `-$${descuento.toLocaleString("es-CL")}`;
        } else {
            filaDescuento.hidden = true;
        }

        actualizarEnvio(carrito.subtotal);
    }

    function plantillaVacia() {
        return `
            <div class="carrito-pagina-vacio">
                <div class="carrito-pagina-vacio__icono">
                    <i class="bi bi-bag"></i>
                </div>

                <h2>Tu carrito está vacío</h2>

                <p>
                    Explora nuestro catálogo y agrega los
                    audífonos que más te gusten.
                </p>

                <a
                    href="/productos/"
                    class="boton boton--primario"
                >
                    Explorar productos
                    <i class="bi bi-arrow-right"></i>
                </a>
            </div>
        `;
    }

    function plantillaProducto(item) {
        const imagen = item.imagen
            ? `
                <img
                    src="${escaparHTML(item.imagen)}"
                    alt="${escaparHTML(item.nombre)}"
                >
            `
            : `<i class="bi bi-earbuds"></i>`;

        const oferta = item.en_oferta
            ? `
                <span class="carrito-producto__oferta">
                    Oferta
                </span>
            `
            : "";

        return `
            <article
                class="carrito-producto"
                data-producto-id="${item.id}"
            >
                <a
                    href="${escaparHTML(item.url_detalle)}"
                    class="carrito-producto__imagen"
                >
                    ${imagen}
                </a>

                <div class="carrito-producto__informacion">
                    <div class="carrito-producto__superior">
                        <div>
                            <div class="carrito-producto__etiquetas">
                                <span class="carrito-producto__categoria">
                                    ${escaparHTML(item.categoria)}
                                </span>

                                ${oferta}
                            </div>

                            <h3>
                                <a href="${escaparHTML(
                                    item.url_detalle
                                )}">
                                    ${escaparHTML(item.nombre)}
                                </a>
                            </h3>

                            <span class="carrito-producto__unitario">
                                Precio unitario:
                                ${escaparHTML(
                                    item.precio_formateado
                                )}
                            </span>
                        </div>

                        <button
                            type="button"
                            class="carrito-producto__eliminar"
                            data-carrito-pagina-accion="eliminar"
                            aria-label="Eliminar producto"
                        >
                            <i class="bi bi-trash3"></i>
                        </button>
                    </div>

                    <div class="carrito-producto__inferior">
                        <div class="carrito-producto__cantidad">
                            <span>Cantidad</span>

                            <div>
                                <button
                                    type="button"
                                    data-carrito-pagina-accion="restar"
                                >
                                    <i class="bi bi-dash-lg"></i>
                                </button>

                                <strong>${item.cantidad}</strong>

                                <button
                                    type="button"
                                    data-carrito-pagina-accion="sumar"
                                    ${
                                        item.cantidad >= item.stock
                                            ? "disabled"
                                            : ""
                                    }
                                >
                                    <i class="bi bi-plus-lg"></i>
                                </button>
                            </div>

                            <small>
                                ${item.stock} unidades disponibles
                            </small>
                        </div>

                        <div class="carrito-producto__total">
                            <span>Total</span>

                            <strong>
                                ${escaparHTML(
                                    item.total_formateado
                                )}
                            </strong>
                        </div>
                    </div>
                </div>
            </article>
        `;
    }

    function renderizar(carrito) {
        carritoActual = carrito;

        productosContenedor.innerHTML = carrito.vacio
            ? plantillaVacia()
            : carrito.items.map(plantillaProducto).join("");

        actualizarResumen(carrito);
    }

    async function cargarCarrito() {
        try {
            const datos = await solicitar(urls.estado);
            renderizar(datos.carrito);
        } catch (error) {
            productosContenedor.innerHTML = `
                <div class="carrito-pagina-vacio">
                    <i class="bi bi-exclamation-circle"></i>
                    <h2>No pudimos cargar el carrito</h2>
                    <p>${escaparHTML(error.message)}</p>
                </div>
            `;
        }
    }

    async function actualizarCantidad(
        productoId,
        cantidad
    ) {
        try {
            const datos = await solicitar(
                urls.actualizar,
                {
                    producto_id: productoId,
                    cantidad,
                }
            );

            renderizar(datos.carrito);

            const producto = productosContenedor.querySelector(
                `[data-producto-id="${productoId}"]`
            );

            producto?.classList.add(
                "carrito-producto--actualizado"
            );

            mostrarToast("La cantidad fue actualizada.");
        } catch (error) {
            mostrarToast(error.message);
        }
    }

    async function eliminarProducto(productoId) {
        const elemento = productosContenedor.querySelector(
            `[data-producto-id="${productoId}"]`
        );

        elemento?.classList.add(
            "carrito-producto--eliminando"
        );

        window.setTimeout(async () => {
            try {
                const datos = await solicitar(
                    urls.eliminar,
                    {
                        producto_id: productoId,
                    }
                );

                renderizar(datos.carrito);
                mostrarToast("El producto fue eliminado.");
            } catch (error) {
                elemento?.classList.remove(
                    "carrito-producto--eliminando"
                );

                mostrarToast(error.message);
            }
        }, 250);
    }

    productosContenedor.addEventListener(
        "click",
        (evento) => {
            const boton = evento.target.closest(
                "[data-carrito-pagina-accion]"
            );

            if (!boton) {
                return;
            }

            const productoElemento = boton.closest(
                ".carrito-producto"
            );

            const productoId = Number(
                productoElemento?.dataset.productoId
            );

            const producto = carritoActual?.items.find(
                (item) => item.id === productoId
            );

            if (!producto) {
                return;
            }

            const accion =
                boton.dataset.carritoPaginaAccion;

            if (accion === "sumar") {
                actualizarCantidad(
                    productoId,
                    producto.cantidad + 1
                );
            }

            if (accion === "restar") {
                actualizarCantidad(
                    productoId,
                    producto.cantidad - 1
                );
            }

            if (accion === "eliminar") {
                eliminarProducto(productoId);
            }
        }
    );

    botonVaciar?.addEventListener("click", async () => {
        const confirmar = window.confirm(
            "¿Deseas eliminar todos los productos del carrito?"
        );

        if (!confirmar) {
            return;
        }

        try {
            const datos = await solicitar(
                urls.vaciar,
                {}
            );

            porcentajeDescuento = 0;
            renderizar(datos.carrito);

            mostrarToast("El carrito fue vaciado.");
        } catch (error) {
            mostrarToast(error.message);
        }
    });

    botonCodigo?.addEventListener("click", () => {
        const codigo = codigoInput.value
            .trim()
            .toUpperCase();

        mensajeCodigo.className = "";

        if (codigo === "AUDEX10") {
            porcentajeDescuento = 0.10;

            mensajeCodigo.textContent =
                "Código aplicado: 10% de descuento.";

            mensajeCodigo.classList.add(
                "codigo-correcto"
            );

            if (carritoActual) {
                actualizarResumen(carritoActual);
            }

            return;
        }

        porcentajeDescuento = 0;

        mensajeCodigo.textContent =
            "El código ingresado no es válido.";

        mensajeCodigo.classList.add(
            "codigo-error"
        );

        if (carritoActual) {
            actualizarResumen(carritoActual);
        }
    });

 

    cargarCarrito();
});