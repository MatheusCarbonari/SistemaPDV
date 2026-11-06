from datetime import UTC, datetime

from database.conexao import CAMINHO_BANCO, conectar
from models.historico_preco_produto import HistoricoPrecoProduto


FORMATO_DATA_SQLITE = "%Y-%m-%d %H:%M:%S"


def listar_historico_precos_repository(
    produto_id: int,
    desde_utc: datetime | None,
    caminho_banco=CAMINHO_BANCO,
) -> tuple[HistoricoPrecoProduto, ...]:
    consulta = """
        SELECT
            id,
            produto_id,
            preco_anterior_centavos,
            preco_novo_centavos,
            alterado_em
        FROM historico_precos_produtos
        WHERE produto_id = ?
    """
    parametros: list[object] = [produto_id]
    if desde_utc is not None:
        consulta += " AND alterado_em >= ?"
        parametros.append(
            desde_utc.astimezone(UTC).strftime(FORMATO_DATA_SQLITE)
        )
    consulta += " ORDER BY alterado_em DESC, id DESC"

    conexao = conectar(caminho_banco)
    try:
        linhas = conexao.execute(consulta, parametros).fetchall()
    finally:
        conexao.close()
    return tuple(_montar_historico(linha) for linha in linhas)


def _montar_historico(linha) -> HistoricoPrecoProduto:
    alterado_em = datetime.strptime(
        linha["alterado_em"],
        FORMATO_DATA_SQLITE,
    ).replace(tzinfo=UTC)
    return HistoricoPrecoProduto(
        id=linha["id"],
        produto_id=linha["produto_id"],
        preco_anterior_centavos=linha["preco_anterior_centavos"],
        preco_novo_centavos=linha["preco_novo_centavos"],
        alterado_em=alterado_em,
    )
