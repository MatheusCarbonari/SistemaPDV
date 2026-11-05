from datetime import UTC, datetime
from pathlib import Path

from database.conexao import CAMINHO_BANCO, conectar
from database.schema import VERSAO_ESQUEMA
from models.autorizacao_pontual import CapacidadeAutorizacao
from models.cancelamento_venda import CancelamentoVenda
from models.sessao_usuario import SessaoUsuario
from repositories.venda_repository import (
    buscar_status_venda,
    cancelar_venda_ativa,
)
from services.autorizacao_pontual_service import (
    GERENCIADOR_AUTORIZACOES,
    OPERACAO_CANCELAR_VENDA,
    GerenciadorAutorizacoesPontuais,
)


FORMATO_DATA_SQLITE = "%Y-%m-%d %H:%M:%S"


class VendaNaoEncontradaError(LookupError):
    pass


class VendaJaCanceladaError(RuntimeError):
    pass


def cancelar_venda(
    venda_id: int,
    motivo: str,
    capacidade: CapacidadeAutorizacao,
    sessao_solicitante: SessaoUsuario,
    caminho_banco: str | Path = CAMINHO_BANCO,
    *,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
) -> CancelamentoVenda:
    """Cancela uma venda ativa sem alterar seus dados comerciais."""
    _validar_venda_id(venda_id)
    motivo_normalizado = _normalizar_motivo(motivo)
    if type(gerenciador_autorizacoes) is not GerenciadorAutorizacoesPontuais:
        raise TypeError(
            "O cancelamento exige um gerenciador de autorizações confiável."
        )
    identidade_autorizador = gerenciador_autorizacoes.consumir(
        capacidade,
        sessao_solicitante,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        caminho_banco,
    )

    cancelada_em = _agora_utc()
    cancelada_em_sqlite = cancelada_em.strftime(FORMATO_DATA_SQLITE)
    conexao = conectar(caminho_banco)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao != VERSAO_ESQUEMA:
            raise RuntimeError(
                "O cancelamento exige o esquema SQLite na versão "
                f"{VERSAO_ESQUEMA}."
            )

        conexao.execute("BEGIN IMMEDIATE")
        cancelou = cancelar_venda_ativa(
            conexao,
            venda_id,
            motivo_normalizado,
            cancelada_em_sqlite,
            identidade_autorizador,
        )
        if not cancelou:
            status = buscar_status_venda(conexao, venda_id)
            if status is None:
                raise VendaNaoEncontradaError(
                    f"A venda {venda_id} não foi encontrada."
                )
            raise VendaJaCanceladaError(
                f"A venda {venda_id} já está cancelada."
            )

        conexao.commit()
        return CancelamentoVenda(
            venda_id=venda_id,
            motivo=motivo_normalizado,
            cancelada_em=cancelada_em,
            identidade_autorizador=identidade_autorizador,
        )
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _validar_venda_id(venda_id: int) -> None:
    if not isinstance(venda_id, int) or isinstance(venda_id, bool):
        raise TypeError("O ID da venda deve ser um número inteiro.")
    if venda_id <= 0:
        raise ValueError("O ID da venda deve ser positivo.")


def _normalizar_motivo(motivo: str) -> str:
    if not isinstance(motivo, str):
        raise TypeError("O motivo do cancelamento deve ser textual.")
    normalizado = motivo.strip()
    if not normalizado:
        raise ValueError("O motivo do cancelamento não pode estar vazio.")
    return normalizado


def _agora_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
