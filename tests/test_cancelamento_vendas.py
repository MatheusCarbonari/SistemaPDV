from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from models.cancelamento_venda import (
    CancelamentoVenda,
    ContextoAutorizacaoCancelamento,
)
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_em_andamento import VendaEmAndamento
import services.cancelamento_venda_service as cancelamento_service
from services.cancelamento_venda_service import (
    VendaJaCanceladaError,
    VendaNaoEncontradaError,
    cancelar_venda,
)
from services.confirmacao_venda_service import confirmar_venda
from services.historico_venda_service import (
    FUSO_SAO_PAULO,
    buscar_venda_detalhada_por_id,
    buscar_venda_resumida_por_id,
    listar_vendas_resumidas_por_data,
)
from services.persistencia_venda_service import (
    gerar_identificador_tentativa,
    persistir_venda_confirmada_idempotente,
)


@pytest.fixture
def banco_teste(tmp_path):
    caminho = tmp_path / "cancelamento_vendas.db"
    criar_tabelas(caminho)
    return caminho


def criar_confirmacao():
    snapshot = ProdutoSnapshot(
        produto_id=None,
        codigo="CANCEL",
        nome="Produto preservado",
        forma_venda="PESO",
        preco_referencia_centavos=7990,
    )
    produto = ItemVenda(
        origem="ETIQUETA",
        subtotal_centavos=5367,
        origem_quantidade="ESTIMADA",
        produto=snapshot,
        codigo_barras="2023400053672",
        quantidade=Decimal("0.671714643300"),
    )
    diversos = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=633,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )
    venda = VendaEmAndamento(itens=(produto, diversos))
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=6000,
        pagamentos=(
            Pagamento("PIX", 2000),
            Pagamento("DINHEIRO", 4000),
        ),
    )
    return confirmar_venda(venda, pagamentos)


@pytest.fixture
def venda_cancelavel(banco_teste):
    identificador_tentativa = gerar_identificador_tentativa()
    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        identificador_tentativa,
        banco_teste,
    )
    return venda_id, identificador_tentativa


def preparar_banco_versao_5(caminho_banco) -> int:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
        conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        conexao.execute(schema._COMANDO_CRIAR_ITENS_VENDA)
        conexao.execute(schema._COMANDO_CRIAR_PAGAMENTOS)
        conexao.execute(schema._COMANDO_ADICIONAR_IDENTIFICADOR_TENTATIVA)
        conexao.execute(schema._COMANDO_CRIAR_INDICE_TENTATIVA)
        conexao.execute(schema._COMANDO_CRIAR_INDICE_HISTORICO_VENDAS)
        venda_id = conexao.execute(
            """
            INSERT INTO vendas (total_centavos, identificador_tentativa)
            VALUES (1000, ?)
            """,
            (gerar_identificador_tentativa(),),
        ).lastrowid
        conexao.execute("PRAGMA user_version = 5")
        conexao.commit()
        return venda_id
    finally:
        conexao.close()


def test_migra_versao_5_para_6_preservando_venda_como_ativa(
    tmp_path,
) -> None:
    caminho = tmp_path / "migracao_v5_v6.db"
    venda_id = preparar_banco_versao_5(caminho)

    criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        venda = conexao.execute(
            """
            SELECT id, total_centavos, status, motivo_cancelamento,
                   cancelada_em, autorizador_identidade
            FROM vendas
            """
        ).fetchone()
        assert (
            conexao.execute("PRAGMA user_version").fetchone()[0]
            == schema.VERSAO_ESQUEMA
        )
        assert tuple(venda) == (venda_id, 1000, "ATIVA", None, None, None)
    finally:
        conexao.close()


def test_schema_exige_metadados_coerentes_com_status(banco_teste) -> None:
    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        gerar_identificador_tentativa(),
        banco_teste,
    )
    conexao = conectar(banco_teste)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                "UPDATE vendas SET status = 'CANCELADA' WHERE id = ?",
                (venda_id,),
            )
        conexao.rollback()

        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                """
                UPDATE vendas
                SET motivo_cancelamento = 'indevido'
                WHERE id = ?
                """,
                (venda_id,),
            )
    finally:
        conexao.close()


def test_cancelamento_valido_registra_motivo_data_e_responsavel(
    banco_teste,
    venda_cancelavel,
    monkeypatch,
) -> None:
    venda_id, _ = venda_cancelavel
    instante = datetime(2026, 11, 4, 18, 30, 45, tzinfo=UTC)
    monkeypatch.setattr(cancelamento_service, "_agora_utc", lambda: instante)
    autorizacao = ContextoAutorizacaoCancelamento("  operador-123  ")

    resultado = cancelar_venda(
        venda_id,
        "  lançamento incorreto  ",
        autorizacao,
        banco_teste,
    )

    assert resultado == CancelamentoVenda(
        venda_id=venda_id,
        motivo="lançamento incorreto",
        cancelada_em=instante,
        identidade_autorizador="operador-123",
    )
    resumo = buscar_venda_resumida_por_id(venda_id, banco_teste)
    assert resumo.status == "CANCELADA"
    assert resumo.motivo_cancelamento == "lançamento incorreto"
    assert resumo.cancelada_em == instante
    assert resumo.autorizador_identidade == "operador-123"


@pytest.mark.parametrize("motivo", [None, "", "   ", 123, True])
def test_rejeita_motivo_ausente_ou_invalido(
    banco_teste,
    venda_cancelavel,
    motivo,
) -> None:
    venda_id, _ = venda_cancelavel
    erro = TypeError if not isinstance(motivo, str) else ValueError

    with pytest.raises(erro):
        cancelar_venda(
            venda_id,
            motivo,
            ContextoAutorizacaoCancelamento("operador"),
            banco_teste,
        )

    assert buscar_venda_resumida_por_id(venda_id, banco_teste).status == "ATIVA"


def test_venda_inexistente_e_rejeitada(banco_teste) -> None:
    with pytest.raises(VendaNaoEncontradaError):
        cancelar_venda(
            999999,
            "motivo válido",
            ContextoAutorizacaoCancelamento("operador"),
            banco_teste,
        )


def test_segundo_cancelamento_e_rejeitado(
    banco_teste,
    venda_cancelavel,
) -> None:
    venda_id, _ = venda_cancelavel
    autorizacao = ContextoAutorizacaoCancelamento("operador")
    cancelar_venda(venda_id, "primeiro motivo", autorizacao, banco_teste)

    with pytest.raises(VendaJaCanceladaError):
        cancelar_venda(venda_id, "segundo motivo", autorizacao, banco_teste)

    resumo = buscar_venda_resumida_por_id(venda_id, banco_teste)
    assert resumo.motivo_cancelamento == "primeiro motivo"


def test_exige_contexto_tipado_sem_aceitar_booleano(
    banco_teste,
    venda_cancelavel,
) -> None:
    venda_id, _ = venda_cancelavel

    with pytest.raises(TypeError):
        cancelar_venda(venda_id, "motivo", True, banco_teste)
    with pytest.raises(ValueError):
        ContextoAutorizacaoCancelamento("   ")


def test_cancelamentos_concorrentes_produzem_um_unico_sucesso(
    banco_teste,
    venda_cancelavel,
) -> None:
    venda_id, _ = venda_cancelavel
    barreira = Barrier(2)
    autorizacao = ContextoAutorizacaoCancelamento("operador-concorrente")

    def tentar_cancelar(indice):
        barreira.wait()
        try:
            resultado = cancelar_venda(
                venda_id,
                f"motivo {indice}",
                autorizacao,
                banco_teste,
            )
            return "SUCESSO", resultado.motivo
        except VendaJaCanceladaError:
            return "JA_CANCELADA", None

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(tentar_cancelar, (1, 2)))

    assert sorted(resultado[0] for resultado in resultados) == [
        "JA_CANCELADA",
        "SUCESSO",
    ]
    resumo = buscar_venda_resumida_por_id(venda_id, banco_teste)
    assert resumo.status == "CANCELADA"
    assert resumo.motivo_cancelamento in {"motivo 1", "motivo 2"}


def test_cancelamento_preserva_venda_itens_pagamentos_e_uuid(
    banco_teste,
    venda_cancelavel,
) -> None:
    venda_id, identificador_tentativa = venda_cancelavel
    detalhe_antes = buscar_venda_detalhada_por_id(venda_id, banco_teste)
    cancelar_venda(
        venda_id,
        "cancelamento preservador",
        ContextoAutorizacaoCancelamento("operador"),
        banco_teste,
    )
    detalhe_depois = buscar_venda_detalhada_por_id(venda_id, banco_teste)

    assert detalhe_depois.venda_id == detalhe_antes.venda_id
    assert detalhe_depois.total_centavos == detalhe_antes.total_centavos
    assert detalhe_depois.registrada_em == detalhe_antes.registrada_em
    assert detalhe_depois.itens == detalhe_antes.itens
    assert detalhe_depois.pagamentos == detalhe_antes.pagamentos
    conexao = conectar(banco_teste)
    try:
        identificador_salvo = conexao.execute(
            """
            SELECT identificador_tentativa FROM vendas WHERE id = ?
            """,
            (venda_id,),
        ).fetchone()[0]
        assert identificador_salvo == identificador_tentativa
    finally:
        conexao.close()


def test_venda_cancelada_permanece_no_historico_por_id_e_data(
    banco_teste,
    venda_cancelavel,
) -> None:
    venda_id, _ = venda_cancelavel
    cancelar_venda(
        venda_id,
        "permanece no histórico",
        ContextoAutorizacaoCancelamento("operador"),
        banco_teste,
    )
    detalhe = buscar_venda_detalhada_por_id(venda_id, banco_teste)
    data_local = detalhe.registrada_em.astimezone(FUSO_SAO_PAULO).date()
    vendas_do_dia = listar_vendas_resumidas_por_data(data_local, banco_teste)

    assert detalhe.status == "CANCELADA"
    assert detalhe.motivo_cancelamento == "permanece no histórico"
    resumo_listado = next(venda for venda in vendas_do_dia if venda.venda_id == venda_id)
    assert resumo_listado.status == "CANCELADA"


def test_falha_durante_update_executa_rollback_integral(
    banco_teste,
    venda_cancelavel,
) -> None:
    venda_id, _ = venda_cancelavel
    detalhe_antes = buscar_venda_detalhada_por_id(venda_id, banco_teste)
    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_cancelamento
            BEFORE UPDATE OF status ON vendas
            BEGIN
                SELECT RAISE(ABORT, 'falha no cancelamento');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha no cancelamento"):
        cancelar_venda(
            venda_id,
            "não deve persistir",
            ContextoAutorizacaoCancelamento("operador"),
            banco_teste,
        )

    detalhe_depois = buscar_venda_detalhada_por_id(venda_id, banco_teste)
    assert detalhe_depois == detalhe_antes


def test_reexecucao_da_migracao_preserva_cancelamento(banco_teste) -> None:
    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        gerar_identificador_tentativa(),
        banco_teste,
    )
    cancelar_venda(
        venda_id,
        "preservar",
        ContextoAutorizacaoCancelamento("operador"),
        banco_teste,
    )

    criar_tabelas(banco_teste)
    criar_tabelas(banco_teste)

    resumo = buscar_venda_resumida_por_id(venda_id, banco_teste)
    assert resumo.status == "CANCELADA"
    assert resumo.motivo_cancelamento == "preservar"
    conexao = conectar(banco_teste)
    try:
        assert (
            conexao.execute("PRAGMA user_version").fetchone()[0]
            == schema.VERSAO_ESQUEMA
        )
    finally:
        conexao.close()


def test_falha_na_migracao_6_reverte_colunas_e_preserva_versao_5(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_migracao_v6.db"
    venda_id = preparar_banco_versao_5(caminho)
    monkeypatch.setattr(
        schema,
        "_COMANDO_ADICIONAR_STATUS_VENDA",
        "ALTER TABLE vendas ADD COLUMN status TEXT CHECK (",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(vendas)").fetchall()
        }
        venda = conexao.execute(
            "SELECT id, total_centavos FROM vendas"
        ).fetchone()
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 5
        assert "status" not in colunas
        assert "motivo_cancelamento" not in colunas
        assert tuple(venda) == (venda_id, 1000)
    finally:
        conexao.close()


def test_limitacao_de_autorizacao_esta_documentada() -> None:
    texto = Path("docs/DECISOES.md").read_text(encoding="utf-8")

    assert "T43 registra a identidade" in texto
    assert "mas não\n  valida credenciais" in texto
    assert "T47" in texto
