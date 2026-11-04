from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from database.conexao import CAMINHO_BANCO
from models.venda_resumo import VendaResumo
from repositories.venda_repository import (
    buscar_resumo_venda_por_id,
    listar_resumos_vendas_no_intervalo,
)


FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")
FORMATO_DATA_SQLITE = "%Y-%m-%d %H:%M:%S"


def buscar_venda_resumida_por_id(
    venda_id: int,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> VendaResumo | None:
    """Retorna o resumo da venda ou None quando o ID não existe."""
    _validar_venda_id(venda_id)
    return buscar_resumo_venda_por_id(venda_id, caminho_banco)


def listar_vendas_resumidas_por_data(
    data_local: date,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> tuple[VendaResumo, ...]:
    """Lista o dia civil de São Paulo, da venda mais recente à mais antiga."""
    if not isinstance(data_local, date) or isinstance(data_local, datetime):
        raise TypeError("A data deve ser uma instância de datetime.date.")

    inicio_local = datetime.combine(
        data_local,
        time.min,
        tzinfo=FUSO_SAO_PAULO,
    )
    fim_local = datetime.combine(
        date.fromordinal(data_local.toordinal() + 1),
        time.min,
        tzinfo=FUSO_SAO_PAULO,
    )
    inicio_utc = inicio_local.astimezone(UTC).strftime(FORMATO_DATA_SQLITE)
    fim_utc = fim_local.astimezone(UTC).strftime(FORMATO_DATA_SQLITE)
    return listar_resumos_vendas_no_intervalo(
        inicio_utc,
        fim_utc,
        caminho_banco,
    )


def _validar_venda_id(venda_id: int) -> None:
    if not isinstance(venda_id, int) or isinstance(venda_id, bool):
        raise TypeError("O ID da venda deve ser um número inteiro.")
    if venda_id <= 0:
        raise ValueError("O ID da venda deve ser positivo.")
