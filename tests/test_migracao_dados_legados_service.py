from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
import sqlite3
import subprocess
from types import SimpleNamespace

import pytest

from database.migracoes import MIGRACOES
from database.schema import VERSAO_ESQUEMA, criar_tabelas
from services.backup_local_service import BackupLocalError
from services.contexto_instalacao_service import (
    AMBIENTE_PRODUCAO_ID,
    PRODUTO_ID,
    AmbienteInstalacao,
    CaminhosInstalacao,
    ContextoInstalacao,
)
from services.instancia_unica_service import criar_nome_mutex_ambiente
import services.migracao_dados_legados_service as migracao_module
from services.migracao_dados_legados_service import (
    AutorizacaoMigracaoLegadaError,
    CopiaDadosLegadosError,
    DestinoComercialInvalidoError,
    FRASES_CONFIRMACAO,
    OrigemLegadaInvalidaError,
    STATUS_MIGRACAO_DADOS,
    VersaoLegadaIncompativelError,
    migrar_dados_legados,
)


class BackendMutexMemoria:
    def __init__(self) -> None:
        self.chamadas = []
        self.liberados = []

    def adquirir(
        self,
        nome,
        *,
        grupo_operadores,
        somente_administradores=False,
    ):
        self.chamadas.append(
            (nome, grupo_operadores, somente_administradores)
        )
        return object(), False

    def liberar(self, recurso):
        self.liberados.append(recurso)


def _criar_contexto_comercial(tmp_path: Path) -> ContextoInstalacao:
    raiz = tmp_path / "ProgramData" / "Sistema-PDV" / "Producao"
    dados = raiz / "data"
    logs = raiz / "logs"
    configuracao = raiz / "config"
    administrativo = raiz / "administrative"
    manifestos = administrativo / "manifests"
    manutencao = raiz / "maintenance"
    for diretorio in (
        dados,
        logs,
        configuracao,
        manifestos,
        manutencao,
    ):
        diretorio.mkdir(parents=True, exist_ok=True)
    raiz_instalacao = tmp_path / "ProgramFiles" / "Sistema-PDV" / "Producao"
    raiz_instalacao.mkdir(parents=True)
    executavel = raiz_instalacao / "Sistema-PDV.exe"
    executavel.write_bytes(b"teste")
    instalacao_id = "52df1475-60e8-4490-a16f-9d8ff82fcba6"
    descritor = administrativo / "installation.json"
    descritor.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "product_id": PRODUTO_ID,
                "environment": "PRODUCAO",
                "environment_id": AMBIENTE_PRODUCAO_ID,
                "installation_id": instalacao_id,
                "install_root": str(raiz_instalacao.resolve()),
                "executable_path": str(executavel.resolve()),
            }
        ),
        encoding="utf-8",
    )
    estado = manutencao / "state.json"
    estado.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "product_id": PRODUTO_ID,
                "environment_id": AMBIENTE_PRODUCAO_ID,
                "installation_id": instalacao_id,
                "status": "IDLE",
            }
        ),
        encoding="utf-8",
    )
    caminhos = CaminhosInstalacao(
        raiz,
        dados,
        dados / "sistema_acougue.db",
        logs,
        configuracao,
        administrativo,
        descritor,
        manifestos,
        manutencao,
        estado,
    )
    return ContextoInstalacao(
        PRODUTO_ID,
        AmbienteInstalacao.PRODUCAO,
        AMBIENTE_PRODUCAO_ID,
        instalacao_id,
        True,
        executavel,
        raiz_instalacao,
        caminhos,
    )


def _criar_origem_legada(tmp_path: Path) -> tuple[Path, Path]:
    local_app_data = tmp_path / "LocalAppData"
    origem = (
        local_app_data
        / "Sistema-PDV"
        / "data"
        / "sistema_acougue.db"
    )
    origem.parent.mkdir(parents=True)
    criar_tabelas(origem, validar_estrutura_estrita=True)
    conexao = sqlite3.connect(origem)
    try:
        conexao.execute("CREATE TABLE marcador_legado (valor TEXT NOT NULL)")
        conexao.execute(
            "INSERT INTO marcador_legado (valor) VALUES (?)",
            ("preservado",),
        )
        conexao.commit()
    finally:
        conexao.close()
    return local_app_data, origem


def _executar(
    origem: Path,
    local_app_data: Path,
    contexto: ContextoInstalacao,
    *,
    backend: BackendMutexMemoria | None = None,
):
    return migrar_dados_legados(
        origem,
        contexto,
        confirmacao=FRASES_CONFIRMACAO[contexto.ambiente],
        raiz_local_app_data=local_app_data,
        verificar_administrador=lambda: True,
        verificar_aplicativos_encerrados=lambda: True,
        backend_mutex=backend or BackendMutexMemoria(),
    )


def _hash(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _estado(contexto: ContextoInstalacao) -> dict:
    return json.loads(
        contexto.caminhos.estado_manutencao.read_text(encoding="utf-8")
    )


def _eventos(contexto: ContextoInstalacao) -> list[dict]:
    raiz = contexto.caminhos.manifestos / "data-migrations"
    return [
        json.loads(caminho.read_text(encoding="utf-8"))
        for caminho in sorted(raiz.glob("*/*.json"))
    ]


def test_migra_banco_legado_valido_sem_alterar_origem_ou_backups(
    tmp_path,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    backup_legado = origem.parent / "backups" / "local" / "preservar.bak"
    backup_legado.parent.mkdir(parents=True)
    backup_legado.write_bytes(b"backup legado")
    hash_origem = _hash(origem)
    backend = BackendMutexMemoria()

    resultado = _executar(
        origem,
        local_app_data,
        contexto,
        backend=backend,
    )

    assert resultado.caminho_destino == contexto.caminhos.banco
    assert resultado.versao_schema == VERSAO_ESQUEMA
    with sqlite3.connect(resultado.caminho_destino) as conexao:
        assert conexao.execute(
            "SELECT valor FROM marcador_legado"
        ).fetchone() == ("preservado",)
    assert _hash(origem) == hash_origem
    assert backup_legado.read_bytes() == b"backup legado"
    assert _estado(contexto)["status"] == "IDLE"
    assert backend.chamadas == [
        (criar_nome_mutex_ambiente(contexto), None, True)
    ]
    assert len(backend.liberados) == 1
    eventos = _eventos(contexto)
    assert [evento["event"] for evento in eventos] == [
        "STARTED",
        "SOURCE_VALIDATED",
        "COPY_VALIDATED",
        "SUCCESS_VALIDATED",
    ]
    assert all("LocalAppData" not in json.dumps(evento) for evento in eventos)
    assert all(
        evento["authorization"] == "ELEVATED_WINDOWS_ADMIN"
        for evento in eventos
    )


def test_origem_em_wal_e_copiada_com_snapshot_consistente(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    conexao = sqlite3.connect(origem)
    try:
        assert conexao.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
        conexao.execute("PRAGMA wal_autocheckpoint = 0")
        conexao.execute(
            "INSERT INTO marcador_legado (valor) VALUES (?)",
            ("somente-no-wal",),
        )
        conexao.commit()
        wal = Path(f"{origem}-wal")
        shm = Path(f"{origem}-shm")
        assert wal.is_file()
        assert shm.is_file()
        hash_origem = _hash(origem)
        conteudo_wal = wal.read_bytes()
        tamanho_shm = shm.stat().st_size

        resultado = _executar(origem, local_app_data, contexto)

        with sqlite3.connect(resultado.caminho_destino) as copia:
            valores = {
                linha[0]
                for linha in copia.execute("SELECT valor FROM marcador_legado")
            }
        assert valores == {"preservado", "somente-no-wal"}
        assert _hash(origem) == hash_origem
        assert wal.is_file() and wal.read_bytes() == conteudo_wal
        assert shm.is_file() and shm.stat().st_size == tamanho_shm
    finally:
        conexao.close()
    with sqlite3.connect(origem) as original:
        assert {
            linha[0]
            for linha in original.execute("SELECT valor FROM marcador_legado")
        } == {"preservado", "somente-no-wal"}


def test_versao_incompativel_e_recusada_sem_migrar_schema(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    with sqlite3.connect(origem) as conexao:
        conexao.execute(f"PRAGMA user_version = {VERSAO_ESQUEMA + 1}")

    with pytest.raises(VersaoLegadaIncompativelError):
        _executar(origem, local_app_data, contexto)

    with sqlite3.connect(origem) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == (
            VERSAO_ESQUEMA + 1
        )
    assert not contexto.caminhos.banco.exists()
    assert _estado(contexto)["status"] == "IDLE"
    assert _eventos(contexto)[-1]["event"] == "REJECTED"


def test_versao_legada_anterior_e_preservada_sem_executar_rota_t58(
    tmp_path,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data = tmp_path / "LocalAppData"
    origem = (
        local_app_data
        / "Sistema-PDV"
        / "data"
        / "sistema_acougue.db"
    )
    origem.parent.mkdir(parents=True)
    versao_legada = VERSAO_ESQUEMA - 1
    with sqlite3.connect(origem) as conexao:
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("BEGIN IMMEDIATE")
        for migracao in MIGRACOES:
            if migracao.destino > versao_legada:
                break
            migracao.aplicar(conexao)
            conexao.execute(f"PRAGMA user_version = {migracao.destino}")
        conexao.commit()
    hash_origem = _hash(origem)

    with pytest.raises(VersaoLegadaIncompativelError):
        _executar(origem, local_app_data, contexto)

    with sqlite3.connect(origem) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == (
            versao_legada
        )
    assert _hash(origem) == hash_origem
    assert not contexto.caminhos.banco.exists()
    assert _estado(contexto)["status"] == "IDLE"


def test_destino_ocupado_e_preservado(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    contexto.caminhos.banco.write_bytes(b"destino existente")

    with pytest.raises(DestinoComercialInvalidoError):
        _executar(origem, local_app_data, contexto)

    assert contexto.caminhos.banco.read_bytes() == b"destino existente"
    assert _estado(contexto)["status"] == "IDLE"
    assert _eventos(contexto)[-1]["event"] == "REJECTED"


@pytest.mark.parametrize("tipo", ["arquivo", "diretorio"])
def test_destino_recusa_qualquer_conteudo_desconhecido(
    tmp_path,
    tipo,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    desconhecido = contexto.caminhos.dados / ".conteudo-oculto"
    if tipo == "arquivo":
        desconhecido.write_bytes(b"preservar")
    else:
        desconhecido.mkdir()

    with pytest.raises(DestinoComercialInvalidoError, match="integralmente vazio"):
        _executar(origem, local_app_data, contexto)

    assert desconhecido.exists()
    if tipo == "arquivo":
        assert desconhecido.read_bytes() == b"preservar"
    assert _estado(contexto)["status"] == "IDLE"


def test_identidade_divergente_bloqueia_antes_de_tocar_destino(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    documento = json.loads(
        contexto.caminhos.descritor_identidade.read_text(encoding="utf-8")
    )
    documento["environment"] = "HOMOLOGACAO"
    contexto.caminhos.descritor_identidade.write_text(
        json.dumps(documento),
        encoding="utf-8",
    )

    with pytest.raises(DestinoComercialInvalidoError):
        _executar(origem, local_app_data, contexto)

    assert not contexto.caminhos.banco.exists()
    assert not (contexto.caminhos.manifestos / "data-migrations").exists()


def test_falha_de_copia_mantem_manutencao_restrita(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)

    def falhar_copia(*args, **kwargs):
        raise BackupLocalError("falha simulada")

    monkeypatch.setattr(
        migracao_module,
        "criar_copia_sqlite_consistente",
        falhar_copia,
    )

    with pytest.raises(CopiaDadosLegadosError):
        _executar(origem, local_app_data, contexto)

    estado = _estado(contexto)
    assert estado["status"] == STATUS_MIGRACAO_DADOS
    assert "operation_id" in estado
    assert not contexto.caminhos.banco.exists()
    assert _eventos(contexto)[-1]["event"] == "FAILED_AFTER_START"


def test_interrupcao_apos_publicacao_impede_repeticao_e_sobrescrita(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)

    def interromper(contexto_recebido):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        migracao_module,
        "_publicar_estado_livre",
        interromper,
    )

    with pytest.raises(KeyboardInterrupt):
        _executar(origem, local_app_data, contexto)

    hash_destino = _hash(contexto.caminhos.banco)
    assert _estado(contexto)["status"] == STATUS_MIGRACAO_DADOS
    with pytest.raises(DestinoComercialInvalidoError):
        _executar(origem, local_app_data, contexto)
    assert _hash(contexto.caminhos.banco) == hash_destino


def test_tentativa_repetida_apos_sucesso_nao_sobrescreve_destino(
    tmp_path,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    _executar(origem, local_app_data, contexto)
    hash_destino = _hash(contexto.caminhos.banco)

    with pytest.raises(DestinoComercialInvalidoError):
        _executar(origem, local_app_data, contexto)

    assert _hash(contexto.caminhos.banco) == hash_destino
    assert _estado(contexto)["status"] == "IDLE"


@pytest.mark.parametrize(
    ("confirmacao", "administrador"),
    [
        ("confirmacao incorreta", True),
        ("MIGRAR DADOS LEGADOS PARA PRODUCAO", False),
    ],
)
def test_exige_confirmacao_e_administrador_explicitos(
    tmp_path,
    confirmacao,
    administrador,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)

    with pytest.raises(AutorizacaoMigracaoLegadaError):
        migrar_dados_legados(
            origem,
            contexto,
            confirmacao=confirmacao,
            raiz_local_app_data=local_app_data,
            verificar_administrador=lambda: administrador,
            verificar_aplicativos_encerrados=lambda: True,
            backend_mutex=BackendMutexMemoria(),
        )

    assert not contexto.caminhos.banco.exists()


def test_recusa_origem_fora_do_local_app_data_legado(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, _ = _criar_origem_legada(tmp_path)
    outra = tmp_path / "escolha-arbitraria.db"
    criar_tabelas(outra, validar_estrutura_estrita=True)

    with pytest.raises(OrigemLegadaInvalidaError):
        _executar(outra, local_app_data, contexto)

    assert not contexto.caminhos.banco.exists()


def test_recusa_redirecionamento_em_componente_intermediario(
    tmp_path,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data = tmp_path / "LocalAppData"
    local_app_data.mkdir()
    externa = tmp_path / "externa" / "Sistema-PDV"
    (externa / "data").mkdir(parents=True)
    origem_externa = externa / "data" / "sistema_acougue.db"
    criar_tabelas(origem_externa, validar_estrutura_estrita=True)
    try:
        (local_app_data / "Sistema-PDV").symlink_to(
            externa,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("criação de symlink não autorizada neste Windows")
    origem_indireta = (
        local_app_data / "Sistema-PDV" / "data" / "sistema_acougue.db"
    )

    with pytest.raises(OrigemLegadaInvalidaError):
        _executar(origem_indireta, local_app_data, contexto)

    assert not contexto.caminhos.banco.exists()


def test_recusa_componente_com_atributo_windows_de_reparse_point(
    tmp_path,
    monkeypatch,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    data = origem.parent
    lstat_original = os.lstat

    def lstat_com_reparse(caminho):
        estado = lstat_original(caminho)
        if Path(caminho) != data:
            return estado
        return SimpleNamespace(
            st_mode=estado.st_mode,
            st_nlink=estado.st_nlink,
            st_dev=estado.st_dev,
            st_ino=estado.st_ino,
            st_size=estado.st_size,
            st_mtime_ns=estado.st_mtime_ns,
            st_ctime_ns=estado.st_ctime_ns,
            st_file_attributes=0x400,
        )

    monkeypatch.setattr(migracao_module.os, "lstat", lstat_com_reparse)

    with pytest.raises(OrigemLegadaInvalidaError):
        _executar(origem, local_app_data, contexto)


def test_substituicao_da_origem_apos_selecao_e_recusada(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    original_preservada = origem.with_name("origem-selecionada-anterior.db")

    class BackendQueSubstituiOrigem(BackendMutexMemoria):
        def adquirir(self, nome, **kwargs):
            recurso = super().adquirir(nome, **kwargs)
            origem.replace(original_preservada)
            criar_tabelas(origem, validar_estrutura_estrita=True)
            return recurso

    with pytest.raises(OrigemLegadaInvalidaError, match="substituída"):
        _executar(
            origem,
            local_app_data,
            contexto,
            backend=BackendQueSubstituiOrigem(),
        )

    assert original_preservada.is_file()
    assert not contexto.caminhos.banco.exists()
    assert _estado(contexto)["status"] == "IDLE"


def test_aplicativo_aberto_bloqueia_antes_do_estado_de_migracao(
    tmp_path,
) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)

    with pytest.raises(
        migracao_module.EstadoMigracaoDadosError,
        match="Feche todas",
    ):
        migrar_dados_legados(
            origem,
            contexto,
            confirmacao=FRASES_CONFIRMACAO[contexto.ambiente],
            raiz_local_app_data=local_app_data,
            verificar_administrador=lambda: True,
            verificar_aplicativos_encerrados=lambda: False,
            backend_mutex=BackendMutexMemoria(),
        )

    assert _estado(contexto)["status"] == "IDLE"
    assert not contexto.caminhos.banco.exists()
    assert _eventos(contexto)[-1]["event"] == "REJECTED"


def test_contexto_com_caminho_de_banco_divergente_e_recusado(tmp_path) -> None:
    contexto = _criar_contexto_comercial(tmp_path)
    local_app_data, origem = _criar_origem_legada(tmp_path)
    contexto = replace(
        contexto,
        caminhos=replace(
            contexto.caminhos,
            banco=tmp_path / "fora" / "sistema_acougue.db",
        ),
    )

    with pytest.raises(DestinoComercialInvalidoError):
        _executar(origem, local_app_data, contexto)


@pytest.mark.parametrize(
    ("saida", "esperado"),
    [
        ('"Sistema-PDV.exe","100","Console","1","10 K"', True),
        (
            '"Sistema-PDV.exe","100","Console","1","10 K"\n'
            '"Sistema-PDV.exe","200","Services","0","10 K"',
            False,
        ),
    ],
)
def test_enumeracao_de_processos_ignora_somente_o_proprio_processo(
    monkeypatch,
    saida,
    esperado,
) -> None:
    monkeypatch.setattr(migracao_module.sys, "platform", "win32")
    monkeypatch.setattr(migracao_module.os, "getpid", lambda: 100)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout=saida,
            stderr="",
        ),
    )

    assert migracao_module._nenhum_sistema_pdv_em_execucao() is esperado
