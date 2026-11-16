from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import multiprocessing
from pathlib import Path
import queue
import sqlite3
from threading import Barrier, Event, Lock
import time

import pytest

from database.conexao import conectar
from database.schema import VERSAO_ESQUEMA, criar_tabelas
from models.produto import Produto
from repositories.produto_repository import salvar_produto
import services.backup_local_service as backup_module
from services.backup_local_service import (
    BackupLocalError,
    DestinoBackupInvalidoError,
    OrigemBackupInvalidaError,
    PublicacaoBackupError,
    ValidacaoBackupError,
    criar_backup_local,
)
from services.catalogo_memoria_service import CatalogoProdutosMemoria
from services.estado_operacional_service import (
    ControladorEstadoOperacional,
    ModoOperacional,
    OperacaoProibidaNoModoAtualError,
    vincular_controlador_ao_banco,
)


def _processo_adquirir_lock(diretorio, identificador, inicio, liberar, fila):
    inicio.wait(20)
    try:
        with backup_module._backup_local_coordenado(
            Path(diretorio),
            identificador,
        ):
            fila.put(("entrou", True))
            liberar.wait(20)
    except Exception as erro:
        fila.put(("erro", type(erro).__name__))


def _criar_banco(caminho: Path, *, codigo="101", preco=1250) -> None:
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


def _consultar_produto(caminho: Path, codigo="101") -> tuple:
    conexao = sqlite3.connect(caminho)
    try:
        return conexao.execute(
            "SELECT codigo, nome, preco_venda_centavos FROM produtos "
            "WHERE codigo = ?",
            (codigo,),
        ).fetchone()
    finally:
        conexao.close()


def test_backup_consistente_preserva_dados_schema_e_relacionamentos(
    tmp_path,
) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)

    resultado = criar_backup_local(banco, tmp_path / "backups")

    assert resultado.caminho_backup.exists()
    assert _consultar_produto(resultado.caminho_backup) == (
        "101",
        "Produto 101",
        1250,
    )
    copia = sqlite3.connect(resultado.caminho_backup)
    try:
        assert copia.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copia.execute("PRAGMA foreign_key_check").fetchone() is None
        assert copia.execute("PRAGMA user_version").fetchone()[0] == (
            VERSAO_ESQUEMA
        )
    finally:
        copia.close()


def test_backup_inclui_commit_presente_no_wal(tmp_path) -> None:
    banco = tmp_path / "wal.db"
    _criar_banco(banco, codigo="201")
    conexao = conectar(banco)
    try:
        assert conexao.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
        categoria_id = conexao.execute(
            "SELECT id FROM categorias WHERE nome_chave = 'geral'"
        ).fetchone()[0]
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria_id, forma_venda,
                preco_venda_centavos, origem
            ) VALUES ('202', 'Produto WAL', ?, 'UNIDADE', 2200, 'COMPRADO')
            """,
            (categoria_id,),
        )
        conexao.commit()

        resultado = criar_backup_local(banco, tmp_path / "backups")
    finally:
        conexao.close()

    assert _consultar_produto(resultado.caminho_backup, "202") == (
        "202",
        "Produto WAL",
        2200,
    )


def test_backup_nao_altera_registros_comerciais_da_origem(tmp_path) -> None:
    banco = tmp_path / "imutavel.db"
    _criar_banco(banco)
    conexao = conectar(banco)
    try:
        antes = tuple(
            conexao.execute(
                "SELECT codigo, nome, preco_venda_centavos FROM produtos"
            ).fetchall()
        )
        versao_antes = conexao.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conexao.close()

    criar_backup_local(banco, tmp_path / "backups")

    conexao = conectar(banco)
    try:
        depois = tuple(
            conexao.execute(
                "SELECT codigo, nome, preco_venda_centavos FROM produtos"
            ).fetchall()
        )
        versao_depois = conexao.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conexao.close()
    assert depois == antes
    assert versao_depois == versao_antes


def test_origem_inexistente_e_recusada_sem_criar_banco(tmp_path) -> None:
    banco = tmp_path / "ausente.db"

    with pytest.raises(OrigemBackupInvalidaError):
        criar_backup_local(banco, tmp_path / "backups")

    assert not banco.exists()


def test_destino_invalido_ou_igual_ao_arquivo_de_origem_e_recusado(
    tmp_path,
) -> None:
    banco = tmp_path / "origem.db"
    _criar_banco(banco)

    with pytest.raises(DestinoBackupInvalidoError):
        criar_backup_local(banco, banco)

    assert _consultar_produto(banco) is not None


@pytest.mark.parametrize(
    "erro",
    [
        sqlite3.OperationalError("falha de leitura"),
        OSError("falha de gravação"),
    ],
    ids=("leitura", "gravacao"),
)
def test_falha_de_leitura_ou_gravacao_limpa_temporario(
    tmp_path,
    monkeypatch,
    erro,
) -> None:
    banco = tmp_path / "falha.db"
    destino = tmp_path / "backups"
    _criar_banco(banco)
    monkeypatch.setattr(
        backup_module,
        "_executar_backup_sqlite",
        lambda origem, temporario: (_ for _ in ()).throw(erro),
    )

    with pytest.raises(BackupLocalError):
        criar_backup_local(banco, destino)

    assert not tuple(destino.rglob("*.tmp"))
    assert not tuple(destino.rglob("*.sqlite3"))


def test_falha_de_integridade_nao_publica_copia(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "integridade.db"
    destino = tmp_path / "backups"
    _criar_banco(banco)
    monkeypatch.setattr(
        backup_module,
        "_validar_backup",
        lambda caminho: (_ for _ in ()).throw(
            ValidacaoBackupError("falha controlada")
        ),
    )

    with pytest.raises(ValidacaoBackupError):
        criar_backup_local(banco, destino)

    assert not tuple(destino.rglob("*.tmp"))
    assert not tuple(destino.rglob("*.sqlite3"))


@pytest.mark.parametrize("cenario", ["corrompido", "schema", "estrutura"])
def test_validacao_rejeita_copia_incompativel(tmp_path, cenario) -> None:
    copia = tmp_path / f"{cenario}.sqlite3"
    if cenario == "corrompido":
        copia.write_bytes(b"nao-e-sqlite")
    else:
        conexao = sqlite3.connect(copia)
        try:
            versao = VERSAO_ESQUEMA - 1 if cenario == "schema" else VERSAO_ESQUEMA
            conexao.execute(f"PRAGMA user_version = {versao}")
            conexao.execute("CREATE TABLE parcial (id INTEGER PRIMARY KEY)")
            conexao.commit()
        finally:
            conexao.close()

    with pytest.raises(ValidacaoBackupError):
        backup_module._validar_backup(copia)


def test_colisao_de_nome_preserva_backup_anterior(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "colisao.db"
    raiz = tmp_path / "backups"
    _criar_banco(banco)
    origem, identificador = backup_module._identificar_origem(banco)
    diretorio = backup_module._preparar_diretorio_destino(
        origem,
        raiz,
        identificador,
    )
    nome = backup_module._criar_nome_backup(
        identificador,
        datetime(2026, 11, 16, 12, tzinfo=UTC),
        "a" * 32,
    )
    anterior = diretorio / nome
    anterior.write_bytes(b"backup-anterior")
    monkeypatch.setattr(
        backup_module,
        "_criar_nome_backup",
        lambda *args: nome,
    )

    with pytest.raises(PublicacaoBackupError):
        criar_backup_local(banco, raiz)

    assert anterior.read_bytes() == b"backup-anterior"
    assert not tuple(diretorio.glob("*.tmp"))


def test_interrupcao_antes_da_publicacao_preserva_backup_anterior(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "interrupcao.db"
    raiz = tmp_path / "backups"
    _criar_banco(banco)
    primeiro = criar_backup_local(banco, raiz).caminho_backup
    monkeypatch.setattr(
        backup_module,
        "_publicar_sem_sobrescrever",
        lambda temporario, definitivo: (_ for _ in ()).throw(
            PublicacaoBackupError("interrupção controlada")
        ),
    )

    with pytest.raises(PublicacaoBackupError):
        criar_backup_local(banco, raiz)

    assert primeiro.exists()
    assert _consultar_produto(primeiro) is not None
    assert not tuple(primeiro.parent.glob("*.tmp"))


def test_retencao_mantem_sete_diarios_quatro_semanais_e_ultimo(tmp_path) -> None:
    diretorio = tmp_path / "retencao"
    diretorio.mkdir()
    identificador = "1" * 16
    outro_identificador = "2" * 16
    base = datetime(2026, 11, 16, 15, tzinfo=UTC)
    for dias in range(50):
        instante = base - timedelta(days=dias)
        nome = backup_module._criar_nome_backup(
            identificador,
            instante,
            f"{dias:032x}",
        )
        (diretorio / nome).write_bytes(b"backup")
    desconhecido = diretorio / "arquivo-do-usuario.db"
    desconhecido.write_bytes(b"externo")
    temporario = diretorio / ".operacao-em-andamento.tmp"
    temporario.write_bytes(b"temporario")
    outra_origem = diretorio / backup_module._criar_nome_backup(
        outro_identificador,
        base,
        "f" * 32,
    )
    outra_origem.write_bytes(b"outra-origem")

    removidos, falhas = backup_module._aplicar_retencao_local(
        diretorio,
        identificador,
        preservar=diretorio / backup_module._criar_nome_backup(
            identificador,
            base,
            f"{0:032x}",
        ),
    )

    restantes = backup_module._listar_backups_reconhecidos(
        diretorio,
        identificador,
    )
    assert removidos == 39
    assert falhas == 0
    assert len(restantes) == 11
    assert max(item.instante_utc for item in restantes) == base
    assert desconhecido.exists()
    assert temporario.exists()
    assert outra_origem.exists()


def test_retencao_so_e_aplicada_depois_de_novo_backup_valido(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "ordem.db"
    _criar_banco(banco)
    chamadas = []
    monkeypatch.setattr(
        backup_module,
        "_aplicar_retencao_local",
        lambda diretorio, origem, **kwargs: (
            chamadas.append((diretorio, origem, kwargs)) or (0, 0)
        ),
    )
    monkeypatch.setattr(
        backup_module,
        "_validar_backup",
        lambda caminho: (_ for _ in ()).throw(
            ValidacaoBackupError("inválido")
        ),
    )

    with pytest.raises(ValidacaoBackupError):
        criar_backup_local(banco, tmp_path / "backups")

    assert chamadas == []


def test_retencao_preserva_novo_backup_mesmo_com_relogio_retrocedido(
    tmp_path,
) -> None:
    diretorio = tmp_path / "relogio"
    diretorio.mkdir()
    identificador = "3" * 16
    base = datetime(2026, 11, 16, 15, tzinfo=UTC)
    for dias in range(50):
        nome = backup_module._criar_nome_backup(
            identificador,
            base - timedelta(days=dias),
            f"{dias:032x}",
        )
        (diretorio / nome).write_bytes(b"backup")
    novo_com_relogio_antigo = diretorio / backup_module._criar_nome_backup(
        identificador,
        base - timedelta(days=100),
        "e" * 32,
    )
    novo_com_relogio_antigo.write_bytes(b"novo-valido")

    backup_module._aplicar_retencao_local(
        diretorio,
        identificador,
        preservar=novo_com_relogio_antigo,
    )

    assert novo_com_relogio_antigo.read_bytes() == b"novo-valido"


def test_falha_de_exclusao_na_retencao_preserva_arquivos_e_e_reportada(
    tmp_path,
    monkeypatch,
) -> None:
    diretorio = tmp_path / "falha-retencao"
    diretorio.mkdir()
    identificador = "4" * 16
    base = datetime(2026, 11, 16, 15, tzinfo=UTC)
    caminhos = []
    for indice in range(15):
        caminho = diretorio / backup_module._criar_nome_backup(
            identificador,
            base - timedelta(hours=indice),
            f"{indice:032x}",
        )
        caminho.write_bytes(b"backup")
        caminhos.append(caminho)
    alvo_com_falha = caminhos[-1]
    unlink_original = Path.unlink

    def unlink_controlado(caminho, *args, **kwargs):
        if caminho == alvo_com_falha:
            raise PermissionError("arquivo em uso")
        return unlink_original(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_controlado)

    removidos, falhas = backup_module._aplicar_retencao_local(
        diretorio,
        identificador,
        preservar=caminhos[0],
    )

    assert removidos == 12
    assert falhas == 1
    assert caminhos[0].exists()
    assert alvo_com_falha.exists()


def test_bancos_independentes_usam_identidades_e_retencoes_isoladas(
    tmp_path,
) -> None:
    producao = tmp_path / "producao" / "pdv.db"
    homologacao = tmp_path / "homologacao" / "pdv.db"
    raiz = tmp_path / "backups"
    _criar_banco(producao, codigo="10", preco=1000)
    _criar_banco(homologacao, codigo="10", preco=9900)

    backup_producao = criar_backup_local(producao, raiz)
    backup_homologacao = criar_backup_local(homologacao, raiz)

    assert backup_producao.identificador_origem != (
        backup_homologacao.identificador_origem
    )
    assert backup_producao.caminho_backup.parent != (
        backup_homologacao.caminho_backup.parent
    )
    assert _consultar_produto(backup_producao.caminho_backup, "10")[2] == 1000
    assert _consultar_produto(backup_homologacao.caminho_backup, "10")[2] == 9900


def test_caminhos_equivalentes_identificam_a_mesma_origem(tmp_path) -> None:
    banco = tmp_path / "origem-equivalente.db"
    _criar_banco(banco)
    equivalente = banco.parent / "segmento" / ".." / banco.name

    origem_a, identidade_a = backup_module._identificar_origem(banco)
    origem_b, identidade_b = backup_module._identificar_origem(equivalente)

    assert origem_b == origem_a
    assert identidade_b == identidade_a


def test_backups_simultaneos_da_mesma_origem_serializam_retencao_e_retorno(
    tmp_path,
    monkeypatch,
) -> None:
    banco = tmp_path / "concorrente.db"
    raiz = tmp_path / "backups"
    _criar_banco(banco)
    origem, identificador = backup_module._identificar_origem(banco)
    diretorio = backup_module._preparar_diretorio_destino(
        origem,
        raiz,
        identificador,
    )
    base = datetime(2026, 11, 16, 15, tzinfo=UTC)
    for dias in range(30):
        caminho = diretorio / backup_module._criar_nome_backup(
            identificador,
            base - timedelta(days=dias),
            f"{dias:032x}",
        )
        caminho.write_bytes(b"backup-anterior")

    original = backup_module._criar_e_publicar_backup
    primeiro_entrou = Event()
    liberar_primeiro = Event()
    bloqueio_contador = Lock()
    ativos = 0
    maximo_ativos = 0
    chamadas = 0

    def criar_controlado(*args, **kwargs):
        nonlocal ativos, maximo_ativos, chamadas
        with bloqueio_contador:
            chamadas += 1
            numero = chamadas
            ativos += 1
            maximo_ativos = max(maximo_ativos, ativos)
        try:
            if numero == 1:
                primeiro_entrou.set()
                assert liberar_primeiro.wait(10)
            return original(*args, **kwargs)
        finally:
            with bloqueio_contador:
                ativos -= 1

    monkeypatch.setattr(
        backup_module,
        "_criar_e_publicar_backup",
        criar_controlado,
    )

    def executar():
        resultado = criar_backup_local(banco, raiz)
        return resultado, resultado.caminho_backup.is_file()

    with ThreadPoolExecutor(max_workers=2) as executor:
        primeiro = executor.submit(executar)
        assert primeiro_entrou.wait(10)
        segundo = executor.submit(executar)
        time.sleep(0.15)
        assert chamadas == 1
        liberar_primeiro.set()
        resultados = (primeiro.result(20), segundo.result(20))

    assert maximo_ativos == 1
    assert all(existia_ao_retornar for _, existia_ao_retornar in resultados)
    assert any(
        resultado.caminho_backup.exists() for resultado, _ in resultados
    )
    restantes = backup_module._listar_backups_reconhecidos(
        diretorio,
        identificador,
    )
    # O novo backup pode ser o 12º ponto quando o relógio aparente é anterior
    # ao backup reconhecido mais recente; ele permanece protegido por contrato.
    assert 1 <= len(restantes) <= 12


def test_origens_diferentes_nao_compartilham_bloqueio(
    tmp_path,
    monkeypatch,
) -> None:
    banco_a = tmp_path / "a" / "pdv.db"
    banco_b = tmp_path / "b" / "pdv.db"
    raiz = tmp_path / "backups"
    _criar_banco(banco_a, codigo="1")
    _criar_banco(banco_b, codigo="2")
    barreira = Barrier(2, timeout=10)
    original = backup_module._executar_backup_sqlite

    def executar_sincronizado(origem, temporario):
        barreira.wait()
        original(origem, temporario)

    monkeypatch.setattr(
        backup_module,
        "_executar_backup_sqlite",
        executar_sincronizado,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_a = executor.submit(criar_backup_local, banco_a, raiz)
        futuro_b = executor.submit(criar_backup_local, banco_b, raiz)
        resultado_a = futuro_a.result(20)
        resultado_b = futuro_b.result(20)

    assert resultado_a.caminho_backup.exists()
    assert resultado_b.caminho_backup.exists()
    assert resultado_a.identificador_origem != resultado_b.identificador_origem


def test_lock_de_arquivo_coordena_processos_cooperantes(tmp_path) -> None:
    banco = tmp_path / "processos.db"
    raiz = tmp_path / "backups"
    _criar_banco(banco)
    origem, identificador = backup_module._identificar_origem(banco)
    diretorio = backup_module._preparar_diretorio_destino(
        origem,
        raiz,
        identificador,
    )
    contexto = multiprocessing.get_context("spawn")
    inicio = contexto.Event()
    liberar_primeiro = contexto.Event()
    liberar_segundo = contexto.Event()
    fila = contexto.Queue()
    primeiro = contexto.Process(
        target=_processo_adquirir_lock,
        args=(diretorio, identificador, inicio, liberar_primeiro, fila),
    )
    segundo = contexto.Process(
        target=_processo_adquirir_lock,
        args=(diretorio, identificador, inicio, liberar_segundo, fila),
    )
    primeiro.start()
    segundo.start()
    inicio.set()
    try:
        primeira_mensagem = fila.get(timeout=20)
        assert primeira_mensagem == ("entrou", True)
        with pytest.raises(queue.Empty):
            fila.get(timeout=0.3)

        liberar_primeiro.set()
        liberar_segundo.set()
        segunda_mensagem = fila.get(timeout=20)
        assert segunda_mensagem == ("entrou", True)
    finally:
        liberar_primeiro.set()
        liberar_segundo.set()
        primeiro.join(20)
        segundo.join(20)
        if primeiro.is_alive():
            primeiro.terminate()
        if segundo.is_alive():
            segundo.terminate()

    assert primeiro.exitcode == 0
    assert segundo.exitcode == 0


@pytest.mark.parametrize("invalidar_catalogo", [False, True])
def test_modo_restritivo_recusa_backup_sem_criar_copia(
    tmp_path,
    invalidar_catalogo,
) -> None:
    banco = tmp_path / f"restritivo-{invalidar_catalogo}.db"
    raiz = tmp_path / "backups"
    _criar_banco(banco)
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)
    assert controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"),
        catalogo,
        banco,
    )
    if invalidar_catalogo:
        catalogo.invalidar("TESTE")
        assert controlador.obter_estado().modo is ModoOperacional.INDISPONIVEL

    with pytest.raises(OperacaoProibidaNoModoAtualError):
        criar_backup_local(
            banco,
            raiz,
            controlador_estado=ControladorEstadoOperacional(),
        )

    assert not raiz.exists()


def test_controlador_em_modo_normal_permite_backup(tmp_path) -> None:
    banco = tmp_path / "normal.db"
    _criar_banco(banco)
    controlador = ControladorEstadoOperacional()
    vincular_controlador_ao_banco(banco, controlador)

    resultado = criar_backup_local(
        banco,
        tmp_path / "backups",
        controlador_estado=controlador,
    )

    assert resultado.caminho_backup.exists()
    assert controlador.obter_estado().modo is ModoOperacional.NORMAL
