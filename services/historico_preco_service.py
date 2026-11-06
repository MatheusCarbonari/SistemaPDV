from calendar import monthrange
from datetime import UTC, datetime

from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from repositories.historico_preco_repository import (
    listar_historico_precos_repository,
)
from repositories.produto_repository import buscar_produto_banco_pelo_id
from services.autenticacao_service import (
    GERENCIADOR_SESSOES,
    GerenciadorSessoes,
    autorizar_sessao,
)


def consultar_historico_precos(
    sessao_administrativa: SessaoUsuario,
    produto_id,
    caminho_banco=CAMINHO_BANCO,
    *,
    meses: int | None = 12,
    agora: datetime | None = None,
    gerenciador_sessoes: GerenciadorSessoes = GERENCIADOR_SESSOES,
):
    autorizar_sessao(
        sessao_administrativa,
        ("ADMINISTRADOR",),
        caminho_banco,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    if not isinstance(produto_id, int) or isinstance(produto_id, bool):
        raise TypeError("O ID do produto deve ser um inteiro.")
    if produto_id <= 0:
        raise ValueError("O ID do produto deve ser positivo.")
    if meses is not None and (
        not isinstance(meses, int) or isinstance(meses, bool) or meses <= 0
    ):
        raise ValueError("O período em meses deve ser positivo.")

    if buscar_produto_banco_pelo_id(produto_id, caminho_banco) is None:
        raise LookupError("O produto não foi encontrado.")

    desde_utc = None
    if meses is not None:
        instante = agora or datetime.now(UTC)
        if not isinstance(instante, datetime) or instante.tzinfo is None:
            raise ValueError("O instante de referência deve possuir fuso horário.")
        desde_utc = _subtrair_meses(instante.astimezone(UTC), meses)

    return listar_historico_precos_repository(
        produto_id,
        desde_utc,
        caminho_banco,
    )


def _subtrair_meses(instante: datetime, meses: int) -> datetime:
    indice_mes = instante.year * 12 + instante.month - 1 - meses
    ano, indice = divmod(indice_mes, 12)
    mes = indice + 1
    dia = min(instante.day, monthrange(ano, mes)[1])
    return instante.replace(year=ano, month=mes, day=dia)
