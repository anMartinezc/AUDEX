"use strict";

document.addEventListener("DOMContentLoaded", () => {
    // =====================================================================
    // SELECTOR DE USO / RECOMENDACIONES
    // =====================================================================

    const botones = document.querySelectorAll(
        ".selector-uso__botones button"
    );

    const recomendacion = document.getElementById(
        "recomendacionCategoria"
    );

    const datos = {
        trabajo: {
            icono: "bi-laptop",
            titulo: "EarFun Air Pro 4",
            texto:
                "Ideal para reuniones, videollamadas y concentración gracias a su cancelación activa de ruido.",
        },

        deporte: {
            icono: "bi-activity",
            titulo: "EarFun Free Pro 3",
            texto:
                "Diseño compacto, resistencia al agua y ajuste seguro para entrenamientos intensos.",
        },

        viajes: {
            icono: "bi-airplane",
            titulo: "EarFun Wave Pro",
            texto:
                "Comodidad prolongada, batería de larga duración y excelente aislamiento para viajes.",
        },

        gaming: {
            icono: "bi-controller",
            titulo: "EarFun Air 2",
            texto:
                "Baja latencia, conexión estable y sonido definido para juegos y contenido multimedia.",
        },
    };

    if (
        botones.length > 0 &&
        recomendacion
    ) {
        botones.forEach((boton) => {
            boton.addEventListener("click", () => {
                botones.forEach((elemento) => {
                    elemento.classList.remove(
                        "activo"
                    );
                });

                boton.classList.add(
                    "activo"
                );

                const uso = boton.dataset.uso;
                const opcion = datos[uso];

                if (!opcion) {
                    return;
                }

                recomendacion.innerHTML = `
                    <div class="recomendacion__icono">
                        <i class="bi ${opcion.icono}"></i>
                    </div>

                    <div>
                        <span>
                            Recomendación Audex
                        </span>

                        <h3>
                            ${opcion.titulo}
                        </h3>

                        <p>
                            ${opcion.texto}
                        </p>
                    </div>
                `;

                recomendacion.animate(
                    [
                        {
                            opacity: 0,
                            transform:
                                "translateY(15px)",
                        },
                        {
                            opacity: 1,
                            transform:
                                "translateY(0)",
                        },
                    ],
                    {
                        duration: 400,
                        easing: "ease",
                    }
                );
            });
        });
    }


    // =====================================================================
    // VIDEOS DE YOUTUBE
    // =====================================================================
    //
    // Cada tarjeta debe tener:
    //
    // data-youtube-id="ID_DEL_VIDEO"
    //
    // Ejemplo:
    //
    // data-youtube-id="EakJJRUFdrY"
    //
    // Dentro de la tarjeta:
    //
    // data-youtube-player
    // data-video-poster
    // data-video-overlay
    // data-video-play
    //
    // =====================================================================

    const tarjetasVideo = document.querySelectorAll(
        ".categoria-video[data-youtube-id]"
    );

    tarjetasVideo.forEach((tarjeta) => {
        const youtubeId = (
            tarjeta.dataset.youtubeId || ""
        ).trim();

        const player = tarjeta.querySelector(
            "[data-youtube-player]"
        );

        const poster = tarjeta.querySelector(
            "[data-video-poster]"
        );

        const overlay = tarjeta.querySelector(
            "[data-video-overlay]"
        );

        const botonesPlay = tarjeta.querySelectorAll(
            "[data-video-play]"
        );

        const enlaceProductos = tarjeta.querySelector(
            "[data-productos-link]"
        );

        let videoCargado = false;


        // -----------------------------------------------------------------
        // VALIDAR ID DE YOUTUBE
        // -----------------------------------------------------------------

        const youtubeIdValido =
            youtubeId &&
            !youtubeId.startsWith(
                "ID_YOUTUBE_"
            );


        // -----------------------------------------------------------------
        // CREAR VIDEO
        // -----------------------------------------------------------------

        const reproducirVideo = () => {
            if (!youtubeIdValido) {
                console.warn(
                    "AUDEX: falta configurar un ID válido de YouTube.",
                    tarjeta
                );

                return;
            }

            if (!player) {
                console.warn(
                    "AUDEX: no se encontró data-youtube-player.",
                    tarjeta
                );

                return;
            }


            // =============================================================
            // OCULTAR POSTER
            // =============================================================

            if (poster) {
                poster.style.opacity = "0";
                poster.style.visibility =
                    "hidden";
                poster.style.pointerEvents =
                    "none";

                poster.classList.add(
                    "is-hidden"
                );
            }


            // =============================================================
            // OCULTAR BOTÓN CENTRAL / OVERLAY
            // =============================================================

            if (overlay) {
                overlay.style.opacity = "0";
                overlay.style.visibility =
                    "hidden";
                overlay.style.pointerEvents =
                    "none";

                overlay.classList.add(
                    "is-hidden"
                );
            }


            // =============================================================
            // CREAR IFRAME SOLO UNA VEZ
            // =============================================================

            if (!videoCargado) {
                const iframe =
                    document.createElement(
                        "iframe"
                    );

                iframe.className =
                    "categoria-video__iframe";


                // =========================================================
                // URL DEL REPRODUCTOR YOUTUBE
                // =========================================================

                const parametros =
                    new URLSearchParams({
                        autoplay: "1",
                        playsinline: "1",
                        rel: "0",
                        enablejsapi: "1",
                        origin:
                            window.location.origin,
                    });


                iframe.src =
                    `https://www.youtube.com/embed/${encodeURIComponent(
                        youtubeId
                    )}?${parametros.toString()}`;


                // =========================================================
                // CONFIGURACIÓN IFRAME
                // =========================================================

                iframe.title =
                    "Video de producto AUDEX";

                iframe.loading = "eager";


                /*
                =============================================================
                IMPORTANTE PARA ERROR 153 DE YOUTUBE
                =============================================================
                */

                iframe.referrerPolicy =
                    "strict-origin-when-cross-origin";


                iframe.allow =
                    "accelerometer; " +
                    "autoplay; " +
                    "clipboard-write; " +
                    "encrypted-media; " +
                    "gyroscope; " +
                    "picture-in-picture; " +
                    "web-share";


                iframe.allowFullscreen = true;


                iframe.setAttribute(
                    "frameborder",
                    "0"
                );


                /*
                =============================================================
                SANDBOX NO SE AGREGA
                =============================================================

                No agregamos atributo sandbox porque puede impedir
                determinadas funciones necesarias del reproductor
                de YouTube.
                */


                player.innerHTML = "";

                player.appendChild(
                    iframe
                );

                videoCargado = true;
            }


            // =============================================================
            // MOSTRAR PLAYER
            // =============================================================

            player.style.display =
                "block";

            player.style.opacity =
                "1";

            player.style.visibility =
                "visible";

            player.style.pointerEvents =
                "auto";

            player.classList.add(
                "is-visible"
            );


            // =============================================================
            // ESTADO DE LA TARJETA
            // =============================================================

            tarjeta.classList.add(
                "video-reproduciendo"
            );


            // =============================================================
            // MOSTRAR LINK DE PRODUCTOS
            // =============================================================

            if (enlaceProductos) {
                enlaceProductos.hidden =
                    false;

                requestAnimationFrame(
                    () => {
                        enlaceProductos.classList.add(
                            "is-visible"
                        );
                    }
                );
            }
        };


        // -----------------------------------------------------------------
        // ASIGNAR PLAY A TODOS LOS BOTONES DE LA TARJETA
        // -----------------------------------------------------------------

        botonesPlay.forEach((boton) => {
            boton.addEventListener(
                "click",
                (evento) => {
                    evento.preventDefault();

                    reproducirVideo();
                }
            );
        });
    });
});