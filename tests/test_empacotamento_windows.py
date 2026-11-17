from pathlib import Path
import py_compile

import pytest
import tools.empacotamento_windows as empacotamento

from tools.empacotamento_windows import (
    EmpacotamentoInvalidoError,
    listar_fontes_runtime,
    publicar_distribuicao,
    preparar_fontes_build,
    validar_ambiente_build,
    validar_arvore_sem_dados,
)


RAIZ_PROJETO = Path(__file__).resolve().parent.parent


def test_allowlist_runtime_exclui_dados_testes_e_documentacao() -> None:
    relativos = {
        caminho.relative_to(RAIZ_PROJETO)
        for caminho in listar_fontes_runtime(RAIZ_PROJETO)
    }

    assert Path("main.py") in relativos
    assert Path("interface/aplicacao.py") in relativos
    assert Path("database/conexao.py") in relativos
    assert all(caminho.suffix == ".py" for caminho in relativos)
    assert all(
        caminho.parts[0] not in {"data", "docs", "tests"}
        for caminho in relativos
    )


def test_preparacao_injeta_metadados_apenas_na_copia_temporaria(
    tmp_path,
) -> None:
    destino = tmp_path / "stage"
    destino.mkdir()
    origem_version = RAIZ_PROJETO / "services" / "version_service.py"
    conteudo_original = origem_version.read_text(encoding="utf-8")

    preparar_fontes_build(
        RAIZ_PROJETO,
        destino,
        identificador_build="win-revisao-t59",
        commit_git="0123456789abcdef0123456789abcdef01234567",
    )

    conteudo_stage = (destino / "services" / "version_service.py").read_text(
        encoding="utf-8"
    )
    assert "IDENTIFICADOR_BUILD_EMBUTIDO: str | None = 'win-revisao-t59'" in conteudo_stage
    assert "COMMIT_GIT_EMBUTIDO: str | None = '0123456789abcdef0123456789abcdef01234567'" in conteudo_stage
    assert origem_version.read_text(encoding="utf-8") == conteudo_original
    assert not (destino / "data").exists()
    assert not (destino / "tests").exists()
    py_compile.compile(
        str(destino / "services" / "version_service.py"),
        doraise=True,
    )


def test_preparacao_recusa_metadados_invalidos(tmp_path) -> None:
    destino = tmp_path / "stage"
    destino.mkdir()

    with pytest.raises(ValueError, match="identificador do build"):
        preparar_fontes_build(
            RAIZ_PROJETO,
            destino,
            identificador_build="inválido com espaços",
            commit_git=None,
        )


def test_validacao_do_ambiente_confere_requisitos_fixados(
    tmp_path,
    monkeypatch,
) -> None:
    requisitos = tmp_path / "requirements-build.txt"
    requisitos.write_text(
        "PySide6_Essentials==6.12.0\nshiboken6==6.12.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(empacotamento.sys, "platform", "win32")
    monkeypatch.setattr(empacotamento.sys, "version_info", (3, 14, 0))
    monkeypatch.setattr(empacotamento.sys, "maxsize", 2**63 - 1)
    monkeypatch.setattr(
        empacotamento.metadata,
        "version",
        lambda nome: "6.12.0",
    )
    monkeypatch.setattr(empacotamento, "import_module", lambda nome: object())

    validar_ambiente_build(requisitos)


def test_validacao_do_ambiente_recusa_dependencia_divergente(
    tmp_path,
    monkeypatch,
) -> None:
    requisitos = tmp_path / "requirements-build.txt"
    requisitos.write_text(
        "PySide6_Essentials==6.12.0\nshiboken6==6.12.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(empacotamento.sys, "platform", "win32")
    monkeypatch.setattr(empacotamento.sys, "version_info", (3, 14, 0))
    monkeypatch.setattr(empacotamento.sys, "maxsize", 2**63 - 1)
    monkeypatch.setattr(
        empacotamento.metadata,
        "version",
        lambda nome: "9.9.9",
    )

    with pytest.raises(
        EmpacotamentoInvalidoError,
        match="Dependências de build divergentes",
    ):
        validar_ambiente_build(requisitos)


def test_contrato_qt_exige_distribuicoes_minimas_fixadas(
    tmp_path,
    monkeypatch,
) -> None:
    requisitos = tmp_path / "requirements-build.txt"
    requisitos.write_text("shiboken6==6.12.0\n", encoding="utf-8")
    monkeypatch.setattr(empacotamento.sys, "platform", "win32")
    monkeypatch.setattr(empacotamento.sys, "version_info", (3, 14, 0))
    monkeypatch.setattr(empacotamento.sys, "maxsize", 2**63 - 1)
    monkeypatch.setattr(
        empacotamento.metadata,
        "version",
        lambda nome: "6.12.0",
    )

    with pytest.raises(EmpacotamentoInvalidoError, match="Contrato Qt incompleto"):
        validar_ambiente_build(requisitos)


def test_lock_qt_exclui_componentes_nao_utilizados() -> None:
    requisitos = (
        RAIZ_PROJETO / "requirements-build.txt"
    ).read_text(encoding="utf-8")
    linhas = {
        linha.strip()
        for linha in requisitos.splitlines()
        if linha.strip() and not linha.startswith("#")
    }

    assert "PySide6_Essentials==6.12.0" in linhas
    assert "shiboken6==6.12.0" in linhas
    assert not any(linha.startswith("PySide6==") for linha in linhas)
    assert not any(linha.startswith("PySide6_Addons==") for linha in linhas)
    assert not any(linha.startswith("PySide6_Pdf==") for linha in linhas)
    assert not any(linha.startswith("PySide6_WebEngine==") for linha in linhas)


@pytest.mark.parametrize(
    "relativo",
    [
        Path("data/sistema_acougue.db"),
        Path("tests/test_interno.py"),
        Path("_internal/segredo.pfx"),
        Path("_internal/.env.production"),
        Path("logs/sistema-pdv.log"),
    ],
)
def test_auditoria_recusa_conteudo_operacional_ou_interno(
    tmp_path,
    relativo,
) -> None:
    alvo = tmp_path / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(b"nao distribuir")

    with pytest.raises(EmpacotamentoInvalidoError):
        validar_arvore_sem_dados(tmp_path)


def test_configuracao_define_onedir_grafico_sem_dados_adicionados() -> None:
    spec = (
        RAIZ_PROJETO / "packaging" / "windows" / "Sistema-PDV.spec"
    ).read_text(encoding="utf-8")

    assert "COLLECT(" in spec
    assert 'name="Sistema-PDV"' in spec
    assert "console=False" in spec
    assert "datas=[]" in spec
    assert "exclude_binaries=True" in spec

    roteiro = (RAIZ_PROJETO / "scripts" / "build_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "Start-Process" in roteiro
    assert "-Wait" in roteiro
    assert "-PassThru" in roteiro
    assert "validar-ambiente" in roteiro
    assert "Select-Object -First 1" in roteiro
    assert "$env:PYTHONPATH = $RaizProjeto" in roteiro
    assert '"$RaizProjeto;$PythonPathAnterior"' not in roteiro
    assert "--distpath $DiretorioDistTemporario" in roteiro
    assert roteiro.index("Start-Process") < roteiro.index(
        "tools.empacotamento_windows publicar"
    )


def test_publicacao_substitui_distribuicao_somente_ao_final(tmp_path) -> None:
    publicada = tmp_path / "dist" / "windows"
    publicada.mkdir(parents=True)
    (publicada / "anterior.txt").write_text("anterior", encoding="utf-8")
    candidata = tmp_path / "build" / "candidata"
    candidata.mkdir(parents=True)
    (candidata / "nova.txt").write_text("nova", encoding="utf-8")

    publicar_distribuicao(candidata, publicada)

    assert not candidata.exists()
    assert not (publicada / "anterior.txt").exists()
    assert (publicada / "nova.txt").read_text(encoding="utf-8") == "nova"


def test_falha_na_publicacao_preserva_distribuicao_anterior(
    tmp_path,
    monkeypatch,
) -> None:
    publicada = tmp_path / "dist" / "windows"
    publicada.mkdir(parents=True)
    (publicada / "anterior.txt").write_text("intacta", encoding="utf-8")
    candidata = tmp_path / "build" / "candidata"
    candidata.mkdir(parents=True)
    (candidata / "nova.txt").write_text("nova", encoding="utf-8")
    substituir_original = empacotamento._substituir_diretorio

    def substituir_com_falha(origem, destino):
        if origem == candidata:
            raise OSError("falha simulada ao publicar")
        return substituir_original(origem, destino)

    monkeypatch.setattr(
        empacotamento,
        "_substituir_diretorio",
        substituir_com_falha,
    )

    with pytest.raises(OSError, match="falha simulada"):
        publicar_distribuicao(candidata, publicada)

    assert (publicada / "anterior.txt").read_text(encoding="utf-8") == "intacta"
    assert not (publicada / "nova.txt").exists()
    assert (candidata / "nova.txt").exists()


def test_publicacao_repete_renomeacao_bloqueada_transitoriamente(
    tmp_path,
    monkeypatch,
) -> None:
    publicada = tmp_path / "dist" / "windows"
    candidata = tmp_path / "build" / "candidata"
    candidata.mkdir(parents=True)
    (candidata / "nova.txt").write_text("nova", encoding="utf-8")
    substituir_original = Path.replace
    chamadas = 0

    def substituir_transitorio(origem, destino):
        nonlocal chamadas
        chamadas += 1
        if chamadas < 3:
            raise PermissionError("arquivo temporariamente ocupado")
        return substituir_original(origem, destino)

    monkeypatch.setattr(Path, "replace", substituir_transitorio)
    monkeypatch.setattr(empacotamento.time, "sleep", lambda segundos: None)

    publicar_distribuicao(candidata, publicada)

    assert chamadas == 3
    assert (publicada / "nova.txt").exists()
