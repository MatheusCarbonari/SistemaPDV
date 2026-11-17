import os
from pathlib import Path
import sys

from services.contexto_instalacao_service import (
    ContextoInstalacao,
    ContextoInstalacaoError,
    obter_contexto_instalacao,
    verificar_estado_manutencao,
)
from services.instancia_unica_service import (
    InstanciaJaExecutandoError,
    InstanciaUnicaError,
    adquirir_instancia_unica,
    exibir_aviso_segunda_instancia,
    exibir_erro_inicializacao_segura,
)


ARGUMENTO_SMOKE_TEST_T59 = "--t59-smoke-test"


def main() -> int:
    """Inicia a aplicação desktop do Sistema-PDV."""
    if ARGUMENTO_SMOKE_TEST_T59 in sys.argv[1:]:
        return _executar_smoke_test_empacotamento()
    try:
        contexto = obter_contexto_instalacao()
        with adquirir_instancia_unica(contexto):
            verificar_estado_manutencao(contexto)
            return _executar_aplicacao_exclusiva(contexto)
    except InstanciaJaExecutandoError:
        exibir_aviso_segunda_instancia()
        return 0
    except (ContextoInstalacaoError, InstanciaUnicaError) as erro:
        exibir_erro_inicializacao_segura(str(erro))
        return 1


def _executar_aplicacao_exclusiva(contexto: ContextoInstalacao) -> int:
    """Importa a aplicação somente depois de adquirir a exclusividade."""
    from interface.aplicacao import executar_aplicacao

    return executar_aplicacao(contexto=contexto)


def _executar_smoke_test_empacotamento() -> int:
    """Valida o runtime congelado e o Qt sem abrir ou criar o banco."""
    from PySide6.QtWidgets import QApplication, QWidget

    from services.contexto_instalacao_service import execucao_empacotada
    from services.version_service import obter_identificacao_aplicativo

    if not execucao_empacotada():
        return 20
    raiz_isolada = os.environ.get("LOCALAPPDATA")
    if not raiz_isolada:
        return 21
    caminho_isolado = Path(raiz_isolada)
    if (
        not caminho_isolado.is_absolute()
        or not caminho_isolado.is_dir()
        or _contem_arquivos(caminho_isolado)
    ):
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
    return 0 if not _contem_arquivos(caminho_isolado) else 24


def _contem_arquivos(diretorio: Path) -> bool:
    try:
        return any(item.is_file() for item in diretorio.rglob("*"))
    except OSError:
        return True


if __name__ == "__main__":
    raise SystemExit(main())
