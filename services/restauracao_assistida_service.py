"""Restauração assistida e isolada de backups SQLite do T57."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

from database.conexao import CAMINHO_BANCO
from database.schema import TABELAS_ESSENCIAIS, VERSAO_ESQUEMA
from models.sessao_usuario import SessaoUsuario
from services.autenticacao_service import (
    LIMITADOR_LOGIN_PADRAO,
    autorizar_sessao,
    coordenar_credenciais,
    validar_credenciais_usuario,
)
from services.backup_local_service import (
    ValidacaoBackupError,
    validar_backup_sqlite,
)
from services.logging_service import registrar_evento


_PADRAO_BACKUP_OFICIAL = re.compile(
    r"^sistema-pdv-(?P<origem>local|externo)-v1\."
    r"[0-9a-f]{16}\."
    r"\d{8}T\d{12}Z\."
    r"[0-9a-f]{32}\.sqlite3$"
)
_PREFIXO_TEMPORARIO = ".sistema-pdv-restauracao-"


class OrigemBackup(str, Enum):
    LOCAL = "LOCAL"
    EXTERNO = "EXTERNO"


class RestauracaoAssistidaError(RuntimeError):
    pass


class ConfirmacaoRestauracaoObrigatoriaError(RestauracaoAssistidaError):
    pass


class RestauracaoNaoAutorizadaError(RestauracaoAssistidaError):
    pass


class BackupNaoEncontradoError(RestauracaoAssistidaError):
    pass


class AcessoBackupError(RestauracaoAssistidaError):
    pass


class BackupInvalidoError(RestauracaoAssistidaError):
    pass


class EstruturaBackupIncompativelError(RestauracaoAssistidaError):
    pass


class OrigemBackupNaoReconhecidaError(RestauracaoAssistidaError):
    pass


class DestinoRestauracaoInvalidoError(RestauracaoAssistidaError):
    pass


class BaseRestauradaJaExisteError(RestauracaoAssistidaError):
    pass


class PublicacaoRestauracaoError(RestauracaoAssistidaError):
    pass


@dataclass(frozen=True, slots=True)
class ResumoBaseRestaurada:
    produtos: int
    vendas: int
    pagamentos: int


@dataclass(frozen=True, slots=True)
class ResultadoRestauracaoAssistida:
    caminho_base_teste: Path
    origem_backup: OrigemBackup
    realizada_em: datetime
    resultado_validacao: str
    versao_schema: int
    registros: ResumoBaseRestaurada


def restaurar_backup_em_base_teste(
    caminho_backup: str | Path,
    caminho_destino: str | Path,
    sessao_solicitante: SessaoUsuario,
    caminho_banco_operacional: str | Path = CAMINHO_BANCO,
    *,
    identificacao_administrador,
    senha_administrador,
    confirmacao_explicita: bool,
    limitador=LIMITADOR_LOGIN_PADRAO,
) -> ResultadoRestauracaoAssistida:
    """Valida e publica uma cópia de teste sem alterar o banco operacional."""
    try:
        resultado = _restaurar_backup_em_base_teste(
            caminho_backup,
            caminho_destino,
            sessao_solicitante,
            caminho_banco_operacional,
            identificacao_administrador=identificacao_administrador,
            senha_administrador=senha_administrador,
            confirmacao_explicita=confirmacao_explicita,
            limitador=limitador,
        )
    except Exception as erro:
        registrar_evento(
            "restauracao_teste_falhou",
            erro_tipo=type(erro).__name__,
            resultado="falha",
        )
        raise
    registrar_evento(
        "restauracao_teste_concluida",
        resultado="sucesso",
    )
    return resultado


def _restaurar_backup_em_base_teste(
    caminho_backup: str | Path,
    caminho_destino: str | Path,
    sessao_solicitante: SessaoUsuario,
    caminho_banco_operacional: str | Path,
    *,
    identificacao_administrador,
    senha_administrador,
    confirmacao_explicita: bool,
    limitador,
) -> ResultadoRestauracaoAssistida:
    if confirmacao_explicita is not True:
        raise ConfirmacaoRestauracaoObrigatoriaError(
            "A restauração de teste exige confirmação explícita."
        )

    backup, origem = _selecionar_backup(caminho_backup)
    operacional = _resolver_banco_operacional(caminho_banco_operacional)
    if _mesmo_arquivo(backup, operacional):
        raise BackupInvalidoError(
            "O banco operacional não pode ser usado como backup de origem."
        )
    destino = _preparar_destino(caminho_destino, backup, operacional)
    _validar_base_sqlite(backup)
    _autorizar_restauracao(
        sessao_solicitante,
        operacional,
        identificacao_administrador,
        senha_administrador,
        limitador,
    )

    descritor, nome_temporario = tempfile.mkstemp(
        prefix=_PREFIXO_TEMPORARIO,
        suffix=".tmp",
        dir=destino.parent,
    )
    os.close(descritor)
    temporario = Path(nome_temporario)
    try:
        _copiar_backup(backup, temporario)
        versao, registros = _validar_base_sqlite(temporario)
        try:
            validar_backup_sqlite(temporario)
        except ValidacaoBackupError as erro:
            raise BackupInvalidoError(
                "A cópia recuperada não atendeu ao contrato do T55."
            ) from erro
        _publicar_sem_sobrescrever(temporario, destino)
        if not destino.is_file():
            raise PublicacaoRestauracaoError(
                "A base restaurada deixou de estar disponível."
            )
        return ResultadoRestauracaoAssistida(
            caminho_base_teste=destino,
            origem_backup=origem,
            realizada_em=datetime.now(UTC),
            resultado_validacao="VALIDA",
            versao_schema=versao,
            registros=registros,
        )
    finally:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass


def _selecionar_backup(caminho_backup: str | Path) -> tuple[Path, OrigemBackup]:
    if not isinstance(caminho_backup, (str, Path)):
        raise TypeError("O caminho do backup é inválido.")
    caminho = Path(caminho_backup).expanduser()
    if caminho.is_symlink():
        raise BackupInvalidoError(
            "Links simbólicos não são aceitos como backup."
        )
    if not caminho.exists():
        raise BackupNaoEncontradoError("O backup selecionado não existe.")
    if not caminho.is_file():
        raise BackupInvalidoError("O backup selecionado não é um arquivo regular.")
    try:
        resolvido = caminho.resolve(strict=True)
    except OSError as erro:
        raise AcessoBackupError("O backup selecionado não está acessível.") from erro

    correspondencia = _PADRAO_BACKUP_OFICIAL.fullmatch(resolvido.name)
    if correspondencia is None:
        raise OrigemBackupNaoReconhecidaError(
            "O arquivo não corresponde a um backup T55 ou T56 reconhecido."
        )
    origem = OrigemBackup(correspondencia.group("origem").upper())
    return resolvido, origem


def _resolver_banco_operacional(caminho_banco: str | Path) -> Path:
    if not isinstance(caminho_banco, (str, Path)):
        raise TypeError("O caminho do banco operacional é inválido.")
    caminho = Path(caminho_banco).expanduser()
    try:
        resolvido = caminho.resolve(strict=True)
    except OSError as erro:
        raise RestauracaoNaoAutorizadaError(
            "O banco operacional não está disponível para autorização."
        ) from erro
    if not resolvido.is_file():
        raise RestauracaoNaoAutorizadaError(
            "O banco operacional não está disponível para autorização."
        )
    return resolvido


def _mesmo_arquivo(primeiro: Path, segundo: Path) -> bool:
    if primeiro == segundo:
        return True
    try:
        return os.path.samefile(primeiro, segundo)
    except OSError:
        return False


def _preparar_destino(
    caminho_destino: str | Path,
    backup: Path,
    operacional: Path,
) -> Path:
    if not isinstance(caminho_destino, (str, Path)):
        raise TypeError("O caminho da base de teste é inválido.")
    informado = Path(caminho_destino).expanduser()
    if informado.is_symlink():
        raise DestinoRestauracaoInvalidoError(
            "Links simbólicos não são aceitos como destino."
        )
    pai = informado.parent
    if pai.is_symlink() or not pai.is_dir():
        raise DestinoRestauracaoInvalidoError(
            "O diretório da base de teste não é válido."
        )
    try:
        destino = pai.resolve(strict=True) / informado.name
    except OSError as erro:
        raise DestinoRestauracaoInvalidoError(
            "O diretório da base de teste não está acessível."
        ) from erro
    if destino == backup or destino == operacional:
        raise DestinoRestauracaoInvalidoError(
            "A base de teste deve ser separada do backup e do banco operacional."
        )
    if destino.exists() or destino.is_symlink():
        raise BaseRestauradaJaExisteError(
            "Já existe um arquivo no destino da base de teste."
        )
    return destino


def _autorizar_restauracao(
    sessao_solicitante: SessaoUsuario,
    banco_operacional: Path,
    identificacao_administrador,
    senha_administrador,
    limitador,
) -> None:
    try:
        with coordenar_credenciais():
            autorizar_sessao(
                sessao_solicitante,
                ("ADMINISTRADOR", "CAIXA"),
                banco_operacional,
            )
            administrador = validar_credenciais_usuario(
                identificacao_administrador,
                senha_administrador,
                banco_operacional,
                limitador=limitador,
            )
    except Exception as erro:
        raise RestauracaoNaoAutorizadaError(
            "A restauração exige sessão válida e credenciais administrativas."
        ) from erro
    if administrador.perfil != "ADMINISTRADOR":
        raise RestauracaoNaoAutorizadaError(
            "A restauração exige credenciais válidas de Administrador."
        )


def _validar_base_sqlite(caminho: Path) -> tuple[int, ResumoBaseRestaurada]:
    conexao = None
    try:
        try:
            conexao = sqlite3.connect(
                f"{caminho.as_uri()}?mode=ro",
                uri=True,
            )
        except (OSError, sqlite3.OperationalError) as erro:
            raise AcessoBackupError(
                "O arquivo SQLite não pôde ser aberto para leitura."
            ) from erro

        integridade = tuple(
            linha[0]
            for linha in conexao.execute("PRAGMA integrity_check").fetchall()
        )
        if integridade != ("ok",):
            raise BackupInvalidoError(
                "A integridade do backup não pôde ser confirmada."
            )
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao != VERSAO_ESQUEMA:
            raise EstruturaBackupIncompativelError(
                "A versão do backup não é compatível com a aplicação."
            )
        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not TABELAS_ESSENCIAIS.issubset(tabelas):
            raise EstruturaBackupIncompativelError(
                "A estrutura essencial do backup está incompleta."
            )
        for tabela in TABELAS_ESSENCIAIS:
            conexao.execute(f'SELECT 1 FROM "{tabela}" LIMIT 1').fetchone()
        if conexao.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BackupInvalidoError(
                "Os relacionamentos do backup não puderam ser confirmados."
            )
        registros = ResumoBaseRestaurada(
            produtos=_contar(conexao, "produtos"),
            vendas=_contar(conexao, "vendas"),
            pagamentos=_contar(conexao, "pagamentos"),
        )
        return versao, registros
    except (BackupInvalidoError, EstruturaBackupIncompativelError):
        raise
    except sqlite3.DatabaseError as erro:
        raise BackupInvalidoError(
            "O arquivo selecionado não é um backup SQLite válido."
        ) from erro
    except OSError as erro:
        raise AcessoBackupError(
            "O backup não pôde ser lido."
        ) from erro
    finally:
        if conexao is not None:
            conexao.close()


def _contar(conexao: sqlite3.Connection, tabela: str) -> int:
    return conexao.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]


def _copiar_backup(origem: Path, destino: Path) -> None:
    try:
        with origem.open("rb") as arquivo_origem, destino.open("wb") as arquivo_destino:
            shutil.copyfileobj(arquivo_origem, arquivo_destino, length=1024 * 1024)
            arquivo_destino.flush()
            os.fsync(arquivo_destino.fileno())
    except OSError as erro:
        raise AcessoBackupError(
            "A cópia de recuperação não pôde ser concluída."
        ) from erro


def _publicar_sem_sobrescrever(temporario: Path, definitivo: Path) -> None:
    try:
        os.link(temporario, definitivo)
    except FileExistsError as erro:
        raise BaseRestauradaJaExisteError(
            "Já existe uma base de teste com o nome escolhido."
        ) from erro
    except OSError as erro:
        raise PublicacaoRestauracaoError(
            "A base de teste não pôde ser publicada com segurança."
        ) from erro
