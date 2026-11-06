import pytest
from PySide6.QtWidgets import QDialog, QLineEdit

from database.conexao import conectar
from database.schema import criar_tabelas
from interface.dialogo_login import DialogoLogin
from interface.janela_principal import JanelaPrincipal
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import IdentificacaoUsuarioEmUsoError
from services.administrador_inicial_service import criar_administrador_inicial
from services.autenticacao_service import (
    CredenciaisInvalidasError,
    LimitadorTentativasLogin,
    PermissaoNegadaError,
    SessaoInvalidaError,
    TentativasLoginExcedidasError,
    autenticar_usuario,
    autorizar_sessao,
    encerrar_sessao,
)
from services.usuario_service import criar_conta_caixa


SENHA_ADMIN = "frase segura do administrador 2026"
SENHA_CAIXA = "frase segura do operador caixa 2026"


@pytest.fixture
def banco_autenticacao(tmp_path):
    caminho = tmp_path / "autenticacao.db"
    criar_tabelas(caminho)
    usuario, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ADMIN,
        SENHA_ADMIN,
        caminho,
    )
    assert usuario is not None
    assert erros == []
    return caminho


def autenticar_admin(caminho):
    return autenticar_usuario("administrador", SENHA_ADMIN, caminho)


def criar_caixa(caminho):
    usuario, erros = criar_conta_caixa(
        autenticar_admin(caminho),
        "caixa01",
        SENHA_CAIXA,
        SENHA_CAIXA,
        caminho,
    )
    assert usuario is not None
    assert erros == []
    return usuario


def test_login_administrador_e_caixa_criam_sessoes_minimas(
    banco_autenticacao,
) -> None:
    admin = autenticar_admin(banco_autenticacao)
    criar_caixa(banco_autenticacao)
    caixa = autenticar_usuario("CAIXA01", SENHA_CAIXA, banco_autenticacao)

    assert admin.perfil == "ADMINISTRADOR"
    assert caixa.perfil == "CAIXA"
    assert admin.autenticada and caixa.autenticada
    assert not hasattr(admin, "senha")
    assert "senha" not in repr(admin).lower()


@pytest.mark.parametrize("identificacao, senha", [
    ("administrador", "senha incorreta segura"),
    ("usuario-inexistente", SENHA_ADMIN),
])
def test_falhas_de_credencial_usam_mensagem_indistinguivel(
    banco_autenticacao,
    identificacao,
    senha,
) -> None:
    limitador = LimitadorTentativasLogin()
    with pytest.raises(CredenciaisInvalidasError) as erro:
        autenticar_usuario(
            identificacao,
            senha,
            banco_autenticacao,
            limitador=limitador,
        )
    assert str(erro.value) == "Identificação ou senha inválida."


def test_conta_inativa_e_hash_invalido_falham_sem_revelar_causa(
    banco_autenticacao,
) -> None:
    caixa = criar_caixa(banco_autenticacao)
    conexao = conectar(banco_autenticacao)
    try:
        conexao.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (caixa.id,))
        conexao.execute(
            "UPDATE usuarios SET senha_hash = 'hash-invalido' WHERE identificacao_acesso = 'administrador'"
        )
        conexao.commit()
    finally:
        conexao.close()

    for identificacao, senha in (("caixa01", SENHA_CAIXA), ("administrador", SENHA_ADMIN)):
        with pytest.raises(CredenciaisInvalidasError) as erro:
            autenticar_usuario(
                identificacao,
                senha,
                banco_autenticacao,
                limitador=LimitadorTentativasLogin(),
            )
        assert str(erro.value) == "Identificação ou senha inválida."


def test_limitador_bloqueia_temporariamente_e_libera_com_relogio(
    banco_autenticacao,
) -> None:
    instante = [100.0]
    limitador = LimitadorTentativasLogin(
        maximo_falhas=2,
        janela_segundos=60,
        espera_segundos=30,
        relogio=lambda: instante[0],
    )
    for _ in range(2):
        with pytest.raises(CredenciaisInvalidasError):
            autenticar_usuario(
                "administrador",
                "incorreta",
                banco_autenticacao,
                limitador=limitador,
            )
    with pytest.raises(TentativasLoginExcedidasError):
        autenticar_usuario(
            "administrador",
            SENHA_ADMIN,
            banco_autenticacao,
            limitador=limitador,
        )

    instante[0] += 31
    sessao = autenticar_usuario(
        "administrador",
        SENHA_ADMIN,
        banco_autenticacao,
        limitador=limitador,
    )
    assert sessao.autenticada


def test_criacao_caixa_exige_sessao_administrativa_ativa(
    banco_autenticacao,
) -> None:
    admin = autenticar_admin(banco_autenticacao)
    caixa, erros = criar_conta_caixa(
        admin,
        "caixa01",
        SENHA_CAIXA,
        SENHA_CAIXA,
        banco_autenticacao,
    )
    assert caixa.perfil == "CAIXA"
    assert erros == []

    sessao_caixa = autenticar_usuario("caixa01", SENHA_CAIXA, banco_autenticacao)
    with pytest.raises(PermissaoNegadaError):
        criar_conta_caixa(
            sessao_caixa,
            "caixa02",
            SENHA_CAIXA,
            SENHA_CAIXA,
            banco_autenticacao,
        )
    encerrar_sessao(admin)
    with pytest.raises(SessaoInvalidaError):
        criar_conta_caixa(
            admin,
            "caixa03",
            SENHA_CAIXA,
            SENHA_CAIXA,
            banco_autenticacao,
        )


def test_criacao_caixa_preserva_identificacao_unica(banco_autenticacao) -> None:
    criar_caixa(banco_autenticacao)
    with pytest.raises(IdentificacaoUsuarioEmUsoError):
        criar_conta_caixa(
            autenticar_admin(banco_autenticacao),
            "CAIXA01",
            SENHA_CAIXA,
            SENHA_CAIXA,
            banco_autenticacao,
        )


def test_logout_invalida_sessao(banco_autenticacao) -> None:
    sessao = autenticar_admin(banco_autenticacao)
    encerrar_sessao(sessao)
    assert not sessao.autenticada
    with pytest.raises(SessaoInvalidaError):
        autorizar_sessao(sessao, ("ADMINISTRADOR",), banco_autenticacao)


def test_desativacao_invalida_sessao_existente(banco_autenticacao) -> None:
    criar_caixa(banco_autenticacao)
    sessao = autenticar_usuario("caixa01", SENHA_CAIXA, banco_autenticacao)
    conexao = conectar(banco_autenticacao)
    try:
        conexao.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (sessao.usuario_id,))
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(SessaoInvalidaError):
        autorizar_sessao(sessao, ("CAIXA",), banco_autenticacao)
    assert not sessao.autenticada


def test_dialogo_login_oculta_senha_e_aceita_credencial_valida(
    qtbot,
    banco_autenticacao,
) -> None:
    dialogo = DialogoLogin(
        banco_autenticacao,
        limitador=LimitadorTentativasLogin(),
    )
    qtbot.addWidget(dialogo)
    assert dialogo.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    dialogo.campo_identificacao.setText("administrador")
    dialogo.campo_senha.setText(SENHA_ADMIN)
    dialogo.entrar()
    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert dialogo.sessao.autenticada
    assert dialogo.campo_senha.text() == ""


def test_caixa_acessa_produtos_sem_acesso_administrativo(
    qtbot,
    banco_autenticacao,
) -> None:
    criar_caixa(banco_autenticacao)
    sessao_caixa = autenticar_usuario("caixa01", SENHA_CAIXA, banco_autenticacao)
    janela_caixa = JanelaPrincipal(banco_autenticacao, sessao_caixa)
    qtbot.addWidget(janela_caixa)
    assert janela_caixa.botao_navegar_produtos.isEnabled()
    janela_caixa.mostrar_produtos()
    assert janela_caixa.paginas.currentWidget() is janela_caixa.pagina_produtos
    assert not janela_caixa.pagina_produtos.botao_alterar_situacao.isEnabled()
    assert not janela_caixa.pagina_produtos.botao_gerenciar_categorias.isEnabled()

    janela_admin = JanelaPrincipal(banco_autenticacao, autenticar_admin(banco_autenticacao))
    qtbot.addWidget(janela_admin)
    assert janela_admin.botao_navegar_produtos.isEnabled()
    janela_admin.mostrar_produtos()
    assert janela_admin.paginas.currentWidget() is janela_admin.pagina_produtos


def test_janela_rejeita_ausencia_de_sessao(banco_autenticacao) -> None:
    with pytest.raises(SessaoInvalidaError):
        JanelaPrincipal(banco_autenticacao, None)


def test_sessao_fabricada_e_rejeitada(banco_autenticacao) -> None:
    legitima = autenticar_admin(banco_autenticacao)
    fabricada = SessaoUsuario(
        usuario_id=legitima.usuario_id,
        identificacao_acesso=legitima.identificacao_acesso,
        perfil=legitima.perfil,
        identificador_sessao=legitima.identificador_sessao,
    )

    with pytest.raises(SessaoInvalidaError, match="gerenciador confiável"):
        autorizar_sessao(
            fabricada,
            ("ADMINISTRADOR",),
            banco_autenticacao,
        )


def test_logout_grafico_fecha_janela_e_preserva_banco(
    qtbot,
    banco_autenticacao,
) -> None:
    sessao = autenticar_admin(banco_autenticacao)
    janela = JanelaPrincipal(banco_autenticacao, sessao)
    qtbot.addWidget(janela)
    janela.show()
    janela.solicitar_logout()
    assert not sessao.autenticada
    assert not janela.isVisible()
    conexao = conectar(banco_autenticacao)
    try:
        assert conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 1
    finally:
        conexao.close()
