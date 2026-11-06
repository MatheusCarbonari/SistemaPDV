from decimal import Decimal
import sqlite3

import pytest

from database.conexao import conectar
from database.schema import criar_tabelas
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_confirmada import VendaConfirmada
from models.venda_em_andamento import VendaEmAndamento
import services.persistencia_venda_service as persistencia_service
from services.confirmacao_venda_service import confirmar_venda
from services.persistencia_venda_service import persistir_venda_confirmada


@pytest.fixture
def banco_teste(tmp_path):
    caminho_banco = tmp_path / "persistencia_venda.db"
    criar_tabelas(caminho_banco)
    return caminho_banco


def inserir_produto(
    caminho_banco,
    codigo="ATUAL",
    nome="Cadastro atual",
    preco_centavos=9999,
) -> int:
    conexao = conectar(caminho_banco)
    try:
        categoria_id = conexao.execute(
            "INSERT INTO categorias (nome, nome_chave) VALUES (?, ?)",
            ("TESTE", "teste"),
        ).lastrowid
        produto_id = conexao.execute(
            """
            INSERT INTO produtos (
                codigo,
                nome,
                categoria_id,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                nome,
                categoria_id,
                "UNIDADE",
                preco_centavos,
                "COMPRADO",
            ),
        ).lastrowid
        conexao.commit()
        return produto_id
    finally:
        conexao.close()


def criar_item_produto(
    subtotal_centavos: int,
    *,
    produto_id: int | None = None,
    codigo="SNAP",
    nome="Produto no momento da venda",
    preco_centavos=1234,
    quantidade=Decimal("1"),
    origem="MANUAL",
    origem_quantidade="INFORMADA",
    codigo_barras=None,
) -> ItemVenda:
    snapshot = ProdutoSnapshot(
        produto_id=produto_id,
        codigo=codigo,
        nome=nome,
        forma_venda="UNIDADE",
        preco_referencia_centavos=preco_centavos,
    )
    return ItemVenda(
        origem=origem,
        subtotal_centavos=subtotal_centavos,
        origem_quantidade=origem_quantidade,
        produto=snapshot,
        codigo_barras=codigo_barras,
        quantidade=quantidade,
    )


def criar_item_diversos(subtotal_centavos: int) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )


def criar_item_legado(subtotal_centavos: int) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
        tipo_item=None,
    )


def criar_confirmacao(
    itens: tuple[ItemVenda, ...],
    pagamentos: tuple[Pagamento, ...],
) -> VendaConfirmada:
    total = sum(item.subtotal_centavos for item in itens)
    venda = VendaEmAndamento(itens=itens)
    composicao = PagamentosEmAndamento(
        total_venda_centavos=total,
        pagamentos=pagamentos,
    )
    return confirmar_venda(venda, composicao)


def consultar_todos(caminho_banco, consulta, parametros=()):
    conexao = conectar(caminho_banco)
    try:
        return conexao.execute(consulta, parametros).fetchall()
    finally:
        conexao.close()


def test_grava_venda_completa_e_retorna_identificador(banco_teste) -> None:
    produto_id = inserir_produto(banco_teste)
    produto = criar_item_produto(1000, produto_id=produto_id)
    diversos = criar_item_diversos(250)
    confirmacao = criar_confirmacao(
        (produto, diversos),
        (Pagamento("PIX", 700), Pagamento("DINHEIRO", 550)),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    vendas = consultar_todos(
        banco_teste,
        "SELECT id, total_centavos FROM vendas",
    )
    assert [tuple(venda) for venda in vendas] == [(venda_id, 1250)]


def test_associa_itens_e_pagamentos_ao_id_da_venda(banco_teste) -> None:
    confirmacao = criar_confirmacao(
        (criar_item_produto(600), criar_item_diversos(400)),
        (Pagamento("DEBITO", 600), Pagamento("PIX", 400)),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    itens = consultar_todos(
        banco_teste,
        "SELECT DISTINCT venda_id FROM itens_venda",
    )
    pagamentos = consultar_todos(
        banco_teste,
        "SELECT DISTINCT venda_id FROM pagamentos",
    )
    assert [item["venda_id"] for item in itens] == [venda_id]
    assert [pagamento["venda_id"] for pagamento in pagamentos] == [venda_id]


def test_preserva_ordem_itens_repetidos_e_subtotais(banco_teste) -> None:
    item_repetido = criar_item_produto(333)
    ultimo = criar_item_diversos(334)
    confirmacao = criar_confirmacao(
        (item_repetido, item_repetido, ultimo),
        (Pagamento("DINHEIRO", 1000),),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    itens = consultar_todos(
        banco_teste,
        """
        SELECT id, posicao, codigo_snapshot, subtotal_centavos
        FROM itens_venda
        WHERE venda_id = ?
        ORDER BY posicao
        """,
        (venda_id,),
    )
    assert [item["posicao"] for item in itens] == [0, 1, 2]
    assert [item["subtotal_centavos"] for item in itens] == [333, 333, 334]
    assert itens[0]["codigo_snapshot"] == itens[1]["codigo_snapshot"]
    assert itens[0]["id"] != itens[1]["id"]


def test_preserva_snapshot_sem_usar_preco_atual_do_cadastro(
    banco_teste,
) -> None:
    produto_id = inserir_produto(
        banco_teste,
        codigo="NOVO",
        nome="Nome atualizado",
        preco_centavos=9999,
    )
    item = criar_item_produto(
        2468,
        produto_id=produto_id,
        codigo="ANTIGO",
        nome="Nome vendido",
        preco_centavos=1234,
        quantidade=Decimal("2"),
    )
    confirmacao = criar_confirmacao(
        (item,),
        (Pagamento("CREDITO", 2468),),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    salvo = consultar_todos(
        banco_teste,
        """
        SELECT produto_id, codigo_snapshot, nome_snapshot,
               preco_referencia_centavos, subtotal_centavos
        FROM itens_venda
        WHERE venda_id = ?
        """,
        (venda_id,),
    )[0]
    assert tuple(salvo) == (
        produto_id,
        "ANTIGO",
        "Nome vendido",
        1234,
        2468,
    )


def test_persiste_diversos_e_item_legado_com_estados_distintos(
    banco_teste,
) -> None:
    confirmacao = criar_confirmacao(
        (criar_item_diversos(700), criar_item_legado(300)),
        (Pagamento("DINHEIRO", 1000),),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    itens = consultar_todos(
        banco_teste,
        """
        SELECT posicao, tipo_item, produto_id, codigo_snapshot,
               nome_snapshot, forma_venda_snapshot,
               preco_referencia_centavos
        FROM itens_venda
        WHERE venda_id = ?
        ORDER BY posicao
        """,
        (venda_id,),
    )
    assert tuple(itens[0]) == (0, "DIVERSOS", None, None, "Diversos", None, None)
    assert tuple(itens[1]) == (1, None, None, None, None, None, None)


def test_formata_quantidades_decimais_sem_notacao_exponencial(
    banco_teste,
) -> None:
    primeiro = criar_item_produto(500, quantidade=Decimal("1E-7"))
    segundo = criar_item_produto(500, quantidade=Decimal("1000.2300"))
    confirmacao = criar_confirmacao(
        (primeiro, segundo),
        (Pagamento("PIX", 1000),),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    quantidades = consultar_todos(
        banco_teste,
        """
        SELECT quantidade_decimal
        FROM itens_venda
        WHERE venda_id = ?
        ORDER BY posicao
        """,
        (venda_id,),
    )
    assert [linha["quantidade_decimal"] for linha in quantidades] == [
        "0.0000001",
        "1000.2300",
    ]


def test_preserva_ordem_e_modalidades_repetidas(banco_teste) -> None:
    confirmacao = criar_confirmacao(
        (criar_item_produto(1000),),
        (
            Pagamento("PIX", 300),
            Pagamento("PIX", 200),
            Pagamento("DINHEIRO", 500),
        ),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    pagamentos = consultar_todos(
        banco_teste,
        """
        SELECT modalidade, valor_centavos
        FROM pagamentos
        WHERE venda_id = ?
        ORDER BY id
        """,
        (venda_id,),
    )
    assert [tuple(pagamento) for pagamento in pagamentos] == [
        ("PIX", 300),
        ("PIX", 200),
        ("DINHEIRO", 500),
    ]


@pytest.mark.parametrize(
    "confirmacao",
    [
        VendaConfirmada(
            venda=VendaEmAndamento(itens=(criar_item_produto(0),)),
            pagamentos=PagamentosEmAndamento(
                total_venda_centavos=100,
                pagamentos=(Pagamento("PIX", 100),),
            ),
        ),
        VendaConfirmada(
            venda=VendaEmAndamento(itens=(criar_item_produto(1000),)),
            pagamentos=PagamentosEmAndamento(
                total_venda_centavos=900,
                pagamentos=(Pagamento("PIX", 900),),
            ),
        ),
        VendaConfirmada(
            venda=VendaEmAndamento(itens=(criar_item_produto(1000),)),
            pagamentos=PagamentosEmAndamento(
                total_venda_centavos=1000,
                pagamentos=(Pagamento("PIX", 900),),
            ),
        ),
    ],
    ids=["total-zero", "total-incompativel", "pagamento-incompleto"],
)
def test_revalida_invariantes_antes_de_gravar(
    banco_teste,
    confirmacao,
) -> None:
    with pytest.raises(ValueError):
        persistir_venda_confirmada(confirmacao, banco_teste)

    assert consultar_todos(banco_teste, "SELECT * FROM vendas") == []


def test_falha_em_item_reverte_cabecalho_e_todos_os_itens(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_item
            BEFORE INSERT ON itens_venda
            BEGIN
                SELECT RAISE(ABORT, 'falha ao gravar item');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()
    confirmacao = criar_confirmacao(
        (criar_item_produto(1000),),
        (Pagamento("PIX", 1000),),
    )

    with pytest.raises(sqlite3.IntegrityError, match="falha ao gravar item"):
        persistir_venda_confirmada(confirmacao, banco_teste)

    assert consultar_todos(banco_teste, "SELECT * FROM vendas") == []
    assert consultar_todos(banco_teste, "SELECT * FROM itens_venda") == []
    assert consultar_todos(banco_teste, "SELECT * FROM pagamentos") == []


def test_falha_em_pagamento_reverte_venda_e_itens(banco_teste) -> None:
    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_pagamento
            BEFORE INSERT ON pagamentos
            BEGIN
                SELECT RAISE(ABORT, 'falha ao gravar pagamento');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()
    confirmacao = criar_confirmacao(
        (criar_item_produto(1000),),
        (Pagamento("PIX", 1000),),
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="falha ao gravar pagamento",
    ):
        persistir_venda_confirmada(confirmacao, banco_teste)

    assert consultar_todos(banco_teste, "SELECT * FROM vendas") == []
    assert consultar_todos(banco_teste, "SELECT * FROM itens_venda") == []
    assert consultar_todos(banco_teste, "SELECT * FROM pagamentos") == []


def test_usa_somente_produto_id_existente_e_mantem_fk_ativa(
    banco_teste,
) -> None:
    produto_id = inserir_produto(banco_teste)
    com_fk = criar_item_produto(500, produto_id=produto_id)
    id_inexistente = criar_item_produto(250, produto_id=999999)
    id_de_tipo_invalido = criar_item_produto(250, produto_id=True)
    confirmacao = criar_confirmacao(
        (com_fk, id_inexistente, id_de_tipo_invalido),
        (Pagamento("DINHEIRO", 1000),),
    )

    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    conexao = conectar(banco_teste)
    try:
        assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        ids = conexao.execute(
            """
            SELECT produto_id FROM itens_venda
            WHERE venda_id = ? ORDER BY posicao
            """,
            (venda_id,),
        ).fetchall()
        assert [linha["produto_id"] for linha in ids] == [
            produto_id,
            None,
            None,
        ]

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conexao.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    finally:
        conexao.close()


class ConexaoMonitorada(sqlite3.Connection):
    commits_executados = 0
    rollbacks_executados = 0

    def commit(self) -> None:
        self.commits_executados += 1
        super().commit()

    def rollback(self) -> None:
        self.rollbacks_executados += 1
        super().rollback()


def test_realiza_um_unico_commit_apos_todos_os_inserts(
    banco_teste,
    monkeypatch,
) -> None:
    conexao_monitorada = sqlite3.connect(
        banco_teste,
        factory=ConexaoMonitorada,
    )
    conexao_monitorada.row_factory = sqlite3.Row
    conexao_monitorada.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(
        persistencia_service,
        "conectar",
        lambda caminho: conexao_monitorada,
    )
    confirmacao = criar_confirmacao(
        (criar_item_produto(1000),),
        (Pagamento("PIX", 1000),),
    )

    persistir_venda_confirmada(confirmacao, banco_teste)

    assert conexao_monitorada.commits_executados == 1
    assert conexao_monitorada.rollbacks_executados == 0


def test_falha_preserva_registros_anteriores(banco_teste) -> None:
    anterior = criar_confirmacao(
        (criar_item_legado(500),),
        (Pagamento("DINHEIRO", 500),),
    )
    venda_anterior_id = persistir_venda_confirmada(anterior, banco_teste)
    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_nova_venda
            BEFORE INSERT ON pagamentos
            BEGIN
                SELECT RAISE(ABORT, 'falha nova venda');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()
    nova = criar_confirmacao(
        (criar_item_produto(1000),),
        (Pagamento("PIX", 1000),),
    )

    with pytest.raises(sqlite3.IntegrityError, match="falha nova venda"):
        persistir_venda_confirmada(nova, banco_teste)

    vendas = consultar_todos(
        banco_teste,
        "SELECT id, total_centavos FROM vendas ORDER BY id",
    )
    assert [tuple(venda) for venda in vendas] == [(venda_anterior_id, 500)]
    assert len(consultar_todos(banco_teste, "SELECT * FROM itens_venda")) == 1
    assert len(consultar_todos(banco_teste, "SELECT * FROM pagamentos")) == 1


def test_persistencia_nao_modifica_objetos_recebidos(banco_teste) -> None:
    item = criar_item_produto(
        1000,
        produto_id=999999,
        quantidade=Decimal("2.500"),
    )
    pagamento = Pagamento("PIX", 1000)
    confirmacao = criar_confirmacao((item,), (pagamento,))
    venda_original = confirmacao.venda
    itens_originais = confirmacao.venda.itens
    snapshot_original = item.produto
    pagamentos_originais = confirmacao.pagamentos
    registros_pagamento_originais = confirmacao.pagamentos.pagamentos

    persistir_venda_confirmada(confirmacao, banco_teste)

    assert confirmacao.venda is venda_original
    assert confirmacao.venda.itens is itens_originais
    assert confirmacao.venda.itens == (item,)
    assert confirmacao.venda.itens[0].produto is snapshot_original
    assert confirmacao.pagamentos is pagamentos_originais
    assert confirmacao.pagamentos.pagamentos is registros_pagamento_originais
    assert confirmacao.pagamentos.pagamentos == (pagamento,)
