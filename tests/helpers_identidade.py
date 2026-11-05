from database.schema import criar_tabelas
from services.administrador_inicial_service import criar_administrador_inicial
from services.autenticacao_service import autenticar_usuario
from services.autenticacao_service import GerenciadorSessoes
from services.autorizacao_pontual_service import (
    OPERACAO_CANCELAR_VENDA,
    GerenciadorAutorizacoesPontuais,
)


SENHA_ADMIN_TESTE = "frase segura exclusiva dos testes 2026"


def criar_sessao_admin_teste(caminho_banco, *, gerenciador_sessoes=None):
    criar_tabelas(caminho_banco)
    usuario, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ADMIN_TESTE,
        SENHA_ADMIN_TESTE,
        caminho_banco,
    )
    assert usuario is not None
    assert erros == []
    return autenticar_usuario(
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho_banco,
        **(
            {"gerenciador_sessoes": gerenciador_sessoes}
            if gerenciador_sessoes is not None
            else {}
        ),
    )


def criar_janela_autenticada(caminho_banco):
    from interface.janela_principal import JanelaPrincipal

    sessao = criar_sessao_admin_teste(caminho_banco)
    return JanelaPrincipal(caminho_banco, sessao)


def criar_ambiente_autorizacao_teste(caminho_banco):
    gerenciador_sessoes = GerenciadorSessoes()
    sessao = criar_sessao_admin_teste(
        caminho_banco,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    gerenciador_autorizacoes = GerenciadorAutorizacoesPontuais(
        gerenciador_sessoes=gerenciador_sessoes,
    )
    return sessao, gerenciador_autorizacoes


def emitir_cancelamento_teste(
    caminho_banco,
    venda_id,
    sessao,
    gerenciador_autorizacoes,
):
    return gerenciador_autorizacoes.emitir(
        sessao,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho_banco,
    )
