from dataclasses import replace

import pytest
from PySide6.QtWidgets import QDialog

from database.conexao import conectar
from database.schema import criar_tabelas
from interface.pagina_produtos import PaginaProdutos
from models.autorizacao_pontual import CapacidadeAutorizacao
from models.produto import Produto
from models.sessao_usuario import SessaoUsuario
from repositories.produto_repository import (
    ConflitoProdutoError,
    buscar_produto_por_codigo,
)
from services.autenticacao_service import (
    GERENCIADOR_SESSOES,
    PermissaoNegadaError,
    autenticar_usuario,
    encerrar_sessao,
)
from services.autorizacao_pontual_service import (
    AutorizacaoPontualConsumidaError,
    AutorizacaoPontualExpiradaError,
    AutorizacaoPontualInvalidaError,
    GerenciadorAutorizacoesPontuais,
    OPERACAO_CANCELAR_VENDA,
)
from services.categoria_service import criar_categoria, renomear_categoria
from services.produto_service import (
    alterar_situacao_produto,
    cadastrar_produto,
    executar_cadastro_produto,
    executar_edicao_produto,
    preparar_comando_cadastro_produto,
    preparar_comando_edicao_produto,
)
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_sessao_admin_teste,
)


SENHA_CAIXA = "frase segura caixa produtos autorizados 2026"


@pytest.fixture
def ambiente(tmp_path):
    caminho = tmp_path / "produtos_autorizados.db"
    criar_tabelas(caminho)
    sessoes = GERENCIADOR_SESSOES
    admin = criar_sessao_admin_teste(caminho)
    caixa_usuario, erros = criar_conta_caixa(
        admin,
        "caixa.produtos",
        SENHA_CAIXA,
        SENHA_CAIXA,
        caminho,
    )
    assert caixa_usuario is not None and erros == []
    caixa = autenticar_usuario(
        "caixa.produtos",
        SENHA_CAIXA,
        caminho,
    )
    gerenciador = GerenciadorAutorizacoesPontuais()
    categoria, erros = criar_categoria(admin, "BOVINOS", caminho)
    assert erros == []
    return caminho, sessoes, gerenciador, admin, caixa, categoria


def preparar_cadastro(ambiente, *, codigo="101", nome="Picanha"):
    caminho, _, _, _, _, categoria = ambiente
    comando, erros = preparar_comando_cadastro_produto(
        codigo,
        nome,
        categoria.nome,
        "PESO",
        7990,
        "COMPRADO",
        caminho,
        categoria_id=categoria.id,
    )
    assert erros == []
    return comando


def emitir(ambiente, comando):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    return gerenciador.emitir(
        caixa,
        comando.operacao,
        comando.recurso_id,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho,
        dados_autorizados_hash=comando.dados_autorizados_hash,
    )


def cadastrar_como_admin(ambiente, *, codigo="101"):
    caminho, _, _, admin, _, categoria = ambiente
    produto, erros = cadastrar_produto(
        codigo,
        "Picanha",
        categoria.nome,
        "PESO",
        7990,
        "COMPRADO",
        caminho,
        categoria_id=categoria.id,
        sessao_solicitante=admin,
    )
    assert erros == []
    return produto


def test_administrador_grava_diretamente_e_caixa_exige_capacidade(ambiente):
    caminho, _, gerenciador, admin, caixa, _ = ambiente
    comando = preparar_cadastro(ambiente)

    with pytest.raises(AutorizacaoPontualInvalidaError):
        executar_cadastro_produto(
            comando,
            caixa,
            caminho,
            gerenciador_autorizacoes=gerenciador,
        )
    produto = executar_cadastro_produto(comando, admin, caminho)

    assert produto.codigo == "101"
    assert caixa.perfil == "CAIXA"


def test_caixa_cadastra_com_capacidade_vinculada_ao_comando(ambiente):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    comando = preparar_cadastro(ambiente)
    capacidade = emitir(ambiente, comando)

    produto = executar_cadastro_produto(
        comando,
        caixa,
        caminho,
        capacidade=capacidade,
        gerenciador_autorizacoes=gerenciador,
    )

    assert produto.nome == "Picanha"
    with pytest.raises(AutorizacaoPontualConsumidaError):
        executar_cadastro_produto(
            comando,
            caixa,
            caminho,
            capacidade=capacidade,
            gerenciador_autorizacoes=gerenciador,
        )


def test_alterar_dado_depois_da_aprovacao_rejeita_e_consume(ambiente):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    aprovado = preparar_cadastro(ambiente)
    capacidade = emitir(ambiente, aprovado)
    alterado = replace(aprovado, nome="Produto diferente")

    with pytest.raises(AutorizacaoPontualInvalidaError):
        executar_cadastro_produto(
            alterado,
            caixa,
            caminho,
            capacidade=capacidade,
            gerenciador_autorizacoes=gerenciador,
        )
    assert buscar_produto_por_codigo("101", caminho) is None
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            caixa,
            aprovado.operacao,
            aprovado.recurso_id,
            caminho,
            dados_autorizados_hash=aprovado.dados_autorizados_hash,
        )


def test_edicao_caixa_preserva_historico_atomico(ambiente):
    caminho, _, gerenciador, _, caixa, categoria = ambiente
    produto = cadastrar_como_admin(ambiente)
    comando, erros = preparar_comando_edicao_produto(
        produto.id,
        produto.codigo,
        "Picanha premium",
        categoria.nome,
        produto.forma_venda,
        8990,
        produto.origem,
        caminho,
        categoria_id=categoria.id,
    )
    assert erros == []
    capacidade = emitir(ambiente, comando)

    atualizado = executar_edicao_produto(
        comando,
        caixa,
        caminho,
        capacidade=capacidade,
        gerenciador_autorizacoes=gerenciador,
    )
    with conectar(caminho) as conexao:
        historico = conexao.execute(
            "SELECT preco_anterior_centavos, preco_novo_centavos "
            "FROM historico_precos_produtos WHERE produto_id = ?",
            (produto.id,),
        ).fetchall()

    assert atualizado.nome == "Picanha premium"
    assert [tuple(linha) for linha in historico] == [(7990, 8990)]


def test_conflito_concorrente_nao_sobrescreve_produto(ambiente):
    caminho, _, gerenciador, _, caixa, categoria = ambiente
    produto = cadastrar_como_admin(ambiente)
    comando, erros = preparar_comando_edicao_produto(
        produto.id,
        produto.codigo,
        "Nome aprovado",
        categoria.nome,
        produto.forma_venda,
        produto.preco_venda_centavos,
        produto.origem,
        caminho,
        categoria_id=categoria.id,
    )
    assert erros == []
    capacidade = emitir(ambiente, comando)
    with conectar(caminho) as conexao:
        conexao.execute(
            "UPDATE produtos SET nome = 'Mudança concorrente' WHERE id = ?",
            (produto.id,),
        )
        conexao.commit()

    with pytest.raises(ConflitoProdutoError):
        executar_edicao_produto(
            comando,
            caixa,
            caminho,
            capacidade=capacidade,
            gerenciador_autorizacoes=gerenciador,
        )
    assert buscar_produto_por_codigo(produto.codigo, caminho).nome == (
        "Mudança concorrente"
    )


def test_categoria_renomeada_apos_aprovacao_gera_conflito(ambiente):
    caminho, _, gerenciador, admin, caixa, categoria = ambiente
    comando = preparar_cadastro(ambiente)
    capacidade = emitir(ambiente, comando)
    renomeada, erros = renomear_categoria(
        admin,
        categoria.id,
        "CARNES",
        caminho,
    )
    assert renomeada.nome == "CARNES" and erros == []

    with pytest.raises(ConflitoProdutoError):
        executar_cadastro_produto(
            comando,
            caixa,
            caminho,
            capacidade=capacidade,
            gerenciador_autorizacoes=gerenciador,
        )


def test_capacidades_de_produto_e_cancelamento_sao_incompativeis(ambiente):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    comando = preparar_cadastro(ambiente)
    produto_capacidade = emitir(ambiente, comando)

    with pytest.raises(AutorizacaoPontualInvalidaError):
        gerenciador.consumir(
            produto_capacidade,
            caixa,
            OPERACAO_CANCELAR_VENDA,
            1,
            caminho,
        )
    with pytest.raises(ValueError):
        gerenciador.emitir(
            caixa,
            OPERACAO_CANCELAR_VENDA,
            1,
            "administrador",
            SENHA_ADMIN_TESTE,
            caminho,
            dados_autorizados_hash=comando.dados_autorizados_hash,
        )


def test_logout_revoga_capacidade_e_sessao_caixa(ambiente):
    caminho, sessoes, gerenciador, _, caixa, _ = ambiente
    comando = preparar_cadastro(ambiente)
    capacidade = emitir(ambiente, comando)

    encerrar_sessao(
        caixa,
        gerenciador_sessoes=sessoes,
        gerenciador_autorizacoes=gerenciador,
    )

    assert not caixa.autenticada
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            caixa,
            comando.operacao,
            comando.recurso_id,
            caminho,
            dados_autorizados_hash=comando.dados_autorizados_hash,
        )


def test_sessao_fabricada_e_caixa_nao_alteram_situacao(ambiente):
    caminho, _, _, admin, caixa, _ = ambiente
    produto = cadastrar_como_admin(ambiente)
    fabricada = SessaoUsuario(
        caixa.usuario_id,
        caixa.identificacao_acesso,
        caixa.perfil,
        caixa.identificador_sessao,
    )

    with pytest.raises(Exception):
        cadastrar_produto(
            "102", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO",
            caminho, sessao_solicitante=fabricada,
        )
    with pytest.raises(PermissaoNegadaError):
        alterar_situacao_produto(
            produto.id,
            False,
            caminho,
            sessao_solicitante=caixa,
        )
    assert admin.perfil == "ADMINISTRADOR"


def test_interface_caixa_preserva_formulario_ao_recusar(
    ambiente,
    qtbot,
):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    pagina = PaginaProdutos(
        caminho,
        sessao_administrativa=caixa,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(pagina)
    pagina.abrir_cadastro()
    formulario = pagina.dialogo_atual
    formulario.campo_codigo.setText("101")
    formulario.campo_nome.setText("Picanha")
    formulario.campo_preco.setText("79,90")
    formulario.confirmar()
    autorizacao = pagina.dialogo_autorizacao_produto

    assert autorizacao is not None
    assert "Picanha" in autorizacao.findChild(
        type(autorizacao.rotulo_mensagem), "descricao_operacao_critica"
    ).text()
    autorizacao.reject()
    qtbot.waitUntil(lambda: pagina.dialogo_autorizacao_produto is None)

    assert formulario.isVisible()
    assert formulario.campo_nome.text() == "Picanha"
    assert buscar_produto_por_codigo("101", caminho) is None


def test_hash_isolado_nao_e_capacidade(ambiente):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    comando = preparar_cadastro(ambiente)

    with pytest.raises(AutorizacaoPontualInvalidaError):
        executar_cadastro_produto(
            comando,
            caixa,
            caminho,
            capacidade=CapacidadeAutorizacao(
                comando.dados_autorizados_hash
            ),
            gerenciador_autorizacoes=gerenciador,
        )


def test_autorizacao_expirada_nao_grava(ambiente):
    caminho, _, _, _, caixa, _ = ambiente
    instante = [100.0]
    gerenciador = GerenciadorAutorizacoesPontuais(
        validade_segundos=5,
        relogio=lambda: instante[0],
    )
    comando = preparar_cadastro(ambiente)
    capacidade = gerenciador.emitir(
        caixa,
        comando.operacao,
        comando.recurso_id,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho,
        dados_autorizados_hash=comando.dados_autorizados_hash,
    )
    instante[0] = 106.0

    with pytest.raises(AutorizacaoPontualExpiradaError):
        executar_cadastro_produto(
            comando,
            caixa,
            caminho,
            capacidade=capacidade,
            gerenciador_autorizacoes=gerenciador,
        )
    assert buscar_produto_por_codigo("101", caminho) is None


def test_interface_caixa_cadastra_sem_elevar_sessao(
    ambiente,
    qtbot,
):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    pagina = PaginaProdutos(
        caminho,
        sessao_administrativa=caixa,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(pagina)
    pagina.abrir_cadastro()
    formulario = pagina.dialogo_atual
    formulario.campo_codigo.setText("101")
    formulario.campo_nome.setText("Picanha")
    formulario.campo_preco.setText("79,90")
    formulario.confirmar()
    autorizacao = pagina.dialogo_autorizacao_produto
    autorizacao.campo_identificacao.setText("administrador")
    autorizacao.campo_senha.setText(SENHA_ADMIN_TESTE)
    autorizacao.autorizar()
    qtbot.waitUntil(lambda: pagina.dialogo_atual is None)

    assert buscar_produto_por_codigo("101", caminho) is not None
    assert caixa.perfil == "CAIXA"
    assert caixa.autenticada


def test_venda_aberta_bloqueia_edicao_do_caixa(ambiente, qtbot):
    caminho, _, gerenciador, _, caixa, _ = ambiente
    cadastrar_como_admin(ambiente)
    pagina = PaginaProdutos(
        caminho,
        sessao_administrativa=caixa,
        gerenciador_autorizacoes=gerenciador,
        tem_venda_em_andamento=lambda: True,
    )
    qtbot.addWidget(pagina)
    pagina.ativar()
    pagina.tabela_produtos.selectRow(0)

    pagina.abrir_edicao()

    assert pagina.dialogo_atual is None
    assert "venda em andamento" in pagina.rotulo_mensagem.text().lower()
