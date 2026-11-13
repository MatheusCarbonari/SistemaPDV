import sqlite3

import pytest

from database.conexao import conectar
from models.produto import Produto
from repositories.produto_repository import salvar_produto
import services.contingencia_service as contingencia_module
from services.catalogo_memoria_service import (
    CATALOGO_DISPONIVEL,
    CatalogoProdutosMemoria,
)
from services.contingencia_service import (
    CondicaoTecnicaNaoComprovadaError,
    ConfirmacaoRetomadaObrigatoriaError,
    FechamentoIncertoBloqueiaRetomadaError,
    RetomadaNaoAutorizadaError,
    confirmar_retomada_operacional,
    verificar_recuperacao_sqlite,
)
from services.estado_operacional_service import (
    ControladorEstadoOperacional,
    ControladorOperacionalNaoCanonicoError,
    ModoOperacional,
    vincular_controlador_ao_banco,
)
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_sessao_admin_teste,
)


SENHA_CAIXA_TESTE = "frase segura individual do caixa 2026"


def _ambiente_degradado(tmp_path, *, nome="recuperacao.db"):
    banco = tmp_path / nome
    sessao_admin = criar_sessao_admin_teste(banco)
    salvar_produto(
        Produto(
            codigo="101",
            nome="Produto inicial",
            categoria="GERAL",
            forma_venda="UNIDADE",
            preco_venda_centavos=1000,
            origem="COMPRADO",
        ),
        banco,
    )
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    assert controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"),
        catalogo,
        banco,
    )
    return banco, sessao_admin, catalogo, controlador


def _confirmar(banco, catalogo, controlador, **kwargs):
    parametros = {
        "controlador_estado": controlador,
        "catalogo_produtos": catalogo,
        "identificacao_administrador": "administrador",
        "senha_administrador": SENHA_ADMIN_TESTE,
        "confirmacao_explicita": True,
        "fechamento_incerto": False,
    }
    parametros.update(kwargs)
    return confirmar_retomada_operacional(banco, **parametros)


def test_verificacao_tecnica_comprova_condicoes_sem_liberar_automaticamente(
    tmp_path,
) -> None:
    banco, _, _, controlador = _ambiente_degradado(tmp_path)
    conexao = conectar(banco)
    try:
        contagens_antes = tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("produtos", "vendas", "itens_venda", "pagamentos")
        )
    finally:
        conexao.close()

    resultado = verificar_recuperacao_sqlite(
        banco,
        controlador_estado=controlador,
        fechamento_incerto=False,
    )

    conexao = conectar(banco)
    try:
        contagens_depois = tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("produtos", "vendas", "itens_venda", "pagamentos")
        )
    finally:
        conexao.close()
    assert resultado.recuperacao_comprovada
    assert resultado.codigo == "RECUPERACAO_COMPROVADA"
    assert contagens_depois == contagens_antes
    assert controlador.obter_estado().modo is ModoOperacional.CALCULO_DEGRADADO


def test_retomada_revalida_admin_recarrega_catalogo_e_libera_normal(
    tmp_path,
) -> None:
    banco, _, catalogo, controlador = _ambiente_degradado(tmp_path)
    salvar_produto(
        Produto(
            codigo="202",
            nome="Produto recuperado",
            categoria="GERAL",
            forma_venda="UNIDADE",
            preco_venda_centavos=2500,
            origem="COMPRADO",
        ),
        banco,
    )

    resultado = _confirmar(banco, catalogo, controlador)

    assert resultado.codigo == "RETOMADA_CONFIRMADA"
    assert controlador.obter_estado().modo is ModoOperacional.NORMAL
    assert catalogo.obter_estado().status == CATALOGO_DISPONIVEL
    assert catalogo.consultar_produto("202").nome == "Produto recuperado"


def test_banco_ausente_nao_e_criado_nem_liberado(tmp_path) -> None:
    banco, _, _, controlador = _ambiente_degradado(tmp_path)
    banco.unlink()

    resultado = verificar_recuperacao_sqlite(
        banco,
        controlador_estado=controlador,
        fechamento_incerto=False,
    )

    assert not resultado.recuperacao_comprovada
    assert resultado.codigo == "BANCO_INDISPONIVEL"
    assert not banco.exists()
    assert controlador.obter_estado().modo is not ModoOperacional.NORMAL


def test_falha_durante_verificacao_mantem_estado_restritivo(
    tmp_path,
    monkeypatch,
) -> None:
    banco, _, _, controlador = _ambiente_degradado(tmp_path)
    monkeypatch.setattr(
        contingencia_module,
        "conectar",
        lambda caminho: (_ for _ in ()).throw(
            sqlite3.OperationalError("disk I/O error")
        ),
    )

    resultado = verificar_recuperacao_sqlite(
        banco,
        controlador_estado=controlador,
        fechamento_incerto=False,
    )

    assert not resultado.recuperacao_comprovada
    assert resultado.codigo == "VERIFICACAO_FALHOU"
    assert controlador.obter_estado().modo is not ModoOperacional.NORMAL


def test_catalogo_que_falha_na_reconstrucao_impede_retomada(
    tmp_path,
    monkeypatch,
) -> None:
    banco, _, catalogo, controlador = _ambiente_degradado(tmp_path)

    def falhar_carga(caminho):
        catalogo.invalidar("FALHA_TESTE")
        raise sqlite3.OperationalError("falha controlada")

    monkeypatch.setattr(catalogo, "carregar", falhar_carga)

    with pytest.raises(CondicaoTecnicaNaoComprovadaError):
        _confirmar(banco, catalogo, controlador)
    assert controlador.obter_estado().modo is ModoOperacional.INDISPONIVEL


def test_catalogo_de_outro_banco_nao_pode_ser_usado_na_retomada(tmp_path) -> None:
    banco_a, _, catalogo_a, _ = _ambiente_degradado(tmp_path / "a")
    banco_b, _, _, controlador_b = _ambiente_degradado(tmp_path / "b")

    with pytest.raises(CondicaoTecnicaNaoComprovadaError):
        _confirmar(banco_b, catalogo_a, controlador_b)
    assert controlador_b.obter_estado().modo is not ModoOperacional.NORMAL
    assert catalogo_a.consultar_produto("101") is not None
    assert banco_a != banco_b


def test_retomada_exige_confirmacao_explicita(tmp_path) -> None:
    banco, _, catalogo, controlador = _ambiente_degradado(tmp_path)

    with pytest.raises(ConfirmacaoRetomadaObrigatoriaError):
        _confirmar(
            banco,
            catalogo,
            controlador,
            confirmacao_explicita=False,
        )
    assert controlador.obter_estado().modo is not ModoOperacional.NORMAL


def test_credenciais_de_caixa_nao_autorizam_retomada(tmp_path) -> None:
    banco, sessao_admin, catalogo, controlador = _ambiente_degradado(tmp_path)
    usuario, erros = criar_conta_caixa(
        sessao_admin,
        "caixa01",
        SENHA_CAIXA_TESTE,
        SENHA_CAIXA_TESTE,
        banco,
    )
    assert usuario is not None
    assert erros == []

    with pytest.raises(RetomadaNaoAutorizadaError):
        _confirmar(
            banco,
            catalogo,
            controlador,
            identificacao_administrador="caixa01",
            senha_administrador=SENHA_CAIXA_TESTE,
        )
    assert controlador.obter_estado().modo is not ModoOperacional.NORMAL


def test_fechamento_incerto_bloqueia_verificacao_e_confirmacao(tmp_path) -> None:
    banco, _, catalogo, controlador = _ambiente_degradado(tmp_path)

    verificacao = verificar_recuperacao_sqlite(
        banco,
        controlador_estado=controlador,
        fechamento_incerto=True,
    )
    assert verificacao.codigo == "FECHAMENTO_INCERTO"
    with pytest.raises(FechamentoIncertoBloqueiaRetomadaError):
        _confirmar(
            banco,
            catalogo,
            controlador,
            fechamento_incerto=True,
        )
    assert controlador.obter_estado().modo is not ModoOperacional.NORMAL


def test_controlador_independente_nao_autoriza_retomada(tmp_path) -> None:
    banco, _, catalogo, controlador = _ambiente_degradado(tmp_path)
    artificial = ControladorEstadoOperacional()

    with pytest.raises(ControladorOperacionalNaoCanonicoError):
        _confirmar(banco, catalogo, artificial)
    assert controlador.obter_estado().modo is not ModoOperacional.NORMAL


def test_segunda_vinculacao_do_mesmo_banco_preserva_controlador_restritivo(
    tmp_path,
) -> None:
    banco, _, _, controlador = _ambiente_degradado(tmp_path)

    segunda_janela = vincular_controlador_ao_banco(
        banco,
        ControladorEstadoOperacional(),
    )

    assert segunda_janela is controlador
    assert segunda_janela.obter_estado().modo is ModoOperacional.CALCULO_DEGRADADO
