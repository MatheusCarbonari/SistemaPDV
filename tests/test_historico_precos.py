from datetime import UTC, datetime
import sqlite3

import pytest

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from interface.pagina_produtos import PaginaProdutos
from models.produto import Produto
from models.produto_snapshot import ProdutoSnapshot
from repositories.produto_repository import (
    alterar_situacao_produto_repository,
    buscar_produto_por_codigo,
    salvar_produto,
)
from services.produto_service import atualizar_produto


@pytest.fixture
def banco_precos(tmp_path):
    caminho = tmp_path / "historico_precos.db"
    criar_tabelas(caminho)
    return caminho


def salvar_produto_teste(caminho, *, codigo="101", preco=7990):
    return salvar_produto(
        Produto(
            codigo=codigo,
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=preco,
            origem="COMPRADO",
        ),
        caminho,
    )


def editar_produto(caminho, produto, *, preco, nome=None):
    return atualizar_produto(
        produto.id,
        produto.codigo,
        nome or produto.nome,
        produto.categoria,
        produto.forma_venda,
        preco,
        produto.origem,
        caminho,
    )


def consultar_historico(caminho, produto_id):
    conexao = conectar(caminho)
    try:
        return conexao.execute(
            """
            SELECT produto_id, preco_anterior_centavos,
                   preco_novo_centavos, alterado_em
            FROM historico_precos_produtos
            WHERE produto_id = ?
            ORDER BY id
            """,
            (produto_id,),
        ).fetchall()
    finally:
        conexao.close()


def rebaixar_para_versao_6(caminho) -> None:
    conexao = conectar(caminho)
    try:
        conexao.execute("DROP TABLE IF EXISTS estado_identidade")
        conexao.execute("DROP TABLE IF EXISTS usuarios")
        conexao.execute(
            "DROP INDEX IF EXISTS ix_historico_precos_produto_data"
        )
        conexao.execute("DROP TABLE IF EXISTS historico_precos_produtos")
        conexao.execute("PRAGMA user_version = 6")
        conexao.commit()
    finally:
        conexao.close()


def test_alteracao_real_registra_precos_exatos_e_instante_utc(
    banco_precos,
) -> None:
    produto = salvar_produto_teste(banco_precos)

    atualizado, erros = editar_produto(banco_precos, produto, preco=8491)

    assert erros == []
    assert atualizado.preco_venda_centavos == 8491
    historico = consultar_historico(banco_precos, produto.id)
    assert len(historico) == 1
    assert tuple(historico[0])[:3] == (produto.id, 7990, 8491)
    registrado = datetime.strptime(historico[0]["alterado_em"], "%Y-%m-%d %H:%M:%S")
    agora_utc = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    assert abs((agora_utc - registrado).total_seconds()) <= 5


def test_edicao_sem_mudanca_de_preco_nao_registra_historico(
    banco_precos,
) -> None:
    produto = salvar_produto_teste(banco_precos)

    atualizado, erros = editar_produto(
        banco_precos,
        produto,
        preco=7990,
        nome="Picanha premium",
    )

    assert erros == []
    assert atualizado.nome == "Picanha premium"
    assert consultar_historico(banco_precos, produto.id) == []


def test_multiplas_alteracoes_preservam_cadeia_de_precos(
    banco_precos,
) -> None:
    produto = salvar_produto_teste(banco_precos)

    primeiro, erros = editar_produto(banco_precos, produto, preco=8490)
    assert erros == []
    segundo, erros = editar_produto(banco_precos, primeiro, preco=8990)
    assert erros == []
    terceiro, erros = editar_produto(banco_precos, segundo, preco=8991)
    assert erros == []

    assert terceiro.preco_venda_centavos == 8991
    assert [tuple(linha)[1:3] for linha in consultar_historico(
        banco_precos,
        produto.id,
    )] == [(7990, 8490), (8490, 8990), (8990, 8991)]


def test_falha_ao_gravar_historico_reverte_preco_e_demais_campos(
    banco_precos,
) -> None:
    produto = salvar_produto_teste(banco_precos)
    conexao = conectar(banco_precos)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_historico_preco
            BEFORE INSERT ON historico_precos_produtos
            BEGIN
                SELECT RAISE(ABORT, 'falha de auditoria');
            END;
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha de auditoria"):
        editar_produto(
            banco_precos,
            produto,
            preco=8490,
            nome="Nome que deve voltar",
        )

    preservado = buscar_produto_por_codigo(produto.codigo, banco_precos)
    assert preservado.nome == "Picanha"
    assert preservado.preco_venda_centavos == 7990
    assert consultar_historico(banco_precos, produto.id) == []


def test_historico_permanece_apos_desativacao_do_produto(banco_precos) -> None:
    produto = salvar_produto_teste(banco_precos)
    atualizado, erros = editar_produto(banco_precos, produto, preco=8490)
    assert erros == []

    assert alterar_situacao_produto_repository(
        atualizado.id,
        False,
        banco_precos,
    )

    inativo = buscar_produto_por_codigo(produto.codigo, banco_precos)
    assert inativo.ativo is False
    assert [tuple(linha)[1:3] for linha in consultar_historico(
        banco_precos,
        produto.id,
    )] == [(7990, 8490)]


def test_snapshot_anterior_nao_muda_com_novo_preco(banco_precos) -> None:
    produto = salvar_produto_teste(banco_precos)
    snapshot = ProdutoSnapshot(
        produto.id,
        produto.codigo,
        produto.nome,
        produto.forma_venda,
        produto.preco_venda_centavos,
    )

    atualizado, erros = editar_produto(banco_precos, produto, preco=9990)

    assert erros == []
    assert atualizado.preco_venda_centavos == 9990
    assert snapshot.preco_referencia_centavos == 7990


def test_migracao_v6_cria_historico_e_preserva_produto(banco_precos) -> None:
    produto = salvar_produto_teste(banco_precos)
    rebaixar_para_versao_6(banco_precos)

    criar_tabelas(banco_precos)

    conexao = conectar(banco_precos)
    try:
        assert (
            conexao.execute("PRAGMA user_version").fetchone()[0]
            == schema.VERSAO_ESQUEMA
        )
        assert conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("historico_precos_produtos",),
        ).fetchone() is not None
    finally:
        conexao.close()
    preservado = buscar_produto_por_codigo(produto.codigo, banco_precos)
    assert preservado.preco_venda_centavos == 7990


def test_falha_na_migracao_v7_reverte_tabela_e_versao(
    banco_precos,
    monkeypatch,
) -> None:
    rebaixar_para_versao_6(banco_precos)
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_INDICE_HISTORICO_PRECOS",
        "COMANDO SQL INVALIDO",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(banco_precos)

    conexao = conectar(banco_precos)
    try:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 6
        assert conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("historico_precos_produtos",),
        ).fetchone() is None
    finally:
        conexao.close()


def test_edicao_grafica_usa_atualizacao_auditavel(
    qtbot,
    banco_precos,
) -> None:
    produto = salvar_produto_teste(banco_precos)
    pagina = PaginaProdutos(banco_precos)
    qtbot.addWidget(pagina)
    pagina.show()
    pagina.ativar()
    pagina.tabela_produtos.selectRow(0)
    pagina.abrir_edicao()
    dialogo = pagina.dialogo_atual
    dialogo.campo_preco.setText("84,90")

    dialogo.confirmar()

    assert [tuple(linha)[1:3] for linha in consultar_historico(
        banco_precos,
        produto.id,
    )] == [(7990, 8490)]
