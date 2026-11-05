import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from database.conexao import conectar
from database.schema import criar_tabelas
import interface.aplicacao as aplicacao_module
from interface.dialogo_login import DialogoLogin
from interface.janela_principal import JanelaPrincipal
from models.item_venda import ItemVenda
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import buscar_usuario_para_autenticacao
from services.administrador_inicial_service import criar_administrador_inicial
from services.autenticacao_service import (
    CredenciaisInvalidasError,
    GerenciadorSessoes,
    LimitadorTentativasLogin,
    PermissaoNegadaError,
    SessaoInvalidaError,
    autenticar_usuario,
)
from services.autorizacao_pontual_service import (
    OPERACAO_CANCELAR_VENDA,
    AutorizacaoPontualConsumidaError,
    GerenciadorAutorizacoesPontuais,
)
from services.senha_service import verificar_senha
from services.usuario_service import (
    alterar_situacao_conta_caixa,
    criar_conta_caixa,
    listar_contas_caixa,
)


SENHA_ADMIN = "frase administrativa para int e 2026"
SENHA_CAIXA = "frase individual do operador caixa 2026"


@pytest.fixture
def ambiente(qtbot, tmp_path):
    caminho = tmp_path / "gestao_operadores.db"
    criar_tabelas(caminho)
    administrador, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ADMIN,
        SENHA_ADMIN,
        caminho,
    )
    assert administrador is not None and erros == []
    sessao_admin = autenticar_usuario("administrador", SENHA_ADMIN, caminho)
    janela = JanelaPrincipal(caminho, sessao_admin)
    qtbot.addWidget(janela)
    janela.show()
    return caminho, sessao_admin, janela


def cadastrar_caixa(caminho, sessao_admin, identificacao="caixa01"):
    usuario, erros = criar_conta_caixa(
        sessao_admin,
        identificacao,
        SENHA_CAIXA,
        SENHA_CAIXA,
        caminho,
    )
    assert usuario is not None and erros == []
    return usuario


def abrir_administracao(janela):
    janela.mostrar_administracao()
    assert janela.paginas.currentWidget() is janela.pagina_administracao
    return janela.pagina_administracao


def test_login_administrador_exibe_identidade_e_administracao(ambiente) -> None:
    _, sessao, janela = ambiente

    assert sessao.perfil == "ADMINISTRADOR"
    assert janela.rotulo_usuario.text() == "administrador (ADMINISTRADOR)"
    assert janela.botao_navegar_administracao.isEnabled()
    assert abrir_administracao(janela).tabela_operadores.rowCount() == 0


def test_login_caixa_opera_sem_acesso_administrativo(ambiente, qtbot) -> None:
    caminho, sessao_admin, janela_admin = ambiente
    cadastrar_caixa(caminho, sessao_admin)
    janela_admin.close()
    sessao_caixa = autenticar_usuario("caixa01", SENHA_CAIXA, caminho)
    janela = JanelaPrincipal(caminho, sessao_caixa)
    qtbot.addWidget(janela)
    janela.show()

    assert janela.rotulo_usuario.text() == "caixa01 (CAIXA)"
    assert not janela.botao_navegar_administracao.isEnabled()
    assert not janela.botao_navegar_produtos.isEnabled()
    janela.mostrar_administracao()
    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert "exige perfil Administrador" in janela.rotulo_status.text()


def test_interface_cadastra_caixa_e_atualiza_lista(ambiente) -> None:
    caminho, _, janela = ambiente
    pagina = abrir_administracao(janela)
    pagina.campo_identificacao.setText("  CAIXA.NOVO  ")
    pagina.campo_senha.setText(SENHA_CAIXA)
    pagina.campo_confirmacao.setText(SENHA_CAIXA)

    pagina.cadastrar_operador()

    assert pagina.tabela_operadores.rowCount() == 1
    assert pagina.tabela_operadores.item(0, 0).text() == "caixa.novo"
    assert pagina.tabela_operadores.item(0, 1).text() == "CAIXA"
    assert pagina.tabela_operadores.item(0, 2).text() == "Ativa"
    assert "cadastrado com sucesso" in pagina.rotulo_mensagem.text()
    linha = buscar_usuario_para_autenticacao("caixa.novo", caminho)
    assert linha["senha_hash"] != SENHA_CAIXA
    assert verificar_senha(SENHA_CAIXA, linha["senha_hash"])


def test_dados_invalidos_e_identificacao_duplicada_sao_tratados(
    ambiente,
) -> None:
    _, _, janela = ambiente
    pagina = abrir_administracao(janela)
    pagina.campo_identificacao.setText("x")
    pagina.campo_senha.setText("curta")
    pagina.campo_confirmacao.setText("diferente")

    pagina.cadastrar_operador()

    assert "entre 3 e 64" in pagina.rotulo_mensagem.text()
    assert pagina.campo_senha.text() == ""
    assert pagina.campo_confirmacao.text() == ""

    pagina.campo_identificacao.setText("caixa01")
    pagina.campo_senha.setText(SENHA_CAIXA)
    pagina.campo_confirmacao.setText(SENHA_CAIXA)
    pagina.cadastrar_operador()
    pagina.campo_identificacao.setText("CAIXA01")
    pagina.campo_senha.setText(SENHA_CAIXA)
    pagina.campo_confirmacao.setText(SENHA_CAIXA)
    pagina.cadastrar_operador()
    assert "já está em uso" in pagina.rotulo_mensagem.text()
    assert pagina.tabela_operadores.rowCount() == 1


def test_senha_inicial_permanece_oculta_e_fora_da_sessao(ambiente) -> None:
    _, _, janela = ambiente
    pagina = abrir_administracao(janela)

    assert pagina.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    assert pagina.campo_confirmacao.echoMode() == QLineEdit.EchoMode.Password
    assert not hasattr(janela.sessao, "senha")
    assert SENHA_CAIXA not in repr(janela.sessao)


def test_interface_desativa_e_reativa_conta_caixa(ambiente) -> None:
    caminho, _, janela = ambiente
    pagina = abrir_administracao(janela)
    pagina.campo_identificacao.setText("caixa01")
    pagina.campo_senha.setText(SENHA_CAIXA)
    pagina.campo_confirmacao.setText(SENHA_CAIXA)
    pagina.cadastrar_operador()
    pagina.tabela_operadores.selectRow(0)

    pagina.alterar_situacao_selecionada()

    assert pagina.tabela_operadores.item(0, 2).text() == "Inativa"
    with pytest.raises(CredenciaisInvalidasError):
        autenticar_usuario(
            "caixa01",
            SENHA_CAIXA,
            caminho,
            limitador=LimitadorTentativasLogin(),
        )

    pagina.tabela_operadores.selectRow(0)
    pagina.alterar_situacao_selecionada()
    assert pagina.tabela_operadores.item(0, 2).text() == "Ativa"
    assert autenticar_usuario("caixa01", SENHA_CAIXA, caminho).autenticada


def test_servicos_administrativos_rejeitam_caixa(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)
    sessao_caixa = autenticar_usuario("caixa01", SENHA_CAIXA, caminho)

    with pytest.raises(PermissaoNegadaError):
        listar_contas_caixa(sessao_caixa, caminho)
    with pytest.raises(PermissaoNegadaError):
        criar_conta_caixa(
            sessao_caixa,
            "caixa02",
            SENHA_CAIXA,
            SENHA_CAIXA,
            caminho,
        )
    with pytest.raises(PermissaoNegadaError):
        alterar_situacao_conta_caixa(
            sessao_caixa,
            usuario.id,
            False,
            caminho,
        )


def test_servicos_rejeitam_sessao_administrativa_fabricada(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    fabricada = SessaoUsuario(
        sessao_admin.usuario_id,
        sessao_admin.identificacao_acesso,
        sessao_admin.perfil,
        sessao_admin.identificador_sessao,
    )

    with pytest.raises(SessaoInvalidaError):
        listar_contas_caixa(fabricada, caminho)
    with pytest.raises(SessaoInvalidaError):
        criar_conta_caixa(
            fabricada,
            "caixa02",
            SENHA_CAIXA,
            SENHA_CAIXA,
            caminho,
        )


def test_desativacao_revoga_sessao_e_autorizacao_do_caixa(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)
    gerenciador_sessoes = GerenciadorSessoes()
    sessao_caixa = autenticar_usuario(
        "caixa01",
        SENHA_CAIXA,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    gerenciador_autorizacoes = GerenciadorAutorizacoesPontuais(
        gerenciador_sessoes=gerenciador_sessoes,
    )
    capacidade = gerenciador_autorizacoes.emitir(
        sessao_caixa,
        OPERACAO_CANCELAR_VENDA,
        10,
        "administrador",
        SENHA_ADMIN,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )

    alterar_situacao_conta_caixa(
        sessao_admin,
        usuario.id,
        False,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
        gerenciador_autorizacoes=gerenciador_autorizacoes,
    )

    assert not sessao_caixa.autenticada
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador_autorizacoes.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            10,
            caminho,
        )


def test_logout_sem_atendimento_invalida_sessao(ambiente) -> None:
    _, sessao, janela = ambiente
    eventos = []
    janela.logout_realizado.connect(lambda: eventos.append(True))

    janela.solicitar_logout()

    assert not sessao.autenticada
    assert eventos == [True]
    assert not janela.isVisible()


def test_logout_e_fechamento_da_janela_bloqueiam_atendimento_pendente(
    ambiente,
) -> None:
    _, sessao, janela = ambiente
    janela.item_criado.emit(
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=1000,
            origem_quantidade="NAO_INFORMADA",
            tipo_item="DIVERSOS",
        )
    )

    janela.solicitar_logout()

    assert sessao.autenticada
    assert janela.isVisible()
    assert "Finalize ou esvazie" in janela.rotulo_status.text()
    assert not janela.close()
    assert sessao.autenticada


def test_commit_incerto_bloqueia_logout_e_administracao(ambiente) -> None:
    _, sessao, janela = ambiente
    janela._fechamento_incerto = True
    janela._atualizar_venda_exibida()

    janela.solicitar_logout()
    janela.mostrar_administracao()

    assert sessao.autenticada
    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert not janela.botao_navegar_administracao.isEnabled()
    assert "fechamento pendente" in janela.rotulo_status.text()


def test_login_preserva_acao_de_recuperacao_t48(ambiente, qtbot) -> None:
    caminho, _, _ = ambiente
    dialogo = DialogoLogin(
        caminho,
        limitador=LimitadorTentativasLogin(),
        limitador_recuperacao=LimitadorTentativasLogin(),
    )
    qtbot.addWidget(dialogo)

    assert dialogo.botao_recuperar.text() == "Recuperar acesso"
    dialogo.abrir_recuperacao()
    assert dialogo.dialogo_recuperacao is not None
    assert dialogo.sessao is None


def test_navegacao_preserva_frente_historico_produtos_e_administracao(
    ambiente,
) -> None:
    _, _, janela = ambiente

    janela.mostrar_historico()
    assert janela.paginas.currentWidget() is janela.pagina_historico
    janela.mostrar_produtos()
    assert janela.paginas.currentWidget() is janela.pagina_produtos
    janela.mostrar_administracao()
    assert janela.paginas.currentWidget() is janela.pagina_administracao
    janela.mostrar_frente_caixa()
    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa


def test_bootstrap_reabre_login_apos_logout(qapp, tmp_path, monkeypatch) -> None:
    caminho = tmp_path / "troca_operador.db"
    criar_tabelas(caminho)
    administrador, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ADMIN,
        SENHA_ADMIN,
        caminho,
    )
    assert administrador is not None and erros == []
    sessoes = (object(), object())
    logins = []

    class LoginSequencial:
        def __init__(self, caminho_banco):
            self.sessao = sessoes[len(logins)]
            logins.append(self)

        def exec(self):
            return QDialog.DialogCode.Accepted

    class Sinal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self):
            for callback in self._callbacks:
                callback()

    janelas = []

    class JanelaFalsa:
        def __init__(self, sessao):
            self.sessao = sessao
            self.logout_realizado = Sinal()

        def show(self):
            if not janelas.index(self):
                self.logout_realizado.emit()

    def criar_janela(caminho_banco, sessao):
        janela = JanelaFalsa(sessao)
        janelas.append(janela)
        return janela

    resultados_exec = iter((0, 37))
    monkeypatch.setattr(aplicacao_module, "DialogoLogin", LoginSequencial)
    monkeypatch.setattr(aplicacao_module, "criar_janela_principal", criar_janela)
    monkeypatch.setattr(QApplication, "exec", lambda self: next(resultados_exec))

    resultado = aplicacao_module.executar_aplicacao([], caminho)

    assert resultado == 37
    assert len(logins) == 2
    assert [janela.sessao for janela in janelas] == list(sessoes)
