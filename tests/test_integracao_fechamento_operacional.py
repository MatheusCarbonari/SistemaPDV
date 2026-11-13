from decimal import Decimal
import sqlite3

import pytest
from PySide6.QtCore import Qt

from database.conexao import conectar
from database.schema import criar_tabelas
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_janela_autenticada,
)
from interface.janela_principal import JanelaPrincipal
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from services.confirmacao_venda_service import confirmar_venda
from services.contingencia_service import (
    FechamentoIncertoBloqueiaRetomadaError,
    confirmar_retomada_operacional,
)
from services.estado_operacional_service import ModoOperacional
from services.persistencia_venda_service import CommitVendaIncertoError
import interface.janela_principal as janela_principal_module


def criar_item(subtotal=1000, nome="Produto") -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal,
        origem_quantidade="INFORMADA",
        produto=ProdutoSnapshot(None, nome, nome, "UNIDADE", subtotal),
        quantidade=Decimal("1"),
    )


def registrar_composicao(janela, total=1000) -> PagamentosEmAndamento:
    composicao = PagamentosEmAndamento(
        total_venda_centavos=total,
        pagamentos=(Pagamento("PIX", total),),
    )
    janela._emitir_pagamentos_confirmados(composicao)
    return composicao


@pytest.fixture
def janela(qtbot, tmp_path):
    caminho = tmp_path / "fechamento.db"
    criar_tabelas(caminho)
    widget = criar_janela_autenticada(caminho)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible)
    qtbot.waitUntil(widget.campo_entrada.hasFocus)
    return widget


def confirmar_pela_interface(janela, qtbot) -> None:
    janela.abrir_dialogo_confirmacao()
    dialogo = janela.dialogo_atual
    qtbot.waitUntil(dialogo.isVisible)
    qtbot.keyPress(dialogo, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)


def contagem_vendas(caminho_banco) -> int:
    conexao = conectar(caminho_banco)
    try:
        return conexao.execute("SELECT COUNT(*) FROM vendas").fetchone()[0]
    finally:
        conexao.close()


def test_confirmacao_persiste_exibe_id_limpa_e_restaura_foco(
    janela,
    qtbot,
) -> None:
    janela.item_criado.emit(criar_item())
    registrar_composicao(janela)
    ids = []
    janela.venda_persistida.connect(ids.append)

    confirmar_pela_interface(janela, qtbot)

    assert ids == [janela.ultimo_id_venda_persistida]
    assert contagem_vendas(janela.caminho_banco) == 1
    assert janela.estado_venda.venda.itens == ()
    assert janela.composicao_pagamentos is None
    assert janela.identificador_tentativa_fechamento is None
    assert f"#{ids[0]:06d}" in janela.rotulo_status.text()
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_falha_antes_do_commit_preserva_dados_e_reutiliza_uuid(
    janela,
    qtbot,
    monkeypatch,
) -> None:
    item = criar_item()
    janela.item_criado.emit(item)
    composicao = registrar_composicao(janela)
    tentativas = []

    def falhar(confirmacao, identificador, caminho, **kwargs):
        tentativas.append(identificador)
        raise sqlite3.OperationalError("banco ocupado")

    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        falhar,
    )
    confirmar_pela_interface(janela, qtbot)

    assert janela.estado_venda.venda.itens == (item,)
    assert janela.composicao_pagamentos is composicao
    assert janela.identificador_tentativa_fechamento == tentativas[0]
    assert contagem_vendas(janela.caminho_banco) == 0
    assert "dados foram preservados" in janela.rotulo_status.text()

    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        lambda confirmacao, identificador, caminho, **kwargs: (
            tentativas.append(identificador) or 41
        ),
    )
    confirmar_pela_interface(janela, qtbot)

    assert tentativas[0] == tentativas[1]
    assert janela.ultimo_id_venda_persistida == 41
    assert janela.estado_venda.venda.itens == ()


def test_commit_incerto_bloqueia_operacao_e_recupera_com_mesmo_uuid(
    janela,
    qtbot,
    monkeypatch,
) -> None:
    item = criar_item()
    janela.item_criado.emit(item)
    registrar_composicao(janela)
    tentativas = []

    def resultado_incerto(confirmacao, identificador, caminho, **kwargs):
        tentativas.append(identificador)
        raise CommitVendaIncertoError(identificador)

    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        resultado_incerto,
    )
    confirmar_pela_interface(janela, qtbot)

    assert janela.estado_venda.venda.itens == (item,)
    assert janela._fechamento_incerto
    assert not janela.campo_entrada.isEnabled()
    assert not janela.botao_pagamento.isEnabled()
    assert janela.botao_verificar_fechamento.isEnabled()
    assert "resultado do fechamento é incerto" in janela.rotulo_status.text()

    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        lambda confirmacao, identificador, caminho, **kwargs: (
            tentativas.append(identificador) or 52
        ),
    )
    qtbot.mouseClick(
        janela.botao_verificar_fechamento,
        Qt.MouseButton.LeftButton,
    )

    assert tentativas[0] == tentativas[1]
    assert janela.ultimo_id_venda_persistida == 52
    assert janela.estado_venda.venda.itens == ()
    assert janela.campo_entrada.isEnabled()
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_verificacao_recusada_na_degradacao_preserva_incerteza_e_uuid(
    janela,
    qtbot,
    monkeypatch,
) -> None:
    janela.item_criado.emit(criar_item())
    registrar_composicao(janela)
    tentativas = []

    def resultado_incerto(confirmacao, identificador, caminho, **kwargs):
        tentativas.append(identificador)
        raise CommitVendaIncertoError(identificador)

    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        resultado_incerto,
    )
    confirmar_pela_interface(janela, qtbot)
    identificador = janela.identificador_tentativa_fechamento
    confirmacao = janela.confirmacao_pendente
    assert janela._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )

    janela.verificar_fechamento_pendente()

    assert tentativas == [identificador]
    assert janela._fechamento_incerto
    assert janela.identificador_tentativa_fechamento == identificador
    assert janela.confirmacao_pendente is confirmacao
    assert not janela.botao_verificar_fechamento.isEnabled()
    assert janela.controlador_estado.obter_estado().modo is (
        ModoOperacional.CALCULO_DEGRADADO
    )
    with pytest.raises(FechamentoIncertoBloqueiaRetomadaError):
        confirmar_retomada_operacional(
            janela.caminho_banco,
            controlador_estado=janela.controlador_estado,
            catalogo_produtos=janela.catalogo_produtos,
            identificacao_administrador="administrador",
            senha_administrador=SENHA_ADMIN_TESTE,
            confirmacao_explicita=True,
            fechamento_incerto=janela._fechamento_incerto,
        )
    assert janela.controlador_estado.obter_estado().modo is (
        ModoOperacional.CALCULO_DEGRADADO
    )


def test_fechamento_incerto_em_outra_janela_bloqueia_retomada(
    janela,
    qtbot,
) -> None:
    janela.item_criado.emit(criar_item())
    composicao = registrar_composicao(janela)
    janela.confirmacao_pendente = confirmar_venda(
        janela.estado_venda.venda,
        composicao,
    )
    janela.identificador_tentativa_fechamento = (
        "dcf79ea4-78d9-42df-a369-20ad255d07b1"
    )
    janela._fechamento_incerto = True
    assert janela._tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked")
    )

    segunda = JanelaPrincipal(janela.caminho_banco, janela.sessao)
    qtbot.addWidget(segunda)
    assert not segunda._fechamento_incerto

    with pytest.raises(FechamentoIncertoBloqueiaRetomadaError):
        confirmar_retomada_operacional(
            segunda.caminho_banco,
            controlador_estado=segunda.controlador_estado,
            catalogo_produtos=segunda.catalogo_produtos,
            identificacao_administrador="administrador",
            senha_administrador=SENHA_ADMIN_TESTE,
            confirmacao_explicita=True,
            fechamento_incerto=False,
        )
    assert segunda.controlador_estado.obter_estado().modo is (
        ModoOperacional.CALCULO_DEGRADADO
    )

    janela._fechamento_incerto = False
    resultado = confirmar_retomada_operacional(
        segunda.caminho_banco,
        controlador_estado=segunda.controlador_estado,
        catalogo_produtos=segunda.catalogo_produtos,
        identificacao_administrador="administrador",
        senha_administrador=SENHA_ADMIN_TESTE,
        confirmacao_explicita=True,
        fechamento_incerto=False,
    )
    assert resultado.codigo == "RETOMADA_CONFIRMADA"
    assert segunda.controlador_estado.obter_estado().modo is ModoOperacional.NORMAL


def test_bloqueia_confirmacao_reentrante_enquanto_processa(
    janela,
    monkeypatch,
) -> None:
    janela.item_criado.emit(criar_item())
    composicao = registrar_composicao(janela)
    confirmacao = confirmar_venda(janela.estado_venda.venda, composicao)
    chamadas = []

    def persistir(confirmacao_recebida, identificador, caminho, **kwargs):
        chamadas.append(identificador)
        janela._receber_venda_confirmada(confirmacao_recebida)
        return 63

    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        persistir,
    )

    janela._receber_venda_confirmada(confirmacao)

    assert len(chamadas) == 1
    assert janela.ultimo_id_venda_persistida == 63


def test_alterar_venda_invalida_pagamento_e_uuid_de_falha(
    janela,
    qtbot,
    monkeypatch,
) -> None:
    janela.item_criado.emit(criar_item())
    registrar_composicao(janela)
    monkeypatch.setattr(
        janela_principal_module.persistencia_venda_service,
        "persistir_venda_confirmada_idempotente",
        lambda confirmacao, identificador, caminho, **kwargs: (
            _ for _ in ()
        ).throw(sqlite3.OperationalError("falha antes do commit")),
    )
    confirmar_pela_interface(janela, qtbot)
    assert janela.identificador_tentativa_fechamento is not None

    janela.item_criado.emit(criar_item(500, "Outro"))

    assert janela.composicao_pagamentos is None
    assert janela.identificador_tentativa_fechamento is None
    assert not janela.botao_confirmar_venda.isEnabled()
