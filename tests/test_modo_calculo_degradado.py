import sqlite3

from database.conexao import conectar
from database.schema import criar_tabelas
from models.produto import Produto
from repositories.produto_repository import salvar_produto
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_janela_autenticada,
)
import interface.janela_principal as janela_module
from interface.janela_principal import JanelaPrincipal
from services.contingencia_service import confirmar_retomada_operacional
from services.estado_operacional_service import ModoOperacional


def _criar_janela_com_produto(qtbot, tmp_path):
    banco = tmp_path / "modo_calculo.db"
    criar_tabelas(banco)
    salvar_produto(
        Produto(
            codigo="234",
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=7990,
            origem="COMPRADO",
        ),
        banco,
    )
    janela = criar_janela_autenticada(banco)
    qtbot.addWidget(janela)
    return janela


def test_falha_de_acesso_usa_catalogo_e_exibe_total_nao_registrado(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    janela = _criar_janela_com_produto(qtbot, tmp_path)
    monkeypatch.setattr(
        janela_module,
        "associar_etiqueta_ao_produto",
        lambda *args: (_ for _ in ()).throw(
            sqlite3.OperationalError("database is locked")
        ),
    )

    janela._processar_etiqueta("2023400053672")

    assert janela.controlador_estado.obter_estado().modo is (
        ModoOperacional.CALCULO_DEGRADADO
    )
    assert len(janela.estado_venda.venda.itens) == 1
    assert janela.estado_venda.venda.itens[0].subtotal_centavos == 5367
    assert "não registrado" in janela.rotulo_total.text()
    assert not janela.rotulo_modo_operacional.isHidden()
    assert not janela.botao_pagamento.isEnabled()
    assert not janela.botao_navegar_produtos.isEnabled()
    assert janela.campo_entrada.isEnabled()


def test_modo_degradado_nao_grava_venda_e_preserva_itens(
    qtbot,
    tmp_path,
) -> None:
    janela = _criar_janela_com_produto(qtbot, tmp_path)
    assert janela._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )
    janela._processar_etiqueta("2023400053672")

    janela.abrir_dialogo_pagamentos()

    conexao = conectar(janela.caminho_banco)
    try:
        quantidade = conexao.execute("SELECT COUNT(*) FROM vendas").fetchone()[0]
    finally:
        conexao.close()
    assert quantidade == 0
    assert len(janela.estado_venda.venda.itens) == 1
    assert janela.dialogo_atual is None
    assert "nada será registrado" in janela.rotulo_status.text()


def test_invalidacao_do_catalogo_bloqueia_calculo_e_atualiza_interface(
    qtbot,
    tmp_path,
) -> None:
    janela = _criar_janela_com_produto(qtbot, tmp_path)
    assert janela._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )
    janela.catalogo_produtos.invalidar("TESTE_INVALIDACAO")
    janela.campo_entrada.setText("234")

    janela.processar_entrada()

    assert janela.controlador_estado.obter_estado().modo is (
        ModoOperacional.INDISPONIVEL
    )
    assert not janela.campo_entrada.isEnabled()
    assert "OPERAÇÃO INDISPONÍVEL" in janela.rotulo_modo_operacional.text()
    assert len(janela.estado_venda.venda.itens) == 0


def test_retomada_confirmada_preserva_itens_em_memoria(
    qtbot,
    tmp_path,
) -> None:
    janela = _criar_janela_com_produto(qtbot, tmp_path)
    assert janela._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )
    janela._processar_etiqueta("2023400053672")
    itens_antes = tuple(janela.estado_venda.venda.itens)

    confirmar_retomada_operacional(
        janela.caminho_banco,
        controlador_estado=janela.controlador_estado,
        catalogo_produtos=janela.catalogo_produtos,
        identificacao_administrador="administrador",
        senha_administrador=SENHA_ADMIN_TESTE,
        confirmacao_explicita=True,
        fechamento_incerto=False,
    )
    janela._atualizar_venda_exibida()

    assert tuple(janela.estado_venda.venda.itens) == itens_antes
    assert janela.controlador_estado.obter_estado().modo is ModoOperacional.NORMAL
    assert janela.rotulo_modo_operacional.isHidden()
    assert janela.botao_verificar_retomada.isHidden()


def test_segunda_janela_do_mesmo_banco_herda_estado_restritivo(
    qtbot,
    tmp_path,
) -> None:
    primeira = _criar_janela_com_produto(qtbot, tmp_path)
    assert primeira._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )

    segunda = JanelaPrincipal(primeira.caminho_banco, primeira.sessao)
    qtbot.addWidget(segunda)

    assert segunda.controlador_estado is primeira.controlador_estado
    assert segunda.controlador_estado.obter_estado().modo is (
        ModoOperacional.CALCULO_DEGRADADO
    )
    assert not segunda.botao_verificar_retomada.isHidden()


def test_aviso_restritivo_distingue_fechamento_incerto(qtbot, tmp_path) -> None:
    janela = _criar_janela_com_produto(qtbot, tmp_path)
    assert janela._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )
    janela._fechamento_incerto = True

    janela._atualizar_aviso_modo_operacional()

    assert "FECHAMENTO INCERTO" in janela.rotulo_modo_operacional.text()
    assert "não gere uma nova tentativa" in janela.rotulo_modo_operacional.text()
