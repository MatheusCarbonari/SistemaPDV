import sqlite3
from threading import Event, Thread

import pytest

from database.schema import criar_tabelas
from services.catalogo_memoria_service import CatalogoProdutosMemoria
from services.estado_operacional_service import (
    ControladorEstadoOperacional,
    ModoOperacional,
    OperacaoProibidaNoModoAtualError,
    exigir_modo_normal,
    falha_sqlite_permite_degradacao,
    vincular_controlador_ao_banco,
)
from services.persistencia_venda_service import persistir_venda_confirmada
from services.cancelamento_venda_service import cancelar_venda
from services.produto_service import alterar_situacao_produto
import services.produto_service as produto_service_module
from tests.helpers_identidade import criar_sessao_admin_teste


def _catalogo_disponivel(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    banco = tmp_path / "pdv.db"
    criar_tabelas(banco)
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    return banco, catalogo


@pytest.mark.parametrize(
    "mensagem",
    (
        "database is locked",
        "database table is locked",
        "unable to open database file",
        "disk I/O error",
    ),
)
def test_falhas_sqlite_de_acesso_sao_elegiveis(mensagem) -> None:
    assert falha_sqlite_permite_degradacao(sqlite3.OperationalError(mensagem))


@pytest.mark.parametrize(
    "erro",
    (
        ValueError("erro comercial"),
        sqlite3.IntegrityError("constraint failed"),
        sqlite3.OperationalError("no such table: produtos"),
    ),
)
def test_erros_nao_operacionais_nao_ativam_degradacao(tmp_path, erro) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()

    assert not controlador.tentar_ativar_calculo_degradado(
        erro, catalogo, banco
    )
    assert controlador.obter_estado().modo is ModoOperacional.NORMAL


def test_ativa_calculo_com_catalogo_valido_e_nao_retorna_automaticamente(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()

    assert controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )
    assert controlador.obter_estado().modo is ModoOperacional.CALCULO_DEGRADADO
    assert controlador.permite_calculo()

    # Uma observação posterior de sucesso não possui API de retorno ao normal.
    assert not controlador.tentar_ativar_calculo_degradado(
        ValueError("SQLite voltou"), catalogo, banco
    )
    assert controlador.obter_estado().modo is ModoOperacional.CALCULO_DEGRADADO


def test_catalogo_indisponivel_torna_operacao_insegura(tmp_path) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    catalogo.invalidar("TESTE")
    controlador = ControladorEstadoOperacional()

    assert not controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )
    assert controlador.obter_estado().modo is ModoOperacional.INDISPONIVEL
    assert not controlador.permite_calculo()


def test_catalogo_de_outro_banco_e_rejeitado_sem_expor_caminho(tmp_path) -> None:
    banco_a, catalogo = _catalogo_disponivel(tmp_path / "a")
    banco_b = tmp_path / "b" / "pdv.db"
    banco_b.parent.mkdir()
    criar_tabelas(banco_b)
    controlador = ControladorEstadoOperacional()

    assert not controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco_b
    )
    estado = controlador.obter_estado()
    assert estado.modo is ModoOperacional.INDISPONIVEL
    assert str(banco_a) not in (estado.motivo or "")
    assert str(banco_b) not in (estado.motivo or "")


def test_barreiras_de_execucao_impedem_gravacoes_antes_de_validar_dados(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )
    vincular_controlador_ao_banco(banco, controlador)

    with pytest.raises(OperacaoProibidaNoModoAtualError):
        persistir_venda_confirmada(object(), banco, controlador_estado=controlador)
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        cancelar_venda(
            1,
            "motivo",
            object(),
            object(),
            banco,
            controlador_estado=controlador,
        )
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        alterar_situacao_produto(
            1,
            False,
            banco,
            sessao_solicitante=object(),
            controlador_estado=controlador,
        )


def test_persistencia_omitindo_controlador_respeita_vinculo_degradado(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )

    with pytest.raises(OperacaoProibidaNoModoAtualError):
        persistir_venda_confirmada(object(), banco)


def test_cancelamento_omitindo_controlador_respeita_vinculo_degradado(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )

    with pytest.raises(OperacaoProibidaNoModoAtualError):
        cancelar_venda(1, "motivo", object(), object(), banco)


def test_mutacao_produto_omitindo_controlador_respeita_vinculo_degradado(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )

    with pytest.raises(OperacaoProibidaNoModoAtualError):
        alterar_situacao_produto(
            1,
            False,
            banco,
            sessao_solicitante=object(),
        )


def test_controlador_normal_artificial_nao_substitui_autoridade_degradada(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador_degradado = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador_degradado)
    controlador_degradado.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )
    controlador_artificial = ControladorEstadoOperacional()

    assert (
        vincular_controlador_ao_banco(banco, controlador_artificial)
        is controlador_degradado
    )
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        exigir_modo_normal(banco, controlador_artificial)
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        persistir_venda_confirmada(
            object(),
            banco,
            controlador_estado=controlador_artificial,
        )


def test_fluxo_sem_vinculo_degradado_preserva_comportamento_normal(
    tmp_path,
) -> None:
    banco, _ = _catalogo_disponivel(tmp_path)

    exigir_modo_normal(banco, None)
    with pytest.raises(TypeError, match="VendaConfirmada"):
        persistir_venda_confirmada(object(), banco)


def test_invalidacao_do_catalogo_encerra_permissao_de_calculo(tmp_path) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )

    catalogo.invalidar("TESTE_INVALIDACAO")

    assert not controlador.permite_calculo()
    estado = controlador.obter_estado()
    assert estado.modo is ModoOperacional.INDISPONIVEL
    assert estado.motivo == "CATALOGO_INVALIDADO_DURANTE_DEGRADACAO"


def test_nova_ativacao_recusa_catalogo_invalidado_durante_degradacao(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    resultados = []
    thread_transicao = Thread(
        target=lambda: resultados.append(
            controlador.tentar_ativar_calculo_degradado(
                sqlite3.OperationalError("database is locked"),
                catalogo,
                banco,
            )
        )
    )
    thread_transicao.start()
    thread_transicao.join(5)

    assert not thread_transicao.is_alive()
    assert resultados == [True]
    catalogo.invalidar("TESTE_INVALIDACAO")

    assert not controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )
    assert controlador.obter_estado().modo is ModoOperacional.INDISPONIVEL
    assert not controlador.permite_calculo()


def test_operacao_comercial_bloqueia_transicao_ate_concluir_e_rejeita_nova_escrita(
    tmp_path,
    monkeypatch,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    sessao = criar_sessao_admin_teste(banco)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    escrita_iniciada = Event()
    liberar_escrita = Event()
    transicao_iniciada = Event()
    transicao_concluida = Event()
    erros: list[BaseException] = []
    chamadas = []

    def gravar_produto(**kwargs):
        chamadas.append(kwargs)
        escrita_iniciada.set()
        if not liberar_escrita.wait(5):
            raise TimeoutError("O teste não liberou a gravação.")
        return True

    monkeypatch.setattr(
        produto_service_module,
        "alterar_situacao_produto_repository",
        gravar_produto,
    )

    def executar_operacao() -> None:
        try:
            alterar_situacao_produto(
                1,
                False,
                banco,
                sessao_solicitante=sessao,
            )
        except BaseException as erro:
            erros.append(erro)

    def ativar_degradacao() -> None:
        transicao_iniciada.set()
        try:
            controlador.tentar_ativar_calculo_degradado(
                sqlite3.OperationalError("database is locked"),
                catalogo,
                banco,
            )
        except BaseException as erro:
            erros.append(erro)
        finally:
            transicao_concluida.set()

    thread_operacao = Thread(target=executar_operacao)
    thread_operacao.start()
    assert escrita_iniciada.wait(5)
    bloqueio_disponivel = controlador._bloqueio.acquire(blocking=False)
    if bloqueio_disponivel:
        controlador._bloqueio.release()
    assert not bloqueio_disponivel

    thread_transicao = Thread(target=ativar_degradacao)
    thread_transicao.start()
    assert transicao_iniciada.wait(5)
    assert not transicao_concluida.is_set()

    liberar_escrita.set()
    thread_operacao.join(5)
    thread_transicao.join(5)

    assert not thread_operacao.is_alive()
    assert not thread_transicao.is_alive()
    assert erros == []
    assert len(chamadas) == 1
    assert controlador.obter_estado().modo is ModoOperacional.CALCULO_DEGRADADO
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        alterar_situacao_produto(
            1,
            True,
            banco,
            sessao_solicitante=sessao,
        )
    assert len(chamadas) == 1


def test_excecao_comercial_libera_bloqueio_para_transicao(
    tmp_path,
    monkeypatch,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    sessao = criar_sessao_admin_teste(banco)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)

    monkeypatch.setattr(
        produto_service_module,
        "alterar_situacao_produto_repository",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("falha controlada")),
    )

    with pytest.raises(RuntimeError, match="falha controlada"):
        alterar_situacao_produto(
            1,
            False,
            banco,
            sessao_solicitante=sessao,
        )

    resultados = []
    thread_transicao = Thread(
        target=lambda: resultados.append(
            controlador.tentar_ativar_calculo_degradado(
                sqlite3.OperationalError("database is locked"),
                catalogo,
                banco,
            )
        )
    )
    thread_transicao.start()
    thread_transicao.join(5)

    assert not thread_transicao.is_alive()
    assert resultados == [True]


def test_caminhos_equivalentes_e_bancos_distintos_preservam_autoridades(
    tmp_path,
) -> None:
    banco_a, catalogo_a = _catalogo_disponivel(tmp_path / "a")
    banco_b, _ = _catalogo_disponivel(tmp_path / "b")
    controlador_a = ControladorEstadoOperacional()
    controlador_b = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco_a, controlador_a)
    vincular_controlador_ao_banco(banco_b, controlador_b)
    caminho_equivalente = banco_a.parent / "segmento" / ".." / banco_a.name

    assert (
        vincular_controlador_ao_banco(
            caminho_equivalente,
            ControladorEstadoOperacional(),
        )
        is controlador_a
    )
    assert controlador_a.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo_a, banco_a
    )
    exigir_modo_normal(banco_b, None)
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        exigir_modo_normal(caminho_equivalente, None)


def test_substituir_arquivo_no_mesmo_caminho_nao_remove_estado_conservador(
    tmp_path,
) -> None:
    banco, catalogo = _catalogo_disponivel(tmp_path)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    assert controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"), catalogo, banco
    )
    substituto = tmp_path / "substituto.db"
    criar_tabelas(substituto)
    substituto.replace(banco)

    assert (
        vincular_controlador_ao_banco(
            banco,
            ControladorEstadoOperacional(),
        )
        is controlador
    )
    with pytest.raises(OperacaoProibidaNoModoAtualError):
        exigir_modo_normal(banco, None)
