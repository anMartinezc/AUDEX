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

    const formatoDinero = (valor) => {
        return new Intl.NumberFormat(
            "es-CL",
            {
                style: "currency",
                currency: "CLP",
                maximumFractionDigits: 0,
            }
        ).format(valor);
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

    const datosVentas = leerDatos(
        "datos-grafico-ventas"
    );

    const ventasCanvas = document.getElementById(
        "graficoVentas"
    );

    if (ventasCanvas) {
        new Chart(
            ventasCanvas,
            {
                type: "line",
                data: {
                    labels: datosVentas.labels || [],
                    datasets: [
                        {
                            label: "Ingresos",
                            data: datosVentas.ingresos || [],
                            borderColor: colores.azulClaro,
                            backgroundColor:
                                "rgba(131,216,243,0.12)",
                            fill: true,
                            tension: 0.32,
                            pointRadius: 3,
                            pointHoverRadius: 6,
                            yAxisID: "dinero",
                        },
                        {
                            label: "Unidades",
                            data: datosVentas.unidades || [],
                            borderColor: colores.verde,
                            backgroundColor:
                                "rgba(124,232,166,0.08)",
                            tension: 0.32,
                            pointRadius: 2,
                            yAxisID: "cantidad",
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
                        tooltip: {
                            callbacks: {
                                label(contexto) {
                                    if (
                                        contexto.dataset.yAxisID
                                        === "dinero"
                                    ) {
                                        return (
                                            `${contexto.dataset.label}: `
                                            + formatoDinero(
                                                contexto.raw
                                            )
                                        );
                                    }

                                    return (
                                        `${contexto.dataset.label}: `
                                        + contexto.raw
                                    );
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false,
                            },
                        },
                        dinero: {
                            position: "left",
                            ticks: {
                                callback: formatoDinero,
                            },
                        },
                        cantidad: {
                            position: "right",
                            grid: {
                                drawOnChartArea: false,
                            },
                            beginAtZero: true,
                        },
                    },
                },
            }
        );
    }

    const datosProductos = leerDatos(
        "datos-grafico-productos"
    );

    const productosCanvas = document.getElementById(
        "graficoProductos"
    );

    if (productosCanvas) {
        new Chart(
            productosCanvas,
            {
                type: "bar",
                data: {
                    labels: datosProductos.labels || [],
                    datasets: [
                        {
                            label: "Unidades",
                            data: datosProductos.unidades || [],
                            backgroundColor: colores.azul,
                            borderRadius: 8,
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
        "datos-grafico-categorias"
    );

    const categoriasCanvas = document.getElementById(
        "graficoCategorias"
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
                            data: datosCategorias.ingresos || [],
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
                        tooltip: {
                            callbacks: {
                                label(contexto) {
                                    return (
                                        `${contexto.label}: `
                                        + formatoDinero(
                                            contexto.raw
                                        )
                                    );
                                },
                            },
                        },
                    },
                },
            }
        );
    }

    const datosMetodos = leerDatos(
        "datos-grafico-metodos"
    );

    const metodosCanvas = document.getElementById(
        "graficoMetodos"
    );

    if (metodosCanvas) {
        new Chart(
            metodosCanvas,
            {
                type: "polarArea",
                data: {
                    labels: datosMetodos.labels || [],
                    datasets: [
                        {
                            data: datosMetodos.cantidades || [],
                            backgroundColor: [
                                "rgba(131,216,243,0.72)",
                                "rgba(54,169,214,0.72)",
                                "rgba(124,232,166,0.72)",
                            ],
                            borderWidth: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                        },
                    },
                    scales: {
                        r: {
                            ticks: {
                                display: false,
                            },
                            grid: {
                                color: colores.grilla,
                            },
                        },
                    },
                },
            }
        );
    }
});