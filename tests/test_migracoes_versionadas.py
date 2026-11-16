import multiprocessing
from pathlib import Path
import sqlite3

import pytest

from database.conexao import conectar
import database.migracoes as migracoes_module
from database.migracoes import (
    DeclaracaoCompatibilidade,
    EstadoDeclaracaoCompatibilidade,
    EstadoHomologacaoCompatibilidade,
    EstruturaEsquemaDivergenteError,
    HomologacaoCompatibilidade,
    IntegridadeEsquemaError,
    MIGRACOES,
    MigracaoVersionada,
    RotaMigracaoIndisponivelError,
    executar_migracoes,
    inspecionar_migracao,
    planejar_migracao,
    planejar_rota_migracao,
    validar_estrutura_versao,
)
from database.schema import VERSAO_ESQUEMA, criar_tabelas
from services.inicializacao_banco_service import (
    BackupPreMigracaoError,
    BancoIncompativelError,
    MigracaoBancoError,
    preparar_banco_para_operacao,
)
import services.inicializacao_banco_service as inicializacao_module


def _criar_banco_na_versao(caminho: Path, versao: int) -> None:
    conexao = conectar(caminho)
    try:
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("BEGIN IMMEDIATE")
        for migracao in MIGRACOES:
            if migracao.destino > versao:
                break
            migracao.aplicar(conexao)
            conexao.execute(f"PRAGMA user_version = {migracao.destino}")
        conexao.commit()
    finally:
        conexao.close()


def _versao(caminho: Path) -> int:
    conexao = conectar(caminho)
    try:
        return conexao.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conexao.close()


def _processo_inicializar(caminho: str, fila) -> None:
    try:
        resultado = preparar_banco_para_operacao(Path(caminho))
        fila.put(
            (
                "sucesso",
                resultado.estado_migracao,
                resultado.backup_pre_migracao_realizado,
            )
        )
    except Exception as erro:
        fila.put(("erro", type(erro).__name__, False))


def test_banco_novo_e_atual_expoem_resultado_estruturado(tmp_path) -> None:
    caminho = tmp_path / "novo.db"

    novo = preparar_banco_para_operacao(caminho)
    atual = preparar_banco_para_operacao(caminho)

    assert novo.banco_novo
    assert novo.versao_inicial == 0
    assert novo.versao_final == VERSAO_ESQUEMA
    assert len(novo.migracoes_realizadas) == VERSAO_ESQUEMA
    assert (
        novo.declaracao_compatibilidade_aplicativo_anterior
        == "NAO_APLICAVEL"
    )
    assert (
        novo.homologacao_compatibilidade_aplicativo_anterior
        == "NAO_APLICAVEL"
    )
    assert novo.banco_apto_operacao_aplicativo_atual
    assert not novo.proxima_etapa_atualizacao_autorizada
    assert not novo.backup_pre_migracao_realizado
    assert atual.estado_migracao == "SEM_ALTERACOES"
    assert atual.migracoes_realizadas == ()
    assert atual.banco_apto_operacao_aplicativo_atual
    assert not atual.proxima_etapa_atualizacao_autorizada


def test_migracao_historica_unica_preserva_dados_mas_nao_autoriza_instalador(
    tmp_path,
) -> None:
    caminho = tmp_path / "v9.db"
    _criar_banco_na_versao(caminho, 9)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria, forma_venda,
                preco_venda_centavos, origem
            ) VALUES ('101', 'Produto legado', 'GERAL', 'UNIDADE', 1000,
                      'COMPRADO')
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    resultado = preparar_banco_para_operacao(caminho)
    segunda_inicializacao = preparar_banco_para_operacao(caminho)

    assert resultado.migracoes_realizadas == ("legado_0010_categorias",)
    assert (
        resultado.declaracao_compatibilidade_aplicativo_anterior
        == "NAO_DECLARADA"
    )
    assert (
        resultado.homologacao_compatibilidade_aplicativo_anterior
        == "PENDENTE"
    )
    assert not resultado.proxima_etapa_atualizacao_autorizada
    assert resultado.banco_apto_operacao_aplicativo_atual
    assert resultado.backup_pre_migracao_realizado
    assert resultado.caminho_backup.is_file()
    assert _versao(resultado.caminho_backup) == 9
    assert segunda_inicializacao.estado_migracao == "SEM_ALTERACOES"
    assert segunda_inicializacao.migracoes_realizadas == ()
    assert segunda_inicializacao.banco_apto_operacao_aplicativo_atual
    assert not segunda_inicializacao.proxima_etapa_atualizacao_autorizada
    conexao = conectar(caminho)
    try:
        assert conexao.execute(
            "SELECT nome FROM produtos WHERE codigo = '101'"
        ).fetchone()[0] == "Produto legado"
    finally:
        conexao.close()


def test_multiplas_migracoes_sao_sequenciais_atomicas_e_idempotentes(
    tmp_path,
) -> None:
    caminho = tmp_path / "v7.db"
    _criar_banco_na_versao(caminho, 7)

    primeiro = preparar_banco_para_operacao(caminho)
    segundo = preparar_banco_para_operacao(caminho)

    assert primeiro.migracoes_realizadas == (
        "legado_0008_identidade",
        "legado_0009_recuperacao",
        "legado_0010_categorias",
    )
    assert _versao(caminho) == VERSAO_ESQUEMA
    assert segundo.migracoes_realizadas == ()
    assert segundo.caminho_backup is None


def test_planejamento_recusa_rota_incompleta_e_versao_futura() -> None:
    with pytest.raises(RotaMigracaoIndisponivelError):
        planejar_rota_migracao(
            10,
            12,
            banco_novo=False,
            migracoes=(
                MigracaoVersionada(
                    10,
                    11,
                    "v11",
                    lambda conexao: None,
                    False,
                    DeclaracaoCompatibilidade.COMPATIVEL,
                ),
            ),
        )
    with pytest.raises(migracoes_module.VersaoEsquemaFuturaError):
        planejar_migracao(VERSAO_ESQUEMA + 1, banco_novo=False)


def test_declaracao_sem_homologacao_nao_autoriza_instalador() -> None:
    somente_declarada = (
        MigracaoVersionada(
            10,
            11,
            "v11",
            lambda conexao: None,
            False,
            DeclaracaoCompatibilidade.COMPATIVEL,
        ),
        MigracaoVersionada(
            11,
            12,
            "v12",
            lambda conexao: None,
            False,
            DeclaracaoCompatibilidade.COMPATIVEL,
        ),
    )
    homologada = tuple(
        MigracaoVersionada(
            item.origem,
            item.destino,
            item.identificador,
            item.aplicar,
            False,
            DeclaracaoCompatibilidade.COMPATIVEL,
            HomologacaoCompatibilidade("1.0.0", f"REL-{item.destino}"),
        )
        for item in somente_declarada
    )
    incompativel = (
        somente_declarada[0],
        MigracaoVersionada(
            11,
            12,
            "v12",
            lambda conexao: None,
            False,
            DeclaracaoCompatibilidade.INCOMPATIVEL,
        ),
    )

    plano_declarado = planejar_rota_migracao(
        10,
        12,
        banco_novo=False,
        migracoes=somente_declarada,
    )
    plano_homologado = planejar_rota_migracao(
        10,
        12,
        banco_novo=False,
        migracoes=homologada,
    )
    plano_incompativel = planejar_rota_migracao(
        10,
        12,
        banco_novo=False,
        migracoes=incompativel,
    )

    assert plano_declarado.declaracao_compatibilidade is (
        EstadoDeclaracaoCompatibilidade.DECLARADA_COMPATIVEL
    )
    assert plano_declarado.homologacao_compatibilidade is (
        EstadoHomologacaoCompatibilidade.PENDENTE
    )
    assert not plano_declarado.proxima_etapa_atualizacao_autorizada
    assert plano_homologado.homologacao_compatibilidade is (
        EstadoHomologacaoCompatibilidade.HOMOLOGADA
    )
    assert plano_homologado.proxima_etapa_atualizacao_autorizada
    assert plano_incompativel.declaracao_compatibilidade is (
        EstadoDeclaracaoCompatibilidade.DECLARADA_INCOMPATIVEL
    )
    assert not plano_incompativel.proxima_etapa_atualizacao_autorizada


@pytest.mark.parametrize("versao", [0, VERSAO_ESQUEMA])
def test_estrutura_divergente_da_versao_e_bloqueada_sem_backup(
    tmp_path,
    versao,
) -> None:
    caminho = tmp_path / f"divergente-{versao}.db"
    if versao == 0:
        conexao = conectar(caminho)
        conexao.execute("CREATE TABLE desconhecida (id INTEGER PRIMARY KEY)")
        conexao.commit()
        conexao.close()
    else:
        criar_tabelas(caminho)
        conexao = conectar(caminho)
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("DROP TABLE pagamentos")
        conexao.commit()
        conexao.close()

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)

    assert not (tmp_path / "backups" / "pre_migracao").exists()


@pytest.mark.parametrize("versao", range(1, VERSAO_ESQUEMA + 1))
def test_contratos_estruturais_preservam_cada_versao_historica(
    tmp_path,
    versao,
) -> None:
    caminho = tmp_path / f"historico-{versao}.db"
    _criar_banco_na_versao(caminho, versao)
    conexao = conectar(caminho)
    try:
        validar_estrutura_versao(conexao, versao)
    finally:
        conexao.close()


def test_coluna_essencial_ausente_com_user_version_correto_e_bloqueada(
    tmp_path,
) -> None:
    caminho = tmp_path / "sem-coluna.db"
    criar_tabelas(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute("ALTER TABLE usuarios DROP COLUMN criado_em")
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)


def test_tipo_de_coluna_incompativel_com_user_version_e_bloqueado(
    tmp_path,
) -> None:
    caminho = tmp_path / "tipo-incompativel.db"
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            CREATE TABLE produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo INTEGER NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                categoria TEXT NOT NULL,
                forma_venda TEXT NOT NULL,
                preco_venda_centavos INTEGER NOT NULL,
                origem TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conexao.execute(
            """
            CREATE TABLE vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_centavos INTEGER NOT NULL,
                registrada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conexao.execute("PRAGMA user_version = 1")
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)


def test_definicao_de_indice_incompativel_e_bloqueada(tmp_path) -> None:
    caminho = tmp_path / "indice-incompativel.db"
    criar_tabelas(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute("DROP INDEX ix_produtos_categoria_ativo_nome")
        conexao.execute(
            """
            CREATE INDEX ix_produtos_categoria_ativo_nome
            ON produtos (ativo, nome)
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)


def test_definicao_de_chave_estrangeira_incompativel_e_bloqueada(
    tmp_path,
) -> None:
    caminho = tmp_path / "fk-incompativel.db"
    criar_tabelas(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("ALTER TABLE pagamentos RENAME TO pagamentos_antigos")
        conexao.execute(
            """
            CREATE TABLE pagamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER NOT NULL,
                modalidade TEXT NOT NULL,
                valor_centavos INTEGER NOT NULL
            )
            """
        )
        conexao.execute("DROP TABLE pagamentos_antigos")
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)


def test_inspecao_de_caminho_inexistente_nao_cria_banco(tmp_path) -> None:
    caminho = tmp_path / "ausente" / "nao-criar.db"

    with pytest.raises(IntegridadeEsquemaError):
        inspecionar_migracao(caminho)

    assert not caminho.exists()
    assert not caminho.parent.exists()


def test_banco_corrompido_e_bloqueado_sem_recriacao(tmp_path) -> None:
    caminho = tmp_path / "corrompido.db"
    conteudo = b"nao e um banco sqlite"
    caminho.write_bytes(conteudo)

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)

    assert caminho.read_bytes() == conteudo


def test_falha_de_backup_impede_qualquer_migracao(tmp_path, monkeypatch) -> None:
    caminho = tmp_path / "falha-backup.db"
    _criar_banco_na_versao(caminho, 9)
    monkeypatch.setattr(
        inicializacao_module,
        "_executar_backup_sqlite",
        lambda *args: (_ for _ in ()).throw(OSError("falha controlada")),
    )

    with pytest.raises(BackupPreMigracaoError):
        preparar_banco_para_operacao(caminho)

    assert _versao(caminho) == 9


def test_falha_de_permissao_na_inspecao_bloqueia_sem_alterar(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "sem-permissao.db"
    _criar_banco_na_versao(caminho, 9)
    monkeypatch.setattr(
        migracoes_module,
        "_conectar_somente_leitura",
        lambda *args: (_ for _ in ()).throw(PermissionError("acesso negado")),
    )

    with pytest.raises(BancoIncompativelError):
        preparar_banco_para_operacao(caminho)

    monkeypatch.undo()
    assert _versao(caminho) == 9


def test_falha_antes_da_primeira_migracao_preserva_versao(tmp_path) -> None:
    caminho = tmp_path / "antes-da-migracao.db"
    _criar_banco_na_versao(caminho, 9)

    with pytest.raises(RuntimeError, match="antes da primeira migracao"):
        executar_migracoes(
            caminho,
            antes_de_migrar=lambda plano: (_ for _ in ()).throw(
                RuntimeError("antes da primeira migracao")
            ),
        )

    assert _versao(caminho) == 9


def test_interrupcao_durante_migracao_reverte_estrutura_e_versao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "interrompida.db"
    _criar_banco_na_versao(caminho, 9)
    monkeypatch.setattr(
        migracoes_module.schema,
        "_migrar_categorias_v10",
        lambda conexao: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        executar_migracoes(caminho)

    assert _versao(caminho) == 9
    conexao = conectar(caminho)
    try:
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(produtos)")
        }
        assert "categoria" in colunas
        assert "categoria_id" not in colunas
    finally:
        conexao.close()


def test_falha_apos_ddl_antes_da_versao_reverte_toda_migracao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "rollback.db"
    _criar_banco_na_versao(caminho, 9)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria, forma_venda,
                preco_venda_centavos, origem
            ) VALUES ('10', 'Preservar', 'GERAL', 'UNIDADE', 1000, 'COMPRADO')
            """
        )
        conexao.commit()
    finally:
        conexao.close()
    monkeypatch.setattr(
        migracoes_module,
        "_atualizar_versao",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("falha antes de atualizar versao")
        ),
    )

    with pytest.raises(MigracaoBancoError):
        preparar_banco_para_operacao(caminho)

    assert _versao(caminho) == 9
    conexao = conectar(caminho)
    try:
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(produtos)")
        }
        assert "categoria" in colunas
        assert "categoria_id" not in colunas
        assert conexao.execute(
            "SELECT nome FROM produtos WHERE codigo = '10'"
        ).fetchone()[0] == "Preservar"
    finally:
        conexao.close()


def test_inicializacoes_concorrentes_entre_processos_sao_serializadas(
    tmp_path,
) -> None:
    caminho = tmp_path / "concorrente.db"
    _criar_banco_na_versao(caminho, 9)
    contexto = multiprocessing.get_context("spawn")
    fila = contexto.Queue()
    processos = [
        contexto.Process(
            target=_processo_inicializar,
            args=(str(caminho), fila),
        )
        for _ in range(2)
    ]
    for processo in processos:
        processo.start()
    try:
        resultados = [fila.get(timeout=30) for _ in processos]
    finally:
        for processo in processos:
            processo.join(30)
            if processo.is_alive():
                processo.terminate()

    assert all(processo.exitcode == 0 for processo in processos)
    assert all(item[0] == "sucesso" for item in resultados)
    assert sum(item[2] for item in resultados) == 1
    assert _versao(caminho) == VERSAO_ESQUEMA


def test_nucleo_t55_valida_antes_de_publicar_pre_migracao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "v9.db"
    _criar_banco_na_versao(caminho, 9)
    destino = tmp_path / "backup.db"
    monkeypatch.setattr(
        inicializacao_module,
        "_verificar_integridade_backup",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.DatabaseError("copia invalida")
        ),
    )

    with pytest.raises(sqlite3.DatabaseError):
        inicializacao_module._executar_backup_sqlite(
            caminho,
            destino,
            versao_esperada=9,
        )

    assert not destino.exists()
    assert not tuple(tmp_path.glob("*.tmp"))


def test_backup_pre_migracao_recusa_versao_diferente_da_esperada(
    tmp_path,
) -> None:
    caminho = tmp_path / "origem-v9.db"
    destino = tmp_path / "backup-divergente.db"
    _criar_banco_na_versao(caminho, 9)

    with pytest.raises(sqlite3.DatabaseError, match="versão original esperada"):
        inicializacao_module._executar_backup_sqlite(
            caminho,
            destino,
            versao_esperada=8,
        )

    assert not destino.exists()
    assert not tuple(tmp_path.glob("*.tmp"))
