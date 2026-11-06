import pytest
import sqlite3
from threading import Event, Thread
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from database.conexao import conectar
from database.schema import criar_tabelas
import interface.aplicacao as aplicacao_module
from interface.dialogo_login import DialogoLogin
from interface.dialogo_redefinicao_senha import DialogoRedefinicaoSenha
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
    autorizar_sessao,
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
    redefinir_senha_conta_caixa,
)


SENHA_ADMIN = "frase administrativa para int e 2026"
SENHA_CAIXA = "frase individual do operador caixa 2026"
SENHA_CAIXA_NOVA = "nova frase individual do operador 2026"


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
    assert janela.botao_navegar_produtos.isEnabled()
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
    with pytest.raises(PermissaoNegadaError):
        redefinir_senha_conta_caixa(
            sessao_caixa,
            usuario.id,
            SENHA_CAIXA_NOVA,
            SENHA_CAIXA_NOVA,
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
    usuario = cadastrar_caixa(caminho, sessao_admin)
    with pytest.raises(SessaoInvalidaError):
        redefinir_senha_conta_caixa(
            fabricada,
            usuario.id,
            SENHA_CAIXA_NOVA,
            SENHA_CAIXA_NOVA,
            caminho,
        )


def test_redefinicao_rejeita_sessao_administrativa_encerrada(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)
    sessao_admin.encerrar()

    with pytest.raises(SessaoInvalidaError):
        redefinir_senha_conta_caixa(
            sessao_admin,
            usuario.id,
            SENHA_CAIXA_NOVA,
            SENHA_CAIXA_NOVA,
            caminho,
        )


def test_admin_redefine_senha_caixa_e_credencial_antiga_falha(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)

    redefinido, erros = redefinir_senha_conta_caixa(
        sessao_admin,
        usuario.id,
        SENHA_CAIXA_NOVA,
        SENHA_CAIXA_NOVA,
        caminho,
    )

    assert erros == []
    assert redefinido.id == usuario.id
    assert redefinido.identificacao_acesso == usuario.identificacao_acesso
    with pytest.raises(CredenciaisInvalidasError):
        autenticar_usuario(
            "caixa01",
            SENHA_CAIXA,
            caminho,
            limitador=LimitadorTentativasLogin(),
        )
    assert autenticar_usuario(
        "caixa01",
        SENHA_CAIXA_NOVA,
        caminho,
        limitador=LimitadorTentativasLogin(),
    ).autenticada


def test_redefinicao_rejeita_admin_e_senhas_invalidas(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente

    usuario, erros = redefinir_senha_conta_caixa(
        sessao_admin,
        999,
        "curta",
        "outra",
        caminho,
    )
    assert usuario is None
    assert any("ao menos 12" in erro for erro in erros)
    assert any("confirma" in erro for erro in erros)

    with pytest.raises(LookupError, match="Caixa"):
        redefinir_senha_conta_caixa(
            sessao_admin,
            sessao_admin.usuario_id,
            SENHA_CAIXA_NOVA,
            SENHA_CAIXA_NOVA,
            caminho,
        )


def test_redefinicao_preserva_conta_inativa(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)
    alterar_situacao_conta_caixa(sessao_admin, usuario.id, False, caminho)

    redefinido, erros = redefinir_senha_conta_caixa(
        sessao_admin,
        usuario.id,
        SENHA_CAIXA_NOVA,
        SENHA_CAIXA_NOVA,
        caminho,
    )

    assert erros == []
    assert not redefinido.ativo
    with pytest.raises(CredenciaisInvalidasError):
        autenticar_usuario(
            "caixa01",
            SENHA_CAIXA_NOVA,
            caminho,
            limitador=LimitadorTentativasLogin(),
        )


def test_redefinicao_revoga_sessoes_e_capacidades_do_caixa(ambiente) -> None:
    caminho, sessao_admin_padrao, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin_padrao)
    gerenciador_sessoes = GerenciadorSessoes()
    sessao_admin = autenticar_usuario(
        "administrador",
        SENHA_ADMIN,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
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

    redefinir_senha_conta_caixa(
        sessao_admin,
        usuario.id,
        SENHA_CAIXA_NOVA,
        SENHA_CAIXA_NOVA,
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
    assert sessao_admin.autenticada


def test_falha_de_persistencia_preserva_senha_e_sessao(ambiente) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)
    sessao_caixa = autenticar_usuario("caixa01", SENHA_CAIXA, caminho)
    with conectar(caminho) as conexao:
        conexao.execute(
            """
            CREATE TRIGGER falhar_redefinicao_caixa
            BEFORE UPDATE OF senha_hash ON usuarios
            WHEN OLD.id = %d
            BEGIN
                SELECT RAISE(ABORT, 'falha redefinicao caixa');
            END
            """ % usuario.id
        )

    with pytest.raises(sqlite3.IntegrityError, match="falha redefinicao caixa"):
        redefinir_senha_conta_caixa(
            sessao_admin,
            usuario.id,
            SENHA_CAIXA_NOVA,
            SENHA_CAIXA_NOVA,
            caminho,
        )

    assert sessao_caixa.autenticada
    assert autenticar_usuario(
        "caixa01",
        SENHA_CAIXA,
        caminho,
        limitador=LimitadorTentativasLogin(),
    ).autenticada
    with pytest.raises(CredenciaisInvalidasError):
        autenticar_usuario(
            "caixa01",
            SENHA_CAIXA_NOVA,
            caminho,
            limitador=LimitadorTentativasLogin(),
        )


def test_redefinicao_serializa_uso_concorrente_de_sessao_antiga(ambiente) -> None:
    caminho, sessao_admin_padrao, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin_padrao)
    gerenciador_sessoes = GerenciadorSessoes()
    sessao_admin = autenticar_usuario(
        "administrador",
        SENHA_ADMIN,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    sessao_caixa = autenticar_usuario(
        "caixa01",
        SENHA_CAIXA,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    invalidacao_iniciada = Event()
    liberar_invalidacao = Event()
    resultados = []

    class AutorizacoesLentas:
        def invalidar_usuario(self, usuario_id):
            invalidacao_iniciada.set()
            assert liberar_invalidacao.wait(5)

    def redefinir():
        redefinir_senha_conta_caixa(
            sessao_admin,
            usuario.id,
            SENHA_CAIXA_NOVA,
            SENHA_CAIXA_NOVA,
            caminho,
            gerenciador_sessoes=gerenciador_sessoes,
            gerenciador_autorizacoes=AutorizacoesLentas(),
        )

    def usar_sessao_antiga():
        try:
            autorizar_sessao(
                sessao_caixa,
                ("CAIXA",),
                caminho,
                gerenciador_sessoes=gerenciador_sessoes,
            )
            resultados.append("autorizada")
        except SessaoInvalidaError:
            resultados.append("revogada")

    thread_redefinicao = Thread(target=redefinir)
    thread_redefinicao.start()
    assert invalidacao_iniciada.wait(5)
    thread_uso = Thread(target=usar_sessao_antiga)
    thread_uso.start()
    assert thread_uso.is_alive()
    liberar_invalidacao.set()
    thread_redefinicao.join(5)
    thread_uso.join(5)

    assert resultados == ["revogada"]


def test_dialogo_redefine_senha_e_limpa_campos(ambiente, qtbot) -> None:
    caminho, sessao_admin, _ = ambiente
    usuario = cadastrar_caixa(caminho, sessao_admin)
    dialogo = DialogoRedefinicaoSenha(
        sessao_admin,
        usuario.id,
        usuario.identificacao_acesso,
        caminho,
    )
    qtbot.addWidget(dialogo)
    dialogo.campo_nova_senha.setText(SENHA_CAIXA_NOVA)
    dialogo.campo_confirmacao.setText(SENHA_CAIXA_NOVA)

    dialogo.redefinir()

    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert dialogo.usuario_redefinido.id == usuario.id
    assert dialogo.campo_nova_senha.text() == ""
    assert dialogo.campo_confirmacao.text() == ""


def test_pagina_habilita_redefinicao_somente_com_operador_selecionado(
    ambiente,
) -> None:
    caminho, sessao_admin, janela = ambiente
    cadastrar_caixa(caminho, sessao_admin)
    pagina = abrir_administracao(janela)

    assert not pagina.botao_redefinir_senha.isEnabled()
    pagina.tabela_operadores.selectRow(0)
    assert pagina.botao_redefinir_senha.isEnabled()


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
