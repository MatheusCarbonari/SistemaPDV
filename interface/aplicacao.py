import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from interface.janela_principal import JanelaPrincipal


def obter_aplicacao(argumentos: Sequence[str] | None = None) -> QApplication:
    """Retorna a instância única de QApplication, criando-a se necessário."""
    aplicacao = QApplication.instance()

    if aplicacao is None:
        argumentos_qt = list(argumentos) if argumentos is not None else sys.argv
        aplicacao = QApplication(argumentos_qt)

    return aplicacao


def executar_aplicacao(argumentos: Sequence[str] | None = None) -> int:
    """Exibe a janela principal e inicia o event loop do Qt."""
    aplicacao = obter_aplicacao(argumentos)
    janela = JanelaPrincipal()
    janela.show()

    return aplicacao.exec()
