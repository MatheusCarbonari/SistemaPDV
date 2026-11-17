from pathlib import Path
import sys

import pytest

import database.conexao as conexao_module


def _simular_pyinstaller(monkeypatch, meipass: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)


def test_desenvolvimento_preserva_data_do_repositorio(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)

    esperado = conexao_module.DIRETORIO_RAIZ_DESENVOLVIMENTO / "data"

    assert not conexao_module.execucao_empacotada()
    assert conexao_module.resolver_diretorio_dados() == esperado
    assert conexao_module.resolver_caminho_banco() == (
        esperado / "sistema_acougue.db"
    )


def test_empacotado_usa_localappdata_especifico_do_usuario(
    tmp_path,
    monkeypatch,
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _simular_pyinstaller(monkeypatch, bundle / "_internal")
    local_app_data = tmp_path / "perfil" / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.chdir(bundle)

    assert conexao_module.execucao_empacotada()
    assert conexao_module.resolver_caminho_banco() == (
        local_app_data / "Sistema-PDV" / "data" / "sistema_acougue.db"
    )


def test_bancos_de_desenvolvimento_e_empacotado_sao_isolados(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    caminho_desenvolvimento = conexao_module.resolver_caminho_banco()

    _simular_pyinstaller(monkeypatch, tmp_path / "_internal")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "usuario"))
    caminho_empacotado = conexao_module.resolver_caminho_banco()

    assert caminho_empacotado != caminho_desenvolvimento
    assert caminho_empacotado.parent != caminho_desenvolvimento.parent
    assert not caminho_empacotado.exists()


@pytest.mark.parametrize("valor", [None, "", "relativo"])
def test_empacotado_recusa_localappdata_ausente_ou_relativo(
    tmp_path,
    monkeypatch,
    valor,
) -> None:
    _simular_pyinstaller(monkeypatch, tmp_path / "_internal")
    if valor is None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.setenv("LOCALAPPDATA", valor)

    with pytest.raises(RuntimeError, match="LOCALAPPDATA"):
        conexao_module.resolver_caminho_banco()
