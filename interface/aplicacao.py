import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from database.conexao import CAMINHO_BANCO
from interface.dialogo_primeiro_acesso import DialogoPrimeiroAcesso
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.administrador_inicial_service import obter_estado_primeiro_acesso
from services.inicializacao_banco_service import (
    InicializacaoBancoError,
    preparar_banco_para_operacao,
)


class PrimeiroAcessoNecessarioError(RuntimeError):
    pass


class LoginPendenteError(RuntimeError):
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
) -> None:
    """Mantém a operação fechada enquanto o T46 não autenticar uma sessão."""
    preparar_banco_para_operacao(caminho_banco)
    estado = obter_estado_primeiro_acesso(caminho_banco)
    if estado == "NAO_CONFIGURADO":
        raise PrimeiroAcessoNecessarioError(
            "O administrador inicial ainda precisa ser configurado."
        )
    raise LoginPendenteError(
        "A operação comercial exige o login que será implementado no T46."
    )


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
            "A configuração foi concluída. A operação comercial permanecerá "
            "bloqueada até a implementação do login no T46.",
        )
        return 0

    QMessageBox.information(
        None,
        "Login ainda não disponível",
        "O administrador inicial já está configurado. A operação comercial "
        "permanecerá bloqueada até a implementação do login no T46.",
    )

    return 0
