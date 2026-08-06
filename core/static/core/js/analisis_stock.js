document.addEventListener("DOMContentLoaded", () => {
    if (typeof Chart === "undefined") {
        console.error("Chart.js no está disponible.");
        return;
    }

    const leerDatos = (id) => {
        const elemento = document.getElementById(id);

        if (!elemento) {
            return {};
        }

        try {
            return JSON.parse(elemento.textContent);
        } catch (error) {
            console.error(`Datos inválidos en ${id}:`, error);
            return {};
        }
    };

    const colores = {
        azulClaro: "#83d8f3",
        azul: "#36a9d6",
        azulOscuro: "#237fa8",
        verde: "#7ce8a6",
        amarillo: "#ffcf70",
        rojo: "#ff8992",
        gris: "#93a6b2",
        grilla: "rgba(255,255,255,0.08)",
    };

    Chart.defaults.color = colores.gris;
    Chart.defaults.borderColor = colores.grilla;
    Chart.defaults.font.family = "Montserrat, Arial, sans-serif";

    const datosSalidas = leerDatos(
        "datos-grafico-salidas"
    );

    const salidasCanvas = document.getElementById(
        "graficoSalidas"
    );

    if (salidasCanvas) {
        new Chart(
            salidasCanvas,
            {
                type: "line",
                data: {
                    labels: datosSalidas.labels || [],
                    datasets: [
                        {
                            label: "Unidades descontadas",
                            data: datosSalidas.unidades || [],
                            borderColor: colores.azulClaro,
                            backgroundColor:
                                "rgba(131,216,243,0.12)",
                            fill: true,
                            tension: 0.3,
                            pointRadius: 3,
                            pointHoverRadius: 6,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: "index",
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            position: "bottom",
                        },
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false,
                            },
                        },
                        y: {
                            beginAtZero: true,
                        },
                    },
                },
            }
        );
    }

    const datosStock = leerDatos(
        "datos-grafico-stock"
    );

    const stockCanvas = document.getElementById(
        "graficoStock"
    );

    if (stockCanvas) {
        new Chart(
            stockCanvas,
            {
                type: "bar",
                data: {
                    labels: datosStock.labels || [],
                    datasets: [
                        {
                            label: "Disponible",
                            data: datosStock.disponible || [],
                            backgroundColor: colores.azul,
                            borderRadius: 7,
                        },
                        {
                            label: "Reservado",
                            data: datosStock.reservado || [],
                            backgroundColor: colores.amarillo,
                            borderRadius: 7,
                        },
                    ],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            stacked: true,
                        },
                        y: {
                            stacked: true,
                            grid: {
                                display: false,
                            },
                        },
                    },
                },
            }
        );
    }

    const datosConsumo = leerDatos(
        "datos-grafico-consumo"
    );

    const consumoCanvas = document.getElementById(
        "graficoConsumo"
    );

    if (consumoCanvas) {
        new Chart(
            consumoCanvas,
            {
                type: "bar",
                data: {
                    labels: datosConsumo.labels || [],
                    datasets: [
                        {
                            label: "Unidades vendidas",
                            data: datosConsumo.vendidas || [],
                            backgroundColor: colores.verde,
                            borderRadius: 7,
                        },
                    ],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false,
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                        },
                        y: {
                            grid: {
                                display: false,
                            },
                        },
                    },
                },
            }
        );
    }

    const datosCategorias = leerDatos(
        "datos-grafico-categorias-stock"
    );

    const categoriasCanvas = document.getElementById(
        "graficoCategoriasStock"
    );

    if (categoriasCanvas) {
        new Chart(
            categoriasCanvas,
            {
                type: "doughnut",
                data: {
                    labels: datosCategorias.labels || [],
                    datasets: [
                        {
                            data: datosCategorias.stock || [],
                            backgroundColor: [
                                colores.azulClaro,
                                colores.azul,
                                colores.azulOscuro,
                                colores.verde,
                                colores.amarillo,
                                colores.rojo,
                            ],
                            borderWidth: 0,
                            hoverOffset: 8,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "68%",
                    plugins: {
                        legend: {
                            position: "bottom",
                        },
                    },
                },
            }
        );
    }
});