import importlib

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from database.conexao import conectar
from database.schema import VERSAO_ESQUEMA
import interface.aplicacao as aplicacao_module
from interface.aplicacao import (
    PrimeiroAcessoNecessarioError,
    criar_janela_principal,
    obter_aplicacao,
)
from services.autenticacao_service import SessaoInvalidaError
from services.inicializacao_banco_service import InicializacaoBancoError
from tests.helpers_identidade import criar_janela_autenticada
from tests.helpers_identidade import criar_sessao_admin_teste


def test_janela_principal_possui_configuracao_minima(qtbot, tmp_path) -> None:
    janela = criar_janela_autenticada(tmp_path / "janela.db")
    qtbot.addWidget(janela)

    assert janela.windowTitle() == "Sistema-PDV"
    assert janela.width() == 1024
    assert janela.height() == 720
    assert isinstance(janela.centralWidget(), QWidget)
    assert janela.centralWidget().objectName() == "estrutura_principal"
    assert janela.pagina_frente_caixa.objectName() == "area_vendas"
    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa


def test_janela_principal_pode_ser_aberta_e_fechada(qtbot, tmp_path) -> None:
    janela = criar_janela_autenticada(tmp_path / "janela_fecha.db")
    qtbot.addWidget(janela)

    janela.show()
    qtbot.waitUntil(janela.isVisible)

    janela.close()
    qtbot.waitUntil(lambda: not janela.isVisible())


def test_obter_aplicacao_reutiliza_instancia_existente(qapp) -> None:
    aplicacao = obter_aplicacao(["sistema-pdv"])

    assert aplicacao is qapp
    assert aplicacao is QApplication.instance()


def test_importar_ponto_de_entrada_nao_abre_janela(qapp) -> None:
    janelas_antes = set(qapp.topLevelWidgets())

    modulo = importlib.import_module("main")
    importlib.reload(modulo)

    assert set(qapp.topLevelWidgets()) == janelas_antes


def test_criar_janela_principal_bloqueia_banco_sem_administrador(
    tmp_path,
) -> None:
    caminho = tmp_path / "aplicacao.db"

    with pytest.raises(PrimeiroAcessoNecessarioError):
        criar_janela_principal(caminho)

    conexao = conectar(caminho)
    try:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == (
            VERSAO_ESQUEMA
        )
    finally:
        conexao.close()


def test_falha_de_inicializacao_nao_abre_operacao_comercial(
    qapp,
    monkeypatch,
) -> None:
    mensagens = []
    monkeypatch.setattr(
        aplicacao_module,
        "preparar_banco_para_operacao",
        lambda caminho: (_ for _ in ()).throw(
            InicializacaoBancoError("backup indisponível")
        ),
    )
    monkeypatch.setattr(
        aplicacao_module.QMessageBox,
        "critical",
        lambda parent, titulo, mensagem: mensagens.append(
            (titulo, mensagem)
        ),
    )

    resultado = aplicacao_module.executar_aplicacao([], "incompativel.db")

    assert resultado == 1
    assert mensagens == [
        ("Falha ao iniciar o Sistema-PDV", "backup indisponível")
    ]


def test_primeiro_acesso_cria_admin_e_exige_login(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "primeiro_acesso.db"
    mensagens = []

    class DialogoConfigurador:
        def __init__(self, caminho_banco):
            self.caminho_banco = caminho_banco

        def exec(self):
            from services.administrador_inicial_service import (
                criar_administrador_inicial,
            )

            usuario, erros = criar_administrador_inicial(
                "administrador",
                "frase segura para o administrador 2026",
                "frase segura para o administrador 2026",
                self.caminho_banco,
            )
            assert usuario is not None
            assert erros == []
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        aplicacao_module,
        "DialogoPrimeiroAcesso",
        DialogoConfigurador,
    )
    class LoginCancelado:
        def __init__(self, caminho_banco):
            self.sessao = None

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(aplicacao_module, "DialogoLogin", LoginCancelado)
    monkeypatch.setattr(
        aplicacao_module.QMessageBox,
        "information",
        lambda parent, titulo, mensagem: mensagens.append((titulo, mensagem)),
    )

    resultado = aplicacao_module.executar_aplicacao([], caminho)

    assert resultado == 0
    assert "sessão autenticada" in mensagens[0][1]
    with pytest.raises(SessaoInvalidaError):
        criar_janela_principal(caminho)


def test_primeiro_acesso_cancelado_nao_configura_nem_abre_operacao(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "primeiro_acesso_cancelado.db"

    class DialogoCancelado:
        def __init__(self, caminho_banco):
            self.caminho_banco = caminho_banco

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        aplicacao_module,
        "DialogoPrimeiroAcesso",
        DialogoCancelado,
    )

    resultado = aplicacao_module.executar_aplicacao([], caminho)

    assert resultado == 1
    from services.administrador_inicial_service import obter_estado_primeiro_acesso

    assert obter_estado_primeiro_acesso(caminho) == "NAO_CONFIGURADO"


def test_admin_configurado_nao_reabre_primeiro_acesso(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "configurado.db"
    aplicacao_module.preparar_banco_para_operacao(caminho)
    from services.administrador_inicial_service import criar_administrador_inicial

    criar_administrador_inicial(
        "administrador",
        "frase segura para o administrador 2026",
        "frase segura para o administrador 2026",
        caminho,
    )
    monkeypatch.setattr(
        aplicacao_module,
        "DialogoPrimeiroAcesso",
        lambda caminho_banco: pytest.fail("não deve reabrir primeiro acesso"),
    )
    class LoginCancelado:
        def __init__(self, caminho_banco):
            self.sessao = None

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(aplicacao_module, "DialogoLogin", LoginCancelado)

    resultado = aplicacao_module.executar_aplicacao([], caminho)

    assert resultado == 0


def test_login_valido_abre_janela_com_sessao(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "login_valido.db"
    sessao = criar_sessao_admin_teste(caminho)

    class LoginValido:
        def __init__(self, caminho_banco):
            self.sessao = sessao

        def exec(self):
            return QDialog.DialogCode.Accepted

    janelas = []
    janela_real = aplicacao_module.criar_janela_principal

    def criar_janela(caminho_banco, sessao_recebida):
        janela = janela_real(caminho_banco, sessao_recebida)
        janelas.append(janela)
        return janela

    monkeypatch.setattr(aplicacao_module, "DialogoLogin", LoginValido)
    monkeypatch.setattr(aplicacao_module, "criar_janela_principal", criar_janela)
    monkeypatch.setattr(QApplication, "exec", lambda self: 37)

    resultado = aplicacao_module.executar_aplicacao([], caminho)

    assert resultado == 37
    assert len(janelas) == 1
    assert janelas[0].sessao is sessao
    assert janelas[0].isVisible()
    janelas[0].close()


def test_estado_de_identidade_inconsistente_bloqueia_sem_recriar(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "identidade_inconsistente.db"
    aplicacao_module.preparar_banco_para_operacao(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            INSERT INTO usuarios (
                identificacao_acesso, perfil, senha_hash
            ) VALUES ('usuario-solto', 'ADMINISTRADOR', 'hash-invalido')
            """
        )
        conexao.commit()
    finally:
        conexao.close()
    mensagens = []
    monkeypatch.setattr(
        aplicacao_module,
        "DialogoPrimeiroAcesso",
        lambda caminho_banco: pytest.fail("não deve permitir recriação"),
    )
    monkeypatch.setattr(
        aplicacao_module.QMessageBox,
        "critical",
        lambda parent, titulo, mensagem: mensagens.append((titulo, mensagem)),
    )

    resultado = aplicacao_module.executar_aplicacao([], caminho)

    assert resultado == 1
    assert "inconsistente" in mensagens[0][0].lower()
    assert "não pode ser recriado" in mensagens[0][1]


def test_camadas_existentes_continuam_importaveis() -> None:
    modulos = [
        "models.item_venda",
        "services.item_venda_service",
        "repositories.produto_repository",
        "database.schema",
    ]

    for nome_modulo in modulos:
        assert importlib.import_module(nome_modulo) is not None
