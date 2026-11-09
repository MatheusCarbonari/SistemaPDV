import sqlite3
from threading import Barrier, Thread

import pytest
from PySide6.QtWidgets import QHeaderView

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from interface.dialogo_categorias import DialogoCategorias
from interface.pagina_produtos import PaginaProdutos
from models.produto import Produto
from models.sessao_usuario import SessaoUsuario
from repositories.categoria_repository import (
    NomeCategoriaEmUsoError,
    buscar_categoria_por_chave_repository,
)
from repositories.produto_repository import (
    CategoriaProdutoIndisponivelError,
    buscar_produto_por_codigo,
    salvar_produto,
)
from services.autenticacao_service import (
    PermissaoNegadaError,
    SessaoInvalidaError,
    autenticar_usuario,
)
from services.categoria_service import (
    alterar_situacao_categoria,
    criar_categoria,
    listar_categorias,
    renomear_categoria,
)
from services.produto_service import cadastrar_produto, atualizar_produto
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_sessao_admin_teste,
)


SENHA_CAIXA = "frase individual categorias caixa 2026"


def criar_banco_v9(caminho, categorias):
    conexao = conectar(caminho)
    try:
        conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
        conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        conexao.execute(schema._COMANDO_CRIAR_ITENS_VENDA)
        conexao.execute(schema._COMANDO_CRIAR_HISTORICO_PRECOS)
        for produto_id, codigo, categoria in categorias:
            conexao.execute(
                """
                INSERT INTO produtos (
                    id, codigo, nome, categoria, forma_venda,
                    preco_venda_centavos, origem, ativo,
                    criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, 'PESO', 7990, 'COMPRADO', 1,
                          '2026-01-01 10:00:00', '2026-02-01 11:00:00')
                """,
                (produto_id, codigo, f"Produto {codigo}", categoria),
            )
        primeiro_id, primeiro_codigo, _ = categorias[0]
        conexao.execute(
            "INSERT INTO vendas (id, total_centavos) VALUES (1, 1000)"
        )
        conexao.execute(
            """
            INSERT INTO itens_venda (
                venda_id, posicao, produto_id, codigo_snapshot,
                nome_snapshot, forma_venda_snapshot,
                preco_referencia_centavos, tipo_item, origem,
                origem_quantidade, quantidade_decimal, codigo_barras,
                subtotal_centavos
            ) VALUES (
                1, 0, ?, ?, 'Snapshot preservado', 'PESO', 7990,
                'PRODUTO', 'MANUAL', 'NAO_INFORMADA', NULL, NULL, 1000
            )
            """,
            (primeiro_id, primeiro_codigo),
        )
        conexao.execute(
            """
            INSERT INTO historico_precos_produtos (
                produto_id, preco_anterior_centavos, preco_novo_centavos
            ) VALUES (?, 7000, 7990)
            """,
            (primeiro_id,),
        )
        conexao.execute("PRAGMA user_version = 9")
        conexao.commit()
    finally:
        conexao.close()


def test_migracao_v9_v10_preserva_produtos_referencias_e_atributos(
    tmp_path,
) -> None:
    caminho = tmp_path / "categorias_v9.db"
    criar_banco_v9(caminho, ((7, "101", " Bovinos "), (11, "102", "BOVINOS")))

    criar_tabelas(caminho)

    with conectar(caminho) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 10
        colunas = {
            linha["name"] for linha in conexao.execute("PRAGMA table_info(produtos)")
        }
        assert "categoria_id" in colunas and "categoria" not in colunas
        produtos = conexao.execute(
            """
            SELECT p.id, p.codigo, c.nome, p.criado_em, p.atualizado_em
            FROM produtos AS p JOIN categorias AS c ON c.id = p.categoria_id
            ORDER BY p.id
            """
        ).fetchall()
        assert [tuple(linha) for linha in produtos] == [
            (7, "101", "Bovinos", "2026-01-01 10:00:00", "2026-02-01 11:00:00"),
            (11, "102", "Bovinos", "2026-01-01 10:00:00", "2026-02-01 11:00:00"),
        ]
        assert conexao.execute("SELECT produto_id FROM itens_venda").fetchone()[0] == 7
        assert conexao.execute(
            "SELECT produto_id FROM historico_precos_produtos"
        ).fetchone()[0] == 7
        assert conexao.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_migracao_normaliza_unicode_e_preserva_legados_invalidos(tmp_path) -> None:
    caminho = tmp_path / "categorias_legadas.db"
    criar_banco_v9(
        caminho,
        (
            (1, "101", "AÇÚCAR"),
            (2, "102", "açúcar"),
            (3, "103", "123"),
            (4, "104", "   "),
        ),
    )

    criar_tabelas(caminho)

    with conectar(caminho) as conexao:
        categorias = conexao.execute(
            "SELECT nome, ativo FROM categorias ORDER BY id"
        ).fetchall()
        assert [tuple(linha) for linha in categorias] == [
            ("AÇÚCAR", 1),
            ("123", 0),
            ("SEM CATEGORIA (LEGADO)", 0),
        ]
        ids = conexao.execute(
            "SELECT categoria_id FROM produtos WHERE id IN (1, 2) ORDER BY id"
        ).fetchall()
        assert ids[0][0] == ids[1][0]


def test_falha_na_migracao_reverte_produtos_categorias_e_versao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_categorias_v10.db"
    criar_banco_v9(caminho, ((5, "101", "BOVINOS"),))
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_INDICE_PRODUTOS_CATEGORIA",
        "COMANDO INVALIDO",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho)

    with conectar(caminho) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 9
        colunas = {
            linha["name"] for linha in conexao.execute("PRAGMA table_info(produtos)")
        }
        assert "categoria" in colunas and "categoria_id" not in colunas
        assert conexao.execute("SELECT categoria FROM produtos").fetchone()[0] == "BOVINOS"
        assert conexao.execute(
            "SELECT name FROM sqlite_master WHERE name = 'categorias'"
        ).fetchone() is None
        assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.fixture
def ambiente(tmp_path):
    caminho = tmp_path / "categorias.db"
    sessao = criar_sessao_admin_teste(caminho)
    return caminho, sessao


def test_crud_categoria_unicode_sem_exclusao_fisica(ambiente) -> None:
    caminho, sessao = ambiente
    categoria, erros = criar_categoria(sessao, "  Açúcar   Refinado  ", caminho)
    assert erros == []
    assert categoria.nome == "Açúcar Refinado"
    with pytest.raises(NomeCategoriaEmUsoError):
        criar_categoria(sessao, "AÇÚCAR REFINADO", caminho)

    renomeada, erros = renomear_categoria(sessao, categoria.id, "Doces", caminho)
    assert erros == [] and renomeada.nome == "Doces"
    inativa = alterar_situacao_categoria(sessao, categoria.id, False, caminho)
    assert not inativa.ativo
    reativada = alterar_situacao_categoria(sessao, categoria.id, True, caminho)
    assert reativada.ativo
    assert not hasattr(__import__("services.categoria_service", fromlist=["x"]), "excluir_categoria")


def test_servicos_de_categoria_rejeitam_caixa_e_sessao_fabricada(ambiente) -> None:
    caminho, sessao_admin = ambiente
    _, erros = criar_conta_caixa(
        sessao_admin, "caixa.cat", SENHA_CAIXA, SENHA_CAIXA, caminho
    )
    assert erros == []
    sessao_caixa = autenticar_usuario("caixa.cat", SENHA_CAIXA, caminho)
    fabricada = SessaoUsuario(
        sessao_admin.usuario_id,
        sessao_admin.identificacao_acesso,
        sessao_admin.perfil,
        sessao_admin.identificador_sessao,
    )
    with pytest.raises(PermissaoNegadaError):
        criar_categoria(sessao_caixa, "AVES", caminho)
    with pytest.raises(SessaoInvalidaError):
        listar_categorias(fabricada, caminho)


def test_produto_exige_categoria_ativa_mas_preserva_associacao_inativa(
    ambiente,
) -> None:
    caminho, sessao = ambiente
    bovinos, _ = criar_categoria(sessao, "BOVINOS", caminho)
    aves, _ = criar_categoria(sessao, "AVES", caminho)
    produto, erros = cadastrar_produto(
        "101", "Picanha", bovinos.nome, "PESO", 7990, "COMPRADO", caminho,
        categoria_id=bovinos.id,
        sessao_solicitante=sessao,
    )
    assert erros == []
    alterar_situacao_categoria(sessao, bovinos.id, False, caminho)

    preservado, erros = atualizar_produto(
        produto.id, produto.codigo, "Picanha premium", produto.categoria,
        produto.forma_venda, produto.preco_venda_centavos, produto.origem,
        caminho, categoria_id=bovinos.id,
        sessao_solicitante=sessao,
    )
    assert erros == [] and preservado.categoria_id == bovinos.id

    alterar_situacao_categoria(sessao, aves.id, False, caminho)
    rejeitado, erros = atualizar_produto(
        produto.id, produto.codigo, produto.nome, aves.nome,
        produto.forma_venda, produto.preco_venda_centavos, produto.origem,
        caminho, categoria_id=aves.id,
        sessao_solicitante=sessao,
    )
    assert rejeitado is None and erros == ["Selecione uma categoria ativa."]


def test_gravacao_e_desativacao_concorrentes_ficam_consistentes(ambiente) -> None:
    caminho, sessao = ambiente
    categoria, _ = criar_categoria(sessao, "BOVINOS", caminho)
    barreira = Barrier(2)
    resultados = []

    def gravar():
        barreira.wait()
        try:
            produto = salvar_produto(
                Produto(
                    "101", "Picanha", categoria.nome, "PESO", 7990,
                    "COMPRADO", categoria_id=categoria.id,
                ),
                caminho,
            )
            resultados.append(("produto", produto.id))
        except CategoriaProdutoIndisponivelError:
            resultados.append(("rejeitado", None))

    def desativar():
        barreira.wait()
        alterar_situacao_categoria(sessao, categoria.id, False, caminho)
        resultados.append(("inativa", None))

    threads = (Thread(target=gravar), Thread(target=desativar))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert all(not thread.is_alive() for thread in threads)
    assert ("inativa", None) in resultados
    produto = buscar_produto_por_codigo("101", caminho)
    if produto is None:
        assert ("rejeitado", None) in resultados
    else:
        assert produto.categoria_id == categoria.id


def test_dialogo_permite_primeira_categoria_e_combo_substitui_texto(
    ambiente,
    qtbot,
) -> None:
    caminho, sessao = ambiente
    dialogo = DialogoCategorias(sessao, caminho)
    qtbot.addWidget(dialogo)
    assert dialogo.tabela.rowCount() == 0
    dialogo.campo_nome.setText("BOVINOS")
    dialogo.cadastrar()
    assert dialogo.tabela.rowCount() == 1

    pagina = PaginaProdutos(caminho, sessao_administrativa=sessao)
    qtbot.addWidget(pagina)
    pagina.abrir_cadastro()
    formulario = pagina.dialogo_atual
    assert formulario.campo_categoria.currentData().nome == "BOVINOS"
    assert formulario.campo_categoria.isEditable() is False


def test_dialogo_categorias_usa_tabela_e_controles_proporcionais(
    ambiente,
    qtbot,
) -> None:
    caminho, sessao = ambiente
    criar_categoria(sessao, "BOVINOS", caminho)
    criar_categoria(sessao, "HORTIFRUTI E VERDURAS", caminho)
    dialogo = DialogoCategorias(sessao, caminho)
    qtbot.addWidget(dialogo)
    dialogo.show()
    dialogo.resize(620, 460)
    qtbot.wait(20)

    cabecalho = dialogo.tabela.horizontalHeader()
    assert cabecalho.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert cabecalho.sectionResizeMode(1) == (
        QHeaderView.ResizeMode.ResizeToContents
    )
    assert dialogo.tabela.columnWidth(0) > dialogo.tabela.columnWidth(1) * 2
    assert dialogo.campo_nome.maximumWidth() == 360
    assert dialogo.botao_cadastrar.width() < dialogo.width() / 2
    assert dialogo.botao_fechar.height() < 50
    assert "QDialog#dialogo_categorias" in dialogo.styleSheet()
