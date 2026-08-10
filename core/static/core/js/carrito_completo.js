"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const pagina = document.getElementById(
        "carritoPagina"
    );

    if (!pagina) {
        return;
    }

    // =========================================================================
    // ELEMENTOS
    // =========================================================================

    const productosContenedor = document.getElementById(
        "carritoPaginaProductos"
    );

    const resumenProductosContenedor = document.getElementById(
        "carritoResumenProductos"
    );

    const cantidadElemento = document.getElementById(
        "carritoPaginaCantidad"
    );

    const resumenCantidadElemento = document.getElementById(
        "carritoResumenCantidad"
    );

    const precioListaElemento = document.getElementById(
        "carritoPaginaPrecioLista"
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

    const filaDescuento = document.getElementById(
        "filaDescuento"
    );

    const descuentoElemento = document.getElementById(
        "carritoPaginaDescuento"
    );

    const despachoElemento = document.getElementById(
        "carritoPaginaDespacho"
    );

    const progresoEnvio = document.getElementById(
        "carritoPaginaProgreso"
    );

    const mensajeEnvio = document.getElementById(
        "carritoPaginaMensajeEnvio"
    );

    const toast = document.getElementById(
        "carritoPaginaToast"
    );

    const toastTexto = document.getElementById(
        "carritoPaginaToastTexto"
    );

    // =========================================================================
    // URLS
    // =========================================================================

    const urls = {
        estado: String(
            pagina.dataset.urlEstado
            || ""
        ).trim(),

        actualizar: String(
            pagina.dataset.urlActualizar
            || ""
        ).trim(),

        eliminar: String(
            pagina.dataset.urlEliminar
            || ""
        ).trim(),

        vaciar: String(
            pagina.dataset.urlVaciar
            || ""
        ).trim(),
    };

    // =========================================================================
    // ESTADO
    // =========================================================================

    let carritoActual = null;

    let temporizadorToast = null;

    const operacionesProductos = new Set();

    // =========================================================================
    // UTILIDADES
    // =========================================================================

    function obtenerCookie(
        nombre
    ) {
        const cookies = document.cookie
            ? document.cookie.split(";")
            : [];

        for (const cookie of cookies) {
            const limpia = cookie.trim();

            if (
                limpia.startsWith(
                    `${nombre}=`
                )
            ) {
                return decodeURIComponent(
                    limpia.substring(
                        nombre.length + 1
                    )
                );
            }
        }

        return "";
    }


    function escaparHTML(
        valor
    ) {
        const elemento = document.createElement(
            "div"
        );

        elemento.textContent = String(
            valor ?? ""
        );

        return elemento.innerHTML;
    }


    function numeroSeguro(
        valor,
        defecto = 0
    ) {
        const numero = Number(
            valor
        );

        if (!Number.isFinite(numero)) {
            return defecto;
        }

        return numero;
    }


    function formatearCLP(
        valor
    ) {
        const numero = Math.round(
            numeroSeguro(
                valor
            )
        );

        return `$${numero.toLocaleString(
            "es-CL"
        )}`;
    }


    function textoProductos(
        cantidad
    ) {
        return (
            `${cantidad} `
            + (
                cantidad === 1
                    ? "producto"
                    : "productos"
            )
        );
    }


    function textoUnidades(
        cantidad
    ) {
        return (
            `${cantidad} `
            + (
                cantidad === 1
                    ? "unidad"
                    : "unidades"
            )
        );
    }

    // =========================================================================
    // FETCH
    // =========================================================================

    async function solicitar(
        url,
        cuerpo = null
    ) {
        if (!url) {
            throw new Error(
                "La URL de la operación no está configurada."
            );
        }

        const esGet = (
            cuerpo === null
        );

        const configuracion = {
            method: esGet
                ? "GET"
                : "POST",

            credentials: "same-origin",

            cache: "no-store",

            headers: {
                Accept: "application/json",

                "X-Requested-With": (
                    "XMLHttpRequest"
                ),
            },
        };

        if (!esGet) {
            configuracion.headers[
                "Content-Type"
            ] = "application/json";

            configuracion.headers[
                "X-CSRFToken"
            ] = obtenerCookie(
                "csrftoken"
            );

            configuracion.body = JSON.stringify(
                cuerpo
            );
        }

        const respuesta = await fetch(
            url,
            configuracion
        );

        let datos = {};

        try {
            datos = await respuesta.json();
        } catch (error) {
            throw new Error(
                "El servidor no devolvió JSON válido."
            );
        }

        if (
            !respuesta.ok
            || datos.ok === false
        ) {
            throw new Error(
                datos.mensaje
                || "No fue posible completar la operación."
            );
        }

        return datos;
    }

    // =========================================================================
    // TOAST
    // =========================================================================

    function mostrarToast(
        texto
    ) {
        if (
            !toast
            || !toastTexto
        ) {
            return;
        }

        toastTexto.textContent = (
            texto
        );

        toast.classList.add(
            "carrito-pagina-toast--visible"
        );

        toast.setAttribute(
            "aria-hidden",
            "false"
        );

        window.clearTimeout(
            temporizadorToast
        );

        temporizadorToast = window.setTimeout(
            () => {
                toast.classList.remove(
                    "carrito-pagina-toast--visible"
                );

                toast.setAttribute(
                    "aria-hidden",
                    "true"
                );
            },
            2200
        );
    }

    // =========================================================================
    // NORMALIZAR CARRITO
    // =========================================================================

    function normalizarCarrito(
        carrito
    ) {
        const itemsOriginales = Array.isArray(
            carrito?.items
        )
            ? carrito.items
            : [];

        let cantidadTotal = 0;
        let subtotal = 0;
        let subtotalPrecioLista = 0;
        let ahorroOfertas = 0;

        const items = itemsOriginales.map(
            (item) => {
                const cantidad = Math.max(
                    1,
                    Math.round(
                        numeroSeguro(
                            item.cantidad,
                            1
                        )
                    )
                );

                const stock = Math.max(
                    0,
                    Math.round(
                        numeroSeguro(
                            item.stock,
                            cantidad
                        )
                    )
                );

                const precio = Math.max(
                    0,
                    numeroSeguro(
                        item.precio,
                        0
                    )
                );

                let precioOriginal = Math.max(
                    0,
                    numeroSeguro(
                        item.precio_original,
                        precio
                    )
                );

                if (
                    precioOriginal < precio
                ) {
                    precioOriginal = precio;
                }

                const enOferta = (
                    Boolean(
                        item.en_oferta
                    )
                    && precioOriginal > precio
                );

                const totalLinea = (
                    precio
                    * cantidad
                );

                const totalOriginalLinea = (
                    precioOriginal
                    * cantidad
                );

                const ahorroUnitario = enOferta
                    ? (
                        precioOriginal
                        - precio
                    )
                    : 0;

                const ahorroLinea = (
                    ahorroUnitario
                    * cantidad
                );

                let porcentajeDescuento = 0;

                if (
                    enOferta
                    && precioOriginal > 0
                ) {
                    porcentajeDescuento = Math.round(
                        (
                            ahorroUnitario
                            / precioOriginal
                        )
                        * 100
                    );
                }

                cantidadTotal += cantidad;

                subtotal += totalLinea;

                subtotalPrecioLista += (
                    totalOriginalLinea
                );

                ahorroOfertas += (
                    ahorroLinea
                );

                return {
                    ...item,

                    cantidad,
                    stock,

                    precio,

                    precio_formateado: (
                        formatearCLP(
                            precio
                        )
                    ),

                    precio_original: (
                        precioOriginal
                    ),

                    precio_original_formateado: (
                        formatearCLP(
                            precioOriginal
                        )
                    ),

                    en_oferta: (
                        enOferta
                    ),

                    porcentaje_descuento: (
                        porcentajeDescuento
                    ),

                    ahorro_unitario: (
                        ahorroUnitario
                    ),

                    ahorro_unitario_formateado: (
                        formatearCLP(
                            ahorroUnitario
                        )
                    ),

                    ahorro_linea: (
                        ahorroLinea
                    ),

                    ahorro_linea_formateado: (
                        formatearCLP(
                            ahorroLinea
                        )
                    ),

                    total: (
                        totalLinea
                    ),

                    total_formateado: (
                        formatearCLP(
                            totalLinea
                        )
                    ),

                    total_original: (
                        totalOriginalLinea
                    ),

                    total_original_formateado: (
                        formatearCLP(
                            totalOriginalLinea
                        )
                    ),
                };
            }
        );

        return {
            ...carrito,

            items,

            cantidad_total: (
                cantidadTotal
            ),

            subtotal,

            subtotal_formateado: (
                formatearCLP(
                    subtotal
                )
            ),

            subtotal_precio_lista: (
                subtotalPrecioLista
            ),

            subtotal_precio_lista_formateado: (
                formatearCLP(
                    subtotalPrecioLista
                )
            ),

            ahorro_ofertas: (
                ahorroOfertas
            ),

            ahorro_ofertas_formateado: (
                formatearCLP(
                    ahorroOfertas
                )
            ),

            tiene_ofertas: (
                ahorroOfertas > 0
            ),

            vacio: (
                items.length === 0
            ),
        };
    }

    // =========================================================================
    // DESPACHO
    // =========================================================================

    function actualizarDespachoPendiente() {
        if (despachoElemento) {
            despachoElemento.textContent = (
                "Por calcular"
            );
        }

        if (progresoEnvio) {
            progresoEnvio.style.width = (
                "0%"
            );
        }

        if (mensajeEnvio) {
            mensajeEnvio.textContent = "";
        }
    }

    // =========================================================================
    // PLANTILLA VACÍA
    // =========================================================================

    function plantillaVacia() {
        return `
            <div class="carrito-pagina-vacio">

                <div class="carrito-pagina-vacio__icono">
                    <i
                        class="bi bi-bag"
                        aria-hidden="true"
                    ></i>
                </div>

                <h2>
                    Tu carrito está vacío
                </h2>

                <p>
                    Explora nuestro catálogo y agrega
                    los audífonos que más te gusten.
                </p>

                <a
                    href="/productos/"
                    class="boton boton--primario"
                >
                    Explorar productos

                    <i
                        class="bi bi-arrow-right"
                        aria-hidden="true"
                    ></i>
                </a>

            </div>
        `;
    }

    // =========================================================================
    // PRODUCTO PRINCIPAL
    // =========================================================================

    function plantillaProducto(
        item
    ) {
        const imagen = item.imagen
            ? `
                <img
                    src="${escaparHTML(
                        item.imagen
                    )}"
                    alt="${escaparHTML(
                        item.nombre
                    )}"
                    loading="lazy"
                >
            `
            : `
                <i
                    class="bi bi-earbuds"
                    aria-hidden="true"
                ></i>
            `;

        const categoria = item.categoria
            ? `
                <span class="carrito-producto__categoria">
                    ${escaparHTML(
                        item.categoria
                    )}
                </span>
            `
            : "";

        const oferta = item.en_oferta
            ? `
                <span class="carrito-producto__oferta">
                    Oferta
                </span>

                <span class="carrito-producto__porcentaje">
                    -${item.porcentaje_descuento}%
                </span>
            `
            : "";

        const precioUnitario = item.en_oferta
            ? `
                <span class="carrito-producto__precio-original">
                    ${item.precio_original_formateado}
                </span>

                <strong class="carrito-producto__precio-oferta">
                    ${item.precio_formateado}
                </strong>
            `
            : `
                <span class="carrito-producto__unitario">

                    Precio unitario:

                    <strong>
                        ${item.precio_formateado}
                    </strong>

                </span>
            `;

        const totalOriginal = item.en_oferta
            ? `
                <small class="carrito-producto__total-original">
                    ${item.total_original_formateado}
                </small>
            `
            : "";

        const ahorro = (
            item.en_oferta
            && item.ahorro_linea > 0
        )
            ? `
                <small class="carrito-producto__ahorro">
                    Ahorras
                    ${item.ahorro_linea_formateado}
                </small>
            `
            : "";

        const sumarDisabled = (
            item.cantidad >= item.stock
        )
            ? "disabled"
            : "";

        return `
            <article
                class="carrito-producto"
                data-producto-id="${item.id}"
            >

                <a
                    href="${escaparHTML(
                        item.url_detalle
                    )}"
                    class="carrito-producto__imagen"
                >
                    ${imagen}
                </a>

                <div class="carrito-producto__informacion">

                    <div class="carrito-producto__superior">

                        <div>

                            <div class="carrito-producto__etiquetas">
                                ${categoria}
                                ${oferta}
                            </div>

                            <h3>
                                <a
                                    href="${escaparHTML(
                                        item.url_detalle
                                    )}"
                                >
                                    ${escaparHTML(
                                        item.nombre
                                    )}
                                </a>
                            </h3>

                            <div class="carrito-producto__precio-unitario">
                                ${precioUnitario}
                            </div>

                        </div>

                        <button
                            type="button"
                            class="carrito-producto__eliminar"
                            data-carrito-pagina-accion="eliminar"
                            aria-label="Eliminar ${escaparHTML(
                                item.nombre
                            )}"
                        >
                            <i
                                class="bi bi-trash3"
                                aria-hidden="true"
                            ></i>
                        </button>

                    </div>

                    <div class="carrito-producto__inferior">

                        <div class="carrito-producto__cantidad">

                            <span>
                                Cantidad
                            </span>

                            <div>

                                <button
                                    type="button"
                                    data-carrito-pagina-accion="restar"
                                >
                                    <i
                                        class="bi bi-dash-lg"
                                        aria-hidden="true"
                                    ></i>
                                </button>

                                <strong>
                                    ${item.cantidad}
                                </strong>

                                <button
                                    type="button"
                                    data-carrito-pagina-accion="sumar"
                                    ${sumarDisabled}
                                >
                                    <i
                                        class="bi bi-plus-lg"
                                        aria-hidden="true"
                                    ></i>
                                </button>

                            </div>

                            <small>
                                ${item.stock}
                                unidades disponibles
                            </small>

                        </div>

                        <div class="carrito-producto__total">

                            <span>
                                Total
                            </span>

                            ${totalOriginal}

                            <strong>
                                ${item.total_formateado}
                            </strong>

                            ${ahorro}

                        </div>

                    </div>

                </div>

            </article>
        `;
    }

    // =========================================================================
    // PRODUCTO RESUMEN
    // =========================================================================

    function plantillaProductoResumen(
        item
    ) {
        const cantidadVisual = (
            item.cantidad > 1
        )
            ? `
                <span class="carrito-resumen-producto__cantidad">
                    x${item.cantidad}
                </span>
            `
            : "";

        const precios = item.en_oferta
            ? `
                <span class="carrito-resumen-producto__precio-original">
                    ${item.precio_original_formateado}
                </span>

                <strong class="carrito-resumen-producto__precio-oferta">
                    ${item.precio_formateado}
                </strong>

                <span class="carrito-resumen-producto__descuento-badge">
                    -${item.porcentaje_descuento}%
                </span>
            `
            : `
                <strong class="carrito-resumen-producto__precio">
                    ${item.precio_formateado}
                </strong>
            `;

        const unitario = (
            item.cantidad > 1
        )
            ? `
                <small class="carrito-resumen-producto__unitario">
                    ${item.precio_formateado}
                    c/u
                </small>
            `
            : "";

        const totalOriginal = item.en_oferta
            ? `
                <span class="carrito-resumen-producto__total-original">
                    ${item.total_original_formateado}
                </span>
            `
            : "";

        return `
            <article
                class="carrito-resumen-producto"
                data-resumen-producto-id="${item.id}"
            >

                <div class="carrito-resumen-producto__principal">

                    <a
                        href="${escaparHTML(
                            item.url_detalle
                        )}"
                        class="carrito-resumen-producto__nombre"
                    >
                        ${escaparHTML(
                            item.nombre
                        )}
                    </a>

                    ${cantidadVisual}

                </div>

                <div class="carrito-resumen-producto__detalle">

                    <div class="carrito-resumen-producto__precios">
                        ${precios}
                    </div>

                    ${unitario}

                </div>

                <div class="carrito-resumen-producto__total">

                    ${totalOriginal}

                    <strong>
                        ${item.total_formateado}
                    </strong>

                </div>

            </article>
        `;
    }

    // =========================================================================
    // ACTUALIZACIÓN OPTIMISTA
    // =========================================================================
    //
    // Cambiamos visualmente la cantidad ANTES de esperar Django.
    // Luego Django confirma y hacemos un GET fresco.
    // =========================================================================

    function aplicarCantidadLocal(
        productoId,
        nuevaCantidad
    ) {
        if (!carritoActual) {
            return;
        }

        const carritoCopia = {
            ...carritoActual,

            items: carritoActual.items.map(
                (item) => {
                    if (
                        Number(item.id)
                        !== Number(productoId)
                    ) {
                        return {
                            ...item,
                        };
                    }

                    return {
                        ...item,

                        cantidad: (
                            nuevaCantidad
                        ),
                    };
                }
            ),
        };

        renderizar(
            carritoCopia
        );
    }

    // =========================================================================
    // RENDER RESUMEN
    // =========================================================================

    function renderizarProductosResumen(
        carrito
    ) {
        if (!resumenProductosContenedor) {
            return;
        }

        if (carrito.vacio) {
            resumenProductosContenedor.innerHTML = "";
            return;
        }

        resumenProductosContenedor.innerHTML = (
            carrito.items
                .map(
                    plantillaProductoResumen
                )
                .join("")
        );
    }

    // =========================================================================
    // RESUMEN ECONÓMICO
    // =========================================================================

    function actualizarResumen(
        carrito
    ) {
        const cantidadTotal = (
            carrito.cantidad_total
        );

        if (cantidadElemento) {
            cantidadElemento.textContent = (
                textoProductos(
                    cantidadTotal
                )
            );
        }

        if (resumenCantidadElemento) {
            resumenCantidadElemento.textContent = (
                textoUnidades(
                    cantidadTotal
                )
            );
        }

        if (contadorHeader) {
            contadorHeader.textContent = (
                cantidadTotal
            );
        }

        if (precioListaElemento) {
            precioListaElemento.textContent = (
                carrito.tiene_ofertas
                    ? carrito
                        .subtotal_precio_lista_formateado
                    : carrito
                        .subtotal_formateado
            );
        }

        if (
            filaDescuento
            && descuentoElemento
        ) {
            if (
                carrito.tiene_ofertas
                && carrito.ahorro_ofertas > 0
            ) {
                filaDescuento.hidden = false;

                descuentoElemento.textContent = (
                    `-${carrito.ahorro_ofertas_formateado}`
                );
            } else {
                filaDescuento.hidden = true;

                descuentoElemento.textContent = (
                    "-$0"
                );
            }
        }

        if (subtotalElemento) {
            subtotalElemento.textContent = (
                carrito.subtotal_formateado
            );
        }

        if (totalElemento) {
            totalElemento.textContent = (
                carrito.subtotal_formateado
            );
        }

        actualizarDespachoPendiente();

        if (botonVaciar) {
            botonVaciar.hidden = (
                carrito.vacio
            );
        }

        if (botonContinuar) {
            botonContinuar.classList.toggle(
                "carrito-continuar--deshabilitado",
                carrito.vacio
            );

            if (carrito.vacio) {
                botonContinuar.setAttribute(
                    "aria-disabled",
                    "true"
                );

                botonContinuar.setAttribute(
                    "tabindex",
                    "-1"
                );
            } else {
                botonContinuar.removeAttribute(
                    "aria-disabled"
                );

                botonContinuar.removeAttribute(
                    "tabindex"
                );
            }
        }
    }

    // =========================================================================
    // RENDER COMPLETO
    // =========================================================================

    function renderizar(
        carritoRecibido
    ) {
        const carrito = normalizarCarrito(
            carritoRecibido
        );

        carritoActual = carrito;

        if (productosContenedor) {
            productosContenedor.innerHTML = (
                carrito.vacio
                    ? plantillaVacia()
                    : carrito.items
                        .map(
                            plantillaProducto
                        )
                        .join("")
            );
        }

        renderizarProductosResumen(
            carrito
        );

        actualizarResumen(
            carrito
        );
    }

    // =========================================================================
    // OBTENER ESTADO REAL DEL SERVIDOR
    // =========================================================================

    async function obtenerCarritoFresco() {
        const datos = await solicitar(
            urls.estado
        );

        if (!datos.carrito) {
            throw new Error(
                "No se recibió el carrito actualizado."
            );
        }

        return datos.carrito;
    }

    // =========================================================================
    // CARGAR
    // =========================================================================

    async function cargarCarrito() {
        try {
            const carrito = await obtenerCarritoFresco();

            renderizar(
                carrito
            );

        } catch (error) {
            console.error(
                "Error cargando carrito:",
                error
            );

            if (productosContenedor) {
                productosContenedor.innerHTML = `
                    <div class="carrito-pagina-vacio">

                        <div class="carrito-pagina-vacio__icono">
                            <i
                                class="bi bi-exclamation-circle"
                                aria-hidden="true"
                            ></i>
                        </div>

                        <h2>
                            No pudimos cargar el carrito
                        </h2>

                        <p>
                            ${escaparHTML(
                                error.message
                            )}
                        </p>

                    </div>
                `;
            }
        }
    }

    // =========================================================================
    // ACTUALIZAR CANTIDAD
    // =========================================================================

    async function actualizarCantidad(
        productoId,
        cantidad
    ) {
        productoId = Number(
            productoId
        );

        cantidad = Number(
            cantidad
        );

        if (
            !Number.isFinite(productoId)
            || !Number.isFinite(cantidad)
        ) {
            return;
        }

        if (
            operacionesProductos.has(
                productoId
            )
        ) {
            return;
        }

        operacionesProductos.add(
            productoId
        );

        const carritoAnterior = (
            carritoActual
        );

        // ---------------------------------------------------------------------
        // CAMBIO INMEDIATO
        // ---------------------------------------------------------------------

        aplicarCantidadLocal(
            productoId,
            cantidad
        );

        try {
            // -----------------------------------------------------------------
            // GUARDAR EN DJANGO
            // -----------------------------------------------------------------

            await solicitar(
                urls.actualizar,
                {
                    producto_id: (
                        productoId
                    ),

                    cantidad: (
                        cantidad
                    ),
                }
            );

            // -----------------------------------------------------------------
            // MUY IMPORTANTE:
            //
            // NO usamos directamente datos.carrito del POST.
            //
            // Hacemos un GET nuevo a carrito_estado para obtener
            // exactamente lo mismo que obtendrías al recargar la página.
            // -----------------------------------------------------------------

            const carritoFresco = (
                await obtenerCarritoFresco()
            );

            renderizar(
                carritoFresco
            );

            const productoElemento = (
                productosContenedor
                    ?.querySelector(
                        `[data-producto-id="${productoId}"]`
                    )
            );

            productoElemento?.classList.add(
                "carrito-producto--actualizado"
            );

            mostrarToast(
                "Cantidad actualizada."
            );

        } catch (error) {
            console.error(
                "Error actualizando cantidad:",
                error
            );

            // -----------------------------------------------------------------
            // SI FALLA:
            // restauramos el estado anterior.
            // -----------------------------------------------------------------

            if (carritoAnterior) {
                renderizar(
                    carritoAnterior
                );
            }

            mostrarToast(
                error.message
            );

        } finally {
            operacionesProductos.delete(
                productoId
            );
        }
    }

    // =========================================================================
    // ELIMINAR PRODUCTO
    // =========================================================================

    async function eliminarProducto(
        productoId
    ) {
        productoId = Number(
            productoId
        );

        if (
            operacionesProductos.has(
                productoId
            )
        ) {
            return;
        }

        operacionesProductos.add(
            productoId
        );

        try {
            await solicitar(
                urls.eliminar,
                {
                    producto_id: (
                        productoId
                    ),
                }
            );

            const carritoFresco = (
                await obtenerCarritoFresco()
            );

            renderizar(
                carritoFresco
            );

            mostrarToast(
                "Producto eliminado."
            );

        } catch (error) {
            console.error(
                "Error eliminando producto:",
                error
            );

            mostrarToast(
                error.message
            );

        } finally {
            operacionesProductos.delete(
                productoId
            );
        }
    }

    // =========================================================================
    // BOTONES + / - / ELIMINAR
    // =========================================================================

    productosContenedor?.addEventListener(
        "click",
        (evento) => {
            const boton = evento.target.closest(
                "[data-carrito-pagina-accion]"
            );

            if (
                !boton
                || boton.disabled
            ) {
                return;
            }

            const productoElemento = (
                boton.closest(
                    ".carrito-producto"
                )
            );

            const productoId = Number(
                productoElemento
                    ?.dataset
                    .productoId
            );

            const producto = (
                carritoActual
                    ?.items
                    ?.find(
                        (item) => (
                            Number(
                                item.id
                            )
                            === productoId
                        )
                    )
            );

            if (!producto) {
                return;
            }

            const accion = (
                boton.dataset
                    .carritoPaginaAccion
            );

            if (accion === "sumar") {
                if (
                    producto.cantidad
                    >= producto.stock
                ) {
                    mostrarToast(
                        "No hay más unidades disponibles."
                    );

                    return;
                }

                actualizarCantidad(
                    productoId,
                    producto.cantidad + 1
                );

                return;
            }

            if (accion === "restar") {
                const nuevaCantidad = (
                    producto.cantidad
                    - 1
                );

                if (nuevaCantidad <= 0) {
                    eliminarProducto(
                        productoId
                    );

                    return;
                }

                actualizarCantidad(
                    productoId,
                    nuevaCantidad
                );

                return;
            }

            if (accion === "eliminar") {
                eliminarProducto(
                    productoId
                );
            }
        }
    );

    // =========================================================================
    // VACIAR
    // =========================================================================

    botonVaciar?.addEventListener(
        "click",
        async () => {
            const confirmar = window.confirm(
                "¿Deseas eliminar todos los productos del carrito?"
            );

            if (!confirmar) {
                return;
            }

            try {
                await solicitar(
                    urls.vaciar,
                    {}
                );

                const carritoFresco = (
                    await obtenerCarritoFresco()
                );

                renderizar(
                    carritoFresco
                );

                mostrarToast(
                    "El carrito fue vaciado."
                );

            } catch (error) {
                console.error(
                    "Error vaciando carrito:",
                    error
                );

                mostrarToast(
                    error.message
                );
            }
        }
    );

    // =========================================================================
    // INICIO
    // =========================================================================

    cargarCarrito();
});