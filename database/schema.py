from database.conexao import CAMINHO_BANCO, conectar


def criar_tabelas(caminho_banco=CAMINHO_BANCO) -> None:
    """
    Cria as tabelas necessárias caso ainda não existam.
    """

    # Centraliza a definição da tabela para o banco principal ou de testes.
    comando_produtos = """
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

    conexao = conectar(caminho_banco)

    # Garante que a conexão seja fechada mesmo se a criação falhar.
    try:
        conexao.execute(comando_produtos)
        conexao.commit()
    finally:
        conexao.close()
