from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from threading import Event, Lock
import time

import pytest

from database.schema import criar_tabelas
from models.produto import Produto
from repositories.produto_repository import salvar_produto
from services.produto_service import cadastrar_produto
import services.backup_externo_service as externo_module
from services.backup_externo_service import (
    AgendadorBackupExterno,
    DestinoDiretorio,
    DIAS_RETENCAO_EXTERNA,
    EstadoBackupExterno,
    INTERVALO_BACKUP_EXTERNO_SEGUNDOS,
    ServicoBackupExterno,
)
from services.logging_service import configurar_logging, encerrar_logging
from tests.helpers_identidade import criar_sessao_admin_teste


def _criar_banco(caminho: Path, *, codigo="101", preco=1200) -> None:
    criar_tabelas(caminho)
    salvar_produto(
        Produto(
            codigo=codigo,
            nome=f"Produto {codigo}",
            categoria="GERAL",
            forma_venda="UNIDADE",
            preco_venda_centavos=preco,
            origem="COMPRADO",
        ),
        caminho,
    )


def _criar_servico(tmp_path, *, banco=None, destino=None):
    banco = banco or tmp_path / "origem.db"
    if not banco.exists():
        _criar_banco(banco)
    destino = destino or DestinoDiretorio(tmp_path / "externo")
    return ServicoBackupExterno(
        banco,
        destino=destino,
        diretorio_backup_local=tmp_path / "local",
    )


def _arquivos_externos(raiz: Path):
    return tuple(raiz.rglob("*.sqlite3")) if raiz.exists() else ()


def test_destino_nao_configurado_nao_executa_backup(tmp_path) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)
    servico = ServicoBackupExterno(
        banco,
        diretorio_backup_local=tmp_path / "local",
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.NAO_CONFIGURADO
    assert estado.ultima_tentativa is None
    assert not (tmp_path / "local").exists()


def test_copia_externa_e_integra_e_confere_sha256(tmp_path) -> None:
    servico = _criar_servico(tmp_path)

    estado = servico.executar()
    resultado = servico.obter_ultimo_resultado()

    assert estado.status is EstadoBackupExterno.SUCESSO
    assert resultado is not None
    assert resultado.caminho_backup.exists()
    assert hashlib.sha256(resultado.caminho_backup.read_bytes()).hexdigest() == (
        resultado.sha256
    )
    conexao = sqlite3.connect(resultado.caminho_backup)
    try:
        assert conexao.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conexao.execute(
            "SELECT preco_venda_centavos FROM produtos WHERE codigo = '101'"
        ).fetchone()[0] == 1200
    finally:
        conexao.close()


def test_corrupcao_durante_transporte_falha_sem_publicar(
    tmp_path,
    monkeypatch,
) -> None:
    servico = _criar_servico(tmp_path)
    original = externo_module._copiar_stream

    def copiar_corrompendo(fonte, destino):
        original(fonte, destino)
        with destino.open("ab") as arquivo:
            arquivo.write(b"corrupcao")

    monkeypatch.setattr(externo_module, "_copiar_stream", copiar_corrompendo)

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "IntegridadeTransporteError"
    assert not _arquivos_externos(tmp_path / "externo")
    assert not tuple((tmp_path / "externo").rglob("*.tmp"))


def test_destino_inexistente_pode_ser_criado_e_arquivo_invalido_falha(
    tmp_path,
) -> None:
    destino = tmp_path / "destino"
    servico = _criar_servico(tmp_path, destino=DestinoDiretorio(destino))
    assert servico.executar().status is EstadoBackupExterno.SUCESSO

    destino_invalido = tmp_path / "arquivo-destino"
    destino_invalido.write_text("não é diretório", encoding="utf-8")
    servico.configurar_destino(DestinoDiretorio(destino_invalido))

    estado = servico.executar()
    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "DestinoExternoInvalidoError"


def test_falta_de_permissao_e_controlada_sem_afetar_banco(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "origem.db"
    servico = _criar_servico(tmp_path, banco=banco)
    monkeypatch.setattr(
        externo_module,
        "_copiar_stream",
        lambda *args: (_ for _ in ()).throw(PermissionError("negado")),
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "PermissionError"
    conexao = sqlite3.connect(banco)
    try:
        assert conexao.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 1
    finally:
        conexao.close()


def test_interrupcao_antes_da_publicacao_preserva_backup_anterior(
    tmp_path,
    monkeypatch,
) -> None:
    servico = _criar_servico(tmp_path)
    assert servico.executar().status is EstadoBackupExterno.SUCESSO
    anterior = servico.obter_ultimo_resultado().caminho_backup
    original = anterior.read_bytes()
    monkeypatch.setattr(
        externo_module,
        "_publicar_externo_sem_sobrescrever",
        lambda *args: (_ for _ in ()).throw(
            externo_module.PublicacaoExternaError("interrompido")
        ),
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert anterior.read_bytes() == original
    assert not tuple(anterior.parent.glob("*.tmp"))


def test_colisao_de_nome_nao_sobrescreve_copia_externa(
    tmp_path,
    monkeypatch,
) -> None:
    servico = _criar_servico(tmp_path)
    assert servico.executar().status is EstadoBackupExterno.SUCESSO
    anterior = servico.obter_ultimo_resultado().caminho_backup
    conteudo = anterior.read_bytes()
    monkeypatch.setattr(
        externo_module,
        "_criar_nome_externo",
        lambda *args: anterior.name,
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "PublicacaoExternaError"
    assert anterior.read_bytes() == conteudo


def test_backup_local_removido_antes_do_transporte_falha_com_seguranca(
    tmp_path,
    monkeypatch,
) -> None:
    servico = _criar_servico(tmp_path)
    original = externo_module.abrir_backup_local_para_transporte

    @contextmanager
    def remover_antes(resultado):
        resultado.caminho_backup.unlink()
        with original(resultado) as arquivo:
            yield arquivo

    monkeypatch.setattr(
        externo_module,
        "abrir_backup_local_para_transporte",
        remover_antes,
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "BackupLocalError"
    assert not _arquivos_externos(tmp_path / "externo")


def test_backup_local_alterado_entre_hash_e_copia_e_rejeitado(
    tmp_path,
    monkeypatch,
) -> None:
    servico = _criar_servico(tmp_path)

    class StreamMutavel(io.BytesIO):
        def __init__(self, dados):
            super().__init__(dados)
            self._retornos_ao_inicio = 0

        def seek(self, deslocamento, origem=0):
            resultado = super().seek(deslocamento, origem)
            if deslocamento == 0 and origem == 0:
                self._retornos_ao_inicio += 1
                if self._retornos_ao_inicio == 3:
                    dados = self.getvalue() + b"alterado"
                    super().seek(0)
                    self.truncate(0)
                    self.write(dados)
                    super().seek(0)
            return resultado

    @contextmanager
    def fonte_mutavel(resultado):
        dados = resultado.caminho_backup.read_bytes()
        with StreamMutavel(dados) as arquivo:
            yield arquivo

    monkeypatch.setattr(
        externo_module,
        "abrir_backup_local_para_transporte",
        fonte_mutavel,
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "IntegridadeTransporteError"


def test_isolamento_entre_bancos_no_mesmo_destino(tmp_path) -> None:
    banco_a = tmp_path / "a" / "pdv.db"
    banco_b = tmp_path / "b" / "pdv.db"
    _criar_banco(banco_a, codigo="10", preco=1000)
    _criar_banco(banco_b, codigo="10", preco=9000)
    destino = DestinoDiretorio(tmp_path / "externo")
    servico_a = _criar_servico(tmp_path / "a-servico", banco=banco_a, destino=destino)
    servico_b = _criar_servico(tmp_path / "b-servico", banco=banco_b, destino=destino)

    assert servico_a.executar().status is EstadoBackupExterno.SUCESSO
    assert servico_b.executar().status is EstadoBackupExterno.SUCESSO
    resultado_a = servico_a.obter_ultimo_resultado()
    resultado_b = servico_b.obter_ultimo_resultado()

    assert resultado_a.caminho_backup.parent != resultado_b.caminho_backup.parent
    assert resultado_a.caminho_backup.exists()
    assert resultado_b.caminho_backup.exists()


def test_retencao_externa_mantem_trinta_diarios_e_arquivos_desconhecidos(
    tmp_path,
) -> None:
    diretorio = tmp_path / "retencao"
    diretorio.mkdir()
    origem = "a" * 16
    base = datetime(2026, 11, 16, 15, tzinfo=UTC)
    caminhos = []
    for dias in range(45):
        caminho = diretorio / externo_module._criar_nome_externo(
            origem,
            base - timedelta(days=dias),
            f"{dias:032x}",
        )
        caminho.write_bytes(b"externo")
        caminhos.append(caminho)
    desconhecido = diretorio / "preservar.txt"
    desconhecido.write_text("usuario", encoding="utf-8")

    removidos, falhas = externo_module._aplicar_retencao_externa(
        diretorio,
        origem,
        preservar=caminhos[0],
    )

    assert removidos == 15
    assert falhas == 0
    assert len(externo_module._listar_copias_externas(diretorio, origem)) == (
        DIAS_RETENCAO_EXTERNA
    )
    assert desconhecido.exists()


def test_duas_execucoes_concorrentes_nao_duplicam_mesmo_trabalho(
    tmp_path,
    monkeypatch,
) -> None:
    servico = _criar_servico(tmp_path)
    entrou = Event()
    liberar = Event()
    original = externo_module.DestinoDiretorio.enviar

    def enviar_bloqueado(self, *args):
        entrou.set()
        assert liberar.wait(10)
        return original(self, *args)

    monkeypatch.setattr(
        externo_module.DestinoDiretorio,
        "enviar",
        enviar_bloqueado,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        primeira = executor.submit(servico.executar)
        assert entrou.wait(10)
        segunda = executor.submit(servico.executar)
        assert segunda.result(5).status is EstadoBackupExterno.EM_EXECUCAO
        liberar.set()
        assert primeira.result(20).status is EstadoBackupExterno.SUCESSO

    assert len(_arquivos_externos(tmp_path / "externo")) == 1


def test_servicos_concorrentes_compartilham_destino_sem_publicacao_parcial(
    tmp_path,
) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)
    destino = DestinoDiretorio(tmp_path / "externo")
    servico_a = _criar_servico(tmp_path / "sa", banco=banco, destino=destino)
    servico_b = _criar_servico(tmp_path / "sb", banco=banco, destino=destino)

    def executar(servico):
        estado = servico.executar()
        resultado = servico.obter_ultimo_resultado()
        return estado, resultado.caminho_backup.is_file()

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = tuple(
            executor.map(executar, (servico_a, servico_b))
        )

    assert all(estado.status is EstadoBackupExterno.SUCESSO for estado, _ in resultados)
    assert all(existia_ao_retornar for _, existia_ao_retornar in resultados)


def test_falha_pode_ser_recuperada_em_execucao_posterior(tmp_path) -> None:
    destino_invalido = tmp_path / "destino-invalido"
    destino_invalido.write_text("arquivo", encoding="utf-8")
    servico = _criar_servico(
        tmp_path,
        destino=DestinoDiretorio(destino_invalido),
    )
    assert servico.executar().status is EstadoBackupExterno.FALHA

    servico.configurar_destino(DestinoDiretorio(tmp_path / "externo-ok"))
    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.SUCESSO
    assert estado.ultimo_sucesso is not None
    assert estado.erro_tipo is None


def test_agendador_usa_duas_horas_nao_inicia_sem_destino_e_nao_bloqueia(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)
    sem_destino = ServicoBackupExterno(banco)
    assert not AgendadorBackupExterno(sem_destino).iniciar()
    assert INTERVALO_BACKUP_EXTERNO_SEGUNDOS == 7200

    servico = _criar_servico(tmp_path / "agendado")
    chamadas = []
    executou = Event()
    original = servico.executar

    def executar_contado():
        chamadas.append(time.monotonic())
        resultado = original()
        executou.set()
        return resultado

    monkeypatch.setattr(servico, "executar", executar_contado)
    agendador = AgendadorBackupExterno(servico, intervalo_segundos=0.05)

    inicio = time.monotonic()
    assert agendador.iniciar()
    assert time.monotonic() - inicio < 0.5
    assert executou.wait(10)
    limite = time.monotonic() + 10
    while len(chamadas) < 2 and time.monotonic() < limite:
        time.sleep(0.01)
    agendador.parar()

    assert len(chamadas) >= 2
    assert chamadas[1] - chamadas[0] >= 0.05


def test_agendador_recupera_falha_na_execucao_posterior(tmp_path) -> None:
    destino_invalido = tmp_path / "destino-invalido"
    destino_invalido.write_text("arquivo", encoding="utf-8")
    servico = _criar_servico(
        tmp_path,
        destino=DestinoDiretorio(destino_invalido),
    )
    agendador = AgendadorBackupExterno(servico, intervalo_segundos=0.2)
    assert agendador.iniciar()
    limite = time.monotonic() + 10
    while (
        servico.obter_estado().status is not EstadoBackupExterno.FALHA
        and time.monotonic() < limite
    ):
        time.sleep(0.01)

    servico.configurar_destino(DestinoDiretorio(tmp_path / "recuperado"))
    limite = time.monotonic() + 10
    while (
        servico.obter_estado().status is not EstadoBackupExterno.SUCESSO
        and time.monotonic() < limite
    ):
        time.sleep(0.01)
    agendador.parar()

    assert servico.obter_estado().status is EstadoBackupExterno.SUCESSO


def test_transporte_em_thread_nao_bloqueia_mutacao_comercial(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "comercial.db"
    _criar_banco(banco)
    sessao = criar_sessao_admin_teste(banco)
    destino = DestinoDiretorio(tmp_path / "externo")
    servico = _criar_servico(tmp_path, banco=banco, destino=destino)
    entrou = Event()
    liberar = Event()
    original = externo_module.DestinoDiretorio.enviar

    def enviar_bloqueado(self, *args):
        entrou.set()
        assert liberar.wait(10)
        return original(self, *args)

    monkeypatch.setattr(
        externo_module.DestinoDiretorio,
        "enviar",
        enviar_bloqueado,
    )
    agendador = AgendadorBackupExterno(servico, intervalo_segundos=7200)
    assert agendador.iniciar()
    assert entrou.wait(10)

    produto, erros = cadastrar_produto(
        "303",
        "Produto durante transporte",
        "GERAL",
        "UNIDADE",
        3300,
        "COMPRADO",
        banco,
        sessao_solicitante=sessao,
    )
    liberar.set()
    agendador.parar(20)

    assert produto is not None
    assert erros == []
    assert servico.obter_estado().status is EstadoBackupExterno.SUCESSO


def test_eventos_de_resultado_nao_expoem_caminhos_nem_dados(
    tmp_path,
) -> None:
    caminho_log = configurar_logging(tmp_path / "logs")
    try:
        servico = _criar_servico(tmp_path / "seguro")
        assert servico.executar().status is EstadoBackupExterno.SUCESSO
    finally:
        encerrar_logging()

    documento = json.loads(caminho_log.read_text(encoding="utf-8"))
    assert documento["event"] == "backup_externo_concluido"
    assert documento["component"] == "backup_externo"
    assert documento["resultado"] == "sucesso"
    assert "path" not in documento
    assert "sha256" not in documento
    assert "Produto" not in caminho_log.read_text(encoding="utf-8")


def test_destino_na_area_local_e_rejeitado_como_falsa_redundancia(
    tmp_path,
) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)
    raiz_local = tmp_path / "backups-local"
    servico = ServicoBackupExterno(
        banco,
        destino=DestinoDiretorio(raiz_local),
        diretorio_backup_local=raiz_local,
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "DestinoExternoInvalidoError"


def test_destino_irmao_do_local_na_area_padrao_e_rejeitado(tmp_path) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)
    servico = ServicoBackupExterno(
        banco,
        destino=DestinoDiretorio(tmp_path / "backups" / "externo"),
        diretorio_backup_local=tmp_path / "backups" / "local",
    )

    estado = servico.executar()

    assert estado.status is EstadoBackupExterno.FALHA
    assert estado.erro_tipo == "DestinoExternoInvalidoError"
    assert not _arquivos_externos(tmp_path / "backups" / "externo")


def test_destino_pode_ser_configurado_explicitamente_por_ambiente(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        externo_module.VARIAVEL_DESTINO_BACKUP_EXTERNO,
        raising=False,
    )
    assert externo_module.destino_externo_configurado_no_ambiente() is None

    monkeypatch.setenv(
        externo_module.VARIAVEL_DESTINO_BACKUP_EXTERNO,
        str(tmp_path / "externo-configurado"),
    )
    assert isinstance(
        externo_module.destino_externo_configurado_no_ambiente(),
        DestinoDiretorio,
    )
