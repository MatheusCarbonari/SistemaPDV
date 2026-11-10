from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from interface.dialogo_autorizacao_administrativa import (
    DialogoAutorizacaoAdministrativa,
)
from interface.dialogo_codigos_recuperacao import DialogoCodigosRecuperacao
from interface.dialogo_confirmacao_venda import DialogoConfirmacaoVenda
from interface.dialogo_login import DialogoLogin
from interface.dialogo_primeiro_acesso import DialogoPrimeiroAcesso
from interface.dialogo_recuperacao_acesso import DialogoRecuperacaoAcesso
from interface.estilo_dialogos import aplicar_tema_mensagens
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.venda_em_andamento import VendaEmAndamento
from services.autorizacao_pontual_service import GerenciadorAutorizacoesPontuais
from tests.helpers_identidade import criar_sessao_admin_teste


def _assert_dialogo_visual(dialogo, largura_minima: int, altura_minima: int) -> None:
    assert dialogo.property("temaPdv") is True
    assert dialogo.minimumWidth() >= largura_minima
    assert dialogo.minimumHeight() >= altura_minima
    assert "background: #171a1f" in dialogo.styleSheet()
    assert all(
        campo.maximumWidth() <= 320
        for campo in dialogo.findChildren(QLineEdit)
    )


def test_primeiro_acesso_e_login_usam_formularios_proporcionais(qtbot, tmp_path):
    primeiro_acesso = DialogoPrimeiroAcesso(tmp_path / "primeiro-acesso.db")
    login = DialogoLogin(tmp_path / "login.db")
    qtbot.addWidget(primeiro_acesso)
    qtbot.addWidget(login)

    _assert_dialogo_visual(primeiro_acesso, 500, 390)
    _assert_dialogo_visual(login, 440, 330)
    assert primeiro_acesso.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    assert login.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    assert login.botao_recuperar.width() < login.width()


def test_recuperacao_e_codigos_preservam_segredos_e_tema(qtbot, tmp_path):
    caminho = tmp_path / "recuperacao.db"
    sessao = criar_sessao_admin_teste(caminho)
    recuperacao = DialogoRecuperacaoAcesso(caminho)
    codigos = DialogoCodigosRecuperacao(sessao, caminho)
    qtbot.addWidget(recuperacao)
    qtbot.addWidget(codigos)

    _assert_dialogo_visual(recuperacao, 520, 440)
    _assert_dialogo_visual(codigos, 540, 450)
    assert recuperacao.campo_codigo.echoMode() == QLineEdit.EchoMode.Password
    assert codigos.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    assert not codigos.grupo_codigos.isVisible()


def test_autorizacao_organiza_resumo_e_destaca_preco_e_categoria(
    qtbot,
    tmp_path,
):
    caminho = tmp_path / "autorizacao.db"
    sessao = criar_sessao_admin_teste(caminho)
    descricao = (
        "Autorizar edição do produto 10\n\n"
        "Nome: Café → Café premium\n"
        "Categoria: MERCEARIA → CAFÉS\n"
        "Forma de venda: UNIDADE → UNIDADE\n"
        "Preço: R$ 10,00 → R$ 12,00\n"
        "Origem: COMPRADO → COMPRADO"
    )
    dialogo = DialogoAutorizacaoAdministrativa(
        sessao,
        "EDITAR_PRODUTO",
        10,
        descricao,
        caminho,
        gerenciador=GerenciadorAutorizacoesPontuais(),
    )
    qtbot.addWidget(dialogo)

    _assert_dialogo_visual(dialogo, 560, 440)
    assert dialogo.rotulo_operacao.text() == "Autorizar edição do produto 10"
    original = dialogo.findChild(QLabel, "descricao_operacao_critica")
    assert original.text() == descricao
    destacados = [
        rotulo.text()
        for rotulo in dialogo.findChildren(QLabel)
        if rotulo.property("dadoAlterado") is True
    ]
    assert destacados == ["MERCEARIA → CAFÉS", "R$ 10,00 → R$ 12,00"]


def test_confirmacao_de_venda_tem_resumo_legivel_e_atalhos(qtbot):
    venda = VendaEmAndamento(
        itens=(
            ItemVenda(
                origem="MANUAL",
                subtotal_centavos=1200,
                origem_quantidade="NAO_INFORMADA",
            ),
        )
    )
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1200,
        pagamentos=(Pagamento("PIX", 700), Pagamento("PIX", 500)),
    )
    dialogo = DialogoConfirmacaoVenda(venda, pagamentos)
    qtbot.addWidget(dialogo)
    dialogo.show()

    _assert_dialogo_visual(dialogo, 540, 430)
    assert dialogo.rotulo_total.text() == "R$ 12,00"
    assert dialogo.tabela_pagamentos.rowCount() == 2
    assert dialogo.tabela_pagamentos.item(0, 1).textAlignment() & int(
        Qt.AlignmentFlag.AlignRight
    )
    assert dialogo.botao_confirmar.isDefault()


def test_dialogos_cabem_nas_resolucoes_alvo_sem_controles_cortados(
    qtbot,
    tmp_path,
):
    dialogos = (
        DialogoPrimeiroAcesso(tmp_path / "alvo-primeiro.db"),
        DialogoLogin(tmp_path / "alvo-login.db"),
        DialogoRecuperacaoAcesso(tmp_path / "alvo-recuperacao.db"),
    )
    for dialogo in dialogos:
        qtbot.addWidget(dialogo)
        dialogo.show()
        qtbot.waitUntil(dialogo.isVisible)
        assert dialogo.width() <= 1024
        assert dialogo.height() <= 720
        assert dialogo.sizeHint().width() <= dialogo.width()
        assert dialogo.sizeHint().height() <= dialogo.height()


def test_mensagens_importantes_recebem_tema_escuro(qapp):
    aplicar_tema_mensagens(qapp)
    aplicar_tema_mensagens(qapp)

    assert qapp.styleSheet().count("/* mensagens-pdv */") == 1
    assert "QMessageBox" in QApplication.instance().styleSheet()

