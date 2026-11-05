from database.conexao import CAMINHO_BANCO, conectar


VERSAO_ESQUEMA = 9

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

_COMANDO_CRIAR_ITENS_VENDA = """
CREATE TABLE IF NOT EXISTS itens_venda (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER NOT NULL,
    posicao INTEGER NOT NULL
        CHECK (typeof(posicao) = 'integer' AND posicao >= 0),
    produto_id INTEGER,
    codigo_snapshot TEXT,
    nome_snapshot TEXT,
    forma_venda_snapshot TEXT,
    preco_referencia_centavos INTEGER,
    tipo_item TEXT
        CHECK (tipo_item IN ('PRODUTO', 'DIVERSOS') OR tipo_item IS NULL),
    origem TEXT NOT NULL
        CHECK (origem IN ('ETIQUETA', 'MANUAL')),
    origem_quantidade TEXT NOT NULL
        CHECK (
            origem_quantidade IN (
                'INFORMADA',
                'ESTIMADA',
                'NAO_INFORMADA'
            )
        ),
    quantidade_decimal TEXT,
    codigo_barras TEXT,
    subtotal_centavos INTEGER NOT NULL
        CHECK (
            typeof(subtotal_centavos) = 'integer'
            AND subtotal_centavos >= 0
        ),
    FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE RESTRICT,
    FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT,
    UNIQUE (venda_id, posicao),
    CHECK (
        (
            tipo_item = 'PRODUTO'
            AND typeof(codigo_snapshot) = 'text'
            AND length(trim(codigo_snapshot)) > 0
            AND typeof(nome_snapshot) = 'text'
            AND length(trim(nome_snapshot)) > 0
            AND typeof(forma_venda_snapshot) = 'text'
            AND forma_venda_snapshot IN ('PESO', 'UNIDADE')
            AND typeof(preco_referencia_centavos) = 'integer'
            AND preco_referencia_centavos > 0
        )
        OR (
            tipo_item = 'DIVERSOS'
            AND produto_id IS NULL
            AND codigo_snapshot IS NULL
            AND typeof(nome_snapshot) = 'text'
            AND nome_snapshot = 'Diversos'
            AND forma_venda_snapshot IS NULL
            AND preco_referencia_centavos IS NULL
        )
        OR (
            tipo_item IS NULL
            AND produto_id IS NULL
            AND codigo_snapshot IS NULL
            AND nome_snapshot IS NULL
            AND forma_venda_snapshot IS NULL
            AND preco_referencia_centavos IS NULL
        )
    ),
    CHECK (
        (
            quantidade_decimal IS NULL
            AND origem_quantidade = 'NAO_INFORMADA'
        )
        OR (
            typeof(quantidade_decimal) = 'text'
            AND length(quantidade_decimal) > 0
            AND quantidade_decimal NOT GLOB '*[^0-9.]*'
            AND quantidade_decimal NOT GLOB '.*'
            AND quantidade_decimal NOT GLOB '*.'
            AND quantidade_decimal NOT GLOB '*.*.*'
            AND CAST(quantidade_decimal AS NUMERIC) > 0
            AND origem_quantidade IN ('INFORMADA', 'ESTIMADA')
        )
    ),
    CHECK (
        (
            origem = 'ETIQUETA'
            AND typeof(codigo_barras) = 'text'
            AND length(codigo_barras) > 0
        )
        OR (origem = 'MANUAL' AND codigo_barras IS NULL)
    )
);
"""

_COMANDO_CRIAR_PAGAMENTOS = """
CREATE TABLE IF NOT EXISTS pagamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER NOT NULL,
    modalidade TEXT NOT NULL
        CHECK (modalidade IN ('DINHEIRO', 'CREDITO', 'DEBITO', 'PIX')),
    valor_centavos INTEGER NOT NULL
        CHECK (
            typeof(valor_centavos) = 'integer'
            AND valor_centavos > 0
        ),
    FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE RESTRICT
);
"""

_COMANDO_ADICIONAR_IDENTIFICADOR_TENTATIVA = """
ALTER TABLE vendas
ADD COLUMN identificador_tentativa TEXT
    CHECK (
        identificador_tentativa IS NULL
        OR (
            typeof(identificador_tentativa) = 'text'
            AND length(identificador_tentativa) = 36
        )
    );
"""

_COMANDO_CRIAR_INDICE_TENTATIVA = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_vendas_identificador_tentativa
ON vendas (identificador_tentativa);
"""

_COMANDO_CRIAR_INDICE_HISTORICO_VENDAS = """
CREATE INDEX IF NOT EXISTS ix_vendas_registrada_em_id
ON vendas (registrada_em DESC, id DESC);
"""

_COMANDO_ADICIONAR_MOTIVO_CANCELAMENTO = """
ALTER TABLE vendas
ADD COLUMN motivo_cancelamento TEXT
    CHECK (
        motivo_cancelamento IS NULL
        OR (
            typeof(motivo_cancelamento) = 'text'
            AND length(trim(motivo_cancelamento)) > 0
        )
    );
"""

_COMANDO_ADICIONAR_DATA_CANCELAMENTO = """
ALTER TABLE vendas
ADD COLUMN cancelada_em TEXT
    CHECK (
        cancelada_em IS NULL
        OR (
            typeof(cancelada_em) = 'text'
            AND length(trim(cancelada_em)) > 0
        )
    );
"""

_COMANDO_ADICIONAR_AUTORIZADOR_CANCELAMENTO = """
ALTER TABLE vendas
ADD COLUMN autorizador_identidade TEXT
    CHECK (
        autorizador_identidade IS NULL
        OR (
            typeof(autorizador_identidade) = 'text'
            AND length(trim(autorizador_identidade)) > 0
        )
    );
"""

_COMANDO_ADICIONAR_STATUS_VENDA = """
ALTER TABLE vendas
ADD COLUMN status TEXT NOT NULL DEFAULT 'ATIVA'
    CHECK (
        (
            status = 'ATIVA'
            AND motivo_cancelamento IS NULL
            AND cancelada_em IS NULL
            AND autorizador_identidade IS NULL
        )
        OR (
            status = 'CANCELADA'
            AND typeof(motivo_cancelamento) = 'text'
            AND length(trim(motivo_cancelamento)) > 0
            AND typeof(cancelada_em) = 'text'
            AND length(trim(cancelada_em)) > 0
            AND typeof(autorizador_identidade) = 'text'
            AND length(trim(autorizador_identidade)) > 0
        )
    );
"""

_COMANDO_CRIAR_HISTORICO_PRECOS = """
CREATE TABLE IF NOT EXISTS historico_precos_produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    preco_anterior_centavos INTEGER NOT NULL
        CHECK (
            typeof(preco_anterior_centavos) = 'integer'
            AND preco_anterior_centavos > 0
        ),
    preco_novo_centavos INTEGER NOT NULL
        CHECK (
            typeof(preco_novo_centavos) = 'integer'
            AND preco_novo_centavos > 0
        ),
    alterado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        CHECK (
            typeof(alterado_em) = 'text'
            AND length(trim(alterado_em)) > 0
        ),
    FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT,
    CHECK (preco_anterior_centavos <> preco_novo_centavos)
);
"""

_COMANDO_CRIAR_INDICE_HISTORICO_PRECOS = """
CREATE INDEX IF NOT EXISTS ix_historico_precos_produto_data
ON historico_precos_produtos (produto_id, alterado_em DESC, id DESC);
"""

_COMANDO_CRIAR_USUARIOS = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identificacao_acesso TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (
            typeof(identificacao_acesso) = 'text'
            AND length(trim(identificacao_acesso)) BETWEEN 3 AND 64
        ),
    perfil TEXT NOT NULL
        CHECK (perfil IN ('ADMINISTRADOR', 'CAIXA')),
    senha_hash TEXT NOT NULL
        CHECK (
            typeof(senha_hash) = 'text'
            AND length(trim(senha_hash)) > 0
        ),
    ativo INTEGER NOT NULL DEFAULT 1
        CHECK (ativo IN (0, 1)),
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        CHECK (
            typeof(criado_em) = 'text'
            AND length(trim(criado_em)) > 0
        )
);
"""

_COMANDO_CRIAR_ESTADO_IDENTIDADE = """
CREATE TABLE IF NOT EXISTS estado_identidade (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    administrador_inicial_id INTEGER UNIQUE,
    configurado_em TEXT,
    FOREIGN KEY (administrador_inicial_id)
        REFERENCES usuarios(id) ON DELETE RESTRICT,
    CHECK (
        (
            administrador_inicial_id IS NULL
            AND configurado_em IS NULL
        )
        OR (
            typeof(administrador_inicial_id) = 'integer'
            AND typeof(configurado_em) = 'text'
            AND length(trim(configurado_em)) > 0
        )
    )
);
"""

_COMANDO_INICIALIZAR_ESTADO_IDENTIDADE = """
INSERT INTO estado_identidade (
    id,
    administrador_inicial_id,
    configurado_em
)
VALUES (1, NULL, NULL);
"""

_COMANDO_CRIAR_CODIGOS_RECUPERACAO = """
CREATE TABLE IF NOT EXISTS codigos_recuperacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    conjunto_id TEXT NOT NULL
        CHECK (
            typeof(conjunto_id) = 'text'
            AND length(conjunto_id) = 36
        ),
    verificador TEXT NOT NULL UNIQUE
        CHECK (
            typeof(verificador) = 'text'
            AND length(verificador) = 64
            AND verificador NOT GLOB '*[^0-9a-f]*'
        ),
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        CHECK (
            typeof(criado_em) = 'text'
            AND length(trim(criado_em)) > 0
        ),
    consumido_em TEXT,
    revogado_em TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE RESTRICT,
    CHECK (
        consumido_em IS NULL
        OR (
            typeof(consumido_em) = 'text'
            AND length(trim(consumido_em)) > 0
        )
    ),
    CHECK (
        revogado_em IS NULL
        OR (
            typeof(revogado_em) = 'text'
            AND length(trim(revogado_em)) > 0
        )
    ),
    CHECK (consumido_em IS NULL OR revogado_em IS NULL)
);
"""

_COMANDO_CRIAR_INDICE_CODIGOS_RECUPERACAO = """
CREATE INDEX IF NOT EXISTS ix_codigos_recuperacao_usuario_conjunto
ON codigos_recuperacao (usuario_id, conjunto_id, id);
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

        if versao_atual < 1:
            conexao.execute(_COMANDO_CRIAR_PRODUTOS)
            conexao.execute(_COMANDO_CRIAR_VENDAS)
            versao_atual = 1

        if versao_atual < 2:
            conexao.execute(_COMANDO_CRIAR_ITENS_VENDA)
            versao_atual = 2

        if versao_atual < 3:
            conexao.execute(_COMANDO_CRIAR_PAGAMENTOS)
            versao_atual = 3

        if versao_atual < 4:
            conexao.execute(_COMANDO_ADICIONAR_IDENTIFICADOR_TENTATIVA)
            conexao.execute(_COMANDO_CRIAR_INDICE_TENTATIVA)
            versao_atual = 4

        if versao_atual < 5:
            conexao.execute(_COMANDO_CRIAR_INDICE_HISTORICO_VENDAS)
            versao_atual = 5

        if versao_atual < 6:
            conexao.execute(_COMANDO_ADICIONAR_MOTIVO_CANCELAMENTO)
            conexao.execute(_COMANDO_ADICIONAR_DATA_CANCELAMENTO)
            conexao.execute(_COMANDO_ADICIONAR_AUTORIZADOR_CANCELAMENTO)
            conexao.execute(_COMANDO_ADICIONAR_STATUS_VENDA)
            versao_atual = 6

        if versao_atual < 7:
            conexao.execute(_COMANDO_CRIAR_HISTORICO_PRECOS)
            conexao.execute(_COMANDO_CRIAR_INDICE_HISTORICO_PRECOS)
            versao_atual = 7

        if versao_atual < 8:
            conexao.execute(_COMANDO_CRIAR_USUARIOS)
            conexao.execute(_COMANDO_CRIAR_ESTADO_IDENTIDADE)
            conexao.execute(_COMANDO_INICIALIZAR_ESTADO_IDENTIDADE)
            versao_atual = 8

        if versao_atual < 9:
            conexao.execute(_COMANDO_CRIAR_CODIGOS_RECUPERACAO)
            conexao.execute(_COMANDO_CRIAR_INDICE_CODIGOS_RECUPERACAO)
            versao_atual = 9

        conexao.execute(f"PRAGMA user_version = {versao_atual}")
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()
