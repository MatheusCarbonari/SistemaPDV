import sqlite3

from database.conexao import conectar


def test_conectar_retorna_conexao_sqlite(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_conexão.db"

    conexao = conectar(caminho_banco)

    try:
        assert isinstance(conexao, sqlite3.Connection)

        resultado = conexao.execute("SELECT 1").fetchone()

        assert resultado[0] == 1
    finally:
        conexao.close()