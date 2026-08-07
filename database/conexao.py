from pathlib import Path
import sqlite3


# Define o banco principal a partir da raiz do projeto.
DIRETORIO_RAIZ = Path(__file__).resolve().parent.parent
DIRETORIO_BANCO = DIRETORIO_RAIZ / "data"
CAMINHO_BANCO = DIRETORIO_BANCO / "sistema_acougue.db"


def conectar(caminho_banco=CAMINHO_BANCO) -> sqlite3.Connection:
    """
    Cria e retorna uma conexão com o banco de dados SQLite.
    """
    caminho_banco = Path(caminho_banco)

    caminho_banco.parent.mkdir(parents=True, exist_ok=True)

    conexao = sqlite3.connect(caminho_banco)

    # Permite acessar os resultados das consultas pelo nome das colunas.
    conexao.row_factory = sqlite3.Row

    # Ativa a validação de chaves estrangeiras nesta conexão.
    conexao.execute("PRAGMA foreign_keys = ON")

    return conexao
