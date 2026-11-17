from pathlib import Path
import sqlite3

from services.contexto_instalacao_service import (
    ContextoInstalacao,
    RAIZ_REPOSITORIO,
    execucao_empacotada,
    obter_contexto_instalacao,
)


NOME_DIRETORIO_APLICATIVO = "Sistema-PDV"
NOME_ARQUIVO_BANCO = "sistema_acougue.db"
DIRETORIO_RAIZ_DESENVOLVIMENTO = RAIZ_REPOSITORIO


def resolver_diretorio_dados(
    contexto: ContextoInstalacao | None = None,
) -> Path:
    """Resolve dados pelo contexto confiável, nunca pelo diretório de trabalho."""
    contexto_efetivo = contexto or obter_contexto_instalacao()
    return contexto_efetivo.caminhos.dados


def resolver_caminho_banco(
    contexto: ContextoInstalacao | None = None,
) -> Path:
    contexto_efetivo = contexto or obter_contexto_instalacao()
    return contexto_efetivo.caminhos.banco


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
