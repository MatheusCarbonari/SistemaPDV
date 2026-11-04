from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from database.conexao import CAMINHO_BANCO, conectar
from database.schema import VERSAO_ESQUEMA
from models.venda_confirmada import VendaConfirmada
from repositories.venda_repository import (
    buscar_venda_por_identificador,
    inserir_venda_confirmada,
    venda_persistida_compativel,
)
from services.confirmacao_venda_service import validar_confirmacao_venda


class IdentificadorTentativaInvalidoError(ValueError):
    pass


class TentativaFechamentoIncompativelError(ValueError):
    pass


class CommitVendaIncertoError(RuntimeError):
    def __init__(self, identificador_tentativa: str) -> None:
        self.identificador_tentativa = identificador_tentativa
        super().__init__(
            "Não foi possível determinar se a venda foi persistida para a "
            f"tentativa {identificador_tentativa}."
        )


def gerar_identificador_tentativa() -> str:
    """Gera o UUID de uma nova tentativa lógica de fechamento."""
    return str(uuid4())


def persistir_venda_confirmada(
    venda_confirmada: VendaConfirmada,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> int:
    """Persiste venda, itens e pagamentos em uma única transação SQLite."""
    if not isinstance(venda_confirmada, VendaConfirmada):
        raise TypeError("A venda deve ser uma VendaConfirmada.")

    validar_confirmacao_venda(
        venda_confirmada.venda,
        venda_confirmada.pagamentos,
    )

    conexao = conectar(caminho_banco)

    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao != VERSAO_ESQUEMA:
            raise RuntimeError(
                "A persistência exige o esquema SQLite na versão "
                f"{VERSAO_ESQUEMA}."
            )

        conexao.execute("BEGIN IMMEDIATE")
        venda_id = inserir_venda_confirmada(conexao, venda_confirmada)
        conexao.commit()
        return venda_id
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def persistir_venda_confirmada_idempotente(
    venda_confirmada: VendaConfirmada,
    identificador_tentativa: str,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> int:
    """Persiste uma tentativa lógica sem duplicá-la em repetições."""
    if not isinstance(venda_confirmada, VendaConfirmada):
        raise TypeError("A venda deve ser uma VendaConfirmada.")

    validar_confirmacao_venda(
        venda_confirmada.venda,
        venda_confirmada.pagamentos,
    )
    identificador = _normalizar_identificador(identificador_tentativa)
    conexao = conectar(caminho_banco)

    try:
        _validar_versao_esquema(conexao)
        venda_existente = buscar_venda_por_identificador(
            conexao,
            identificador,
        )
        if venda_existente is not None:
            return _resolver_venda_existente(
                conexao,
                venda_existente,
                venda_confirmada,
                identificador,
            )

        conexao.execute("BEGIN IMMEDIATE")
        try:
            venda_id = inserir_venda_confirmada(
                conexao,
                venda_confirmada,
                identificador,
            )
        except sqlite3.IntegrityError as erro:
            _rollback_seguro(conexao)
            _fechar_conexao(conexao)
            conexao = None
            return _verificar_apos_falha(
                venda_confirmada,
                identificador,
                caminho_banco,
                erro,
            )

        try:
            conexao.commit()
        except Exception as erro:
            _rollback_seguro(conexao)
            _fechar_conexao(conexao)
            conexao = None
            return _verificar_apos_falha(
                venda_confirmada,
                identificador,
                caminho_banco,
                erro,
            )

        return venda_id
    except Exception:
        if conexao is not None:
            _rollback_seguro(conexao)
        raise
    finally:
        if conexao is not None:
            _fechar_conexao(conexao)


def _normalizar_identificador(identificador_tentativa: str) -> str:
    if not isinstance(identificador_tentativa, str):
        raise IdentificadorTentativaInvalidoError(
            "O identificador da tentativa deve ser um UUID válido."
        )

    try:
        return str(UUID(identificador_tentativa))
    except (ValueError, AttributeError):
        raise IdentificadorTentativaInvalidoError(
            "O identificador da tentativa deve ser um UUID válido."
        ) from None


def _validar_versao_esquema(conexao) -> None:
    versao = conexao.execute("PRAGMA user_version").fetchone()[0]
    if versao != VERSAO_ESQUEMA:
        raise RuntimeError(
            "A persistência exige o esquema SQLite na versão "
            f"{VERSAO_ESQUEMA}."
        )


def _resolver_venda_existente(
    conexao,
    venda_id: int,
    venda_confirmada: VendaConfirmada,
    identificador_tentativa: str,
) -> int:
    if venda_persistida_compativel(conexao, venda_id, venda_confirmada):
        return venda_id

    raise TentativaFechamentoIncompativelError(
        "O identificador da tentativa já pertence a uma venda com dados "
        f"diferentes: {identificador_tentativa}."
    )


def _verificar_apos_falha(
    venda_confirmada: VendaConfirmada,
    identificador_tentativa: str,
    caminho_banco: str | Path,
    erro_original: Exception,
) -> int:
    conexao_verificacao = None
    venda_id = None
    resultado = None
    try:
        conexao_verificacao = conectar(caminho_banco)
        _validar_versao_esquema(conexao_verificacao)
        venda_id = buscar_venda_por_identificador(
            conexao_verificacao,
            identificador_tentativa,
        )
        if venda_id is not None:
            resultado = _resolver_venda_existente(
                conexao_verificacao,
                venda_id,
                venda_confirmada,
                identificador_tentativa,
            )
    except TentativaFechamentoIncompativelError:
        raise
    except Exception as erro_verificacao:
        raise CommitVendaIncertoError(
            identificador_tentativa
        ) from erro_verificacao
    finally:
        if conexao_verificacao is not None:
            _fechar_conexao(conexao_verificacao)

    if venda_id is None:
        raise erro_original

    return resultado


def _rollback_seguro(conexao) -> None:
    try:
        conexao.rollback()
    except sqlite3.Error:
        pass


def _fechar_conexao(conexao) -> None:
    try:
        conexao.close()
    except sqlite3.Error:
        pass
