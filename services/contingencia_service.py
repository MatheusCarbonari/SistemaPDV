"""Protocolo controlado de verificação e retomada operacional do T54."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from database.conexao import CAMINHO_BANCO, conectar
from database.schema import TABELAS_ESSENCIAIS, VERSAO_ESQUEMA
from services.autenticacao_service import (
    LIMITADOR_LOGIN_PADRAO,
    coordenar_credenciais,
    validar_credenciais_usuario,
)
from services.catalogo_memoria_service import (
    CATALOGO_DISPONIVEL,
    CatalogoProdutosMemoria,
)
from services.estado_operacional_service import (
    ControladorEstadoOperacional,
    ModoOperacional,
    recuperacao_operacional_protegida,
)


class RetomadaOperacionalError(RuntimeError):
    pass


class ConfirmacaoRetomadaObrigatoriaError(RetomadaOperacionalError):
    pass


class RetomadaNaoAutorizadaError(RetomadaOperacionalError):
    pass


class FechamentoIncertoBloqueiaRetomadaError(RetomadaOperacionalError):
    pass


class CondicaoTecnicaNaoComprovadaError(RetomadaOperacionalError):
    pass


@dataclass(frozen=True, slots=True)
class ResumoContingencia:
    modo: ModoOperacional
    calculo_apenas_memoria: bool
    persistencia_bloqueada: bool
    catalogo_disponivel: bool
    fechamento_incerto: bool
    orientacao: str


@dataclass(frozen=True, slots=True)
class ResultadoVerificacaoRecuperacao:
    recuperacao_comprovada: bool
    codigo: str
    mensagem: str


def resumir_contingencia(
    controlador: ControladorEstadoOperacional,
    catalogo: CatalogoProdutosMemoria,
    *,
    fechamento_incerto: bool,
) -> ResumoContingencia:
    if not isinstance(controlador, ControladorEstadoOperacional):
        raise TypeError("O controlador operacional é inválido.")
    if not isinstance(catalogo, CatalogoProdutosMemoria):
        raise TypeError("O catálogo em memória é inválido.")
    if not isinstance(fechamento_incerto, bool):
        raise TypeError("O estado do fechamento incerto deve ser booleano.")

    modo = controlador.obter_estado().modo
    catalogo_disponivel = (
        catalogo.obter_estado().status == CATALOGO_DISPONIVEL
    )
    if fechamento_incerto:
        orientacao = (
            "Resolva o fechamento pendente antes de solicitar a retomada."
        )
    elif modo is ModoOperacional.CALCULO_DEGRADADO:
        orientacao = (
            "Os valores são apenas cálculos em memória e não representam "
            "vendas registradas."
        )
    elif modo is ModoOperacional.INDISPONIVEL:
        orientacao = (
            "Aguarde a recuperação técnica antes de continuar o atendimento."
        )
    else:
        orientacao = "A operação normal está disponível."
    return ResumoContingencia(
        modo=modo,
        calculo_apenas_memoria=(
            modo is ModoOperacional.CALCULO_DEGRADADO
        ),
        persistencia_bloqueada=(modo is not ModoOperacional.NORMAL),
        catalogo_disponivel=catalogo_disponivel,
        fechamento_incerto=fechamento_incerto,
        orientacao=orientacao,
    )


def verificar_recuperacao_sqlite(
    caminho_banco: str | Path = CAMINHO_BANCO,
    *,
    controlador_estado: ControladorEstadoOperacional,
    fechamento_incerto: bool,
) -> ResultadoVerificacaoRecuperacao:
    if not isinstance(fechamento_incerto, bool):
        raise TypeError("O estado do fechamento incerto deve ser booleano.")
    with recuperacao_operacional_protegida(
        caminho_banco,
        controlador_estado,
    ):
        if (
            fechamento_incerto
            or controlador_estado.possui_fechamento_incerto()
        ):
            return ResultadoVerificacaoRecuperacao(
                False,
                "FECHAMENTO_INCERTO",
                "Existe um fechamento com resultado incerto que precisa ser resolvido.",
            )
        if controlador_estado.obter_estado().modo is ModoOperacional.NORMAL:
            return ResultadoVerificacaoRecuperacao(
                True,
                "JA_NORMAL",
                "O sistema já está em operação normal.",
            )
        return _verificar_condicao_tecnica(caminho_banco)


def confirmar_retomada_operacional(
    caminho_banco: str | Path = CAMINHO_BANCO,
    *,
    controlador_estado: ControladorEstadoOperacional,
    catalogo_produtos: CatalogoProdutosMemoria,
    identificacao_administrador,
    senha_administrador,
    confirmacao_explicita: bool,
    fechamento_incerto: bool,
    limitador=LIMITADOR_LOGIN_PADRAO,
) -> ResultadoVerificacaoRecuperacao:
    if not isinstance(fechamento_incerto, bool):
        raise TypeError("O estado do fechamento incerto deve ser booleano.")
    if confirmacao_explicita is not True:
        raise ConfirmacaoRetomadaObrigatoriaError(
            "A retomada exige confirmação explícita do Administrador."
        )
    if fechamento_incerto:
        raise FechamentoIncertoBloqueiaRetomadaError(
            "Resolva o fechamento com resultado incerto antes da retomada."
        )
    if not isinstance(catalogo_produtos, CatalogoProdutosMemoria):
        raise TypeError("O catálogo em memória informado é inválido.")

    with recuperacao_operacional_protegida(
        caminho_banco,
        controlador_estado,
    ) as controlador_canonico:
        if controlador_canonico.possui_fechamento_incerto():
            raise FechamentoIncertoBloqueiaRetomadaError(
                "Resolva o fechamento com resultado incerto antes da retomada."
            )
        if controlador_canonico.obter_estado().modo is ModoOperacional.NORMAL:
            return ResultadoVerificacaoRecuperacao(
                True,
                "JA_NORMAL",
                "O sistema já está em operação normal.",
            )
        verificacao = _verificar_condicao_tecnica(caminho_banco)
        if not verificacao.recuperacao_comprovada:
            raise CondicaoTecnicaNaoComprovadaError(verificacao.mensagem)

        try:
            with coordenar_credenciais():
                administrador = validar_credenciais_usuario(
                    identificacao_administrador,
                    senha_administrador,
                    caminho_banco,
                    limitador=limitador,
                )
        except Exception as erro:
            raise RetomadaNaoAutorizadaError(
                "A retomada exige credenciais válidas de Administrador."
            ) from erro
        if administrador.perfil != "ADMINISTRADOR":
            raise RetomadaNaoAutorizadaError(
                "A retomada exige credenciais válidas de Administrador."
            )

        try:
            catalogo_produtos.vincular_ou_validar_banco(caminho_banco)
            catalogo_produtos.carregar(caminho_banco)
        except Exception as erro:
            raise CondicaoTecnicaNaoComprovadaError(
                "O catálogo não pôde ser reconstruído com segurança."
            ) from erro

        controlador_canonico._retomar_modo_normal_sem_bloquear()
        return ResultadoVerificacaoRecuperacao(
            True,
            "RETOMADA_CONFIRMADA",
            "Operação normal retomada com confirmação administrativa.",
        )


def _verificar_condicao_tecnica(
    caminho_banco: str | Path,
) -> ResultadoVerificacaoRecuperacao:
    caminho = Path(caminho_banco)
    if not caminho.is_file():
        return _falha_tecnica(
            "BANCO_INDISPONIVEL",
            "O banco ainda não está disponível para verificação.",
        )

    conexao = None
    try:
        conexao = conectar(caminho)
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao != VERSAO_ESQUEMA:
            return _falha_tecnica(
                "SCHEMA_INCOMPATIVEL",
                "A versão do banco não é compatível com esta aplicação.",
            )

        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not TABELAS_ESSENCIAIS.issubset(tabelas):
            return _falha_tecnica(
                "ESTRUTURA_INCOMPLETA",
                "A estrutura essencial do banco não está completa.",
            )
        for tabela in TABELAS_ESSENCIAIS:
            conexao.execute(f'SELECT 1 FROM "{tabela}" LIMIT 1').fetchone()

        integridade = tuple(
            linha[0]
            for linha in conexao.execute("PRAGMA quick_check").fetchall()
        )
        if integridade != ("ok",):
            return _falha_tecnica(
                "INTEGRIDADE_NAO_COMPROVADA",
                "A integridade do banco não pôde ser confirmada.",
            )

        conexao.execute("BEGIN IMMEDIATE")
        conexao.rollback()
        return ResultadoVerificacaoRecuperacao(
            True,
            "RECUPERACAO_COMPROVADA",
            "Leitura, integridade e capacidade operacional foram confirmadas.",
        )
    except (OSError, sqlite3.Error):
        return _falha_tecnica(
            "VERIFICACAO_FALHOU",
            "O banco ainda não oferece condições seguras para retomada.",
        )
    finally:
        if conexao is not None:
            try:
                conexao.rollback()
            except sqlite3.Error:
                pass
            conexao.close()


def _falha_tecnica(
    codigo: str,
    mensagem: str,
) -> ResultadoVerificacaoRecuperacao:
    return ResultadoVerificacaoRecuperacao(False, codigo, mensagem)
