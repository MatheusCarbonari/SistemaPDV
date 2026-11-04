import sqlite3

from models.item_venda import DESCRICAO_DIVERSOS, ItemVenda
from models.venda_confirmada import VendaConfirmada
from services.venda_em_andamento_service import calcular_total


def inserir_venda_confirmada(
    conexao: sqlite3.Connection,
    venda_confirmada: VendaConfirmada,
    identificador_tentativa: str | None = None,
) -> int:
    """Insere toda a venda usando a transação controlada pelo chamador."""
    cursor = conexao.execute(
        """
        INSERT INTO vendas (total_centavos, identificador_tentativa)
        VALUES (?, ?)
        """,
        (
            calcular_total(venda_confirmada.venda),
            identificador_tentativa,
        ),
    )
    venda_id = cursor.lastrowid

    if venda_id is None:
        raise RuntimeError("O SQLite não retornou o identificador da venda.")

    for posicao, item in enumerate(venda_confirmada.venda.itens):
        _inserir_item(conexao, venda_id, posicao, item)

    for pagamento in venda_confirmada.pagamentos.pagamentos:
        conexao.execute(
            """
            INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
            VALUES (?, ?, ?)
            """,
            (
                venda_id,
                pagamento.modalidade,
                pagamento.valor_centavos,
            ),
        )

    return venda_id


def buscar_venda_por_identificador(
    conexao: sqlite3.Connection,
    identificador_tentativa: str,
) -> int | None:
    venda = conexao.execute(
        """
        SELECT id
        FROM vendas
        WHERE identificador_tentativa = ?
        """,
        (identificador_tentativa,),
    ).fetchone()
    return venda["id"] if venda is not None else None


def venda_persistida_compativel(
    conexao: sqlite3.Connection,
    venda_id: int,
    venda_confirmada: VendaConfirmada,
) -> bool:
    venda = conexao.execute(
        "SELECT total_centavos FROM vendas WHERE id = ?",
        (venda_id,),
    ).fetchone()
    if venda is None:
        return False

    total_esperado = calcular_total(venda_confirmada.venda)
    if venda["total_centavos"] != total_esperado:
        return False

    itens_persistidos = conexao.execute(
        """
        SELECT
            posicao,
            codigo_snapshot,
            nome_snapshot,
            forma_venda_snapshot,
            preco_referencia_centavos,
            tipo_item,
            origem,
            origem_quantidade,
            quantidade_decimal,
            codigo_barras,
            subtotal_centavos
        FROM itens_venda
        WHERE venda_id = ?
        ORDER BY posicao
        """,
        (venda_id,),
    ).fetchall()
    itens_esperados = [
        _assinatura_item(posicao, item)
        for posicao, item in enumerate(venda_confirmada.venda.itens)
    ]
    if [tuple(item) for item in itens_persistidos] != itens_esperados:
        return False

    pagamentos_persistidos = conexao.execute(
        """
        SELECT modalidade, valor_centavos
        FROM pagamentos
        WHERE venda_id = ?
        ORDER BY id
        """,
        (venda_id,),
    ).fetchall()
    pagamentos_esperados = [
        (pagamento.modalidade, pagamento.valor_centavos)
        for pagamento in venda_confirmada.pagamentos.pagamentos
    ]
    return [tuple(pagamento) for pagamento in pagamentos_persistidos] == (
        pagamentos_esperados
    )


def _inserir_item(
    conexao: sqlite3.Connection,
    venda_id: int,
    posicao: int,
    item: ItemVenda,
) -> None:
    produto_id = None
    codigo_snapshot = None
    nome_snapshot = None
    forma_venda_snapshot = None
    preco_referencia_centavos = None

    if item.tipo_item == "PRODUTO":
        snapshot = item.produto
        if snapshot is None:
            raise ValueError("Item PRODUTO exige snapshot comercial.")

        produto_id = _produto_id_existente(conexao, snapshot.produto_id)
        codigo_snapshot = snapshot.codigo
        nome_snapshot = snapshot.nome
        forma_venda_snapshot = snapshot.forma_venda
        preco_referencia_centavos = snapshot.preco_referencia_centavos
    elif item.tipo_item == "DIVERSOS":
        nome_snapshot = DESCRICAO_DIVERSOS

    quantidade_decimal = (
        format(item.quantidade, "f")
        if item.quantidade is not None
        else None
    )

    conexao.execute(
        """
        INSERT INTO itens_venda (
            venda_id,
            posicao,
            produto_id,
            codigo_snapshot,
            nome_snapshot,
            forma_venda_snapshot,
            preco_referencia_centavos,
            tipo_item,
            origem,
            origem_quantidade,
            quantidade_decimal,
            codigo_barras,
            subtotal_centavos
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            venda_id,
            posicao,
            produto_id,
            codigo_snapshot,
            nome_snapshot,
            forma_venda_snapshot,
            preco_referencia_centavos,
            item.tipo_item,
            item.origem,
            item.origem_quantidade,
            quantidade_decimal,
            item.codigo_barras,
            item.subtotal_centavos,
        ),
    )


def _produto_id_existente(
    conexao: sqlite3.Connection,
    produto_id: int | None,
) -> int | None:
    if (
        not isinstance(produto_id, int)
        or isinstance(produto_id, bool)
        or produto_id <= 0
    ):
        return None

    produto = conexao.execute(
        "SELECT 1 FROM produtos WHERE id = ?",
        (produto_id,),
    ).fetchone()
    return produto_id if produto is not None else None


def _assinatura_item(
    posicao: int,
    item: ItemVenda,
) -> tuple:
    codigo_snapshot = None
    nome_snapshot = None
    forma_venda_snapshot = None
    preco_referencia_centavos = None

    if item.tipo_item == "PRODUTO":
        snapshot = item.produto
        if snapshot is None:
            raise ValueError("Item PRODUTO exige snapshot comercial.")

        codigo_snapshot = snapshot.codigo
        nome_snapshot = snapshot.nome
        forma_venda_snapshot = snapshot.forma_venda
        preco_referencia_centavos = snapshot.preco_referencia_centavos
    elif item.tipo_item == "DIVERSOS":
        nome_snapshot = DESCRICAO_DIVERSOS

    quantidade_decimal = (
        format(item.quantidade, "f")
        if item.quantidade is not None
        else None
    )
    return (
        posicao,
        codigo_snapshot,
        nome_snapshot,
        forma_venda_snapshot,
        preco_referencia_centavos,
        item.tipo_item,
        item.origem,
        item.origem_quantidade,
        quantidade_decimal,
        item.codigo_barras,
        item.subtotal_centavos,
    )
