from datetime import UTC, datetime
from pathlib import Path

from database.conexao import CAMINHO_BANCO, conectar
from database.schema import VERSAO_ESQUEMA
from models.autorizacao_pontual import CapacidadeAutorizacao
from models.cancelamento_venda import CancelamentoVenda
from models.sessao_usuario import SessaoUsuario
from repositories.venda_repository import (
    buscar_estado_cancelamento_venda,
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


class CancelamentoVendaNaoPersistidoError(RuntimeError):
    """A leitura posterior confirmou que a venda continua ativa."""

    def __init__(self, venda_id: int) -> None:
        self.venda_id = venda_id
        super().__init__(
            f"O cancelamento da venda {venda_id} não foi persistido."
        )


class CancelamentoVendaIncertoError(RuntimeError):
    """Não há correlação persistente suficiente para atribuir o resultado."""

    def __init__(
        self,
        venda_id: int,
        *,
        estado_observado: str | None = None,
        metadados_correspondem: bool | None = None,
    ) -> None:
        self.venda_id = venda_id
        self.estado_observado = estado_observado
        self.metadados_correspondem = metadados_correspondem
        super().__init__(
            "Não foi possível confirmar o resultado do cancelamento da venda "
            f"{venda_id}. Consulte o Histórico antes de qualquer nova ação."
        )


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
    resultado = CancelamentoVenda(
        venda_id=venda_id,
        motivo=motivo_normalizado,
        cancelada_em=cancelada_em,
        identidade_autorizador=identidade_autorizador,
    )
    conexao = None
    try:
        conexao = conectar(caminho_banco)
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

        try:
            conexao.commit()
        except Exception as erro_commit:
            _rollback_seguro(conexao)
            _fechar_conexao(conexao)
            conexao = None
            return _reconciliar_apos_falha_commit(
                resultado,
                cancelada_em_sqlite,
                caminho_banco,
                erro_commit,
            )
        return resultado
    except Exception:
        if conexao is not None:
            _rollback_seguro(conexao)
        raise
    finally:
        if conexao is not None:
            _fechar_conexao(conexao)


def _reconciliar_apos_falha_commit(
    cancelamento: CancelamentoVenda,
    cancelada_em_sqlite: str,
    caminho_banco: str | Path,
    erro_original: Exception,
) -> CancelamentoVenda:
    conexao_verificacao = None
    try:
        conexao_verificacao = conectar(caminho_banco)
        estado = buscar_estado_cancelamento_venda(
            conexao_verificacao,
            cancelamento.venda_id,
        )
    except Exception as erro_verificacao:
        raise CancelamentoVendaIncertoError(
            cancelamento.venda_id,
        ) from erro_verificacao
    finally:
        if conexao_verificacao is not None:
            _fechar_conexao(conexao_verificacao)

    if estado is not None and estado[0] == "ATIVA":
        raise CancelamentoVendaNaoPersistidoError(
            cancelamento.venda_id,
        ) from erro_original

    if estado is None:
        raise CancelamentoVendaIncertoError(
            cancelamento.venda_id,
        ) from erro_original

    metadados_correspondem = estado[1:] == (
        cancelamento.motivo,
        cancelada_em_sqlite,
        cancelamento.identidade_autorizador,
    )
    # Mesmo metadados iguais não identificam a tentativa sem um UUID
    # persistente. A leitura comprova o estado comercial, não sua autoria.
    raise CancelamentoVendaIncertoError(
        cancelamento.venda_id,
        estado_observado=estado[0],
        metadados_correspondem=metadados_correspondem,
    ) from erro_original


def _rollback_seguro(conexao) -> None:
    try:
        conexao.rollback()
    except Exception:
        # A falha original do commit conserva precedência causal.
        pass


def _fechar_conexao(conexao) -> None:
    try:
        conexao.close()
    except Exception:
        pass


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
