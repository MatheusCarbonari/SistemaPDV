import json
import subprocess

import pytest

import interface.aplicacao as aplicacao_module
import interface.janela_principal as janela_principal_module
import services.logging_service as logging_service
import services.version_service as version_service
from services.version_service import IdentificacaoAplicativo
from tests.helpers_identidade import criar_janela_autenticada


def test_versao_oficial_e_valida_e_independente_do_schema() -> None:
    identificacao = version_service.obter_identificacao_aplicativo()

    assert identificacao.nome == "Sistema-PDV"
    assert identificacao.versao == "0.1.0"
    assert version_service._VERSAO_SEMANTICA.fullmatch(identificacao.versao)
    assert identificacao.versao != "10"


def test_metadados_embutidos_conhecidos_sao_preservados(monkeypatch) -> None:
    monkeypatch.setattr(
        version_service,
        "IDENTIFICADOR_BUILD_EMBUTIDO",
        "windows-x64.20261111",
    )
    monkeypatch.setattr(
        version_service,
        "COMMIT_GIT_EMBUTIDO",
        "4c571fc",
    )

    identificacao = version_service.obter_identificacao_aplicativo()

    assert identificacao.identificador_build == "windows-x64.20261111"
    assert identificacao.commit_git == "4c571fc"
    assert identificacao.dados_diagnostico() == {
        "nome_aplicativo": "Sistema-PDV",
        "versao_aplicativo": "0.1.0",
        "build_id": "windows-x64.20261111",
        "commit_git": "4c571fc",
    }


@pytest.mark.parametrize(
    ("build", "commit"),
    [
        (None, None),
        ("", ""),
        ("build com espaços", "não-é-hexadecimal"),
    ],
)
def test_metadados_ausentes_ou_invalidos_sao_exibidos_como_desconhecidos(
    monkeypatch,
    build,
    commit,
) -> None:
    monkeypatch.setattr(version_service, "IDENTIFICADOR_BUILD_EMBUTIDO", build)
    monkeypatch.setattr(version_service, "COMMIT_GIT_EMBUTIDO", commit)

    identificacao = version_service.obter_identificacao_aplicativo()

    assert identificacao.identificador_build is None
    assert identificacao.commit_git is None
    assert identificacao.build_exibicao == "desconhecido"
    assert identificacao.commit_exibicao == "desconhecido"


def test_identificacao_funciona_sem_git_pasta_git_ou_rede(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def git_proibido(*args, **kwargs):
        raise AssertionError("A identificação não deve executar comandos externos.")

    monkeypatch.setattr(subprocess, "run", git_proibido)

    identificacao = version_service.obter_identificacao_aplicativo()

    assert not (tmp_path / ".git").exists()
    assert identificacao.nome == "Sistema-PDV"
    assert identificacao.versao == "0.1.0"


def test_texto_sobre_distingue_versao_build_e_commit() -> None:
    identificacao = IdentificacaoAplicativo(
        nome="Sistema-PDV",
        versao="0.1.0",
        identificador_build="windows-x64.42",
        commit_git="abcdef1",
    )

    texto = version_service.formatar_informacoes_sobre(identificacao)

    assert "Versão do aplicativo: 0.1.0" in texto
    assert "Identificador do build: windows-x64.42" in texto
    assert "Commit Git de origem: abcdef1" in texto
    assert "schema" not in texto.lower()
    assert "SQLite" not in texto


def test_sobre_exibe_identificacao_sem_alterar_tela_operacional(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    janela = criar_janela_autenticada(tmp_path / "sobre.db")
    qtbot.addWidget(janela)
    janela.show()
    qtbot.waitUntil(janela.isVisible)
    mensagens = []
    monkeypatch.setattr(
        janela_principal_module.QMessageBox,
        "information",
        lambda parent, titulo, mensagem: mensagens.append(
            (parent, titulo, mensagem)
        ),
    )

    janela.botao_sobre.click()

    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert janela.botao_sobre.isVisible()
    assert janela.botao_sobre.height() >= 34
    assert janela.botao_sobre.geometry().right() <= (
        janela.botao_sobre.parentWidget().contentsRect().right()
    )
    assert mensagens[0][0] is janela
    assert mensagens[0][1] == "Sobre o Sistema-PDV"
    assert "Versão do aplicativo: 0.1.0" in mensagens[0][2]
    assert "desconhecido" in mensagens[0][2]


def test_inicializacao_registra_identificacao_no_log_seguro(tmp_path) -> None:
    caminho_log = logging_service.configurar_logging(tmp_path / "logs")
    try:
        aplicacao_module.registrar_identificacao_aplicativo()
    finally:
        logging_service.encerrar_logging()

    documento = json.loads(caminho_log.read_text(encoding="utf-8"))
    assert documento["event"] == "aplicacao_identificada"
    assert documento["component"] == "aplicacao"
    assert documento["nome_aplicativo"] == "Sistema-PDV"
    assert documento["versao_aplicativo"] == "0.1.0"
    assert documento["build_id"] == "desconhecido"
    assert documento["commit_git"] == "desconhecido"
