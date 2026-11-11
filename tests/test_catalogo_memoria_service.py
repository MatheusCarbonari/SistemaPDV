from dataclasses import FrozenInstanceError
from decimal import Decimal
import os
import sqlite3

import pytest

from database.conexao import conectar
from database.schema import criar_tabelas
from models.produto import Produto
from repositories.produto_repository import (
    buscar_produto_por_codigo,
    salvar_produto,
)
import services.catalogo_memoria_service as catalogo_module
import services.produto_service as produto_service
from services.catalogo_memoria_service import (
    CATALOGO_DISPONIVEL,
    CATALOGO_INDISPONIVEL,
    CatalogoInconsistenteError,
    CatalogoIndisponivelError,
    CatalogoBancoDivergenteError,
    CatalogoProdutosMemoria,
)
from services.item_venda_service import (
    criar_item_de_etiqueta_com_estimativa,
    criar_item_manual_unidade,
)
from services.produto_etiqueta import associar_etiqueta_ao_catalogo
from tests.helpers_identidade import criar_sessao_admin_teste


def _salvar_produto(
    caminho_banco,
    *,
    codigo="234",
    nome="Picanha",
    forma_venda="PESO",
    preco=7990,
    ativo=True,
):
    produto = salvar_produto(
        Produto(
            codigo=codigo,
            nome=nome,
            categoria="BOVINOS",
            forma_venda=forma_venda,
            preco_venda_centavos=preco,
            origem="COMPRADO",
        ),
        caminho_banco,
    )
    if not ativo:
        conexao = conectar(caminho_banco)
        try:
            conexao.execute(
                "UPDATE produtos SET ativo = 0 WHERE id = ?",
                (produto.id,),
            )
            conexao.commit()
        finally:
            conexao.close()
    return produto


def test_carrega_snapshot_valido_com_produtos_ativos_e_inativos(tmp_path) -> None:
    banco = tmp_path / "catalogo.db"
    criar_tabelas(banco)
    _salvar_produto(banco, codigo="101", nome="Ativo")
    _salvar_produto(banco, codigo="102", nome="Inativo", ativo=False)
    catalogo = CatalogoProdutosMemoria()

    estado = catalogo.carregar(banco)

    assert estado.status == CATALOGO_DISPONIVEL
    assert estado.quantidade_produtos == 2
    assert estado.carregado_em is not None
    assert catalogo.consultar_produto("101").ativo is True
    assert catalogo.consultar_produto("102").ativo is False


def test_catalogo_vazio_e_snapshot_valido(tmp_path) -> None:
    banco = tmp_path / "catalogo_vazio.db"
    criar_tabelas(banco)
    catalogo = CatalogoProdutosMemoria()

    estado = catalogo.carregar(banco)

    assert estado.status == CATALOGO_DISPONIVEL
    assert estado.quantidade_produtos == 0
    assert catalogo.listar_entradas() == ()
    assert catalogo.consultar_produto("999") is None


def test_janela_carrega_catalogo_inicial_apos_autenticacao(qtbot, tmp_path) -> None:
    from interface.janela_principal import JanelaPrincipal

    banco = tmp_path / "catalogo_inicial.db"
    sessao = criar_sessao_admin_teste(banco)
    _salvar_produto(banco, codigo="101")

    janela = JanelaPrincipal(banco, sessao)
    qtbot.addWidget(janela)

    estado = janela.catalogo_produtos.obter_estado()
    assert estado.status == CATALOGO_DISPONIVEL
    assert estado.quantidade_produtos == 1


def test_falha_de_leitura_deixa_catalogo_explicitamente_indisponivel(
    tmp_path,
    monkeypatch,
) -> None:
    catalogo = CatalogoProdutosMemoria()
    monkeypatch.setattr(
        catalogo_module,
        "listar_produtos_repository",
        lambda **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("banco indisponível")
        ),
    )

    with pytest.raises(sqlite3.OperationalError):
        catalogo.carregar(tmp_path / "indisponivel.db")

    estado = catalogo.obter_estado()
    assert estado.status == CATALOGO_INDISPONIVEL
    assert estado.quantidade_produtos == 0
    assert estado.motivo_indisponibilidade == "FALHA_CARGA:OperationalError"
    with pytest.raises(CatalogoIndisponivelError):
        catalogo.consultar_produto("101")


def test_falha_parcial_descarta_snapshot_anterior_sem_publicar_parcial(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "catalogo_parcial.db"
    criar_tabelas(banco)
    produto = _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    monkeypatch.setattr(
        catalogo_module,
        "listar_produtos_repository",
        lambda **kwargs: [produto, object()],
    )

    with pytest.raises(CatalogoInconsistenteError):
        catalogo.carregar(banco)

    assert catalogo.obter_estado().status == CATALOGO_INDISPONIVEL
    with pytest.raises(CatalogoIndisponivelError):
        catalogo.listar_entradas()


def test_entradas_e_consultas_sao_imutaveis(tmp_path) -> None:
    banco = tmp_path / "catalogo_imutavel.db"
    criar_tabelas(banco)
    _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    entrada = catalogo.listar_entradas()[0]

    with pytest.raises(FrozenInstanceError):
        entrada.codigo = "999"

    consultado = catalogo.consultar_produto("101")
    with pytest.raises(FrozenInstanceError):
        consultado.codigo = "999"
    assert catalogo.consultar_produto("101").codigo == "101"


def test_recarga_reflete_mudanca_de_codigo_e_preco_sem_misturar_versoes(
    tmp_path,
) -> None:
    banco = tmp_path / "catalogo_atualizado.db"
    sessao = criar_sessao_admin_teste(banco)
    produto = _salvar_produto(banco, codigo="101", preco=1000)
    catalogo = CatalogoProdutosMemoria()
    primeira_geracao = catalogo.carregar(banco).geracao

    atualizado, erros = produto_service.atualizar_produto(
        produto.id,
        "202",
        produto.nome,
        produto.categoria,
        produto.forma_venda,
        2500,
        produto.origem,
        banco,
        categoria_id=produto.categoria_id,
        sessao_solicitante=sessao,
        catalogo_produtos=catalogo,
    )

    assert atualizado is not None
    assert erros == []
    assert catalogo.obter_estado().geracao == primeira_geracao + 1
    assert catalogo.consultar_produto("101") is None
    assert catalogo.consultar_produto("202").preco_venda_centavos == 2500


def test_mutacao_de_situacao_recarrega_catalogo(tmp_path) -> None:
    banco = tmp_path / "catalogo_situacao.db"
    sessao = criar_sessao_admin_teste(banco)
    produto = _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)

    atualizado, erros = produto_service.alterar_situacao_produto(
        produto.id,
        False,
        banco,
        sessao_solicitante=sessao,
        catalogo_produtos=catalogo,
    )

    assert atualizado is True
    assert erros == []
    assert catalogo.consultar_produto("101").ativo is False


def test_cadastro_integrado_recarrega_catalogo(tmp_path) -> None:
    banco = tmp_path / "catalogo_cadastro.db"
    sessao = criar_sessao_admin_teste(banco)
    produto_base = _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    comando, erros = produto_service.preparar_comando_cadastro_produto(
        "202",
        "Produto novo",
        produto_base.categoria,
        "UNIDADE",
        2500,
        produto_base.origem,
        banco,
        categoria_id=produto_base.categoria_id,
    )
    assert erros == []

    produto_service.executar_cadastro_produto(
        comando,
        sessao,
        banco,
        catalogo_produtos=catalogo,
    )

    assert catalogo.consultar_produto("202").preco_venda_centavos == 2500


def test_falha_de_recarga_apos_mutacao_invalida_catalogo(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "catalogo_invalido_apos_mutacao.db"
    sessao = criar_sessao_admin_teste(banco)
    produto = _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    monkeypatch.setattr(
        catalogo_module,
        "listar_produtos_repository",
        lambda **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("falha na recarga")
        ),
    )

    atualizado, erros = produto_service.alterar_situacao_produto(
        produto.id,
        False,
        banco,
        sessao_solicitante=sessao,
        catalogo_produtos=catalogo,
    )

    assert atualizado is True
    assert erros == []
    assert catalogo.obter_estado().status == CATALOGO_INDISPONIVEL
    with pytest.raises(CatalogoIndisponivelError):
        catalogo.consultar_produto("101")


def test_snapshot_continua_consultavel_sem_nova_leitura_sqlite(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "catalogo_degradado.db"
    criar_tabelas(banco)
    _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    monkeypatch.setattr(
        catalogo_module,
        "listar_produtos_repository",
        lambda **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("sqlite indisponível")
        ),
    )

    produto = catalogo.consultar_produto("101")

    assert produto.nome == "Picanha"
    assert catalogo.obter_estado().status == CATALOGO_DISPONIVEL


def test_produto_do_catalogo_preserva_regras_de_etiqueta_e_calculo(
    tmp_path,
) -> None:
    banco = tmp_path / "catalogo_calculo.db"
    criar_tabelas(banco)
    _salvar_produto(banco, codigo="234", preco=7990)
    _salvar_produto(
        banco,
        codigo="11",
        nome="Espetinho",
        forma_venda="UNIDADE",
        preco=1500,
    )
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)

    produto_etiqueta, erros = associar_etiqueta_ao_catalogo(
        "2023400053672",
        catalogo,
    )
    item_etiqueta = criar_item_de_etiqueta_com_estimativa(produto_etiqueta)
    produto_unidade, erros_unidade = produto_service.consultar_produto_no_catalogo(
        " 11 ",
        catalogo,
    )
    item_manual = criar_item_manual_unidade(
        produto_unidade,
        Decimal("2"),
    )

    assert erros == []
    assert erros_unidade == []
    assert item_etiqueta.subtotal_centavos == 5367
    assert item_manual.subtotal_centavos == 3000


def test_associacao_de_etiqueta_recusa_produto_inativo_do_catalogo(
    tmp_path,
) -> None:
    banco = tmp_path / "catalogo_etiqueta_inativa.db"
    criar_tabelas(banco)
    _salvar_produto(banco, codigo="234", ativo=False)
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)

    associacao, erros = associar_etiqueta_ao_catalogo(
        "2023400053672",
        catalogo,
    )

    assert associacao is None
    assert erros == ["O produto associado à etiqueta está inativo."]


def test_falha_de_gravacao_nao_e_substituida_por_alteracao_em_memoria(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "catalogo_sem_persistencia_ficticia.db"
    sessao = criar_sessao_admin_teste(banco)
    produto = _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    monkeypatch.setattr(
        produto_service,
        "alterar_situacao_produto_repository",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("gravação indisponível")
        ),
    )

    with pytest.raises(sqlite3.OperationalError):
        produto_service.alterar_situacao_produto(
            produto.id,
            False,
            banco,
            sessao_solicitante=sessao,
            catalogo_produtos=catalogo,
        )

    assert catalogo.consultar_produto("101").ativo is True


def test_recarga_com_outro_banco_e_rejeitada_sem_publicar_seus_dados(
    tmp_path,
) -> None:
    banco_a = tmp_path / "producao.db"
    banco_b = tmp_path / "homologacao.db"
    criar_tabelas(banco_a)
    criar_tabelas(banco_b)
    _salvar_produto(banco_a, codigo="101", preco=1000)
    _salvar_produto(banco_b, codigo="101", preco=9000)
    catalogo = CatalogoProdutosMemoria()
    estado_original = catalogo.carregar(banco_a)

    with pytest.raises(
        CatalogoBancoDivergenteError,
        match="pertence a outro banco SQLite",
    ):
        catalogo.carregar(banco_b)

    estado_final = catalogo.obter_estado()
    assert estado_final == estado_original
    assert catalogo.consultar_produto("101").preco_venda_centavos == 1000
    assert buscar_produto_por_codigo("101", banco_a).preco_venda_centavos == 1000
    assert buscar_produto_por_codigo("101", banco_b).preco_venda_centavos == 9000
    assert str(banco_a) not in repr(estado_final)
    assert str(banco_b) not in repr(estado_final)


def test_atualizacao_com_outro_banco_preserva_snapshot_e_estado(tmp_path) -> None:
    banco_a = tmp_path / "origem.db"
    banco_b = tmp_path / "outra_origem.db"
    criar_tabelas(banco_a)
    criar_tabelas(banco_b)
    _salvar_produto(banco_a, codigo="101", preco=1000)
    _salvar_produto(banco_b, codigo="101", preco=9000)
    catalogo = CatalogoProdutosMemoria()
    estado_original = catalogo.carregar(banco_a)

    with pytest.raises(CatalogoBancoDivergenteError):
        catalogo.atualizar_apos_mutacao(banco_b)

    assert catalogo.obter_estado() == estado_original
    assert catalogo.consultar_produto("101").preco_venda_centavos == 1000


def test_caminho_relativo_e_absoluto_do_mesmo_banco_sao_equivalentes(
    tmp_path,
) -> None:
    banco = tmp_path / "mesmo_banco.db"
    criar_tabelas(banco)
    _salvar_produto(banco, codigo="101", preco=1000)
    catalogo = CatalogoProdutosMemoria()
    primeira_geracao = catalogo.carregar(banco.resolve()).geracao
    caminho_relativo = os.path.relpath(banco, start=os.getcwd())

    estado = catalogo.carregar(caminho_relativo)

    assert estado.geracao == primeira_geracao + 1
    assert catalogo.consultar_produto("101").preco_venda_centavos == 1000


def test_catalogo_de_outro_banco_bloqueia_mutacoes_antes_de_gravar(
    tmp_path,
) -> None:
    banco_a = tmp_path / "ambiente_a.db"
    banco_b = tmp_path / "ambiente_b.db"
    criar_tabelas(banco_a)
    sessao_b = criar_sessao_admin_teste(banco_b)
    produto_a = _salvar_produto(banco_a, codigo="101", preco=1000)
    produto_b = _salvar_produto(banco_b, codigo="101", preco=9000)
    catalogo = CatalogoProdutosMemoria()
    estado_original = catalogo.carregar(banco_a)

    comando_cadastro, erros = produto_service.preparar_comando_cadastro_produto(
        "303",
        "Novo",
        produto_b.categoria,
        "UNIDADE",
        3000,
        produto_b.origem,
        banco_b,
        categoria_id=produto_b.categoria_id,
    )
    assert erros == []
    with pytest.raises(CatalogoBancoDivergenteError):
        produto_service.executar_cadastro_produto(
            comando_cadastro,
            sessao_b,
            banco_b,
            catalogo_produtos=catalogo,
        )

    comando_edicao, erros = produto_service.preparar_comando_edicao_produto(
        produto_b.id,
        "202",
        produto_b.nome,
        produto_b.categoria,
        produto_b.forma_venda,
        2500,
        produto_b.origem,
        banco_b,
        categoria_id=produto_b.categoria_id,
    )
    assert erros == []
    with pytest.raises(CatalogoBancoDivergenteError):
        produto_service.executar_edicao_produto(
            comando_edicao,
            sessao_b,
            banco_b,
            catalogo_produtos=catalogo,
        )

    with pytest.raises(CatalogoBancoDivergenteError):
        produto_service.alterar_situacao_produto(
            produto_b.id,
            False,
            banco_b,
            sessao_solicitante=sessao_b,
            catalogo_produtos=catalogo,
        )

    assert buscar_produto_por_codigo("303", banco_b) is None
    produto_b_final = buscar_produto_por_codigo("101", banco_b)
    assert produto_b_final.codigo == "101"
    assert produto_b_final.preco_venda_centavos == 9000
    assert produto_b_final.ativo is True
    assert buscar_produto_por_codigo("101", banco_a).preco_venda_centavos == 1000
    assert catalogo.obter_estado() == estado_original
    assert catalogo.consultar_produto("101").id == produto_a.id


def test_mutacao_externa_sem_catalogo_nao_sincroniza_snapshot(tmp_path) -> None:
    banco = tmp_path / "chamada_externa.db"
    sessao = criar_sessao_admin_teste(banco)
    produto = _salvar_produto(banco, codigo="101")
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)

    atualizado, erros = produto_service.alterar_situacao_produto(
        produto.id,
        False,
        banco,
        sessao_solicitante=sessao,
    )

    assert atualizado is True
    assert erros == []
    assert buscar_produto_por_codigo("101", banco).ativo is False
    assert catalogo.consultar_produto("101").ativo is True
