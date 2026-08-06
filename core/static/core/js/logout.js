"use strict";

/* =========================================================
   AUDEX
   Archivo: core/static/core/js/logout.js

   Confirmación mediante <dialog>.
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById(
        "logoutModal"
    );

    const confirmar = document.getElementById(
        "confirmarLogout"
    );

    const cancelar = document.getElementById(
        "cancelarLogout"
    );

    const cerrar = document.getElementById(
        "cerrarLogoutModal"
    );

    let formularioPendiente = null;
    let elementoAnterior = null;
    let enviando = false;


    if (
        !(modal instanceof HTMLDialogElement) ||
        !confirmar
    ) {
        console.warn(
            "Logout Audex: no se encontró el <dialog> de confirmación."
        );

        return;
    }


    const abrirModal = (formulario) => {
        formularioPendiente = formulario;
        elementoAnterior = document.activeElement;
        enviando = false;

        if (!modal.open) {
            modal.showModal();
        }

        document.body.classList.add(
            "no-scroll"
        );

        window.requestAnimationFrame(() => {
            modal.classList.add(
                "logout-dialog--visible"
            );

            if (cancelar) {
                cancelar.focus();
            } else {
                confirmar.focus();
            }
        });
    };


    const cerrarModal = () => {
        if (
            enviando ||
            !modal.open
        ) {
            return;
        }

        modal.classList.remove(
            "logout-dialog--visible"
        );

        document.body.classList.remove(
            "no-scroll"
        );

        window.setTimeout(() => {
            if (modal.open) {
                modal.close();
            }

            formularioPendiente = null;
            confirmar.disabled = false;

            confirmar.innerHTML = `
                Cerrar sesión
                <i class="bi bi-box-arrow-right"></i>
            `;

            if (
                elementoAnterior &&
                typeof elementoAnterior.focus === "function"
            ) {
                elementoAnterior.focus();
            }

            elementoAnterior = null;
        }, 220);
    };


    document.addEventListener(
        "submit",
        (evento) => {
            const formulario = evento.target;

            if (
                !(formulario instanceof HTMLFormElement) ||
                !formulario.classList.contains(
                    "js-logout-form"
                )
            ) {
                return;
            }

            evento.preventDefault();
            evento.stopImmediatePropagation();

            abrirModal(formulario);
        },
        true
    );


    confirmar.addEventListener("click", () => {
        if (
            !formularioPendiente ||
            enviando
        ) {
            return;
        }

        enviando = true;
        confirmar.disabled = true;

        confirmar.innerHTML = `
            Cerrando sesión...
            <i class="bi bi-box-arrow-right"></i>
        `;

        HTMLFormElement.prototype.submit.call(
            formularioPendiente
        );
    });


    if (cancelar) {
        cancelar.addEventListener(
            "click",
            cerrarModal
        );
    }


    if (cerrar) {
        cerrar.addEventListener(
            "click",
            cerrarModal
        );
    }


    modal.addEventListener(
        "cancel",
        (evento) => {
            evento.preventDefault();
            cerrarModal();
        }
    );


    modal.addEventListener(
        "click",
        (evento) => {
            if (evento.target === modal) {
                cerrarModal();
            }
        }
    );


    console.log(
        "Confirmación de cierre de sesión cargada correctamente."
    );
});