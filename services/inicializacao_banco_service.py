from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from database.conexao import CAMINHO_BANCO, conectar
from database.migracoes import (
    ConcorrenciaMigracaoError,
    EstruturaEsquemaDivergenteError,
    IntegridadeEsquemaError,
    PlanoMigracao,
    RotaMigracaoIndisponivelError,
    VersaoEsquemaFuturaError,
    inspecionar_migracao,
    validar_estrutura_versao,
)
from database.schema import VERSAO_ESQUEMA, criar_tabelas
from services.backup_local_service import (
    CoordenacaoBackupError,
    coordenar_diretorio_backup,
    criar_copia_sqlite_consistente,
)
from services.contexto_instalacao_service import (
    ContextoInstalacao,
    ContextoInstalacaoError,
    obter_contexto_instalacao,
    verificar_estado_manutencao,
)


class InicializacaoBancoError(RuntimeError):
    pass


class VersaoBancoFuturaError(InicializacaoBancoError):
    pass


class BackupPreMigracaoError(InicializacaoBancoError):
    pass


class MigracaoBancoError(InicializacaoBancoError):
    pass


class BancoIncompativelError(InicializacaoBancoError):
    pass


class InicializacaoConcorrenteError(InicializacaoBancoError):
    pass


class AtualizacaoCoordenadaNecessariaError(InicializacaoBancoError):
    pass


class ContextoBancoComercialError(InicializacaoBancoError):
    pass


@dataclass(frozen=True)
class ResultadoInicializacaoBanco:
    caminho_banco: Path
    banco_novo: bool
    versao_inicial: int
    versao_final: int
    caminho_backup: Path | None = None
    migracoes_realizadas: tuple[str, ...] = ()
    declaracao_compatibilidade_aplicativo_anterior: str = "NAO_APLICAVEL"
    homologacao_compatibilidade_aplicativo_anterior: str = "NAO_APLICAVEL"
    backup_pre_migracao_realizado: bool = False
    estado_migracao: str = "SEM_ALTERACOES"
    banco_apto_operacao_aplicativo_atual: bool = False
    proxima_etapa_atualizacao_autorizada: bool = False


def preparar_banco_para_operacao(
    caminho_banco: str | Path = CAMINHO_BANCO,
    *,
    contexto: ContextoInstalacao | None = None,
) -> ResultadoInicializacaoBanco:
    """Aplica a política de preparação adequada ao contexto da instalação."""
    contexto_efetivo = contexto or obter_contexto_instalacao()
    caminho = Path(caminho_banco)
    if contexto_efetivo.comercial:
        _validar_preparacao_comercial(contexto_efetivo, caminho)
    banco_novo = not caminho.exists()
    caminho_backup = None

    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with coordenar_diretorio_backup(
            caminho.parent,
            _nome_lock_migracao(caminho),
        ):
            if contexto_efetivo.comercial:
                _validar_preparacao_comercial(contexto_efetivo, caminho)
            banco_novo = not caminho.exists()
            if not banco_novo:
                plano = inspecionar_migracao(caminho)
                if plano.migracoes:
                    if contexto_efetivo.comercial:
                        raise AtualizacaoCoordenadaNecessariaError(
                            "O banco comercial exige atualização coordenada "
                            "antes de iniciar o Sistema-PDV."
                        )
                    caminho_backup = _criar_backup_pre_migracao(
                        caminho,
                        plano.versao_inicial,
                    )
                elif contexto_efetivo.comercial:
                    return _resultado_validacao_comercial(caminho, plano)
            resultado_migracao = criar_tabelas(
                caminho,
                validar_estrutura_estrita=True,
            )
            inspecionar_migracao(caminho, banco_novo=banco_novo)
    except (AtualizacaoCoordenadaNecessariaError, ContextoBancoComercialError):
        raise
    except BackupPreMigracaoError:
        raise
    except VersaoEsquemaFuturaError as erro:
        raise VersaoBancoFuturaError(
            "O banco usa uma versão de esquema mais nova que a aplicação. "
            "Atualize o Sistema-PDV antes de continuar."
        ) from erro
    except (
        EstruturaEsquemaDivergenteError,
        IntegridadeEsquemaError,
        RotaMigracaoIndisponivelError,
    ) as erro:
        raise BancoIncompativelError(
            "O banco não corresponde a uma versão de esquema compatível."
        ) from erro
    except ConcorrenciaMigracaoError as erro:
        raise InicializacaoConcorrenteError(
            "Outra instância está preparando o banco de dados."
        ) from erro
    except CoordenacaoBackupError as erro:
        raise InicializacaoConcorrenteError(
            "Outra instância está preparando o banco de dados."
        ) from erro
    except Exception as erro:
        if banco_novo:
            mensagem = "Não foi possível criar o banco de dados da aplicação."
        else:
            mensagem = (
                "A migração do banco falhou e foi interrompida. "
                "O backup pré-migração foi preservado."
            )
        raise MigracaoBancoError(
            mensagem
        ) from erro

    return ResultadoInicializacaoBanco(
        caminho_banco=caminho,
        banco_novo=banco_novo,
        versao_inicial=resultado_migracao.versao_inicial,
        versao_final=resultado_migracao.versao_final,
        caminho_backup=caminho_backup,
        migracoes_realizadas=resultado_migracao.migracoes_realizadas,
        declaracao_compatibilidade_aplicativo_anterior=(
            resultado_migracao.declaracao_compatibilidade.value
        ),
        homologacao_compatibilidade_aplicativo_anterior=(
            resultado_migracao.homologacao_compatibilidade.value
        ),
        backup_pre_migracao_realizado=caminho_backup is not None,
        estado_migracao=resultado_migracao.estado.value,
        banco_apto_operacao_aplicativo_atual=(
            resultado_migracao.banco_apto_operacao_aplicativo_atual
        ),
        proxima_etapa_atualizacao_autorizada=(
            resultado_migracao.proxima_etapa_atualizacao_autorizada
        ),
    )


def _validar_preparacao_comercial(
    contexto: ContextoInstalacao,
    caminho_banco: Path,
) -> None:
    try:
        verificar_estado_manutencao(contexto)
    except ContextoInstalacaoError as erro:
        raise ContextoBancoComercialError(
            "A instalação comercial não possui estado de manutenção livre."
        ) from erro
    esperado = contexto.caminhos.banco.resolve(strict=False)
    observado = caminho_banco.resolve(strict=False)
    if os.path.normcase(str(esperado)) != os.path.normcase(str(observado)):
        try:
            equivalente = os.path.samefile(esperado, observado)
        except OSError:
            equivalente = False
        if not equivalente:
            raise ContextoBancoComercialError(
                "O banco informado não pertence ao contexto da instalação."
            )


def _resultado_validacao_comercial(
    caminho_banco: Path,
    plano: PlanoMigracao,
) -> ResultadoInicializacaoBanco:
    return ResultadoInicializacaoBanco(
        caminho_banco=caminho_banco,
        banco_novo=False,
        versao_inicial=plano.versao_inicial,
        versao_final=plano.versao_alvo,
        declaracao_compatibilidade_aplicativo_anterior=(
            plano.declaracao_compatibilidade.value
        ),
        homologacao_compatibilidade_aplicativo_anterior=(
            plano.homologacao_compatibilidade.value
        ),
        estado_migracao="SEM_ALTERACOES",
        banco_apto_operacao_aplicativo_atual=True,
        proxima_etapa_atualizacao_autorizada=False,
    )


def _nome_lock_migracao(caminho_banco: Path) -> str:
    chave = str(caminho_banco.resolve(strict=False)).casefold().encode("utf-8")
    identificador = hashlib.sha256(chave).hexdigest()[:16]
    return f".sistema-pdv-migracao.{identificador}.lock"


def _consultar_versao(caminho_banco: Path) -> int:
    conexao = None
    try:
        conexao = conectar(caminho_banco)
        return conexao.execute("PRAGMA user_version").fetchone()[0]
    except (OSError, sqlite3.Error) as erro:
        raise InicializacaoBancoError(
            "Não foi possível abrir o banco de dados da aplicação."
        ) from erro
    finally:
        if conexao is not None:
            conexao.close()


def _criar_backup_pre_migracao(
    caminho_banco: Path,
    versao_inicial: int,
) -> Path:
    diretorio = caminho_banco.parent / "backups" / "pre_migracao"
    caminho_backup = None

    try:
        diretorio.mkdir(parents=True, exist_ok=True)
        instante = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        sufixo_unico = uuid4().hex
        caminho_backup = diretorio / (
            f"{caminho_banco.stem}.v{versao_inicial}"
            f"-para-v{VERSAO_ESQUEMA}.{instante}.{sufixo_unico}.db"
        )
        _executar_backup_sqlite(
            caminho_banco,
            caminho_backup,
            versao_esperada=versao_inicial,
        )
    except Exception as erro:
        if caminho_backup is not None:
            try:
                caminho_backup.unlink(missing_ok=True)
            except OSError:
                pass
        raise BackupPreMigracaoError(
            "Não foi possível criar e verificar o backup pré-migração. "
            "O banco original não foi alterado."
        ) from erro

    return caminho_backup


def _executar_backup_sqlite(
    caminho_origem: Path,
    caminho_destino: Path,
    *,
    versao_esperada: int,
) -> None:
    criar_copia_sqlite_consistente(
        caminho_origem,
        caminho_destino,
        validador=lambda copia: _verificar_integridade_backup(
            copia,
            versao_esperada=versao_esperada,
        ),
    )


def _verificar_integridade_backup(
    caminho_backup: Path,
    *,
    versao_esperada: int,
) -> None:
    uri = f"file:{caminho_backup.as_posix()}?mode=ro"
    conexao = sqlite3.connect(uri, uri=True)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao != versao_esperada:
            raise sqlite3.DatabaseError(
                "A cópia não corresponde à versão original esperada."
            )
        validar_estrutura_versao(conexao, versao)
    finally:
        conexao.close()
