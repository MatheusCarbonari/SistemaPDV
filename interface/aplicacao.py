import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from database.conexao import CAMINHO_BANCO
from interface.dialogo_login import DialogoLogin
from interface.dialogo_primeiro_acesso import DialogoPrimeiroAcesso
from interface.janela_principal import JanelaPrincipal
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.administrador_inicial_service import obter_estado_primeiro_acesso
from services.autenticacao_service import autorizar_sessao
from services.inicializacao_banco_service import (
    InicializacaoBancoError,
    preparar_banco_para_operacao,
)


class PrimeiroAcessoNecessarioError(RuntimeError):
    pass


def obter_aplicacao(argumentos: Sequence[str] | None = None) -> QApplication:
    """Retorna a instância única de QApplication, criando-a se necessário."""
    aplicacao = QApplication.instance()

    if aplicacao is None:
        argumentos_qt = list(argumentos) if argumentos is not None else sys.argv
        aplicacao = QApplication(argumentos_qt)

    return aplicacao


def criar_janela_principal(
    caminho_banco=CAMINHO_BANCO,
    sessao: SessaoUsuario | None = None,
) -> JanelaPrincipal:
    """Cria a janela somente para uma sessão autenticada e ainda válida."""
    preparar_banco_para_operacao(caminho_banco)
    estado = obter_estado_primeiro_acesso(caminho_banco)
    if estado == "NAO_CONFIGURADO":
        raise PrimeiroAcessoNecessarioError(
            "O administrador inicial ainda precisa ser configurado."
        )
    autorizar_sessao(sessao, ("ADMINISTRADOR", "CAIXA"), caminho_banco)
    return JanelaPrincipal(caminho_banco, sessao)


def executar_aplicacao(
    argumentos: Sequence[str] | None = None,
    caminho_banco=CAMINHO_BANCO,
) -> int:
    """Exibe a janela principal e inicia o event loop do Qt."""
    aplicacao = obter_aplicacao(argumentos)
    try:
        preparar_banco_para_operacao(caminho_banco)
    except InicializacaoBancoError as erro:
        QMessageBox.critical(
            None,
            "Falha ao iniciar o Sistema-PDV",
            str(erro),
        )
        return 1

    try:
        estado = obter_estado_primeiro_acesso(caminho_banco)
    except EstadoIdentidadeInconsistenteError:
        QMessageBox.critical(
            None,
            "Configuração de identidade inconsistente",
            "A configuração administrativa está inconsistente. A operação "
            "foi bloqueada e o primeiro acesso não pode ser recriado.",
        )
        return 1
    except Exception:
        QMessageBox.critical(
            None,
            "Falha ao verificar identidade",
            "Não foi possível verificar a configuração administrativa. "
            "A operação foi bloqueada com segurança.",
        )
        return 1

    if estado == "NAO_CONFIGURADO":
        dialogo = DialogoPrimeiroAcesso(caminho_banco)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return 1
        try:
            estado = obter_estado_primeiro_acesso(caminho_banco)
        except EstadoIdentidadeInconsistenteError:
            estado = "INCONSISTENTE"
        if estado != "CONFIGURADO":
            QMessageBox.critical(
                None,
                "Configuração inicial incompleta",
                "Não foi possível comprovar a criação do administrador. "
                "A operação continuará bloqueada.",
            )
            return 1

        QMessageBox.information(
            None,
            "Administrador inicial criado",
            "A configuração foi concluída. Entre com a conta criada para "
            "iniciar uma sessão autenticada.",
        )

    while True:
        dialogo_login = DialogoLogin(caminho_banco)
        if dialogo_login.exec() != QDialog.DialogCode.Accepted:
            return 0
        if dialogo_login.sessao is None:
            QMessageBox.critical(
                None,
                "Falha ao iniciar sessão",
                "O login foi concluído sem uma sessão válida. "
                "A operação foi bloqueada.",
            )
            return 1

        try:
            janela = criar_janela_principal(
                caminho_banco,
                dialogo_login.sessao,
            )
        except Exception:
            dialogo_login.sessao.encerrar()
            QMessageBox.critical(
                None,
                "Falha ao abrir a operação",
                "Não foi possível validar a sessão. A operação foi bloqueada.",
            )
            return 1

        troca_operador = {"solicitada": False}
        janela.logout_realizado.connect(
            lambda: troca_operador.__setitem__("solicitada", True)
        )
        janela.show()
        resultado = aplicacao.exec()
        if not troca_operador["solicitada"]:
            return resultado
