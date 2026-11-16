"""Motor único de migrações SQLite versionadas do Sistema-PDV."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Callable

from database.conexao import CAMINHO_BANCO, conectar
import database.schema as schema


TIMEOUT_MIGRACAO_MS = 5_000
VERSAO_MINIMA_OPERACIONAL = schema.VERSAO_ESQUEMA
VERSAO_MAXIMA_OPERACIONAL = schema.VERSAO_ESQUEMA


class MigracaoError(RuntimeError):
    pass


class VersaoEsquemaFuturaError(MigracaoError):
    pass


class RotaMigracaoIndisponivelError(MigracaoError):
    pass


class EstruturaEsquemaDivergenteError(MigracaoError):
    pass


class IntegridadeEsquemaError(MigracaoError):
    pass


class ConcorrenciaMigracaoError(MigracaoError):
    pass


class RollbackMigracaoNaoComprovadoError(MigracaoError):
    pass


class DeclaracaoCompatibilidade(str, Enum):
    NAO_DECLARADA = "NAO_DECLARADA"
    COMPATIVEL = "COMPATIVEL"
    INCOMPATIVEL = "INCOMPATIVEL"


class EstadoDeclaracaoCompatibilidade(str, Enum):
    NAO_APLICAVEL = "NAO_APLICAVEL"
    NAO_DECLARADA = "NAO_DECLARADA"
    DECLARADA_COMPATIVEL = "DECLARADA_COMPATIVEL"
    DECLARADA_INCOMPATIVEL = "DECLARADA_INCOMPATIVEL"


class EstadoHomologacaoCompatibilidade(str, Enum):
    NAO_APLICAVEL = "NAO_APLICAVEL"
    PENDENTE = "PENDENTE"
    HOMOLOGADA = "HOMOLOGADA"


class EstadoExecucaoMigracao(str, Enum):
    SEM_ALTERACOES = "SEM_ALTERACOES"
    SUCESSO = "SUCESSO"


@dataclass(frozen=True, slots=True)
class HomologacaoCompatibilidade:
    versao_aplicativo_anterior: str
    referencia_evidencia: str

    def __post_init__(self) -> None:
        if not self.versao_aplicativo_anterior.strip():
            raise ValueError("A homologação deve identificar o aplicativo anterior.")
        if not self.referencia_evidencia.strip():
            raise ValueError("A homologação deve referenciar sua evidência técnica.")


@dataclass(frozen=True, slots=True)
class MigracaoVersionada:
    origem: int
    destino: int
    identificador: str
    aplicar: Callable[[sqlite3.Connection], None]
    legada: bool
    compatibilidade_declarada: DeclaracaoCompatibilidade
    homologacao: HomologacaoCompatibilidade | None = None

    def __post_init__(self) -> None:
        if self.destino != self.origem + 1:
            raise ValueError("Cada migração deve avançar exatamente uma versão.")
        if not self.identificador:
            raise ValueError("A migração deve possuir identificação.")
        if not isinstance(self.compatibilidade_declarada, DeclaracaoCompatibilidade):
            raise TypeError("A declaração de compatibilidade é inválida.")
        if self.homologacao is not None and (
            self.legada
            or self.compatibilidade_declarada is not DeclaracaoCompatibilidade.COMPATIVEL
        ):
            raise ValueError(
                "Somente migração futura declarada compatível pode ser homologada."
            )


@dataclass(frozen=True, slots=True)
class PlanoMigracao:
    versao_inicial: int
    versao_alvo: int
    migracoes: tuple[MigracaoVersionada, ...]
    banco_novo: bool
    declaracao_compatibilidade: EstadoDeclaracaoCompatibilidade
    homologacao_compatibilidade: EstadoHomologacaoCompatibilidade
    proxima_etapa_atualizacao_autorizada: bool


@dataclass(frozen=True, slots=True)
class ResultadoMigracao:
    estado: EstadoExecucaoMigracao
    versao_inicial: int
    versao_final: int
    migracoes_realizadas: tuple[str, ...]
    banco_novo: bool
    declaracao_compatibilidade: EstadoDeclaracaoCompatibilidade
    homologacao_compatibilidade: EstadoHomologacaoCompatibilidade
    banco_apto_operacao_aplicativo_atual: bool
    proxima_etapa_atualizacao_autorizada: bool


@dataclass(frozen=True, slots=True)
class _ContratoColuna:
    tipo: str
    obrigatoria: bool = False
    chave_primaria: bool = False
    padrao: str | None = None


@dataclass(frozen=True, slots=True)
class _ContratoIndice:
    tabela: str
    colunas: tuple[str, ...]
    unico: bool
    nome: str | None = None
    descendentes: tuple[bool, ...] = ()
    colacoes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ContratoChaveEstrangeira:
    tabela: str
    coluna: str
    tabela_destino: str
    coluna_destino: str
    ao_excluir: str = "RESTRICT"
    ao_atualizar: str = "NO ACTION"


def _migrar_v0_v1(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
    conexao.execute(schema._COMANDO_CRIAR_VENDAS)


def _migrar_v1_v2(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_ITENS_VENDA)


def _migrar_v2_v3(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_PAGAMENTOS)


def _migrar_v3_v4(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_ADICIONAR_IDENTIFICADOR_TENTATIVA)
    conexao.execute(schema._COMANDO_CRIAR_INDICE_TENTATIVA)


def _migrar_v4_v5(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_INDICE_HISTORICO_VENDAS)


def _migrar_v5_v6(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_ADICIONAR_MOTIVO_CANCELAMENTO)
    conexao.execute(schema._COMANDO_ADICIONAR_DATA_CANCELAMENTO)
    conexao.execute(schema._COMANDO_ADICIONAR_AUTORIZADOR_CANCELAMENTO)
    conexao.execute(schema._COMANDO_ADICIONAR_STATUS_VENDA)


def _migrar_v6_v7(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_HISTORICO_PRECOS)
    conexao.execute(schema._COMANDO_CRIAR_INDICE_HISTORICO_PRECOS)


def _migrar_v7_v8(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_USUARIOS)
    conexao.execute(schema._COMANDO_CRIAR_ESTADO_IDENTIDADE)
    conexao.execute(schema._COMANDO_INICIALIZAR_ESTADO_IDENTIDADE)


def _migrar_v8_v9(conexao: sqlite3.Connection) -> None:
    conexao.execute(schema._COMANDO_CRIAR_CODIGOS_RECUPERACAO)
    conexao.execute(schema._COMANDO_CRIAR_INDICE_CODIGOS_RECUPERACAO)


def _migrar_v9_v10(conexao: sqlite3.Connection) -> None:
    schema._migrar_categorias_v10(conexao)


# Rotas v0→v10 são históricas. Nenhuma comprova compatibilidade com o
# aplicativo anterior nem autoriza o avanço de um instalador coordenado.
MIGRACOES: tuple[MigracaoVersionada, ...] = (
    MigracaoVersionada(
        0, 1, "legado_0001_produtos_vendas", _migrar_v0_v1, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        1, 2, "legado_0002_itens_venda", _migrar_v1_v2, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        2, 3, "legado_0003_pagamentos", _migrar_v2_v3, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        3, 4, "legado_0004_idempotencia", _migrar_v3_v4, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        4, 5, "legado_0005_indice_historico", _migrar_v4_v5, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        5, 6, "legado_0006_cancelamento", _migrar_v5_v6, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        6, 7, "legado_0007_historico_precos", _migrar_v6_v7, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        7, 8, "legado_0008_identidade", _migrar_v7_v8, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        8, 9, "legado_0009_recuperacao", _migrar_v8_v9, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
    MigracaoVersionada(
        9, 10, "legado_0010_categorias", _migrar_v9_v10, True,
        DeclaracaoCompatibilidade.NAO_DECLARADA,
    ),
)


def planejar_migracao(
    versao_inicial: int,
    *,
    banco_novo: bool,
    migracoes: tuple[MigracaoVersionada, ...] = MIGRACOES,
) -> PlanoMigracao:
    return planejar_rota_migracao(
        versao_inicial,
        schema.VERSAO_ESQUEMA,
        banco_novo=banco_novo,
        migracoes=migracoes,
    )


def planejar_rota_migracao(
    versao_inicial: int,
    versao_alvo: int,
    *,
    banco_novo: bool,
    migracoes: tuple[MigracaoVersionada, ...],
) -> PlanoMigracao:
    if not isinstance(versao_inicial, int) or isinstance(versao_inicial, bool):
        raise TypeError("A versão inicial do esquema deve ser inteira.")
    if not isinstance(versao_alvo, int) or isinstance(versao_alvo, bool):
        raise TypeError("A versão alvo do esquema deve ser inteira.")
    if versao_inicial < 0:
        raise RotaMigracaoIndisponivelError(
            "A versão do esquema não possui rota de migração."
        )
    if versao_inicial > versao_alvo:
        raise VersaoEsquemaFuturaError(
            "O banco usa uma versão de esquema mais nova que a aplicação."
        )

    por_origem: dict[int, MigracaoVersionada] = {}
    for migracao in migracoes:
        if migracao.origem in por_origem:
            raise ValueError("Existe mais de uma migração para a mesma origem.")
        por_origem[migracao.origem] = migracao

    rota = []
    versao = versao_inicial
    while versao < versao_alvo:
        migracao = por_origem.get(versao)
        if migracao is None:
            raise RotaMigracaoIndisponivelError(
                "Não existe caminho completo para atualizar o esquema."
            )
        rota.append(migracao)
        versao = migracao.destino

    if banco_novo or not rota:
        declaracao = EstadoDeclaracaoCompatibilidade.NAO_APLICAVEL
        homologacao = EstadoHomologacaoCompatibilidade.NAO_APLICAVEL
        autoriza = False
    elif any(
        item.compatibilidade_declarada is DeclaracaoCompatibilidade.INCOMPATIVEL
        for item in rota
    ):
        declaracao = EstadoDeclaracaoCompatibilidade.DECLARADA_INCOMPATIVEL
        homologacao = EstadoHomologacaoCompatibilidade.PENDENTE
        autoriza = False
    elif any(
        item.compatibilidade_declarada is DeclaracaoCompatibilidade.NAO_DECLARADA
        for item in rota
    ):
        declaracao = EstadoDeclaracaoCompatibilidade.NAO_DECLARADA
        homologacao = EstadoHomologacaoCompatibilidade.PENDENTE
        autoriza = False
    else:
        declaracao = EstadoDeclaracaoCompatibilidade.DECLARADA_COMPATIVEL
        homologada = not any(item.legada for item in rota) and all(
            item.homologacao is not None for item in rota
        )
        homologacao = (
            EstadoHomologacaoCompatibilidade.HOMOLOGADA
            if homologada
            else EstadoHomologacaoCompatibilidade.PENDENTE
        )
        autoriza = homologada
    return PlanoMigracao(
        versao_inicial,
        versao_alvo,
        tuple(rota),
        banco_novo,
        declaracao,
        homologacao,
        autoriza,
    )


def executar_migracoes(
    caminho_banco: str | Path = CAMINHO_BANCO,
    *,
    antes_de_migrar: Callable[[PlanoMigracao], None] | None = None,
    validar_estrutura_estrita: bool = True,
) -> ResultadoMigracao:
    caminho = Path(caminho_banco)
    banco_novo = not caminho.exists()
    conexao = conectar(caminho)
    chaves_desabilitadas = False
    versao_original = None
    alteracoes_iniciadas = False
    try:
        conexao.execute(f"PRAGMA busy_timeout = {TIMEOUT_MIGRACAO_MS}")
        versao_observada = _consultar_versao(conexao)
        if versao_observada < schema.VERSAO_ESQUEMA:
            conexao.execute("PRAGMA foreign_keys = OFF")
            chaves_desabilitadas = True
        try:
            conexao.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as erro:
            raise ConcorrenciaMigracaoError(
                "Outra instância está preparando o banco de dados."
            ) from erro

        versao_original = _consultar_versao(conexao)
        plano = planejar_migracao(
            versao_original,
            banco_novo=banco_novo,
        )
        validar_estrutura_versao(
            conexao,
            versao_original,
            estrita=validar_estrutura_estrita,
        )
        if not plano.migracoes:
            conexao.commit()
            return ResultadoMigracao(
                EstadoExecucaoMigracao.SEM_ALTERACOES,
                versao_original,
                versao_original,
                (),
                banco_novo,
                plano.declaracao_compatibilidade,
                plano.homologacao_compatibilidade,
                True,
                plano.proxima_etapa_atualizacao_autorizada,
            )

        if antes_de_migrar is not None:
            antes_de_migrar(plano)
        for migracao in plano.migracoes:
            alteracoes_iniciadas = True
            migracao.aplicar(conexao)
            _atualizar_versao(conexao, migracao.destino)
            validar_estrutura_versao(
                conexao,
                migracao.destino,
                estrita=validar_estrutura_estrita,
            )
        conexao.commit()
        return ResultadoMigracao(
            EstadoExecucaoMigracao.SUCESSO,
            versao_original,
            schema.VERSAO_ESQUEMA,
            tuple(item.identificador for item in plano.migracoes),
            banco_novo,
            plano.declaracao_compatibilidade,
            plano.homologacao_compatibilidade,
            True,
            plano.proxima_etapa_atualizacao_autorizada,
        )
    except BaseException as erro:
        conexao.rollback()
        if versao_original is not None and alteracoes_iniciadas:
            try:
                if chaves_desabilitadas:
                    conexao.execute("PRAGMA foreign_keys = ON")
                    chaves_desabilitadas = False
                validar_estrutura_versao(
                    conexao,
                    versao_original,
                    estrita=validar_estrutura_estrita,
                )
            except Exception as erro_rollback:
                raise RollbackMigracaoNaoComprovadoError(
                    "A migração falhou e o estado anterior não pôde ser comprovado."
                ) from erro_rollback
        raise erro
    finally:
        if chaves_desabilitadas:
            conexao.execute("PRAGMA foreign_keys = ON")
        conexao.close()


def inspecionar_migracao(
    caminho_banco: str | Path,
    *,
    banco_novo: bool = False,
) -> PlanoMigracao:
    """Valida versão, estrutura e rota sem modificar o banco."""
    conexao = None
    try:
        conexao = _conectar_somente_leitura(caminho_banco)
        versao = _consultar_versao(conexao)
        plano = planejar_migracao(versao, banco_novo=banco_novo)
        validar_estrutura_versao(conexao, versao, estrita=True)
        return plano
    except MigracaoError:
        raise
    except (OSError, sqlite3.DatabaseError) as erro:
        raise IntegridadeEsquemaError(
            "O banco não pôde ser validado com segurança."
        ) from erro
    finally:
        if conexao is not None:
            conexao.close()


def validar_estrutura_versao(
    conexao: sqlite3.Connection,
    versao: int,
    *,
    estrita: bool = True,
) -> None:
    integridade = tuple(
        linha[0]
        for linha in conexao.execute("PRAGMA integrity_check").fetchall()
    )
    if integridade != ("ok",):
        raise IntegridadeEsquemaError(
            "A integridade do banco de dados não pôde ser confirmada."
        )
    tabelas = {
        linha[0]
        for linha in conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        if not linha[0].startswith("sqlite_")
    }
    if versao == 0:
        if estrita and tabelas:
            raise EstruturaEsquemaDivergenteError(
                "Um banco sem versão declarada contém estruturas desconhecidas."
            )
        return
    if not estrita:
        if conexao.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise IntegridadeEsquemaError(
                "Os relacionamentos do banco de dados não puderam ser confirmados."
            )
        return

    contratos_colunas = _contratos_colunas(versao)
    if not contratos_colunas.keys() <= tabelas:
        raise EstruturaEsquemaDivergenteError(
            "A estrutura do banco diverge da versão declarada."
        )
    for tabela, contrato in contratos_colunas.items():
        _validar_colunas(conexao, tabela, contrato)
    _validar_indices(conexao, _contratos_indices(versao))
    _validar_chaves_estrangeiras(
        conexao,
        contratos_colunas.keys(),
        _contratos_chaves_estrangeiras(versao),
    )
    if conexao.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise IntegridadeEsquemaError(
            "Os relacionamentos do banco de dados não puderam ser confirmados."
        )


def _contratos_colunas(
    versao: int,
) -> dict[str, dict[str, _ContratoColuna]]:
    pk = _ContratoColuna("INTEGER", chave_primaria=True)
    inteiro = _ContratoColuna("INTEGER")
    inteiro_obrigatorio = _ContratoColuna("INTEGER", obrigatoria=True)
    texto = _ContratoColuna("TEXT")
    texto_obrigatorio = _ContratoColuna("TEXT", obrigatoria=True)
    inteiro_ativo = _ContratoColuna("INTEGER", obrigatoria=True, padrao="1")
    instante_atual = _ContratoColuna(
        "TEXT", obrigatoria=True, padrao="CURRENT_TIMESTAMP"
    )
    produtos = {
        "id": pk,
        "codigo": texto_obrigatorio,
        "nome": texto_obrigatorio,
        "categoria": texto_obrigatorio,
        "forma_venda": texto_obrigatorio,
        "preco_venda_centavos": inteiro_obrigatorio,
        "origem": texto_obrigatorio,
        "ativo": inteiro_ativo,
        "criado_em": instante_atual,
        "atualizado_em": instante_atual,
    }
    if versao >= 10:
        produtos = dict(produtos)
        del produtos["categoria"]
        produtos["categoria_id"] = inteiro_obrigatorio
    vendas = {
        "id": pk,
        "total_centavos": inteiro_obrigatorio,
        "registrada_em": instante_atual,
    }
    if versao >= 4:
        vendas["identificador_tentativa"] = texto
    if versao >= 6:
        vendas.update(
            {
                "motivo_cancelamento": texto,
                "cancelada_em": texto,
                "autorizador_identidade": texto,
                "status": _ContratoColuna(
                    "TEXT", obrigatoria=True, padrao="'ATIVA'"
                ),
            }
        )
    contratos = {"produtos": produtos, "vendas": vendas}
    if versao >= 2:
        contratos["itens_venda"] = {
            "id": pk,
            "venda_id": inteiro_obrigatorio,
            "posicao": inteiro_obrigatorio,
            "produto_id": inteiro,
            "codigo_snapshot": texto,
            "nome_snapshot": texto,
            "forma_venda_snapshot": texto,
            "preco_referencia_centavos": inteiro,
            "tipo_item": texto,
            "origem": texto_obrigatorio,
            "origem_quantidade": texto_obrigatorio,
            "quantidade_decimal": texto,
            "codigo_barras": texto,
            "subtotal_centavos": inteiro_obrigatorio,
        }
    if versao >= 3:
        contratos["pagamentos"] = {
            "id": pk,
            "venda_id": inteiro_obrigatorio,
            "modalidade": texto_obrigatorio,
            "valor_centavos": inteiro_obrigatorio,
        }
    if versao >= 7:
        contratos["historico_precos_produtos"] = {
            "id": pk,
            "produto_id": inteiro_obrigatorio,
            "preco_anterior_centavos": inteiro_obrigatorio,
            "preco_novo_centavos": inteiro_obrigatorio,
            "alterado_em": instante_atual,
        }
    if versao >= 8:
        contratos["usuarios"] = {
            "id": pk,
            "identificacao_acesso": texto_obrigatorio,
            "perfil": texto_obrigatorio,
            "senha_hash": texto_obrigatorio,
            "ativo": inteiro_ativo,
            "criado_em": instante_atual,
        }
        contratos["estado_identidade"] = {
            "id": pk,
            "administrador_inicial_id": inteiro,
            "configurado_em": texto,
        }
    if versao >= 9:
        contratos["codigos_recuperacao"] = {
            "id": pk,
            "usuario_id": inteiro_obrigatorio,
            "conjunto_id": texto_obrigatorio,
            "verificador": texto_obrigatorio,
            "criado_em": instante_atual,
            "consumido_em": texto,
            "revogado_em": texto,
        }
    if versao >= 10:
        contratos["categorias"] = {
            "id": pk,
            "nome": texto_obrigatorio,
            "nome_chave": texto_obrigatorio,
            "ativo": inteiro_ativo,
        }
    return contratos


def _contratos_indices(versao: int) -> tuple[_ContratoIndice, ...]:
    contratos = [
        _ContratoIndice(
            "produtos", ("codigo",), True,
            descendentes=(False,), colacoes=("BINARY",),
        ),
    ]
    if versao >= 2:
        contratos.append(
            _ContratoIndice(
                "itens_venda",
                ("venda_id", "posicao"),
                True,
                descendentes=(False, False),
                colacoes=("BINARY", "BINARY"),
            )
        )
    if versao >= 4:
        contratos.append(
            _ContratoIndice(
                "vendas",
                ("identificador_tentativa",),
                True,
                "ux_vendas_identificador_tentativa",
                (False,),
                ("BINARY",),
            )
        )
    if versao >= 5:
        contratos.append(
            _ContratoIndice(
                "vendas",
                ("registrada_em", "id"),
                False,
                "ix_vendas_registrada_em_id",
                (True, True),
                ("BINARY", "BINARY"),
            )
        )
    if versao >= 7:
        contratos.append(
            _ContratoIndice(
                "historico_precos_produtos",
                ("produto_id", "alterado_em", "id"),
                False,
                "ix_historico_precos_produto_data",
                (False, True, True),
                ("BINARY", "BINARY", "BINARY"),
            )
        )
    if versao >= 8:
        contratos.extend(
            (
                _ContratoIndice(
                    "usuarios",
                    ("identificacao_acesso",),
                    True,
                    descendentes=(False,),
                    colacoes=("NOCASE",),
                ),
                _ContratoIndice(
                    "estado_identidade",
                    ("administrador_inicial_id",),
                    True,
                    descendentes=(False,),
                    colacoes=("BINARY",),
                ),
            )
        )
    if versao >= 9:
        contratos.extend(
            (
                _ContratoIndice(
                    "codigos_recuperacao",
                    ("verificador",),
                    True,
                    descendentes=(False,),
                    colacoes=("BINARY",),
                ),
                _ContratoIndice(
                    "codigos_recuperacao",
                    ("usuario_id", "conjunto_id", "id"),
                    False,
                    "ix_codigos_recuperacao_usuario_conjunto",
                    (False, False, False),
                    ("BINARY", "BINARY", "BINARY"),
                ),
            )
        )
    if versao >= 10:
        contratos.extend(
            (
                _ContratoIndice(
                    "categorias",
                    ("nome_chave",),
                    True,
                    descendentes=(False,),
                    colacoes=("BINARY",),
                ),
                _ContratoIndice(
                    "produtos",
                    ("categoria_id", "ativo", "nome"),
                    False,
                    "ix_produtos_categoria_ativo_nome",
                    (False, False, False),
                    ("BINARY", "BINARY", "BINARY"),
                ),
            )
        )
    return tuple(contratos)


def _contratos_chaves_estrangeiras(
    versao: int,
) -> tuple[_ContratoChaveEstrangeira, ...]:
    contratos: list[_ContratoChaveEstrangeira] = []
    if versao >= 2:
        contratos.extend(
            (
                _ContratoChaveEstrangeira(
                    "itens_venda", "venda_id", "vendas", "id"
                ),
                _ContratoChaveEstrangeira(
                    "itens_venda", "produto_id", "produtos", "id"
                ),
            )
        )
    if versao >= 3:
        contratos.append(
            _ContratoChaveEstrangeira(
                "pagamentos", "venda_id", "vendas", "id"
            )
        )
    if versao >= 7:
        contratos.append(
            _ContratoChaveEstrangeira(
                "historico_precos_produtos", "produto_id", "produtos", "id"
            )
        )
    if versao >= 8:
        contratos.append(
            _ContratoChaveEstrangeira(
                "estado_identidade",
                "administrador_inicial_id",
                "usuarios",
                "id",
            )
        )
    if versao >= 9:
        contratos.append(
            _ContratoChaveEstrangeira(
                "codigos_recuperacao", "usuario_id", "usuarios", "id"
            )
        )
    if versao >= 10:
        contratos.append(
            _ContratoChaveEstrangeira(
                "produtos", "categoria_id", "categorias", "id"
            )
        )
    return tuple(contratos)


def _validar_colunas(
    conexao: sqlite3.Connection,
    tabela: str,
    contrato: dict[str, _ContratoColuna],
) -> None:
    observadas = {
        linha[1]: linha
        for linha in conexao.execute(f'PRAGMA table_info("{tabela}")').fetchall()
    }
    if observadas.keys() != contrato.keys():
        raise EstruturaEsquemaDivergenteError(
            f"As colunas essenciais de {tabela} divergem da versão declarada."
        )
    for nome, esperado in contrato.items():
        observado = observadas[nome]
        if (
            str(observado[2]).upper() != esperado.tipo
            or bool(observado[3]) != esperado.obrigatoria
            or bool(observado[5]) != esperado.chave_primaria
            or observado[4] != esperado.padrao
        ):
            raise EstruturaEsquemaDivergenteError(
                f"A definição da coluna {tabela}.{nome} é incompatível."
            )


def _validar_indices(
    conexao: sqlite3.Connection,
    contratos: tuple[_ContratoIndice, ...],
) -> None:
    por_tabela: dict[str, list[dict[str, object]]] = {}
    for contrato in contratos:
        if contrato.tabela not in por_tabela:
            indices = []
            for linha in conexao.execute(
                f'PRAGMA index_list("{contrato.tabela}")'
            ).fetchall():
                detalhes = tuple(
                    detalhe
                    for detalhe in conexao.execute(
                        f'PRAGMA index_xinfo("{linha[1]}")'
                    ).fetchall()
                    if detalhe[5]
                )
                indices.append(
                    {
                        "nome": linha[1],
                        "unico": bool(linha[2]),
                        "parcial": bool(linha[4]),
                        "colunas": tuple(item[2] for item in detalhes),
                        "descendentes": tuple(bool(item[3]) for item in detalhes),
                        "colacoes": tuple(item[4].upper() for item in detalhes),
                    }
                )
            por_tabela[contrato.tabela] = indices
        encontrado = False
        for indice in por_tabela[contrato.tabela]:
            if contrato.nome is not None and indice["nome"] != contrato.nome:
                continue
            if indice["unico"] != contrato.unico:
                continue
            if indice["parcial"]:
                continue
            if indice["colunas"] != contrato.colunas:
                continue
            if contrato.descendentes and (
                indice["descendentes"] != contrato.descendentes
            ):
                continue
            if contrato.colacoes and indice["colacoes"] != contrato.colacoes:
                continue
            encontrado = True
            break
        if not encontrado:
            identificacao = contrato.nome or "/".join(contrato.colunas)
            raise EstruturaEsquemaDivergenteError(
                f"O índice essencial {identificacao} está ausente ou incompatível."
            )


def _validar_chaves_estrangeiras(
    conexao: sqlite3.Connection,
    tabelas: Iterable[str],
    contratos: tuple[_ContratoChaveEstrangeira, ...],
) -> None:
    esperadas_por_tabela: dict[str, set[tuple[str, ...]]] = {
        tabela: set() for tabela in tabelas
    }
    for contrato in contratos:
        esperadas_por_tabela[contrato.tabela].add(
            (
                contrato.coluna,
                contrato.tabela_destino,
                contrato.coluna_destino,
                contrato.ao_atualizar,
                contrato.ao_excluir,
            )
        )
    for tabela, esperadas in esperadas_por_tabela.items():
        observadas = {
            (
                linha[3],
                linha[2],
                linha[4],
                linha[5],
                linha[6],
            )
            for linha in conexao.execute(
                f'PRAGMA foreign_key_list("{tabela}")'
            ).fetchall()
        }
        if observadas != esperadas:
            raise EstruturaEsquemaDivergenteError(
                f"As chaves estrangeiras de {tabela} divergem da versão declarada."
            )


def versao_operacional_compativel(versao: int) -> bool:
    return VERSAO_MINIMA_OPERACIONAL <= versao <= VERSAO_MAXIMA_OPERACIONAL


def _consultar_versao(conexao: sqlite3.Connection) -> int:
    return conexao.execute("PRAGMA user_version").fetchone()[0]


def _atualizar_versao(conexao: sqlite3.Connection, versao: int) -> None:
    conexao.execute(f"PRAGMA user_version = {versao}")


def _conectar_somente_leitura(caminho_banco: str | Path) -> sqlite3.Connection:
    caminho = Path(caminho_banco).expanduser().resolve(strict=True)
    if not caminho.is_file():
        raise OSError("O banco informado não é um arquivo.")
    conexao = sqlite3.connect(f"{caminho.as_uri()}?mode=ro", uri=True)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao
