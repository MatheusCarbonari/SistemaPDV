from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from database.conexao import conectar
from database.schema import VERSAO_ESQUEMA
from models.produto import Produto
from repositories.produto_repository import salvar_produto
from services.autenticacao_service import LimitadorTentativasLogin
from services.backup_externo_service import DestinoDiretorio, ServicoBackupExterno
from services.backup_local_service import criar_backup_local
from services.catalogo_memoria_service import CatalogoProdutosMemoria
from services.estado_operacional_service import (
    ControladorEstadoOperacional,
    ModoOperacional,
    vincular_controlador_ao_banco,
)
from services.logging_service import configurar_logging, encerrar_logging
import services.restauracao_assistida_service as restauracao_module
from services.restauracao_assistida_service import (
    AcessoBackupError,
    BackupInvalidoError,
    BackupNaoEncontradoError,
    BaseRestauradaJaExisteError,
    ConfirmacaoRestauracaoObrigatoriaError,
    DestinoRestauracaoInvalidoError,
    EstruturaBackupIncompativelError,
    OrigemBackup,
    OrigemBackupNaoReconhecidaError,
    PublicacaoRestauracaoError,
    RestauracaoNaoAutorizadaError,
    restaurar_backup_em_base_teste,
)
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_sessao_admin_teste,
)


SENHA_CAIXA_TESTE = "frase segura exclusiva do caixa restauracao"


def _criar_ambiente(tmp_path):
    banco = tmp_path / "operacional.db"
    sessao = criar_sessao_admin_teste(banco)
    salvar_produto(
        Produto(
            codigo="101",
            nome="Produto restaurado",
            categoria="GERAL",
            forma_venda="UNIDADE",
            preco_venda_centavos=1250,
            origem="COMPRADO",
        ),
        banco,
    )
    conexao = conectar(banco)
    try:
        cursor = conexao.execute(
            "INSERT INTO vendas (total_centavos) VALUES (1250)"
        )
        conexao.execute(
            """
            INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
            VALUES (?, 'DINHEIRO', 1250)
            """,
            (cursor.lastrowid,),
        )
        conexao.commit()
    finally:
        conexao.close()
    backup = criar_backup_local(banco, tmp_path / "backups").caminho_backup
    destino_dir = tmp_path / "restauradas"
    destino_dir.mkdir()
    return banco, sessao, backup, destino_dir


def _restaurar(
    backup,
    destino,
    sessao,
    banco,
    **alteracoes,
):
    parametros = {
        "identificacao_administrador": "administrador",
        "senha_administrador": SENHA_ADMIN_TESTE,
        "confirmacao_explicita": True,
        "limitador": LimitadorTentativasLogin(),
    }
    parametros.update(alteracoes)
    return restaurar_backup_em_base_teste(
        backup,
        destino,
        sessao,
        banco,
        **parametros,
    )


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_backup_local_valido_e_restaurado_em_base_isolada(tmp_path) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    destino = diretorio / "teste.sqlite3"

    resultado = _restaurar(backup, destino, sessao, banco)

    assert resultado.caminho_base_teste == destino
    assert resultado.origem_backup is OrigemBackup.LOCAL
    assert resultado.resultado_validacao == "VALIDA"
    assert resultado.versao_schema == VERSAO_ESQUEMA
    assert resultado.registros.produtos == 1
    assert resultado.registros.vendas == 1
    assert resultado.registros.pagamentos == 1
    conexao = sqlite3.connect(destino)
    try:
        assert conexao.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conexao.execute(
            "SELECT nome FROM produtos WHERE codigo = '101'"
        ).fetchone()[0] == "Produto restaurado"
    finally:
        conexao.close()


def test_backup_externo_valido_e_aceito(tmp_path) -> None:
    banco, sessao, _, diretorio = _criar_ambiente(tmp_path)
    servico = ServicoBackupExterno(
        banco,
        destino=DestinoDiretorio(tmp_path / "externo"),
        diretorio_backup_local=tmp_path / "local-transporte",
    )
    assert servico.executar().status.value == "SUCESSO"
    backup_externo = servico.obter_ultimo_resultado().caminho_backup

    resultado = _restaurar(
        backup_externo,
        diretorio / "externo.sqlite3",
        sessao,
        banco,
    )

    assert resultado.origem_backup is OrigemBackup.EXTERNO
    assert resultado.caminho_base_teste.is_file()


def test_arquivo_inexistente_diretorio_e_nome_nao_oficial_sao_recusados(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    with pytest.raises(BackupNaoEncontradoError):
        _restaurar(
            tmp_path / "ausente.sqlite3",
            diretorio / "ausente.sqlite3",
            sessao,
            banco,
        )
    with pytest.raises(BackupInvalidoError):
        _restaurar(
            diretorio,
            diretorio / "diretorio.sqlite3",
            sessao,
            banco,
        )

    nao_oficial = tmp_path / "backup-renomeado.sqlite3"
    nao_oficial.write_bytes(backup.read_bytes())
    with pytest.raises(OrigemBackupNaoReconhecidaError):
        _restaurar(
            nao_oficial,
            diretorio / "nao-oficial.sqlite3",
            sessao,
            banco,
        )


def test_link_simbolico_de_backup_e_recusado(tmp_path, monkeypatch) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    link = tmp_path / "link" / backup.name
    original = Path.is_symlink

    def identificar_link(caminho):
        return caminho == link or original(caminho)

    monkeypatch.setattr(Path, "is_symlink", identificar_link)

    with pytest.raises(BackupInvalidoError):
        _restaurar(link, diretorio / "link.sqlite3", sessao, banco)


def test_arquivo_corrompido_e_recusado_sem_publicacao(tmp_path) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    backup.write_bytes(b"nao e sqlite")
    destino = diretorio / "corrompido.sqlite3"

    with pytest.raises(BackupInvalidoError):
        _restaurar(backup, destino, sessao, banco)

    assert not destino.exists()
    assert not tuple(diretorio.glob("*.tmp"))


def test_schema_incompativel_e_estrutura_incompleta_sao_distinguidos(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    conexao = sqlite3.connect(backup)
    try:
        conexao.execute(f"PRAGMA user_version = {VERSAO_ESQUEMA + 1}")
        conexao.commit()
    finally:
        conexao.close()
    with pytest.raises(EstruturaBackupIncompativelError):
        _restaurar(
            backup,
            diretorio / "schema.sqlite3",
            sessao,
            banco,
        )

    outro = criar_backup_local(banco, tmp_path / "outros").caminho_backup
    conexao = sqlite3.connect(outro)
    try:
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("DROP TABLE pagamentos")
        conexao.commit()
    finally:
        conexao.close()
    with pytest.raises(EstruturaBackupIncompativelError):
        _restaurar(
            outro,
            diretorio / "estrutura.sqlite3",
            sessao,
            banco,
        )


def test_violacao_de_chave_estrangeira_e_recusada(tmp_path) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    conexao = sqlite3.connect(backup)
    try:
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute(
            """
            INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
            VALUES (999999, 'PIX', 100)
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(BackupInvalidoError):
        _restaurar(
            backup,
            diretorio / "fk.sqlite3",
            sessao,
            banco,
        )


def test_falha_de_acesso_e_diferenciada(tmp_path, monkeypatch) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    monkeypatch.setattr(
        restauracao_module.sqlite3,
        "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("acesso negado")
        ),
    )

    with pytest.raises(AcessoBackupError):
        _restaurar(
            backup,
            diretorio / "acesso.sqlite3",
            sessao,
            banco,
        )


def test_confirmacao_sessao_e_credenciais_administrativas_sao_obrigatorias(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    with pytest.raises(ConfirmacaoRestauracaoObrigatoriaError):
        _restaurar(
            backup,
            diretorio / "sem-confirmacao.sqlite3",
            sessao,
            banco,
            confirmacao_explicita=False,
        )
    with pytest.raises(RestauracaoNaoAutorizadaError):
        _restaurar(
            backup,
            diretorio / "senha-invalida.sqlite3",
            sessao,
            banco,
            senha_administrador="senha incorreta",
        )
    with pytest.raises(RestauracaoNaoAutorizadaError):
        _restaurar(
            backup,
            diretorio / "sessao-invalida.sqlite3",
            object(),
            banco,
        )
    assert not tuple(diretorio.glob("*.sqlite3"))


def test_credenciais_de_caixa_nao_autorizam_restauracao(tmp_path) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    caixa, erros = criar_conta_caixa(
        sessao,
        "caixa01",
        SENHA_CAIXA_TESTE,
        SENHA_CAIXA_TESTE,
        banco,
    )
    assert caixa is not None and erros == []

    with pytest.raises(RestauracaoNaoAutorizadaError):
        _restaurar(
            backup,
            diretorio / "caixa.sqlite3",
            sessao,
            banco,
            identificacao_administrador="caixa01",
            senha_administrador=SENHA_CAIXA_TESTE,
        )


@pytest.mark.parametrize("alvo", ["operacional", "backup"])
def test_destino_igual_ou_equivalente_a_arquivo_protegido_e_recusado(
    tmp_path,
    alvo,
) -> None:
    banco, sessao, backup, _ = _criar_ambiente(tmp_path)
    segmento = tmp_path / "segmento"
    segmento.mkdir()
    protegido = banco if alvo == "operacional" else backup
    equivalente = segmento / ".." / protegido.name
    if alvo == "backup":
        equivalente = backup.parent / "segmento" / ".." / backup.name
        (backup.parent / "segmento").mkdir()

    with pytest.raises(DestinoRestauracaoInvalidoError):
        _restaurar(backup, equivalente, sessao, banco)


def test_colisao_preserva_base_anterior(tmp_path) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    destino = diretorio / "existente.sqlite3"
    destino.write_bytes(b"conteudo anterior")

    with pytest.raises(BaseRestauradaJaExisteError):
        _restaurar(backup, destino, sessao, banco)

    assert destino.read_bytes() == b"conteudo anterior"


def test_banco_operacional_nao_pode_ser_disfarcado_de_backup(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    banco_disfarcado = tmp_path / backup.name
    try:
        os.link(banco, banco_disfarcado)
    except OSError:
        pytest.skip("O filesystem não permitiu criar hard link para o teste.")

    with pytest.raises(BackupInvalidoError):
        _restaurar(
            banco_disfarcado,
            diretorio / "proibido.sqlite3",
            sessao,
            banco,
        )


def test_falha_na_copia_e_interrupcao_antes_da_publicacao_limpam_temporario(
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    monkeypatch.setattr(
        restauracao_module,
        "_copiar_backup",
        lambda *args: (_ for _ in ()).throw(AcessoBackupError("falha controlada")),
    )
    with pytest.raises(AcessoBackupError):
        _restaurar(
            backup,
            diretorio / "copia.sqlite3",
            sessao,
            banco,
        )
    assert not tuple(diretorio.glob("*.tmp"))

    monkeypatch.undo()
    monkeypatch.setattr(
        restauracao_module,
        "_publicar_sem_sobrescrever",
        lambda *args: (_ for _ in ()).throw(
            PublicacaoRestauracaoError("interrompido")
        ),
    )
    with pytest.raises(PublicacaoRestauracaoError):
        _restaurar(
            backup,
            diretorio / "publicacao.sqlite3",
            sessao,
            banco,
        )
    assert not tuple(diretorio.glob("*.tmp"))
    assert not (diretorio / "publicacao.sqlite3").exists()


def test_backup_banco_operacional_e_restauracoes_anteriores_sao_preservados(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    hash_banco = _sha256(banco)
    hash_backup = _sha256(backup)
    primeira = diretorio / "primeira.sqlite3"
    segunda = diretorio / "segunda.sqlite3"

    _restaurar(backup, primeira, sessao, banco)
    conteudo_primeira = primeira.read_bytes()
    _restaurar(backup, segunda, sessao, banco)

    assert _sha256(banco) == hash_banco
    assert _sha256(backup) == hash_backup
    assert primeira.read_bytes() == conteudo_primeira
    assert segunda.is_file()


def test_execucoes_concorrentes_nao_sobrescrevem_mesmo_destino(
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    destino = diretorio / "concorrente.sqlite3"
    barreira = Barrier(2, timeout=20)
    publicar_original = restauracao_module._publicar_sem_sobrescrever

    def publicar_sincronizado(*args):
        barreira.wait()
        publicar_original(*args)

    monkeypatch.setattr(
        restauracao_module,
        "_publicar_sem_sobrescrever",
        publicar_sincronizado,
    )

    def executar():
        try:
            return _restaurar(backup, destino, sessao, banco)
        except Exception as erro:
            return erro

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = tuple(executor.map(lambda _: executar(), range(2)))

    assert sum(not isinstance(item, Exception) for item in resultados) == 1
    assert sum(
        isinstance(item, BaseRestauradaJaExisteError) for item in resultados
    ) == 1
    assert destino.is_file()
    assert not tuple(diretorio.glob("*.tmp"))


def test_restauracao_nao_altera_estado_operacional_nem_fechamento_incerto(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    catalogo = CatalogoProdutosMemoria()
    catalogo.carregar(banco)
    controlador = ControladorEstadoOperacional()
    controlador = vincular_controlador_ao_banco(banco, controlador)
    assert controlador.tentar_ativar_calculo_degradado(
        sqlite3.OperationalError("database is locked"),
        catalogo,
        banco,
    )
    origem_incerteza = object()
    controlador.registrar_fechamento_incerto(origem_incerteza)

    _restaurar(
        backup,
        diretorio / "sem-retomada.sqlite3",
        sessao,
        banco,
    )

    assert controlador.obter_estado().modo is ModoOperacional.CALCULO_DEGRADADO
    assert controlador.possui_fechamento_incerto()


def test_logs_nao_expoem_caminhos_credenciais_ou_dados_comerciais(
    tmp_path,
) -> None:
    banco, sessao, backup, diretorio = _criar_ambiente(tmp_path)
    caminho_log = configurar_logging(tmp_path / "logs")
    try:
        _restaurar(
            backup,
            diretorio / "log-seguro.sqlite3",
            sessao,
            banco,
        )
    finally:
        encerrar_logging()

    documento = json.loads(caminho_log.read_text(encoding="utf-8"))
    conteudo = caminho_log.read_text(encoding="utf-8")
    assert documento["event"] == "restauracao_teste_concluida"
    assert documento["component"] == "restauracao"
    assert documento["resultado"] == "sucesso"
    assert str(tmp_path) not in conteudo
    assert SENHA_ADMIN_TESTE not in conteudo
    assert "Produto restaurado" not in conteudo
