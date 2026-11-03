import importlib

from PySide6.QtWidgets import QApplication, QWidget

from interface.aplicacao import obter_aplicacao
from interface.janela_principal import JanelaPrincipal


def test_janela_principal_possui_configuracao_minima(qtbot) -> None:
    janela = JanelaPrincipal()
    qtbot.addWidget(janela)

    assert janela.windowTitle() == "Sistema-PDV"
    assert janela.width() == 1024
    assert janela.height() == 720
    assert isinstance(janela.centralWidget(), QWidget)
    assert janela.centralWidget().objectName() == "area_vendas"


def test_janela_principal_pode_ser_aberta_e_fechada(qtbot) -> None:
    janela = JanelaPrincipal()
    qtbot.addWidget(janela)

    janela.show()
    qtbot.waitUntil(janela.isVisible)

    janela.close()
    qtbot.waitUntil(lambda: not janela.isVisible())


def test_obter_aplicacao_reutiliza_instancia_existente(qapp) -> None:
    aplicacao = obter_aplicacao(["sistema-pdv"])

    assert aplicacao is qapp
    assert aplicacao is QApplication.instance()


def test_importar_ponto_de_entrada_nao_abre_janela(qapp) -> None:
    janelas_antes = set(qapp.topLevelWidgets())

    modulo = importlib.import_module("main")
    importlib.reload(modulo)

    assert set(qapp.topLevelWidgets()) == janelas_antes


def test_camadas_existentes_continuam_importaveis() -> None:
    modulos = [
        "models.item_venda",
        "services.item_venda_service",
        "repositories.produto_repository",
        "database.schema",
    ]

    for nome_modulo in modulos:
        assert importlib.import_module(nome_modulo) is not None
