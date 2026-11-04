from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from database.conexao import CAMINHO_BANCO, conectar
from database.schema import VERSAO_ESQUEMA, criar_tabelas


class InicializacaoBancoError(RuntimeError):
    pass


class VersaoBancoFuturaError(InicializacaoBancoError):
    pass


class BackupPreMigracaoError(InicializacaoBancoError):
    pass


class MigracaoBancoError(InicializacaoBancoError):
    pass


@dataclass(frozen=True)
class ResultadoInicializacaoBanco:
    caminho_banco: Path
    banco_novo: bool
    versao_inicial: int
    versao_final: int
    caminho_backup: Path | None = None


def preparar_banco_para_operacao(
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> ResultadoInicializacaoBanco:
    """Prepara o esquema e protege bancos legados com backup verificado."""
    caminho = Path(caminho_banco)
    banco_novo = not caminho.exists()

    if banco_novo:
        try:
            criar_tabelas(caminho)
        except Exception as erro:
            raise MigracaoBancoError(
                "Não foi possível criar o banco de dados da aplicação."
            ) from erro
        return ResultadoInicializacaoBanco(
            caminho_banco=caminho,
            banco_novo=True,
            versao_inicial=0,
            versao_final=VERSAO_ESQUEMA,
        )

    versao_inicial = _consultar_versao(caminho)
    if versao_inicial > VERSAO_ESQUEMA:
        raise VersaoBancoFuturaError(
            "O banco usa uma versão de esquema mais nova que a aplicação. "
            "Atualize o Sistema-PDV antes de continuar."
        )

    if versao_inicial == VERSAO_ESQUEMA:
        return ResultadoInicializacaoBanco(
            caminho_banco=caminho,
            banco_novo=False,
            versao_inicial=versao_inicial,
            versao_final=versao_inicial,
        )

    caminho_backup = _criar_backup_pre_migracao(caminho, versao_inicial)
    try:
        criar_tabelas(caminho)
    except Exception as erro:
        raise MigracaoBancoError(
            "A migração do banco falhou e foi interrompida. O backup "
            f"pré-migração foi preservado em: {caminho_backup}"
        ) from erro

    return ResultadoInicializacaoBanco(
        caminho_banco=caminho,
        banco_novo=False,
        versao_inicial=versao_inicial,
        versao_final=VERSAO_ESQUEMA,
        caminho_backup=caminho_backup,
    )


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
        _executar_backup_sqlite(caminho_banco, caminho_backup)
        _verificar_integridade_backup(caminho_backup)
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
) -> None:
    origem = conectar(caminho_origem)
    destino = sqlite3.connect(caminho_destino)
    try:
        origem.backup(destino)
        destino.commit()
    finally:
        destino.close()
        origem.close()


def _verificar_integridade_backup(caminho_backup: Path) -> None:
    uri = f"file:{caminho_backup.as_posix()}?mode=ro"
    conexao = sqlite3.connect(uri, uri=True)
    try:
        resultados = [
            linha[0]
            for linha in conexao.execute("PRAGMA integrity_check").fetchall()
        ]
    finally:
        conexao.close()

    if resultados != ["ok"]:
        raise sqlite3.DatabaseError(
            "A verificação de integridade do backup não retornou 'ok'."
        )
