import os
from pathlib import Path
import subprocess
import sys

import pytest

from services.contexto_instalacao_service import (
    AMBIENTE_HOMOLOGACAO_ID,
    AMBIENTE_PRODUCAO_ID,
    PRODUTO_ID,
    AmbienteInstalacao,
    CaminhosInstalacao,
    ContextoInstalacao,
    resolver_contexto_instalacao,
)
from services.instancia_unica_service import (
    InstanciaJaExecutandoError,
    adquirir_instancia_unica,
    criar_nome_mutex,
)


RAIZ_PROJETO = Path(__file__).resolve().parent.parent


class BackendMemoria:
    def __init__(self):
        self.chamadas = []
        self.liberados = []

    def adquirir(self, nome, *, grupo_operadores):
        self.chamadas.append((nome, grupo_operadores))
        return object(), False

    def liberar(self, recurso):
        self.liberados.append(recurso)


def _contexto_desenvolvimento(raiz: Path):
    return resolver_contexto_instalacao(
        empacotado=False,
        caminho_executavel=sys.executable,
        raiz_repositorio=raiz,
    )


def _contexto_comercial(tmp_path: Path) -> ContextoInstalacao:
    raiz = tmp_path / "ProgramData" / "Sistema-PDV" / "Producao"
    caminhos = CaminhosInstalacao(
        raiz,
        raiz / "data",
        raiz / "data" / "sistema_acougue.db",
        raiz / "logs",
        raiz / "config",
        raiz / "administrative",
        raiz / "administrative" / "installation.json",
        raiz / "administrative" / "manifests",
        raiz / "maintenance",
        raiz / "maintenance" / "state.json",
    )
    return ContextoInstalacao(
        PRODUTO_ID,
        AmbienteInstalacao.PRODUCAO,
        AMBIENTE_PRODUCAO_ID,
        "52df1475-60e8-4490-a16f-9d8ff82fcba6",
        True,
        tmp_path / "Sistema-PDV.exe",
        tmp_path,
        caminhos,
    )


def _ambiente_subprocesso() -> dict[str, str]:
    ambiente = os.environ.copy()
    ambiente["PYTHONPATH"] = str(RAIZ_PROJETO)
    return ambiente


def test_mutex_comercial_e_global_e_vinculado_a_instalacao(tmp_path) -> None:
    contexto = _contexto_comercial(tmp_path)

    nome = criar_nome_mutex(contexto)

    assert nome.startswith("Global\\Sistema-PDV-")
    assert contexto.ambiente_id in nome
    assert contexto.instalacao_id in nome


def test_producao_e_homologacao_nao_compartilham_mutex(tmp_path) -> None:
    producao = _contexto_comercial(tmp_path)
    homologacao = ContextoInstalacao(
        producao.produto_id,
        AmbienteInstalacao.HOMOLOGACAO,
        AMBIENTE_HOMOLOGACAO_ID,
        producao.instalacao_id,
        True,
        producao.caminho_executavel,
        producao.raiz_instalacao,
        producao.caminhos,
    )

    assert criar_nome_mutex(producao) != criar_nome_mutex(homologacao)


def test_backend_recebe_grupo_operadores_somente_no_contexto_comercial(
    tmp_path,
) -> None:
    backend = BackendMemoria()
    contexto = _contexto_comercial(tmp_path)

    with adquirir_instancia_unica(contexto, backend=backend):
        pass

    assert backend.chamadas[0][1] == "Sistema-PDV-Operadores"
    assert len(backend.liberados) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="contrato específico do Windows")
def test_instancia_unica_funciona_entre_processos(tmp_path) -> None:
    contexto = _contexto_desenvolvimento(tmp_path / "repositorio")
    codigo = r"""
import sys
from pathlib import Path
from services.contexto_instalacao_service import resolver_contexto_instalacao
from services.instancia_unica_service import adquirir_instancia_unica, InstanciaJaExecutandoError
contexto = resolver_contexto_instalacao(empacotado=False, raiz_repositorio=Path(sys.argv[1]))
try:
    with adquirir_instancia_unica(contexto):
        raise SystemExit(20)
except InstanciaJaExecutandoError:
    raise SystemExit(0)
"""

    with adquirir_instancia_unica(contexto):
        resultado = subprocess.run(
            [sys.executable, "-c", codigo, str(tmp_path / "repositorio")],
            cwd=RAIZ_PROJETO,
            env=_ambiente_subprocesso(),
            check=False,
        )

    assert resultado.returncode == 0


@pytest.mark.skipif(sys.platform != "win32", reason="contrato específico do Windows")
def test_encerramento_normal_libera_mutex(tmp_path) -> None:
    contexto = _contexto_desenvolvimento(tmp_path / "repositorio")

    with adquirir_instancia_unica(contexto):
        pass
    with adquirir_instancia_unica(contexto) as estado:
        assert estado.mutex_abandonado is False


@pytest.mark.skipif(sys.platform != "win32", reason="contrato específico do Windows")
def test_encerramento_abrupto_nao_deixa_lock_abandonado_permanente(
    tmp_path,
) -> None:
    raiz = tmp_path / "repositorio"
    contexto = _contexto_desenvolvimento(raiz)
    codigo = r"""
import sys, time
from pathlib import Path
from services.contexto_instalacao_service import resolver_contexto_instalacao
from services.instancia_unica_service import adquirir_instancia_unica
contexto = resolver_contexto_instalacao(empacotado=False, raiz_repositorio=Path(sys.argv[1]))
with adquirir_instancia_unica(contexto):
    print("READY", flush=True)
    time.sleep(60)
"""
    processo = subprocess.Popen(
        [sys.executable, "-c", codigo, str(raiz)],
        cwd=RAIZ_PROJETO,
        env=_ambiente_subprocesso(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert processo.stdout.readline().strip() == "READY"
        processo.kill()
        processo.wait(timeout=10)

        with adquirir_instancia_unica(contexto) as estado:
            assert estado.nome == criar_nome_mutex(contexto)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)
