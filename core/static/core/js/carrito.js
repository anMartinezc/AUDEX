"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const carritoLateral = document.getElementById(
        "carritoLateral"
    );

    if (!carritoLateral) {
        return;
    }

    const abrirCarrito = document.getElementById(
        "abrirCarrito"
    );

    const cerrarCarrito = document.getElementById(
        "cerrarCarrito"
    );

    const overlay = document.getElementById("overlay");

    const productosContenedor = document.getElementById(
        "carritoProductos"
    );

    const subtotalElemento = document.getElementById(
        "carritoSubtotal"
    );

    const contadorElemento = document.getElementById(
        "carritoContador"
    );

    const finalizarCompra = document.getElementById(
        "finalizarCompra"
    );

    const vaciarCarrito = document.getElementById(
        "vaciarCarrito"
    );

    const confirmacion = document.getElementById(
        "carritoConfirmacion"
    );

    const confirmacionTexto = document.getElementById(
        "carritoConfirmacionTexto"
    );

    const progresoEnvio = document.getElementById(
        "carritoProgresoEnvio"
    );

    const mensajeEnvio = document.getElementById(
        "carritoMensajeEnvio"
    );

    const URL_ESTADO = carritoLateral.dataset.urlEstado;
    const URL_AGREGAR = carritoLateral.dataset.urlAgregar;
    const URL_ACTUALIZAR =
        carritoLateral.dataset.urlActualizar;
    const URL_ELIMINAR =
        carritoLateral.dataset.urlEliminar;
    const URL_VACIAR = carritoLateral.dataset.urlVaciar;

    const META_ENVIO_GRATIS = 50000;

    let temporizadorConfirmacion = null;
    let carritoActual = null;
    let solicitudEnCurso = false;

    function obtenerCookie(nombre) {
        const cookies = document.cookie
            ? document.cookie.split(";")
            : [];

        for (const cookieTexto of cookies) {
            const cookie = cookieTexto.trim();

            if (cookie.startsWith(`${nombre}=`)) {
                return decodeURIComponent(
                    cookie.substring(nombre.length + 1)
                );
            }
        }

        return null;
    }

    function obtenerTokenCsrf() {
        const tokenCookie = obtenerCookie("csrftoken");

        if (tokenCookie) {
            return tokenCookie;
        }

        const inputCsrf = document.querySelector(
            'input[name="csrfmiddlewaretoken"]'
        );

        return inputCsrf?.value || null;
    }

    async function solicitar(url, opciones = {}) {
        const configuracion = {
            method: opciones.method || "GET",
            headers: {
                Accept: "application/json",
                ...(opciones.headers || {}),
            },
            credentials: "same-origin",
            cache: "no-store",
        };

        if (configuracion.method !== "GET") {
            const csrfToken = obtenerTokenCsrf();

            if (!csrfToken) {
                throw new Error(
                    "No se encontró el token CSRF. Recarga la página e intenta nuevamente."
                );
            }

            configuracion.headers[
                "Content-Type"
            ] = "application/json";

            configuracion.headers[
                "X-CSRFToken"
            ] = csrfToken;

            configuracion.headers[
                "X-Requested-With"
            ] = "XMLHttpRequest";

            configuracion.body = JSON.stringify(
                opciones.body || {}
            );
        }

        const respuesta = await fetch(
            url,
            configuracion
        );

        let datos;

        try {
            datos = await respuesta.json();
        } catch {
            throw new Error(
                "El servidor entregó una respuesta inválida."
            );
        }

        if (!respuesta.ok || datos.ok === false) {
            throw new Error(
                datos.mensaje ||
                    "No fue posible completar la operación."
            );
        }

        return datos;
    }

    function escaparHTML(texto) {
        const elemento = document.createElement("div");
        elemento.textContent = texto ?? "";

        return elemento.innerHTML;
    }

    function abrirPanelCarrito() {
        carritoLateral.classList.add(
            "carrito-lateral--activo"
        );

        carritoLateral.setAttribute(
            "aria-hidden",
            "false"
        );

        overlay?.classList.add("overlay--activo");
        document.body.classList.add("no-scroll");
    }

    function cerrarPanelCarrito() {
        carritoLateral.classList.remove(
            "carrito-lateral--activo"
        );

        carritoLateral.setAttribute(
            "aria-hidden",
            "true"
        );

        overlay?.classList.remove(
            "overlay--activo"
        );

        document.body.classList.remove("no-scroll");
    }

    function mostrarConfirmacion(nombreProducto) {
        if (!confirmacion) {
            return;
        }

        confirmacionTexto.textContent = nombreProducto;

        confirmacion.classList.remove(
            "carrito-confirmacion--visible"
        );

        void confirmacion.offsetWidth;

        confirmacion.classList.add(
            "carrito-confirmacion--visible"
        );

        confirmacion.setAttribute(
            "aria-hidden",
            "false"
        );

        window.clearTimeout(
            temporizadorConfirmacion
        );

        temporizadorConfirmacion = window.setTimeout(
            () => {
                confirmacion.classList.remove(
                    "carrito-confirmacion--visible"
                );

                confirmacion.setAttribute(
                    "aria-hidden",
                    "true"
                );
            },
            2800
        );
    }

    function animarContador() {
        if (!contadorElemento) {
            return;
        }

        contadorElemento.classList.remove(
            "carrito-contador--animado"
        );

        void contadorElemento.offsetWidth;

        contadorElemento.classList.add(
            "carrito-contador--animado"
        );
    }

    function animarCarritoHeader() {
        if (!abrirCarrito) {
            return;
        }

        abrirCarrito.classList.remove(
            "boton-carrito--animado"
        );

        void abrirCarrito.offsetWidth;

        abrirCarrito.classList.add(
            "boton-carrito--animado"
        );
    }

    function actualizarEnvioGratis(subtotal) {
        if (!progresoEnvio || !mensajeEnvio) {
            return;
        }

        const porcentaje = Math.min(
            (subtotal / META_ENVIO_GRATIS) * 100,
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

        const faltante =
            META_ENVIO_GRATIS - subtotal;

        mensajeEnvio.textContent =
            `Te faltan $${faltante
                .toLocaleString("es-CL")} para despacho gratis.`;
    }

    function plantillaVacia() {
        return `
            <div class="carrito-vacio">
                <div class="carrito-vacio__icono">
                    <i class="bi bi-bag"></i>
                </div>

                <h3>Tu carrito está vacío</h3>

                <p>
                    Agrega tus productos favoritos y comienza
                    a disfrutar del mejor sonido.
                </p>

                <a
                    href="/productos/"
                    class="boton boton--primario"
                >
                    Ver productos
                </a>
            </div>
        `;
    }

    function plantillaItem(item) {
        const imagen = item.imagen
            ? `
                <img
                    src="${escaparHTML(item.imagen)}"
                    alt="${escaparHTML(item.nombre)}"
                >
            `
            : `
                <div class="carrito-item__sin-imagen">
                    <i class="bi bi-earbuds"></i>
                </div>
            `;

        const oferta = item.en_oferta
            ? `
                <span class="carrito-item__oferta">
                    Oferta
                </span>
            `
            : "";

        return `
            <article
                class="carrito-item"
                data-producto-id="${item.id}"
            >
                <a
                    href="${escaparHTML(item.url_detalle)}"
                    class="carrito-item__imagen"
                >
                    ${imagen}
                </a>

                <div class="carrito-item__contenido">
                    <div class="carrito-item__superior">
                        <div>
                            <span class="carrito-item__categoria">
                                ${escaparHTML(item.categoria)}
                            </span>

                            ${oferta}
                        </div>

                        <button
                            type="button"
                            class="carrito-item__eliminar"
                            data-accion="eliminar"
                            aria-label="Eliminar ${escaparHTML(
                                item.nombre
                            )}"
                        >
                            <i class="bi bi-trash3"></i>
                        </button>
                    </div>

                    <a
                        href="${escaparHTML(item.url_detalle)}"
                        class="carrito-item__nombre"
                    >
                        ${escaparHTML(item.nombre)}
                    </a>

                    <span class="carrito-item__precio">
                        ${item.precio_formateado}
                    </span>

                    <div class="carrito-item__inferior">
                        <div class="carrito-item__cantidad">
                            <button
                                type="button"
                                data-accion="restar"
                                aria-label="Disminuir cantidad"
                            >
                                <i class="bi bi-dash"></i>
                            </button>

                            <span>${item.cantidad}</span>

                            <button
                                type="button"
                                data-accion="sumar"
                                aria-label="Aumentar cantidad"
                                ${
                                    item.cantidad >= item.stock
                                        ? "disabled"
                                        : ""
                                }
                            >
                                <i class="bi bi-plus"></i>
                            </button>
                        </div>

                        <strong>
                            ${item.total_formateado}
                        </strong>
                    </div>
                </div>
            </article>
        `;
    }

function renderizarCarrito(carrito) {
    console.log("Carrito recibido:", carrito);

    if (!carrito || !Array.isArray(carrito.items)) {
        console.error(
            "La estructura del carrito no es válida:",
            carrito
        );

        mostrarError(
            "No fue posible mostrar los productos del carrito."
        );

        return;
    }

    carritoActual = carrito;

    const items = carrito.items;
    const cantidadTotal = Number(
        carrito.cantidad_total || 0
    );

    const subtotal = Number(
        carrito.subtotal || 0
    );

    const carritoEstaVacio =
        items.length === 0;

    if (contadorElemento) {
        contadorElemento.textContent =
            cantidadTotal;
    }

    if (subtotalElemento) {
        subtotalElemento.textContent =
            carrito.subtotal_formateado ||
            `$${subtotal.toLocaleString("es-CL")}`;
    }

    actualizarEnvioGratis(subtotal);

    if (finalizarCompra) {
        finalizarCompra.disabled =
            carritoEstaVacio;
    }

    if (vaciarCarrito) {
        vaciarCarrito.hidden =
            carritoEstaVacio;
    }

    if (!productosContenedor) {
        console.error(
            "No se encontró #carritoProductos."
        );

        return;
    }

    if (carritoEstaVacio) {
        productosContenedor.innerHTML =
            plantillaVacia();

        return;
    }

    productosContenedor.innerHTML =
        items
            .map((item) => plantillaItem(item))
            .join("");
    }

    function mostrarError(mensaje) {
        productosContenedor.insertAdjacentHTML(
            "afterbegin",
            `
                <div class="carrito-error">
                    <i class="bi bi-exclamation-circle"></i>
                    <span>${escaparHTML(mensaje)}</span>
                </div>
            `
        );

        window.setTimeout(() => {
            productosContenedor
                .querySelector(".carrito-error")
                ?.remove();
        }, 3500);
    }

    async function cargarCarrito() {
        try {
            const datos = await solicitar(URL_ESTADO);
            renderizarCarrito(datos.carrito);
        } catch (error) {
            productosContenedor.innerHTML = `
                <div class="carrito-error carrito-error--fijo">
                    <i class="bi bi-wifi-off"></i>
                    <span>${escaparHTML(error.message)}</span>
                </div>
            `;
        }
    }

    async function agregarProducto(
        productoId,
        cantidad,
        nombreProducto,
        boton
    ) {
        if (solicitudEnCurso) {
            return;
        }

        solicitudEnCurso = true;

        const contenidoOriginal = boton?.innerHTML;

        if (boton) {
            boton.disabled = true;

            boton.innerHTML = `
                <span class="carrito-spinner"></span>
                <span>Agregando...</span>
            `;
        }

        try {
            const datos = await solicitar(
                URL_AGREGAR,
                {
                    method: "POST",
                    body: {
                        producto_id: productoId,
                        cantidad: cantidad,
                    },
                }
            );

            console.log(
                "Respuesta al agregar producto:",
                datos
            );

            if (!datos.carrito) {
                throw new Error(
                    "El servidor no devolvió la información del carrito."
                );
            }

            renderizarCarrito(datos.carrito);

            const estadoActualizado = await solicitar(
                `${URL_ESTADO}?t=${Date.now()}`
            );

            if (
                estadoActualizado.carrito
                && Array.isArray(
                    estadoActualizado.carrito.items
                )
            ) {
                renderizarCarrito(
                    estadoActualizado.carrito
                );
            }

            mostrarConfirmacion(nombreProducto);
            animarContador();
            animarCarritoHeader();
            abrirPanelCarrito();

            productosContenedor
                .querySelector(
                    `[data-producto-id="${productoId}"]`
                )
                ?.classList.add(
                    "carrito-item--nuevo"
                );
        } catch (error) {
            mostrarError(error.message);
        } finally {
            solicitudEnCurso = false;

            if (boton) {
                boton.disabled = false;
                boton.innerHTML = contenidoOriginal;
            }
        }
}

    async function actualizarCantidad(
        productoId,
        cantidad
    ) {
        try {
            const datos = await solicitar(
                URL_ACTUALIZAR,
                {
                    method: "POST",
                    body: {
                        producto_id: productoId,
                        cantidad,
                    },
                }
            );

            renderizarCarrito(datos.carrito);
            animarContador();
        } catch (error) {
            mostrarError(error.message);
        }
    }

    async function eliminarProducto(productoId) {
        const item = productosContenedor.querySelector(
            `[data-producto-id="${productoId}"]`
        );

        item?.classList.add(
            "carrito-item--eliminando"
        );

        window.setTimeout(async () => {
            try {
                const datos = await solicitar(
                    URL_ELIMINAR,
                    {
                        method: "POST",
                        body: {
                            producto_id: productoId,
                        },
                    }
                );

                renderizarCarrito(datos.carrito);
                animarContador();
            } catch (error) {
                item?.classList.remove(
                    "carrito-item--eliminando"
                );

                mostrarError(error.message);
            }
        }, 250);
    }

    document.addEventListener("click", (evento) => {
        const botonAgregar = evento.target.closest(
            ".agregar-carrito, .detalle-agregar-carrito"
        );

        if (!botonAgregar) {
            return;
        }

        evento.preventDefault();

        const productoId = Number(
            botonAgregar.dataset.productoId
        );

        const nombreProducto =
            botonAgregar.dataset.producto ||
            "Producto";

        const cantidadDetalle =
            document.getElementById(
                "cantidadProducto"
            );

        const cantidad = botonAgregar.classList.contains(
            "detalle-agregar-carrito"
        )
            ? Number(cantidadDetalle?.value || 1)
            : Number(
                  botonAgregar.dataset.cantidad || 1
              );

        agregarProducto(
            productoId,
            cantidad,
            nombreProducto,
            botonAgregar
        );
    });

    productosContenedor.addEventListener(
        "click",
        (evento) => {
            const boton = evento.target.closest(
                "[data-accion]"
            );

            if (!boton) {
                return;
            }

            const item = boton.closest(
                ".carrito-item"
            );

            const productoId = Number(
                item?.dataset.productoId
            );

            const producto = carritoActual?.items.find(
                (elemento) =>
                    elemento.id === productoId
            );

            if (!producto) {
                return;
            }

            const accion = boton.dataset.accion;

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

    abrirCarrito?.addEventListener(
        "click",
        async () => {
            abrirPanelCarrito();
            await cargarCarrito();
        }
    );

    cerrarCarrito?.addEventListener(
        "click",
        cerrarPanelCarrito
    );

    overlay?.addEventListener(
        "click",
        cerrarPanelCarrito
    );

    vaciarCarrito?.addEventListener(
        "click",
        async () => {
            if (solicitudEnCurso) {
                return;
            }

            solicitudEnCurso = true;
            vaciarCarrito.disabled = true;

            try {
                const datos = await solicitar(
                    URL_VACIAR,
                    {
                        method: "POST",
                        body: {},
                    }
                );

                carritoActual = {
                    items: [],
                    cantidad_total: 0,
                    subtotal: 0,
                    subtotal_formateado: "$0",
                    vacio: true,
                };

                renderizarCarrito(
                    datos.carrito || carritoActual
                );

                animarContador();
            } catch (error) {
                mostrarError(error.message);
            } finally {
                solicitudEnCurso = false;
                vaciarCarrito.disabled = false;
            }
        }
    );

    finalizarCompra?.addEventListener(
        "click",
        () => {
            console.log(
                "El checkout se implementará posteriormente."
            );
        }
    );

    document.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Escape") {
                cerrarPanelCarrito();
            }
        }
    );

    cargarCarrito();
});