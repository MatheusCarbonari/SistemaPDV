import sys

import pytest

import database.conexao as conexao_module
from services.contexto_instalacao_service import (
    IdentidadeInstalacaoAusenteError,
    resolver_contexto_instalacao,
)


class RegistroVazio:
    def listar_instalacoes(self):
        return ()


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


def test_empacotado_sem_identidade_nao_cai_em_localappdata(
    tmp_path,
    monkeypatch,
) -> None:
    local_app_data = tmp_path / "perfil" / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    executavel = tmp_path / "Sistema-PDV.exe"
    executavel.write_bytes(b"teste")

    with pytest.raises(IdentidadeInstalacaoAusenteError):
        resolver_contexto_instalacao(
            empacotado=True,
            caminho_executavel=executavel,
            provedor_registro=RegistroVazio(),
            program_data=tmp_path / "ProgramData",
            program_files=tmp_path / "Program Files",
        )

    assert not local_app_data.exists()


def test_desenvolvimento_e_instalacao_comercial_nao_compartilham_fallback(
    tmp_path,
) -> None:
    desenvolvimento = resolver_contexto_instalacao(
        empacotado=False,
        raiz_repositorio=tmp_path / "repositorio",
    )
    executavel = tmp_path / "instalado" / "Sistema-PDV.exe"
    executavel.parent.mkdir()
    executavel.write_bytes(b"teste")

    assert desenvolvimento.caminhos.banco == (
        tmp_path / "repositorio" / "data" / "sistema_acougue.db"
    )
    with pytest.raises(IdentidadeInstalacaoAusenteError):
        resolver_contexto_instalacao(
            empacotado=True,
            caminho_executavel=executavel,
            provedor_registro=RegistroVazio(),
            program_data=tmp_path / "ProgramData",
            program_files=tmp_path / "Program Files",
        )
