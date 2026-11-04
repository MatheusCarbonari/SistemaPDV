import sqlite3

from models.item_venda import DESCRICAO_DIVERSOS, ItemVenda
from models.venda_confirmada import VendaConfirmada
from services.venda_em_andamento_service import calcular_total


def inserir_venda_confirmada(
    conexao: sqlite3.Connection,
    venda_confirmada: VendaConfirmada,
) -> int:
    """Insere toda a venda usando a transação controlada pelo chamador."""
    cursor = conexao.execute(
        "INSERT INTO vendas (total_centavos) VALUES (?)",
        (calcular_total(venda_confirmada.venda),),
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
