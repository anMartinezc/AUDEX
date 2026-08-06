"use strict";

document.addEventListener("DOMContentLoaded", () => {
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

    botones.forEach((boton) => {
        boton.addEventListener("click", () => {
            botones.forEach((elemento) => {
                elemento.classList.remove("activo");
            });

            boton.classList.add("activo");

            const uso = boton.dataset.uso;
            const opcion = datos[uso];

            recomendacion.innerHTML = `
                <div class="recomendacion__icono">
                    <i class="bi ${opcion.icono}"></i>
                </div>

                <div>
                    <span>Recomendación Audex</span>
                    <h3>${opcion.titulo}</h3>
                    <p>${opcion.texto}</p>
                </div>
            `;

            recomendacion.animate(
                [
                    {
                        opacity: 0,
                        transform: "translateY(15px)",
                    },
                    {
                        opacity: 1,
                        transform: "translateY(0)",
                    },
                ],
                {
                    duration: 400,
                    easing: "ease",
                }
            );
        });
    });
});