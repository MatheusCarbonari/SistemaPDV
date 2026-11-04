from pathlib import Path

from database.conexao import CAMINHO_BANCO, conectar
from database.schema import VERSAO_ESQUEMA
from models.venda_confirmada import VendaConfirmada
from repositories.venda_repository import inserir_venda_confirmada
from services.confirmacao_venda_service import validar_confirmacao_venda


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
