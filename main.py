import os
import sys

from interface.aplicacao import executar_aplicacao


ARGUMENTO_SMOKE_TEST_T59 = "--t59-smoke-test"


def main() -> int:
    """Inicia a aplicação desktop do Sistema-PDV."""
    if ARGUMENTO_SMOKE_TEST_T59 in sys.argv[1:]:
        return _executar_smoke_test_empacotamento()
    return executar_aplicacao()


def _executar_smoke_test_empacotamento() -> int:
    """Valida o runtime congelado e o Qt sem abrir ou criar o banco."""
    from PySide6.QtWidgets import QApplication, QWidget

    from database.conexao import (
        CAMINHO_BANCO,
        execucao_empacotada,
        resolver_caminho_banco,
    )
    from services.version_service import obter_identificacao_aplicativo

    if not execucao_empacotada() or CAMINHO_BANCO != resolver_caminho_banco():
        return 20
    if CAMINHO_BANCO.exists():
        return 21

    identificacao = obter_identificacao_aplicativo()
    build_esperado = os.environ.get("SISTEMA_PDV_SMOKE_BUILD_ID")
    commit_esperado = os.environ.get("SISTEMA_PDV_SMOKE_COMMIT_GIT")
    if build_esperado and identificacao.identificador_build != build_esperado:
        return 22
    if commit_esperado and identificacao.commit_git != commit_esperado:
        return 23

    aplicacao = QApplication.instance() or QApplication(["Sistema-PDV-smoke"])
    janela = QWidget()
    janela.setWindowTitle("Sistema-PDV smoke test")
    janela.show()
    aplicacao.processEvents()
    janela.close()
    aplicacao.processEvents()
    return 0 if not CAMINHO_BANCO.exists() else 24


if __name__ == "__main__":
    raise SystemExit(main())
