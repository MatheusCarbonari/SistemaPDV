"""Padrão visual compartilhado pelos diálogos operacionais do PDV."""

from PySide6.QtWidgets import QDialog, QLineEdit


ESTILO_DIALOGO_ESCURO = """
QDialog[temaPdv="true"] {
    background: #171a1f;
    color: #e8edf2;
}
QDialog[temaPdv="true"] QLabel {
    color: #e3e8ed;
    background: transparent;
}
QDialog[temaPdv="true"] QLabel[papelVisual="titulo"] {
    color: #f7fbff;
    font-size: 19px;
    font-weight: 700;
}
QDialog[temaPdv="true"] QLabel[papelVisual="instrucao"] {
    color: #c7d0d8;
    line-height: 1.25;
}
QDialog[temaPdv="true"] QLabel[papelVisual="mensagem"] {
    color: #ffb8b1;
    background: #352426;
    border: 1px solid #7b4547;
    border-radius: 5px;
    padding: 7px 9px;
}
QDialog[temaPdv="true"] QLabel[papelVisual="mensagem"][semMensagem="true"] {
    background: transparent;
    border-color: transparent;
    padding: 0;
}
QDialog[temaPdv="true"] QGroupBox {
    color: #dce4ea;
    border: 1px solid #404850;
    border-radius: 6px;
    margin-top: 10px;
    font-weight: 700;
}
QDialog[temaPdv="true"] QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QDialog[temaPdv="true"] QLineEdit,
QDialog[temaPdv="true"] QPlainTextEdit,
QDialog[temaPdv="true"] QTableWidget {
    color: #f5f7fa;
    background: #23272e;
    border: 1px solid #5b6570;
    border-radius: 5px;
    selection-background-color: #245d85;
    selection-color: #ffffff;
}
QDialog[temaPdv="true"] QLineEdit {
    min-height: 30px;
    max-height: 30px;
    padding: 1px 8px;
}
QDialog[temaPdv="true"] QLineEdit:focus,
QDialog[temaPdv="true"] QPlainTextEdit:focus {
    border: 2px solid #4aa3df;
}
QDialog[temaPdv="true"] QHeaderView::section {
    color: #dfe7ed;
    background: #30363d;
    border: 0;
    border-right: 1px solid #4d5660;
    border-bottom: 1px solid #4d5660;
    padding: 6px;
    font-weight: 700;
}
QDialog[temaPdv="true"] QPushButton {
    color: #e8edf2;
    background: #2a2f36;
    border: 1px solid #525d68;
    border-radius: 5px;
    min-height: 30px;
    padding: 2px 13px;
}
QDialog[temaPdv="true"] QPushButton:hover:enabled {
    background: #353c44;
    border-color: #687684;
}
QDialog[temaPdv="true"] QPushButton:default,
QDialog[temaPdv="true"] QPushButton[papelVisual="principal"] {
    background: #176b9c;
    border-color: #3d9bd1;
    color: #ffffff;
    font-weight: 700;
}
QDialog[temaPdv="true"] QPushButton:disabled {
    color: #929ba4;
    background: #22262c;
    border-color: #3c4249;
}
QDialog[temaPdv="true"] QLabel[papelVisual="destaque"] {
    color: #f7fbff;
    background: #1d3040;
    border: 1px solid #4d83aa;
    border-radius: 5px;
    padding: 8px 10px;
    font-weight: 700;
}
QDialog[temaPdv="true"] QLabel[dadoAlterado="true"] {
    color: #ffe09a;
    background: #352f20;
    border: 1px solid #7b6738;
    border-radius: 4px;
    padding: 5px 7px;
    font-weight: 700;
}
"""

ESTILO_MENSAGENS_ESCURO = """
/* mensagens-pdv */
QMessageBox {
    background: #171a1f;
    color: #e8edf2;
}
QMessageBox QLabel {
    color: #e8edf2;
    min-width: 320px;
}
QMessageBox QPushButton {
    color: #e8edf2;
    background: #2a2f36;
    border: 1px solid #525d68;
    border-radius: 5px;
    min-width: 90px;
    min-height: 30px;
    padding: 2px 12px;
}
QMessageBox QPushButton:hover {
    background: #353c44;
    border-color: #687684;
}
"""


def aplicar_padrao_dialogo(
    dialogo: QDialog,
    *,
    nome: str,
    tamanho: tuple[int, int],
    minimo: tuple[int, int],
) -> None:
    dialogo.setObjectName(nome)
    dialogo.setProperty("temaPdv", True)
    dialogo.resize(*tamanho)
    dialogo.setMinimumSize(*minimo)
    dialogo.setStyleSheet(ESTILO_DIALOGO_ESCURO)


def configurar_campo_texto(campo: QLineEdit, largura: int = 320) -> None:
    campo.setMaximumWidth(largura)


def atualizar_apresentacao_mensagem(rotulo, mensagem: str) -> None:
    rotulo.setText(mensagem)
    rotulo.setProperty("semMensagem", not bool(mensagem))
    estilo = rotulo.style()
    estilo.unpolish(rotulo)
    estilo.polish(rotulo)


def aplicar_tema_mensagens(aplicacao) -> None:
    estilo_atual = aplicacao.styleSheet()
    if "/* mensagens-pdv */" not in estilo_atual:
        aplicacao.setStyleSheet(f"{estilo_atual}\n{ESTILO_MENSAGENS_ESCURO}")
