import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from database.conexao import CAMINHO_BANCO, conectar
from models.item_venda import DESCRICAO_DIVERSOS, ItemVenda
from models.pagamento import Pagamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_confirmada import VendaConfirmada
from models.venda_detalhada import (
    ItemVendaDetalhado,
    VendaDetalhada,
)
from models.venda_resumo import VendaResumo
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


def buscar_resumo_venda_por_id(
    venda_id: int,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> VendaResumo | None:
    conexao = conectar(caminho_banco)
    try:
        venda = conexao.execute(
            """
            SELECT
                id,
                total_centavos,
                registrada_em,
                status,
                motivo_cancelamento,
                cancelada_em,
                autorizador_identidade
            FROM vendas
            WHERE id = ?
            """,
            (venda_id,),
        ).fetchone()
    finally:
        conexao.close()

    return _montar_resumo_venda(venda) if venda is not None else None


def listar_resumos_vendas_no_intervalo(
    inicio_utc: str,
    fim_utc: str,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> tuple[VendaResumo, ...]:
    conexao = conectar(caminho_banco)
    try:
        vendas = conexao.execute(
            """
            SELECT
                id,
                total_centavos,
                registrada_em,
                status,
                motivo_cancelamento,
                cancelada_em,
                autorizador_identidade
            FROM vendas
            WHERE registrada_em >= ? AND registrada_em < ?
            ORDER BY registrada_em DESC, id DESC
            """,
            (inicio_utc, fim_utc),
        ).fetchall()
    finally:
        conexao.close()

    return tuple(_montar_resumo_venda(venda) for venda in vendas)


def buscar_detalhe_venda_por_id(
    venda_id: int,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> VendaDetalhada | None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN")
        venda = conexao.execute(
            """
            SELECT
                id,
                total_centavos,
                registrada_em,
                status,
                motivo_cancelamento,
                cancelada_em,
                autorizador_identidade
            FROM vendas
            WHERE id = ?
            """,
            (venda_id,),
        ).fetchone()
        if venda is None:
            return None

        itens = conexao.execute(
            """
            SELECT
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
            FROM itens_venda
            WHERE venda_id = ?
            ORDER BY posicao ASC
            """,
            (venda_id,),
        ).fetchall()
        pagamentos = conexao.execute(
            """
            SELECT modalidade, valor_centavos
            FROM pagamentos
            WHERE venda_id = ?
            ORDER BY id ASC
            """,
            (venda_id,),
        ).fetchall()

        return VendaDetalhada(
            resumo=_montar_resumo_venda(venda),
            itens=tuple(_montar_item_detalhado(item) for item in itens),
            pagamentos=tuple(
                Pagamento(
                    modalidade=pagamento["modalidade"],
                    valor_centavos=pagamento["valor_centavos"],
                )
                for pagamento in pagamentos
            ),
        )
    finally:
        if conexao.in_transaction:
            conexao.rollback()
        conexao.close()


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


def cancelar_venda_ativa(
    conexao: sqlite3.Connection,
    venda_id: int,
    motivo: str,
    cancelada_em: str,
    autorizador_identidade: str,
) -> bool:
    cursor = conexao.execute(
        """
        UPDATE vendas
        SET
            status = 'CANCELADA',
            motivo_cancelamento = ?,
            cancelada_em = ?,
            autorizador_identidade = ?
        WHERE id = ? AND status = 'ATIVA'
        """,
        (
            motivo,
            cancelada_em,
            autorizador_identidade,
            venda_id,
        ),
    )
    return cursor.rowcount == 1


def buscar_status_venda(
    conexao: sqlite3.Connection,
    venda_id: int,
) -> str | None:
    venda = conexao.execute(
        "SELECT status FROM vendas WHERE id = ?",
        (venda_id,),
    ).fetchone()
    return venda["status"] if venda is not None else None


def buscar_estado_cancelamento_venda(
    conexao: sqlite3.Connection,
    venda_id: int,
) -> tuple[str, str | None, str | None, str | None] | None:
    """Lê o estado persistido usado somente para reconciliação."""
    venda = conexao.execute(
        """
        SELECT
            status,
            motivo_cancelamento,
            cancelada_em,
            autorizador_identidade
        FROM vendas
        WHERE id = ?
        """,
        (venda_id,),
    ).fetchone()
    return tuple(venda) if venda is not None else None


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


def _montar_resumo_venda(venda) -> VendaResumo:
    registrada_em = datetime.fromisoformat(venda["registrada_em"])
    if registrada_em.tzinfo is None:
        registrada_em = registrada_em.replace(tzinfo=UTC)
    else:
        registrada_em = registrada_em.astimezone(UTC)

    cancelada_em = None
    if venda["cancelada_em"] is not None:
        cancelada_em = datetime.fromisoformat(venda["cancelada_em"])
        if cancelada_em.tzinfo is None:
            cancelada_em = cancelada_em.replace(tzinfo=UTC)
        else:
            cancelada_em = cancelada_em.astimezone(UTC)

    return VendaResumo(
        venda_id=venda["id"],
        total_centavos=venda["total_centavos"],
        registrada_em=registrada_em,
        status=venda["status"],
        motivo_cancelamento=venda["motivo_cancelamento"],
        cancelada_em=cancelada_em,
        autorizador_identidade=venda["autorizador_identidade"],
    )


def _montar_item_detalhado(item) -> ItemVendaDetalhado:
    produto = None
    if item["tipo_item"] == "PRODUTO":
        produto = ProdutoSnapshot(
            produto_id=item["produto_id"],
            codigo=item["codigo_snapshot"],
            nome=item["nome_snapshot"],
            forma_venda=item["forma_venda_snapshot"],
            preco_referencia_centavos=item["preco_referencia_centavos"],
        )

    quantidade = (
        Decimal(item["quantidade_decimal"])
        if item["quantidade_decimal"] is not None
        else None
    )
    item_venda = ItemVenda(
        origem=item["origem"],
        subtotal_centavos=item["subtotal_centavos"],
        origem_quantidade=item["origem_quantidade"],
        produto=produto,
        codigo_barras=item["codigo_barras"],
        quantidade=quantidade,
        tipo_item=item["tipo_item"],
    )
    return ItemVendaDetalhado(
        posicao=item["posicao"],
        item=item_venda,
    )
