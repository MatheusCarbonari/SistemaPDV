from contextlib import contextmanager
import sys

import main as main_module
import services.migracao_dados_legados_service as migracao_module
from services.contexto_instalacao_service import (
    EstadoManutencaoInvalidoError,
    resolver_contexto_instalacao,
)
from services.instancia_unica_service import InstanciaJaExecutandoError


def _contexto(tmp_path):
    return resolver_contexto_instalacao(
        empacotado=False,
        caminho_executavel=sys.executable,
        raiz_repositorio=tmp_path / "repositorio",
    )


def test_exclusividade_e_manutencao_antecedem_importacao_da_aplicacao(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _contexto(tmp_path)
    ordem = []

    @contextmanager
    def exclusividade(contexto_recebido):
        assert contexto_recebido is contexto
        ordem.append("mutex")
        yield object()

    monkeypatch.setattr(main_module, "obter_contexto_instalacao", lambda: contexto)
    monkeypatch.setattr(main_module, "adquirir_instancia_unica", exclusividade)
    monkeypatch.setattr(
        main_module,
        "verificar_estado_manutencao",
        lambda contexto_recebido: ordem.append("manutencao"),
    )
    monkeypatch.setattr(
        main_module,
        "_executar_aplicacao_exclusiva",
        lambda contexto_recebido: ordem.append("aplicacao") or 7,
    )
    monkeypatch.setattr(sys, "argv", ["Sistema-PDV"])

    assert main_module.main() == 7
    assert ordem == ["mutex", "manutencao", "aplicacao"]


def test_segunda_instancia_avisa_sem_inicializar_aplicacao_ou_criar_arquivos(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _contexto(tmp_path)
    avisos = []

    class ExclusividadeRecusada:
        def __enter__(self):
            raise InstanciaJaExecutandoError("já aberta")

        def __exit__(self, tipo, valor, traceback):
            return None

    monkeypatch.setattr(main_module, "obter_contexto_instalacao", lambda: contexto)
    monkeypatch.setattr(
        main_module,
        "adquirir_instancia_unica",
        lambda contexto_recebido: ExclusividadeRecusada(),
    )
    monkeypatch.setattr(
        main_module,
        "exibir_aviso_segunda_instancia",
        lambda: avisos.append("aviso"),
    )
    monkeypatch.setattr(
        main_module,
        "_executar_aplicacao_exclusiva",
        lambda contexto_recebido: (_ for _ in ()).throw(
            AssertionError("a aplicação não deve ser importada")
        ),
    )
    monkeypatch.setattr(sys, "argv", ["Sistema-PDV"])

    assert main_module.main() == 0
    assert avisos == ["aviso"]
    assert not (tmp_path / "repositorio").exists()


def test_estado_de_manutencao_invalido_bloqueia_antes_da_aplicacao(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _contexto(tmp_path)
    erros = []

    @contextmanager
    def exclusividade(contexto_recebido):
        yield object()

    monkeypatch.setattr(main_module, "obter_contexto_instalacao", lambda: contexto)
    monkeypatch.setattr(main_module, "adquirir_instancia_unica", exclusividade)
    monkeypatch.setattr(
        main_module,
        "verificar_estado_manutencao",
        lambda contexto_recebido: (_ for _ in ()).throw(
            EstadoManutencaoInvalidoError("atualização incompleta")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_executar_aplicacao_exclusiva",
        lambda contexto_recebido: (_ for _ in ()).throw(
            AssertionError("a aplicação não deve iniciar")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "exibir_erro_inicializacao_segura",
        lambda mensagem: erros.append(mensagem),
    )
    monkeypatch.setattr(sys, "argv", ["Sistema-PDV"])

    assert main_module.main() == 1
    assert erros == ["atualização incompleta"]


def test_modo_migracao_administrativa_nao_inicia_fluxo_operacional(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _contexto(tmp_path)
    chamadas = []
    monkeypatch.setattr(main_module, "obter_contexto_instalacao", lambda: contexto)
    monkeypatch.setattr(
        migracao_module,
        "migrar_dados_legados",
        lambda origem, destino, *, confirmacao: chamadas.append(
            (origem, destino, confirmacao)
        ),
    )
    monkeypatch.setattr(
        main_module,
        "adquirir_instancia_unica",
        lambda contexto_recebido: (_ for _ in ()).throw(
            AssertionError("o mutex operacional não deve ser adquirido")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_executar_aplicacao_exclusiva",
        lambda contexto_recebido: (_ for _ in ()).throw(
            AssertionError("a aplicação não deve iniciar")
        ),
    )
    origem = tmp_path / "selecionado.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "Sistema-PDV",
            "--t60-migrar-dados-legados",
            str(origem),
            "--confirmar-ambiente",
            "MIGRAR DADOS LEGADOS PARA PRODUCAO",
        ],
    )

    assert main_module.main() == 0
    assert chamadas == [
        (str(origem), contexto, "MIGRAR DADOS LEGADOS PARA PRODUCAO")
    ]


def test_modo_migracao_recusa_argumentos_incompletos(monkeypatch) -> None:
    erros = []
    monkeypatch.setattr(
        main_module,
        "exibir_erro_inicializacao_segura",
        lambda mensagem: erros.append(mensagem),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["Sistema-PDV", "--t60-migrar-dados-legados"],
    )

    assert main_module.main() == 1
    assert erros == ["Os argumentos da migração administrativa são inválidos."]
