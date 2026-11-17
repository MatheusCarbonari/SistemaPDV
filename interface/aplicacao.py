import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from database.conexao import CAMINHO_BANCO
from interface.dialogo_login import DialogoLogin
from interface.dialogo_primeiro_acesso import DialogoPrimeiroAcesso
from interface.estilo_dialogos import aplicar_tema_mensagens
from interface.janela_principal import JanelaPrincipal
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.administrador_inicial_service import obter_estado_primeiro_acesso
from services.autenticacao_service import autorizar_sessao, encerrar_sessao
from services.backup_externo_service import (
    AgendadorBackupExterno,
    ServicoBackupExterno,
    destino_externo_configurado_no_ambiente,
)
from services.inicializacao_banco_service import (
    InicializacaoBancoError,
    preparar_banco_para_operacao,
)
from services.logging_service import (
    configurar_logging,
    instalar_tratamento_erros_nao_tratados,
    registrar_evento,
)
from services.version_service import (
    IdentificacaoAplicativo,
    obter_identificacao_aplicativo,
)
from services.contexto_instalacao_service import (
    ContextoInstalacao,
    obter_contexto_instalacao,
)


class PrimeiroAcessoNecessarioError(RuntimeError):
    pass


def registrar_identificacao_aplicativo() -> IdentificacaoAplicativo:
    """Registra os metadados técnicos embutidos sem consultar Git ou rede."""
    identificacao = obter_identificacao_aplicativo()
    registrar_evento(
        "aplicacao_identificada",
        **identificacao.dados_diagnostico(),
    )
    return identificacao


def obter_aplicacao(argumentos: Sequence[str] | None = None) -> QApplication:
    """Retorna a instância única de QApplication, criando-a se necessário."""
    aplicacao = QApplication.instance()

    if aplicacao is None:
        argumentos_qt = list(argumentos) if argumentos is not None else sys.argv
        aplicacao = QApplication(argumentos_qt)

    aplicar_tema_mensagens(aplicacao)

    return aplicacao


def criar_janela_principal(
    caminho_banco=CAMINHO_BANCO,
    sessao: SessaoUsuario | None = None,
    *,
    contexto: ContextoInstalacao | None = None,
) -> JanelaPrincipal:
    """Cria a janela somente para uma sessão autenticada e ainda válida."""
    preparar_banco_para_operacao(caminho_banco, contexto=contexto)
    estado = obter_estado_primeiro_acesso(caminho_banco)
    if estado == "NAO_CONFIGURADO":
        raise PrimeiroAcessoNecessarioError(
            "O administrador inicial ainda precisa ser configurado."
        )
    autorizar_sessao(sessao, ("ADMINISTRADOR", "CAIXA"), caminho_banco)
    return JanelaPrincipal(caminho_banco, sessao)


def executar_aplicacao(
    argumentos: Sequence[str] | None = None,
    caminho_banco=None,
    *,
    contexto: ContextoInstalacao | None = None,
) -> int:
    """Exibe a janela principal e inicia o event loop do Qt."""
    contexto_efetivo = contexto or obter_contexto_instalacao()
    caminho_banco = caminho_banco or contexto_efetivo.caminhos.banco
    configurar_logging(
        contexto_efetivo.caminhos.logs if contexto_efetivo.comercial else None
    )
    instalar_tratamento_erros_nao_tratados()
    registrar_evento(
        "inicializacao_iniciada",
    )
    registrar_identificacao_aplicativo()
    aplicacao = obter_aplicacao(argumentos)
    try:
        resultado_banco = preparar_banco_para_operacao(
            caminho_banco,
            contexto=contexto_efetivo,
        )
    except InicializacaoBancoError as erro:
        registrar_evento(
            "preparacao_banco_falhou",
            erro_tipo=type(erro).__name__,
            resultado="bloqueado",
        )
        QMessageBox.critical(
            None,
            "Falha ao iniciar o Sistema-PDV",
            str(erro),
        )
        return 1
    registrar_evento(
        "preparacao_banco_concluida",
        banco_novo=resultado_banco.banco_novo,
        versao_inicial=resultado_banco.versao_inicial,
        versao_final=resultado_banco.versao_final,
        backup_criado=resultado_banco.caminho_backup is not None,
        resultado="sucesso",
    )

    try:
        estado = obter_estado_primeiro_acesso(caminho_banco)
    except EstadoIdentidadeInconsistenteError as erro:
        registrar_evento(
            "identidade_inconsistente",
            erro_tipo=type(erro).__name__,
            resultado="bloqueado",
        )
        QMessageBox.critical(
            None,
            "Configuração de identidade inconsistente",
            "A configuração administrativa está inconsistente. A operação "
            "foi bloqueada e o primeiro acesso não pode ser recriado.",
        )
        return 1
    except Exception as erro:
        registrar_evento(
            "verificacao_identidade_falhou",
            erro_tipo=type(erro).__name__,
            resultado="bloqueado",
        )
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
            registrar_evento(
                "primeiro_acesso_cancelado",
                codigo_saida=1,
            )
            return 1
        try:
            estado = obter_estado_primeiro_acesso(caminho_banco)
        except EstadoIdentidadeInconsistenteError:
            estado = "INCONSISTENTE"
        if estado != "CONFIGURADO":
            registrar_evento(
                "primeiro_acesso_incompleto",
                resultado="bloqueado",
            )
            QMessageBox.critical(
                None,
                "Configuração inicial incompleta",
                "Não foi possível comprovar a criação do administrador. "
                "A operação continuará bloqueada.",
            )
            return 1

        registrar_evento(
            "primeiro_acesso_concluido",
            resultado="sucesso",
        )

        QMessageBox.information(
            None,
            "Administrador inicial criado",
            "A configuração foi concluída. Entre com a conta criada para "
            "iniciar uma sessão autenticada.",
        )

    dialogo_login = DialogoLogin(caminho_banco)
    if dialogo_login.exec() != QDialog.DialogCode.Accepted:
        registrar_evento(
            "inicializacao_cancelada",
            codigo_saida=0,
        )
        return 0
    if dialogo_login.sessao is None:
        registrar_evento(
            "sessao_ausente_apos_login",
            resultado="bloqueado",
        )
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
            contexto=contexto_efetivo,
        )
    except Exception as erro:
        registrar_evento(
            "abertura_operacao_falhou",
            erro_tipo=type(erro).__name__,
            resultado="bloqueado",
        )
        encerrar_sessao(dialogo_login.sessao)
        QMessageBox.critical(
            None,
            "Falha ao abrir a operação",
            "Não foi possível validar a sessão. A operação foi bloqueada.",
        )
        return 1

    janela.show()
    servico_backup_externo = ServicoBackupExterno(
        caminho_banco,
        destino=destino_externo_configurado_no_ambiente(),
        controlador_estado=getattr(janela, "controlador_estado", None),
    )
    agendador_backup_externo = AgendadorBackupExterno(
        servico_backup_externo
    )
    agendador_backup_externo.iniciar()
    registrar_evento(
        "operacao_iniciada",
        resultado="sucesso",
    )
    try:
        codigo_saida = aplicacao.exec()
    finally:
        agendador_backup_externo.parar()
    registrar_evento(
        "aplicacao_encerrada",
        codigo_saida=codigo_saida,
    )
    return codigo_saida
