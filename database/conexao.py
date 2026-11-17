import os
from pathlib import Path
import sqlite3
import sys


NOME_DIRETORIO_APLICATIVO = "Sistema-PDV"
NOME_ARQUIVO_BANCO = "sistema_acougue.db"
DIRETORIO_RAIZ_DESENVOLVIMENTO = Path(__file__).resolve().parent.parent


def execucao_empacotada() -> bool:
    """Detecta o processo congelado pelo PyInstaller, sem usar o CWD."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resolver_diretorio_dados() -> Path:
    """Resolve a raiz persistente sem misturá-la aos arquivos do executável."""
    if not execucao_empacotada():
        return DIRETORIO_RAIZ_DESENVOLVIMENTO / "data"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data or not local_app_data.strip():
        raise RuntimeError(
            "LOCALAPPDATA não está disponível para armazenar os dados do PDV."
        )
    diretorio_usuario = Path(local_app_data.strip()).expanduser()
    if not diretorio_usuario.is_absolute():
        raise RuntimeError("LOCALAPPDATA deve indicar um caminho absoluto.")
    return diretorio_usuario / NOME_DIRETORIO_APLICATIVO / "data"


def resolver_caminho_banco() -> Path:
    return resolver_diretorio_dados() / NOME_ARQUIVO_BANCO


DIRETORIO_BANCO = resolver_diretorio_dados()
CAMINHO_BANCO = resolver_caminho_banco()


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
