from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from PySide6.QtWidgets import QLineEdit

from database.conexao import conectar
from database.schema import criar_tabelas
from interface.dialogo_historico_precos import DialogoHistoricoPrecos
from interface.pagina_produtos import PaginaProdutos
from models.produto import Produto
from models.sessao_usuario import SessaoUsuario
from repositories.produto_repository import (
    alterar_situacao_produto_repository,
    salvar_produto,
)
from services.autenticacao_service import (
    PermissaoNegadaError,
    SessaoInvalidaError,
    autenticar_usuario,
)
from services.historico_preco_service import consultar_historico_precos
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import criar_sessao_admin_teste


FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")
SENHA_CAIXA = "frase individual historico preco 2026"


@pytest.fixture
def ambiente(tmp_path):
    caminho = tmp_path / "consulta_historico_precos.db"
    criar_tabelas(caminho)
    sessao_admin = criar_sessao_admin_teste(caminho)
    produto = salvar_produto(
        Produto(
            codigo="101",
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=8990,
            origem="COMPRADO",
        ),
        caminho,
    )
    return caminho, sessao_admin, produto


def inserir_alteracao(caminho, produto_id, anterior, novo, instante):
    with conectar(caminho) as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO historico_precos_produtos (
                produto_id,
                preco_anterior_centavos,
                preco_novo_centavos,
                alterado_em
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                produto_id,
                anterior,
                novo,
                instante.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        return cursor.lastrowid


def linhas_historico(caminho):
    with conectar(caminho) as conexao:
        return tuple(
            tuple(linha)
            for linha in conexao.execute(
                """
                SELECT id, produto_id, preco_anterior_centavos,
                       preco_novo_centavos, alterado_em
                FROM historico_precos_produtos
                ORDER BY id
                """
            ).fetchall()
        )


def test_consulta_alteracoes_em_ordem_decrescente(ambiente) -> None:
    caminho, sessao, produto = ambiente
    agora = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
    primeiro_id = inserir_alteracao(
        caminho, produto.id, 7990, 8490, agora - timedelta(days=2)
    )
    segundo_id = inserir_alteracao(
        caminho, produto.id, 8490, 8990, agora - timedelta(days=1)
    )

    registros = consultar_historico_precos(
        sessao,
        produto.id,
        caminho,
        agora=agora,
    )

    assert [registro.id for registro in registros] == [segundo_id, primeiro_id]
    assert registros[0].preco_anterior_centavos == 8490
    assert registros[0].preco_novo_centavos == 8990
    assert registros[0].alterado_em.tzinfo is UTC


def test_produto_sem_historico_retorna_colecao_vazia(ambiente) -> None:
    caminho, sessao, produto = ambiente

    assert consultar_historico_precos(sessao, produto.id, caminho) == ()


def test_recorte_de_doze_meses_preserva_registro_anterior(ambiente) -> None:
    caminho, sessao, produto = ambiente
    agora = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
    dentro_id = inserir_alteracao(
        caminho,
        produto.id,
        8490,
        8990,
        datetime(2025, 11, 6, 15, 0, tzinfo=UTC),
    )
    antigo_id = inserir_alteracao(
        caminho,
        produto.id,
        7990,
        8490,
        datetime(2025, 11, 6, 14, 59, 59, tzinfo=UTC),
    )

    recentes = consultar_historico_precos(
        sessao, produto.id, caminho, meses=12, agora=agora
    )
    completo = consultar_historico_precos(
        sessao, produto.id, caminho, meses=None
    )

    assert [registro.id for registro in recentes] == [dentro_id]
    assert {registro.id for registro in completo} == {dentro_id, antigo_id}
    assert len(linhas_historico(caminho)) == 2


def test_consulta_admite_produto_inativo(ambiente) -> None:
    caminho, sessao, produto = ambiente
    inserir_alteracao(caminho, produto.id, 7990, 8990, datetime.now(UTC))
    assert alterar_situacao_produto_repository(produto.id, False, caminho)

    registros = consultar_historico_precos(sessao, produto.id, caminho)

    assert len(registros) == 1
    assert registros[0].produto_id == produto.id


def test_consulta_rejeita_caixa_e_sessao_fabricada(ambiente) -> None:
    caminho, sessao_admin, produto = ambiente
    caixa, erros = criar_conta_caixa(
        sessao_admin,
        "caixa.preco",
        SENHA_CAIXA,
        SENHA_CAIXA,
        caminho,
    )
    assert caixa is not None and erros == []
    sessao_caixa = autenticar_usuario("caixa.preco", SENHA_CAIXA, caminho)
    fabricada = SessaoUsuario(
        sessao_admin.usuario_id,
        sessao_admin.identificacao_acesso,
        sessao_admin.perfil,
        sessao_admin.identificador_sessao,
    )

    with pytest.raises(PermissaoNegadaError):
        consultar_historico_precos(sessao_caixa, produto.id, caminho)
    with pytest.raises(SessaoInvalidaError):
        consultar_historico_precos(fabricada, produto.id, caminho)


def test_dialogo_exibe_reais_data_local_e_ausencia_de_responsavel(
    ambiente,
    qtbot,
) -> None:
    caminho, sessao, produto = ambiente
    instante = datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
    inserir_alteracao(caminho, produto.id, 7990, 8990, instante)
    dialogo = DialogoHistoricoPrecos(sessao, produto, caminho)
    qtbot.addWidget(dialogo)

    assert dialogo.tabela.rowCount() == 1
    assert dialogo.tabela.item(0, 0).text() == instante.astimezone(
        FUSO_SAO_PAULO
    ).strftime("%d/%m/%Y %H:%M:%S")
    assert dialogo.tabela.item(0, 1).text() == "R$ 79,90"
    assert dialogo.tabela.item(0, 2).text() == "R$ 89,90"
    assert "1 altera" in dialogo.rotulo_mensagem.text()
    assert dialogo.findChild(QLineEdit) is None


def test_dialogo_informa_ausencia_e_permite_todo_historico(
    ambiente,
    qtbot,
) -> None:
    caminho, sessao, produto = ambiente
    instante_antigo = datetime.now(UTC) - timedelta(days=500)
    inserir_alteracao(caminho, produto.id, 7990, 8990, instante_antigo)
    dialogo = DialogoHistoricoPrecos(sessao, produto, caminho)
    qtbot.addWidget(dialogo)

    assert dialogo.tabela.rowCount() == 0
    assert "Nenhuma alteração" in dialogo.rotulo_mensagem.text()
    dialogo.combo_periodo.setCurrentIndex(1)
    assert dialogo.tabela.rowCount() == 1


def test_abrir_e_fechar_preserva_pagina_e_nao_grava(ambiente, qtbot) -> None:
    caminho, sessao, produto = ambiente
    inserir_alteracao(caminho, produto.id, 7990, 8990, datetime.now(UTC))
    pagina = PaginaProdutos(
        caminho,
        sessao_administrativa=sessao,
    )
    qtbot.addWidget(pagina)
    pagina.show()
    pagina.campo_pesquisa.setText("101")
    pagina.combo_situacao.setCurrentIndex(0)
    pagina.carregar_produtos()
    pagina.tabela_produtos.selectRow(0)
    antes = linhas_historico(caminho)

    pagina.abrir_historico_precos()
    dialogo = pagina.dialogo_atual
    assert isinstance(dialogo, DialogoHistoricoPrecos)
    dialogo.reject()
    qtbot.waitUntil(lambda: pagina.dialogo_atual is None)

    assert pagina.campo_pesquisa.text() == "101"
    assert pagina.combo_situacao.currentData() is None
    assert pagina.tabela_produtos.currentRow() == 0
    assert linhas_historico(caminho) == antes
