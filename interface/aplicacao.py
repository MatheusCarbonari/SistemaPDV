import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from database.conexao import CAMINHO_BANCO
from interface.janela_principal import JanelaPrincipal
from services.inicializacao_banco_service import (
    InicializacaoBancoError,
    preparar_banco_para_operacao,
)


def obter_aplicacao(argumentos: Sequence[str] | None = None) -> QApplication:
    """Retorna a instância única de QApplication, criando-a se necessário."""
    aplicacao = QApplication.instance()

    if aplicacao is None:
        argumentos_qt = list(argumentos) if argumentos is not None else sys.argv
        aplicacao = QApplication(argumentos_qt)

    return aplicacao


def criar_janela_principal(
    caminho_banco=CAMINHO_BANCO,
) -> JanelaPrincipal:
    """Prepara o banco antes de permitir operações comerciais."""
    preparar_banco_para_operacao(caminho_banco)
    return JanelaPrincipal(caminho_banco)


def executar_aplicacao(
    argumentos: Sequence[str] | None = None,
    caminho_banco=CAMINHO_BANCO,
) -> int:
    """Exibe a janela principal e inicia o event loop do Qt."""
    aplicacao = obter_aplicacao(argumentos)
    try:
        janela = criar_janela_principal(caminho_banco)
    except InicializacaoBancoError as erro:
        QMessageBox.critical(
            None,
            "Falha ao iniciar o Sistema-PDV",
            str(erro),
        )
        return 1
    janela.show()

    return aplicacao.exec()
