import sqlite3

import pytest

from database.conexao import conectar
import database.schema as schema
from services.inicializacao_banco_service import (
    BackupPreMigracaoError,
    MigracaoBancoError,
    VersaoBancoFuturaError,
    preparar_banco_para_operacao,
)
import services.inicializacao_banco_service as inicializacao_service


def preparar_banco_legado(caminho_banco, *, wal=False) -> None:
    conexao = conectar(caminho_banco)
    try:
        if wal:
            conexao.execute("PRAGMA journal_mode = WAL")
        conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
        conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria, forma_venda,
                preco_venda_centavos, origem
            ) VALUES ('10', 'Produto legado', 'TESTE', 'UNIDADE', 1000,
                      'COMPRADO')
            """
        )
        conexao.execute("PRAGMA user_version = 1")
        conexao.commit()
    finally:
        conexao.close()


def consultar_versao(caminho_banco) -> int:
    conexao = conectar(caminho_banco)
    try:
        return conexao.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conexao.close()


def backups_criados(caminho_banco):
    diretorio = caminho_banco.parent / "backups" / "pre_migracao"
    return sorted(diretorio.glob("*.db")) if diretorio.exists() else []


def test_banco_novo_cria_esquema_sem_backup(tmp_path) -> None:
    caminho = tmp_path / "novo.db"

    resultado = preparar_banco_para_operacao(caminho)

    assert resultado.banco_novo
    assert resultado.caminho_backup is None
    assert consultar_versao(caminho) == schema.VERSAO_ESQUEMA
    assert backups_criados(caminho) == []


def test_banco_atualizado_nao_cria_backup_desnecessario(tmp_path) -> None:
    caminho = tmp_path / "atual.db"
    schema.criar_tabelas(caminho)

    resultado = preparar_banco_para_operacao(caminho)

    assert not resultado.banco_novo
    assert resultado.versao_inicial == schema.VERSAO_ESQUEMA
    assert resultado.caminho_backup is None
    assert backups_criados(caminho) == []


def test_banco_legado_em_wal_e_migrado_apos_backup_verificado(
    tmp_path,
) -> None:
    caminho = tmp_path / "legado.db"
    preparar_banco_legado(caminho, wal=True)

    resultado = preparar_banco_para_operacao(caminho)

    assert resultado.versao_inicial == 1
    assert resultado.versao_final == schema.VERSAO_ESQUEMA
    assert resultado.caminho_backup is not None
    assert resultado.caminho_backup.exists()
    assert consultar_versao(caminho) == schema.VERSAO_ESQUEMA
    conexao = conectar(caminho)
    try:
        assert conexao.execute(
            "SELECT nome FROM produtos WHERE codigo = '10'"
        ).fetchone()[0] == "Produto legado"
    finally:
        conexao.close()

    backup = sqlite3.connect(resultado.caminho_backup)
    try:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
        produto = backup.execute(
            "SELECT codigo, nome FROM produtos"
        ).fetchone()
        assert produto == ("10", "Produto legado")
    finally:
        backup.close()


def test_backups_recebem_nomes_unicos_e_nao_sobrescrevem(tmp_path) -> None:
    caminho = tmp_path / "legado_unico.db"
    preparar_banco_legado(caminho)

    primeiro = inicializacao_service._criar_backup_pre_migracao(caminho, 1)
    segundo = inicializacao_service._criar_backup_pre_migracao(caminho, 1)

    assert primeiro != segundo
    assert primeiro.exists()
    assert segundo.exists()
    assert len(backups_criados(caminho)) == 2


def test_falha_de_backup_interrompe_sem_modificar_original(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_backup.db"
    preparar_banco_legado(caminho)
    monkeypatch.setattr(
        inicializacao_service,
        "_executar_backup_sqlite",
        lambda origem, destino: (_ for _ in ()).throw(
            OSError("destino indisponível")
        ),
    )

    with pytest.raises(BackupPreMigracaoError, match="não foi alterado"):
        preparar_banco_para_operacao(caminho)

    assert consultar_versao(caminho) == 1
    assert backups_criados(caminho) == []


def test_falha_de_integridade_interrompe_e_remove_copia_invalida(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_integridade.db"
    preparar_banco_legado(caminho)
    monkeypatch.setattr(
        inicializacao_service,
        "_verificar_integridade_backup",
        lambda backup: (_ for _ in ()).throw(
            sqlite3.DatabaseError("integridade inválida")
        ),
    )

    with pytest.raises(BackupPreMigracaoError):
        preparar_banco_para_operacao(caminho)

    assert consultar_versao(caminho) == 1
    assert backups_criados(caminho) == []


def test_falha_de_migracao_preserva_original_e_backup(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_migracao.db"
    preparar_banco_legado(caminho)
    monkeypatch.setattr(
        inicializacao_service,
        "criar_tabelas",
        lambda caminho_banco: (_ for _ in ()).throw(
            sqlite3.OperationalError("falha DDL")
        ),
    )

    with pytest.raises(MigracaoBancoError, match="backup.*preservado"):
        preparar_banco_para_operacao(caminho)

    assert consultar_versao(caminho) == 1
    assert len(backups_criados(caminho)) == 1


def test_versao_futura_e_recusada_sem_backup_ou_alteracao(tmp_path) -> None:
    caminho = tmp_path / "futuro.db"
    schema.criar_tabelas(caminho)
    versao_futura = schema.VERSAO_ESQUEMA + 1
    conexao = conectar(caminho)
    try:
        conexao.execute(f"PRAGMA user_version = {versao_futura}")
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(VersaoBancoFuturaError, match="mais nova"):
        preparar_banco_para_operacao(caminho)

    assert consultar_versao(caminho) == versao_futura
    assert backups_criados(caminho) == []
