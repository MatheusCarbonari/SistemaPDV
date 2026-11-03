from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class JanelaPrincipal(QMainWindow):
    """Janela principal mínima do Sistema-PDV."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sistema-PDV")
        self.resize(1024, 720)

        area_vendas = QWidget(self)
        area_vendas.setObjectName("area_vendas")

        layout = QVBoxLayout(area_vendas)
        titulo = QLabel("Área de vendas", area_vendas)
        titulo.setObjectName("titulo_area_vendas")
        layout.addWidget(titulo)
        layout.addStretch()

        self.setCentralWidget(area_vendas)
