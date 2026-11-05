import pytest
from PySide6.QtWidgets import QDialog

from database.conexao import conectar
from database.schema import criar_tabelas
from interface.janela_principal import JanelaPrincipal
from interface.pagina_historico import PaginaHistorico
from models.autorizacao_pontual import CapacidadeAutorizacao
from models.sessao_usuario import SessaoUsuario
from services.autenticacao_service import (
    LimitadorTentativasLogin,
    autenticar_usuario,
)
from services.autorizacao_pontual_service import (
    OPERACAO_CANCELAR_VENDA,
    AutorizacaoPontualConsumidaError,
    GerenciadorAutorizacoesPontuais,
)
from services.cancelamento_venda_service import cancelar_venda
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_sessao_admin_teste,
)
from tests.test_solicitacao_cancelamento_interface import (
    estado_persistido,
    persistir_venda,
    selecionar_venda,
)


SENHA_CAIXA = "frase segura do caixa int d2 2026"


@pytest.fixture
def ambiente(qtbot, tmp_path):
    caminho = tmp_path / "cancelamento_grafico_autorizado.db"
    criar_tabelas(caminho)
    sessao_admin = criar_sessao_admin_teste(caminho)
    caixa, erros = criar_conta_caixa(
        sessao_admin,
        "caixa-int-d2",
        SENHA_CAIXA,
        SENHA_CAIXA,
        caminho,
    )
    assert caixa is not None and erros == []
    sessao_caixa = autenticar_usuario("caixa-int-d2", SENHA_CAIXA, caminho)
    gerenciador = GerenciadorAutorizacoesPontuais()
    pagina = PaginaHistorico(
        caminho,
        sessao_solicitante=sessao_caixa,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(pagina)
    pagina.show()
    return caminho, sessao_caixa, gerenciador, pagina


def abrir_fluxo(pagina, venda_id, motivo="Erro operacional"):
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    solicitacao = pagina.dialogo_cancelamento
    solicitacao.campo_motivo.setPlainText(motivo)
    solicitacao.preparar_solicitacao()
    return solicitacao, pagina.dialogo_autorizacao


def autorizar(dialogo, senha=SENHA_ADMIN_TESTE) -> None:
    dialogo.campo_identificacao.setText("administrador")
    dialogo.campo_senha.setText(senha)
    dialogo.autorizar()


def snapshot_comercial(caminho, venda_id):
    conexao = conectar(caminho)
    try:
        venda = tuple(
            conexao.execute(
                """
                SELECT id, total_centavos, registrada_em,
                       identificador_tentativa
                FROM vendas WHERE id = ?
                """,
                (venda_id,),
            ).fetchone()
        )
        itens = tuple(
            tuple(linha)
            for linha in conexao.execute(
                "SELECT * FROM itens_venda WHERE venda_id = ? ORDER BY posicao",
                (venda_id,),
            ).fetchall()
        )
        pagamentos = tuple(
            tuple(linha)
            for linha in conexao.execute(
                "SELECT * FROM pagamentos WHERE venda_id = ? ORDER BY id",
                (venda_id,),
            ).fetchall()
        )
        return venda, itens, pagamentos
    finally:
        conexao.close()


def test_cancelamento_valido_atualiza_lista_detalhe_e_preserva_venda(
    ambiente,
) -> None:
    caminho, sessao_caixa, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    antes = snapshot_comercial(caminho, venda_id)
    solicitacao, dialogo = abrir_fluxo(
        pagina,
        venda_id,
        "  Lançamento duplicado  ",
    )

    autorizar(dialogo)

    assert solicitacao.result() == QDialog.DialogCode.Accepted
    assert estado_persistido(caminho, venda_id)[0][0] == "CANCELADA"
    assert pagina.tabela_vendas.item(0, 3).text() == "CANCELADA"
    assert pagina.detalhe_selecionado.status == "CANCELADA"
    assert pagina.rotulo_motivo_cancelamento.text() == "Lançamento duplicado"
    assert pagina.rotulo_autorizador_cancelamento.text() == "administrador"
    assert not pagina.botao_solicitar_cancelamento.isEnabled()
    assert snapshot_comercial(caminho, venda_id) == antes
    assert sessao_caixa.perfil == "CAIXA"
    assert sessao_caixa.autenticada


def test_dialogo_exibe_itens_e_pagamentos_originais(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento

    assert dialogo.tabela_itens.rowCount() == 1
    assert dialogo.tabela_itens.item(0, 1).text() == "Picanha histórica"
    assert dialogo.tabela_itens.item(0, 2).text() == "R$ 50,00"
    assert dialogo.tabela_pagamentos.rowCount() == 2
    assert dialogo.tabela_pagamentos.item(0, 0).text() == "PIX"
    assert dialogo.tabela_pagamentos.item(1, 0).text() == "DINHEIRO"


def test_motivo_obrigatorio_nao_abre_autorizacao(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    solicitacao = pagina.dialogo_cancelamento
    solicitacao.campo_motivo.setPlainText("   ")

    solicitacao.preparar_solicitacao()

    assert pagina.dialogo_autorizacao is None
    assert "Informe o motivo" in solicitacao.rotulo_mensagem.text()
    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"


def test_desistencia_antes_da_autorizacao_preserva_venda(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()

    pagina.dialogo_cancelamento.reject()

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"


def test_desistencia_durante_autorizacao_permite_nova_tentativa(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)

    dialogo.reject()

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert solicitacao.botao_prosseguir.isEnabled()
    assert "Autorização cancelada" in solicitacao.rotulo_mensagem.text()


def test_senha_administrativa_incorreta_nao_cancela(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    _, dialogo = abrir_fluxo(pagina, venda_id)

    autorizar(dialogo, "senha administrativa incorreta")

    assert dialogo.result() != QDialog.DialogCode.Accepted
    assert "inválida" in dialogo.rotulo_mensagem.text()
    assert dialogo.campo_senha.text() == ""
    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"


def test_administrador_inativo_nao_autoriza(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    _, dialogo = abrir_fluxo(pagina, venda_id)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            "UPDATE usuarios SET ativo = 0 WHERE perfil = 'ADMINISTRADOR'"
        )
        conexao.commit()
    finally:
        conexao.close()

    autorizar(dialogo)

    assert dialogo.result() != QDialog.DialogCode.Accepted
    assert "autorização foi negada" in dialogo.rotulo_mensagem.text()
    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"


def test_sessao_fabricada_e_rejeitada(ambiente, qtbot) -> None:
    caminho, _, gerenciador, _ = ambiente
    venda_id = persistir_venda(caminho)
    fabricada = SessaoUsuario(
        999,
        "caixa-fabricado",
        "CAIXA",
        "x" * 43,
    )
    pagina = PaginaHistorico(
        caminho,
        sessao_solicitante=fabricada,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(pagina)
    pagina.show()
    _, dialogo = abrir_fluxo(pagina, venda_id)

    autorizar(dialogo)

    assert dialogo.result() != QDialog.DialogCode.Accepted
    assert "Não foi possível autorizar" in dialogo.rotulo_mensagem.text()
    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"


def test_autorizacao_para_id_incorreto_e_consumida_sem_cancelar(ambiente) -> None:
    caminho, sessao, gerenciador, pagina = ambiente
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    dialogo.capacidade = gerenciador.emitir(
        sessao,
        OPERACAO_CANCELAR_VENDA,
        venda_id + 1,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )

    dialogo.accept()

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert solicitacao.botao_prosseguir.isEnabled()
    assert "não é mais válida" in solicitacao.rotulo_mensagem.text()


def test_autorizacao_expirada_exige_nova_autorizacao(ambiente, qtbot) -> None:
    caminho, sessao, gerenciador_original, pagina_original = ambiente
    pagina_original.close()
    instante = [100.0]
    gerenciador = GerenciadorAutorizacoesPontuais(
        gerenciador_sessoes=gerenciador_original.gerenciador_sessoes,
        validade_segundos=5,
        relogio=lambda: instante[0],
    )
    pagina = PaginaHistorico(
        caminho,
        sessao_solicitante=sessao,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(pagina)
    pagina.show()
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    dialogo.capacidade = gerenciador.emitir(
        sessao,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )
    instante[0] = 106.0

    dialogo.accept()

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert "expirou" in solicitacao.rotulo_mensagem.text()
    assert solicitacao.botao_prosseguir.isEnabled()


def test_capacidade_reutilizada_e_rejeitada(ambiente) -> None:
    caminho, sessao, gerenciador, pagina = ambiente
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    capacidade = gerenciador.emitir(
        sessao,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )
    gerenciador.consumir(
        capacidade,
        sessao,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        caminho,
    )
    dialogo.capacidade = capacidade

    dialogo.accept()

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert "não é mais válida" in solicitacao.rotulo_mensagem.text()


def test_cancelamento_repetido_atualiza_historico_sem_sucesso_falso(
    ambiente,
) -> None:
    caminho, sessao, gerenciador, pagina = ambiente
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    capacidade_externa = gerenciador.emitir(
        sessao,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        "administrador",
        SENHA_ADMIN_TESTE,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )
    cancelar_venda(
        venda_id,
        "Cancelado externamente",
        capacidade_externa,
        sessao,
        caminho,
        gerenciador_autorizacoes=gerenciador,
    )

    autorizar(dialogo)

    assert solicitacao.result() == QDialog.DialogCode.Rejected
    assert pagina.detalhe_selecionado.status == "CANCELADA"
    assert pagina.rotulo_mensagem.text() == "A venda já estava cancelada."


def test_duplo_acionamento_abre_uma_unica_autorizacao(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    solicitacao = pagina.dialogo_cancelamento
    solicitacao.campo_motivo.setPlainText("Duplicidade")

    solicitacao.preparar_solicitacao()
    primeiro = pagina.dialogo_autorizacao
    solicitacao.preparar_solicitacao()

    assert pagina.dialogo_autorizacao is primeiro
    assert pagina._cancelamento_em_processamento
    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"


def test_falha_de_persistencia_preserva_venda_e_exige_nova_autorizacao(
    ambiente,
) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_cancelamento_int_d2
            BEFORE UPDATE OF status ON vendas
            BEGIN
                SELECT RAISE(ABORT, 'falha int d2');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    autorizar(dialogo)

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert solicitacao.botao_prosseguir.isEnabled()
    assert "Falha no banco de dados" in solicitacao.rotulo_mensagem.text()


def test_commit_incerto_bloqueia_execucao_mesmo_apos_autorizacao(
    ambiente,
    qtbot,
) -> None:
    caminho, sessao, gerenciador, pagina_original = ambiente
    pagina_original.close()
    bloqueada = [False]
    pagina = PaginaHistorico(
        caminho,
        operacao_bloqueada=lambda: bloqueada[0],
        sessao_solicitante=sessao,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(pagina)
    pagina.show()
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    bloqueada[0] = True

    autorizar(dialogo)

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert "fechamento pendente" in solicitacao.rotulo_mensagem.text()
    assert solicitacao.botao_prosseguir.isEnabled()
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            dialogo.capacidade,
            sessao,
            OPERACAO_CANCELAR_VENDA,
            venda_id,
            caminho,
        )


def test_sessao_da_janela_e_reutilizada_sem_elevacao(
    ambiente,
    qtbot,
) -> None:
    caminho, sessao, _, pagina = ambiente
    pagina.close()
    janela = JanelaPrincipal(caminho, sessao)
    qtbot.addWidget(janela)
    janela.show()

    assert janela.pagina_historico.sessao_solicitante is janela.sessao
    assert janela.sessao.perfil == "CAIXA"
    assert janela.pagina_frente_caixa is not None
    assert janela.pagina_produtos is not None


def test_capacidade_fabricada_nao_chega_ao_banco(ambiente) -> None:
    caminho, _, _, pagina = ambiente
    venda_id = persistir_venda(caminho)
    solicitacao, dialogo = abrir_fluxo(pagina, venda_id)
    dialogo.capacidade = CapacidadeAutorizacao("z" * 43)

    dialogo.accept()

    assert estado_persistido(caminho, venda_id)[0][0] == "ATIVA"
    assert "não é mais válida" in solicitacao.rotulo_mensagem.text()
