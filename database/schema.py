from database.conexao import CAMINHO_BANCO, conectar


VERSAO_ESQUEMA = 1

_COMANDO_CRIAR_PRODUTOS = """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    forma_venda TEXT NOT NULL
        CHECK (forma_venda IN ('PESO', 'UNIDADE')),
    preco_venda_centavos INTEGER NOT NULL
        CHECK (preco_venda_centavos > 0),
    origem TEXT NOT NULL
        CHECK (origem IN ('COMPRADO', 'PRODUZIDO')),
    ativo INTEGER NOT NULL DEFAULT 1
        CHECK (ativo IN (0, 1)),
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_COMANDO_CRIAR_VENDAS = """
CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_centavos INTEGER NOT NULL
        CHECK (
            typeof(total_centavos) = 'integer'
            AND total_centavos > 0
        ),
    registrada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        CHECK (
            typeof(registrada_em) = 'text'
            AND length(trim(registrada_em)) > 0
        )
);
"""


def criar_tabelas(caminho_banco=CAMINHO_BANCO) -> None:
    """
    Evolui o banco até a versão de esquema suportada pela aplicação.
    """
    conexao = conectar(caminho_banco)

    try:
        versao_atual = conexao.execute("PRAGMA user_version").fetchone()[0]

        if versao_atual > VERSAO_ESQUEMA:
            raise RuntimeError(
                "O banco usa uma versão de esquema mais nova que a aplicação."
            )

        if versao_atual == VERSAO_ESQUEMA:
            return

        # DDL também participa da transação no SQLite. Se qualquer comando
        # falhar, nem as tabelas anteriores nem a nova versão são confirmadas.
        conexao.execute("BEGIN IMMEDIATE")
        conexao.execute(_COMANDO_CRIAR_PRODUTOS)
        conexao.execute(_COMANDO_CRIAR_VENDAS)
        conexao.execute(f"PRAGMA user_version = {VERSAO_ESQUEMA}")
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()
