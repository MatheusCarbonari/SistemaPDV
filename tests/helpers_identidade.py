from database.schema import criar_tabelas
from services.administrador_inicial_service import criar_administrador_inicial
from services.autenticacao_service import autenticar_usuario


SENHA_ADMIN_TESTE = "frase segura exclusiva dos testes 2026"


def criar_sessao_admin_teste(caminho_banco):
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
    )


def criar_janela_autenticada(caminho_banco):
    from interface.janela_principal import JanelaPrincipal

    sessao = criar_sessao_admin_teste(caminho_banco)
    return JanelaPrincipal(caminho_banco, sessao)
