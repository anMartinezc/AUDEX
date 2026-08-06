# tributario/base.py

from dataclasses import dataclass


@dataclass
class ResultadoDTE:
    folio: str
    tipo: str
    estado: str
    pdf: bytes
    xml: bytes | None = None


class EmisorDTE:
    def emitir_boleta(self, pedido) -> ResultadoDTE:
        raise NotImplementedError