"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const contadores = document.querySelectorAll(
        "[data-contador]"
    );

    let ejecutado = false;

    function animarContador(elemento) {
        const objetivo = Number(elemento.dataset.contador);
        const duracion = 1800;
        const inicio = performance.now();

        function actualizar(tiempoActual) {
            const progreso = Math.min(
                (tiempoActual - inicio) / duracion,
                1
            );

            const valor = Math.floor(objetivo * progreso);

            elemento.textContent =
                objetivo === 100
                    ? `${valor}%`
                    : valor.toLocaleString("es-CL");

            if (progreso < 1) {
                requestAnimationFrame(actualizar);
            }
        }

        requestAnimationFrame(actualizar);
    }

    const seccionMetricas = document.querySelector(".metricas");

    const observador = new IntersectionObserver(
        (entradas) => {
            entradas.forEach((entrada) => {
                if (entrada.isIntersecting && !ejecutado) {
                    ejecutado = true;

                    contadores.forEach(animarContador);
                }
            });
        },
        {
            threshold: 0.3,
        }
    );

    if (seccionMetricas) {
        observador.observe(seccionMetricas);
    }

    const elementos = document.querySelectorAll(
        ".valor-card, .historia__puntos article"
    );

    elementos.forEach((elemento, indice) => {
        elemento.style.opacity = "0";
        elemento.style.transform = "translateY(25px)";
        elemento.style.transition = `
            opacity 0.6s ease ${indice * 0.08}s,
            transform 0.6s ease ${indice * 0.08}s
        `;
    });

    const observadorElementos = new IntersectionObserver(
        (entradas) => {
            entradas.forEach((entrada) => {
                if (entrada.isIntersecting) {
                    entrada.target.style.opacity = "1";
                    entrada.target.style.transform =
                        "translateY(0)";

                    observadorElementos.unobserve(
                        entrada.target
                    );
                }
            });
        },
        {
            threshold: 0.15,
        }
    );

    elementos.forEach((elemento) => {
        observadorElementos.observe(elemento);
    });
});