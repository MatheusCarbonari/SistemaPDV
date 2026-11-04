from decimal import Decimal
import sqlite3

import pytest

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_em_andamento import VendaEmAndamento
import services.persistencia_venda_service as persistencia_service
from services.confirmacao_venda_service import confirmar_venda
from services.persistencia_venda_service import (
    CommitVendaIncertoError,
    IdentificadorTentativaInvalidoError,
    TentativaFechamentoIncompativelError,
    gerar_identificador_tentativa,
    persistir_venda_confirmada,
    persistir_venda_confirmada_idempotente,
)


@pytest.fixture
def banco_teste(tmp_path):
    caminho = tmp_path / "idempotencia_venda.db"
    criar_tabelas(caminho)
    return caminho


def criar_confirmacao(
    *,
    nome="Produto",
    subtotal=1000,
    pagamentos=(Pagamento("PIX", 1000),),
):
    snapshot = ProdutoSnapshot(
        produto_id=None,
        codigo=f"COD-{nome}",
        nome=nome,
        forma_venda="UNIDADE",
        preco_referencia_centavos=subtotal,
    )
    item = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal,
        origem_quantidade="INFORMADA",
        produto=snapshot,
        quantidade=Decimal("1"),
    )
    venda = VendaEmAndamento(itens=(item,))
    composicao = PagamentosEmAndamento(
        total_venda_centavos=subtotal,
        pagamentos=pagamentos,
    )
    return confirmar_venda(venda, composicao)


def contagens(caminho_banco) -> tuple[int, int, int]:
    conexao = conectar(caminho_banco)
    try:
        return tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("vendas", "itens_venda", "pagamentos")
        )
    finally:
        conexao.close()


def preparar_banco_na_versao(caminho_banco, versao: int) -> None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        if versao >= 1:
            conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
            conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        if versao >= 2:
            conexao.execute(schema._COMANDO_CRIAR_ITENS_VENDA)
        if versao >= 3:
            conexao.execute(schema._COMANDO_CRIAR_PAGAMENTOS)
        conexao.execute(f"PRAGMA user_version = {versao}")
        conexao.commit()
    finally:
        conexao.close()


def inserir_venda_legada_versao_3(caminho_banco) -> int:
    preparar_banco_na_versao(caminho_banco, 3)
    conexao = conectar(caminho_banco)
    try:
        venda_id = conexao.execute(
            "INSERT INTO vendas (total_centavos) VALUES (1000)"
        ).lastrowid
        conexao.execute(
            """
            INSERT INTO itens_venda (
                venda_id, posicao, produto_id, codigo_snapshot,
                nome_snapshot, forma_venda_snapshot,
                preco_referencia_centavos, tipo_item, origem,
                origem_quantidade, quantidade_decimal, codigo_barras,
                subtotal_centavos
            )
            VALUES (?, 0, NULL, NULL, NULL, NULL, NULL, NULL,
                    'MANUAL', 'NAO_INFORMADA', NULL, NULL, 1000)
            """,
            (venda_id,),
        )
        conexao.execute(
            """
            INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
            VALUES (?, 'DINHEIRO', 1000)
            """,
            (venda_id,),
        )
        conexao.commit()
        return venda_id
    finally:
        conexao.close()


def test_primeira_gravacao_idempotente_persiste_uuid(banco_teste) -> None:
    confirmacao = criar_confirmacao()
    tentativa = gerar_identificador_tentativa()

    venda_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        tentativa,
        banco_teste,
    )

    conexao = conectar(banco_teste)
    try:
        venda = conexao.execute(
            """
            SELECT id, identificador_tentativa
            FROM vendas WHERE id = ?
            """,
            (venda_id,),
        ).fetchone()
        assert tuple(venda) == (venda_id, tentativa)
    finally:
        conexao.close()


def test_repeticao_retorna_id_original_sem_duplicar_filhos(
    banco_teste,
) -> None:
    confirmacao = criar_confirmacao()
    tentativa = gerar_identificador_tentativa()

    primeiro_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        tentativa,
        banco_teste,
    )
    segundo_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        tentativa,
        banco_teste,
    )

    assert segundo_id == primeiro_id
    assert contagens(banco_teste) == (1, 1, 1)


def test_vendas_identicas_com_identificadores_distintos_sao_legitimas(
    banco_teste,
) -> None:
    confirmacao = criar_confirmacao()

    primeiro_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        gerar_identificador_tentativa(),
        banco_teste,
    )
    segundo_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        gerar_identificador_tentativa(),
        banco_teste,
    )

    assert segundo_id != primeiro_id
    assert contagens(banco_teste) == (2, 2, 2)


def test_rejeita_reutilizacao_do_uuid_com_conteudo_comercial_diferente(
    banco_teste,
) -> None:
    tentativa = gerar_identificador_tentativa()
    original = criar_confirmacao(nome="Original")
    diferente = criar_confirmacao(
        nome="Outro snapshot",
        pagamentos=(Pagamento("DINHEIRO", 1000),),
    )
    persistir_venda_confirmada_idempotente(
        original,
        tentativa,
        banco_teste,
    )

    with pytest.raises(TentativaFechamentoIncompativelError):
        persistir_venda_confirmada_idempotente(
            diferente,
            tentativa,
            banco_teste,
        )

    assert contagens(banco_teste) == (1, 1, 1)


@pytest.mark.parametrize(
    "identificador",
    [None, "", "não-e-uuid", 123, True],
)
def test_rejeita_identificador_ausente_ou_invalido(
    banco_teste,
    identificador,
) -> None:
    with pytest.raises(IdentificadorTentativaInvalidoError):
        persistir_venda_confirmada_idempotente(
            criar_confirmacao(),
            identificador,
            banco_teste,
        )

    assert contagens(banco_teste) == (0, 0, 0)


def test_falha_antes_do_commit_permite_repetir_o_mesmo_uuid(
    banco_teste,
) -> None:
    tentativa = gerar_identificador_tentativa()
    confirmacao = criar_confirmacao()
    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_item_idempotente
            BEFORE INSERT ON itens_venda
            BEGIN
                SELECT RAISE(ABORT, 'falha antes do commit');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="antes do commit"):
        persistir_venda_confirmada_idempotente(
            confirmacao,
            tentativa,
            banco_teste,
        )

    assert contagens(banco_teste) == (0, 0, 0)
    conexao = conectar(banco_teste)
    try:
        conexao.execute("DROP TRIGGER falhar_item_idempotente")
        conexao.commit()
    finally:
        conexao.close()

    venda_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        tentativa,
        banco_teste,
    )
    assert venda_id > 0
    assert contagens(banco_teste) == (1, 1, 1)


class ConexaoCommitConfirmadoComErro(sqlite3.Connection):
    def commit(self) -> None:
        super().commit()
        raise sqlite3.OperationalError("resposta do commit perdida")


def conexao_com_commit_incerto(caminho_banco):
    conexao = sqlite3.connect(
        caminho_banco,
        factory=ConexaoCommitConfirmadoComErro,
    )
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def test_recupera_id_quando_commit_ocorre_antes_da_falha(
    banco_teste,
    monkeypatch,
) -> None:
    tentativa = gerar_identificador_tentativa()
    conectar_real = conectar
    chamadas = 0

    def conectar_simulado(caminho):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return conexao_com_commit_incerto(caminho)
        return conectar_real(caminho)

    monkeypatch.setattr(
        persistencia_service,
        "conectar",
        conectar_simulado,
    )

    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        tentativa,
        banco_teste,
    )

    assert venda_id > 0
    assert chamadas >= 2
    assert contagens(banco_teste) == (1, 1, 1)


def test_banco_indisponivel_na_verificacao_resulta_em_estado_incerto(
    banco_teste,
    monkeypatch,
) -> None:
    tentativa = gerar_identificador_tentativa()
    chamadas = 0

    def conectar_simulado(caminho):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return conexao_com_commit_incerto(caminho)
        raise sqlite3.OperationalError("banco indisponível")

    monkeypatch.setattr(
        persistencia_service,
        "conectar",
        conectar_simulado,
    )

    with pytest.raises(CommitVendaIncertoError) as erro:
        persistir_venda_confirmada_idempotente(
            criar_confirmacao(),
            tentativa,
            banco_teste,
        )

    assert erro.value.identificador_tentativa == tentativa
    assert contagens(banco_teste) == (1, 1, 1)


def test_conflito_unique_e_verificado_sem_duplicar(
    banco_teste,
    monkeypatch,
) -> None:
    tentativa = gerar_identificador_tentativa()
    confirmacao = criar_confirmacao()
    venda_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        tentativa,
        banco_teste,
    )
    busca_real = persistencia_service.buscar_venda_por_identificador
    chamadas = 0

    def ocultar_primeira_busca(conexao, identificador):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return None
        return busca_real(conexao, identificador)

    monkeypatch.setattr(
        persistencia_service,
        "buscar_venda_por_identificador",
        ocultar_primeira_busca,
    )

    recuperado = persistir_venda_confirmada_idempotente(
        confirmacao,
        tentativa,
        banco_teste,
    )

    assert recuperado == venda_id
    assert chamadas >= 2
    assert contagens(banco_teste) == (1, 1, 1)


def test_falha_em_pagamento_preserva_atomicidade_do_t39(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_pagamento_idempotente
            BEFORE INSERT ON pagamentos
            BEGIN
                SELECT RAISE(ABORT, 'falha no pagamento');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha no pagamento"):
        persistir_venda_confirmada_idempotente(
            criar_confirmacao(),
            gerar_identificador_tentativa(),
            banco_teste,
        )

    assert contagens(banco_teste) == (0, 0, 0)


def test_contrato_t39_permanece_compativel_na_versao_4(
    banco_teste,
) -> None:
    confirmacao = criar_confirmacao()

    primeiro_id = persistir_venda_confirmada(confirmacao, banco_teste)
    segundo_id = persistir_venda_confirmada(confirmacao, banco_teste)

    assert segundo_id != primeiro_id
    conexao = conectar(banco_teste)
    try:
        identificadores = conexao.execute(
            """
            SELECT identificador_tentativa FROM vendas ORDER BY id
            """
        ).fetchall()
        assert [linha["identificador_tentativa"] for linha in identificadores] == [
            None,
            None,
        ]
    finally:
        conexao.close()


def test_migra_versao_3_para_4_preservando_venda_legada(tmp_path) -> None:
    caminho = tmp_path / "migracao_v3_v4.db"
    venda_id = inserir_venda_legada_versao_3(caminho)

    criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        venda = conexao.execute(
            """
            SELECT id, total_centavos, identificador_tentativa
            FROM vendas
            """
        ).fetchone()
        indices = {
            linha["name"]
            for linha in conexao.execute("PRAGMA index_list(vendas)").fetchall()
        }
        assert versao == 4
        assert tuple(venda) == (venda_id, 1000, None)
        assert "ux_vendas_identificador_tentativa" in indices
        assert contagens(caminho) == (1, 1, 1)
    finally:
        conexao.close()


@pytest.mark.parametrize("versao_inicial", [0, 1, 2, 3])
def test_bancos_anteriores_evoluem_ate_versao_4(
    tmp_path,
    versao_inicial,
) -> None:
    caminho = tmp_path / f"versao_{versao_inicial}.db"
    preparar_banco_na_versao(caminho, versao_inicial)

    criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(vendas)").fetchall()
        }
        assert versao == 4
        assert "identificador_tentativa" in colunas
    finally:
        conexao.close()


def test_reexecucao_da_migracao_e_segura(banco_teste) -> None:
    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        gerar_identificador_tentativa(),
        banco_teste,
    )

    criar_tabelas(banco_teste)
    criar_tabelas(banco_teste)

    conexao = conectar(banco_teste)
    try:
        vendas = conexao.execute("SELECT id FROM vendas").fetchall()
        assert [venda["id"] for venda in vendas] == [venda_id]
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 4
    finally:
        conexao.close()


def test_falha_na_migracao_reverte_coluna_indice_e_versao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_migracao_v4.db"
    venda_id = inserir_venda_legada_versao_3(caminho)
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_INDICE_TENTATIVA",
        "CREATE UNIQUE INDEX indice_incompleto ON vendas (",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(vendas)").fetchall()
        }
        venda = conexao.execute(
            "SELECT id, total_centavos FROM vendas"
        ).fetchone()
        assert versao == 3
        assert "identificador_tentativa" not in colunas
        assert tuple(venda) == (venda_id, 1000)
        assert contagens(caminho) == (1, 1, 1)
    finally:
        conexao.close()
