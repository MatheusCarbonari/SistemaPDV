from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest
from PySide6.QtWidgets import QDialog, QLineEdit

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from interface.dialogo_primeiro_acesso import DialogoPrimeiroAcesso
from repositories.usuario_repository import (
    AdministradorJaConfiguradoError,
    EstadoIdentidadeInconsistenteError,
    buscar_hash_administrador_inicial,
)
from services.administrador_inicial_service import (
    criar_administrador_inicial,
    obter_estado_primeiro_acesso,
)
from services.senha_service import gerar_hash_senha, verificar_senha


SENHA_FORTE = "frase segura para o administrador 2026"


@pytest.fixture
def banco_identidade(tmp_path):
    caminho = tmp_path / "identidade.db"
    criar_tabelas(caminho)
    return caminho


def criar_admin(caminho, identificacao="administrador", senha=SENHA_FORTE):
    usuario, erros = criar_administrador_inicial(
        identificacao,
        senha,
        senha,
        caminho,
    )
    assert erros == []
    return usuario


def test_migracao_v7_cria_identidade_e_preserva_dados(tmp_path) -> None:
    caminho = tmp_path / "migracao_v7_v8.db"
    criar_tabelas(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria, forma_venda,
                preco_venda_centavos, origem
            ) VALUES ('101', 'Picanha', 'BOVINOS', 'PESO', 7990, 'COMPRADO')
            """
        )
        conexao.execute("DROP TABLE estado_identidade")
        conexao.execute("DROP TABLE usuarios")
        conexao.execute("PRAGMA user_version = 7")
        conexao.commit()
    finally:
        conexao.close()

    criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 8
        assert conexao.execute(
            "SELECT nome FROM produtos WHERE codigo = '101'"
        ).fetchone()[0] == "Picanha"
        estado = conexao.execute(
            "SELECT administrador_inicial_id, configurado_em "
            "FROM estado_identidade WHERE id = 1"
        ).fetchone()
        assert tuple(estado) == (None, None)
    finally:
        conexao.close()


def test_falha_na_migracao_v8_reverte_estruturas_e_versao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_migracao_v8.db"
    criar_tabelas(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute("DROP TABLE estado_identidade")
        conexao.execute("DROP TABLE usuarios")
        conexao.execute("PRAGMA user_version = 7")
        conexao.commit()
    finally:
        conexao.close()
    monkeypatch.setattr(
        schema,
        "_COMANDO_INICIALIZAR_ESTADO_IDENTIDADE",
        "INSERT INTO estado_identidade (id) VALUES (2)",
    )

    with pytest.raises(sqlite3.IntegrityError):
        criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 7
        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "usuarios" not in tabelas
        assert "estado_identidade" not in tabelas
    finally:
        conexao.close()


def test_criacao_valida_persiste_admin_sem_senha_em_texto_puro(
    banco_identidade,
) -> None:
    usuario = criar_admin(banco_identidade, "  ADMIN.Principal  ")

    assert usuario.identificacao_acesso == "admin.principal"
    assert usuario.perfil == "ADMINISTRADOR"
    assert usuario.ativo is True
    assert obter_estado_primeiro_acesso(banco_identidade) == "CONFIGURADO"
    conexao = conectar(banco_identidade)
    try:
        linha = conexao.execute(
            "SELECT identificacao_acesso, perfil, senha_hash FROM usuarios"
        ).fetchone()
        assert linha["identificacao_acesso"] == "admin.principal"
        assert linha["perfil"] == "ADMINISTRADOR"
        assert linha["senha_hash"] != SENHA_FORTE
        assert SENHA_FORTE not in linha["senha_hash"]
        assert linha["senha_hash"].startswith("scrypt$v=1$")
    finally:
        conexao.close()


def test_verificacao_de_senha_correta_incorreta_e_hash_corrompido(
    banco_identidade,
) -> None:
    criar_admin(banco_identidade)
    armazenado = buscar_hash_administrador_inicial(banco_identidade)

    assert verificar_senha(SENHA_FORTE, armazenado)
    assert not verificar_senha("senha incorreta", armazenado)
    assert not verificar_senha(SENHA_FORTE, "scrypt$v=1$corrompido")
    assert not verificar_senha(SENHA_FORTE, "")
    assert not verificar_senha(SENHA_FORTE, None)


def test_salt_individual_produz_hashes_distintos() -> None:
    primeiro = gerar_hash_senha(SENHA_FORTE)
    segundo = gerar_hash_senha(SENHA_FORTE)

    assert primeiro != segundo
    assert verificar_senha(SENHA_FORTE, primeiro)
    assert verificar_senha(SENHA_FORTE, segundo)


@pytest.mark.parametrize(
    ("identificacao", "senha", "confirmacao", "trecho"),
    (
        ("", SENHA_FORTE, SENHA_FORTE, "identificação"),
        ("ab", SENHA_FORTE, SENHA_FORTE, "entre 3 e 64"),
        ("admin inválido", SENHA_FORTE, SENHA_FORTE, "permite apenas"),
        ("admin", "curta", "curta", "ao menos 12"),
        ("admin", "x" * 129, "x" * 129, "no máximo 128"),
        ("admin", " " * 12, " " * 12, "somente espaços"),
        ("admin", SENHA_FORTE, "outra confirmação", "não confere"),
    ),
)
def test_credenciais_invalidas_nao_criam_usuario(
    banco_identidade,
    identificacao,
    senha,
    confirmacao,
    trecho,
) -> None:
    usuario, erros = criar_administrador_inicial(
        identificacao,
        senha,
        confirmacao,
        banco_identidade,
    )

    assert usuario is None
    assert any(trecho in erro for erro in erros)
    assert obter_estado_primeiro_acesso(banco_identidade) == "NAO_CONFIGURADO"


def test_segunda_inicializacao_e_rejeitada(banco_identidade) -> None:
    primeiro = criar_admin(banco_identidade)

    with pytest.raises(AdministradorJaConfiguradoError):
        criar_administrador_inicial(
            "outro-admin",
            "outra frase de senha bem segura",
            "outra frase de senha bem segura",
            banco_identidade,
        )

    conexao = conectar(banco_identidade)
    try:
        assert conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 1
        assert conexao.execute(
            "SELECT id FROM usuarios"
        ).fetchone()[0] == primeiro.id
    finally:
        conexao.close()


def test_identificacao_de_acesso_e_unica_sem_diferenciar_maiusculas(
    banco_identidade,
) -> None:
    criar_admin(banco_identidade, "admin.principal")
    conexao = conectar(banco_identidade)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                """
                INSERT INTO usuarios (
                    identificacao_acesso, perfil, senha_hash
                ) VALUES ('ADMIN.PRINCIPAL', 'CAIXA', 'hash-qualquer')
                """
            )
        conexao.rollback()
    finally:
        conexao.close()


def test_criacoes_concorrentes_produzem_um_unico_administrador(
    banco_identidade,
) -> None:
    def tentar(indice):
        try:
            usuario, erros = criar_administrador_inicial(
                f"admin-{indice}",
                SENHA_FORTE,
                SENHA_FORTE,
                banco_identidade,
            )
            return usuario, erros, None
        except Exception as erro:
            return None, [], erro

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(tentar, (1, 2)))

    sucessos = [resultado for resultado in resultados if resultado[0] is not None]
    falhas = [resultado[2] for resultado in resultados if resultado[2] is not None]
    assert len(sucessos) == 1
    assert len(falhas) == 1
    assert isinstance(falhas[0], AdministradorJaConfiguradoError)
    assert obter_estado_primeiro_acesso(banco_identidade) == "CONFIGURADO"


def test_falha_ao_marcar_configuracao_reverte_usuario(
    banco_identidade,
) -> None:
    conexao = conectar(banco_identidade)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_estado_identidade
            BEFORE UPDATE ON estado_identidade
            BEGIN
                SELECT RAISE(ABORT, 'falha ao marcar configuração');
            END;
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha ao marcar"):
        criar_admin(banco_identidade)

    conexao = conectar(banco_identidade)
    try:
        assert conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
    finally:
        conexao.close()
    assert obter_estado_primeiro_acesso(banco_identidade) == "NAO_CONFIGURADO"


def test_usuario_sem_marcador_e_estado_inconsistente(banco_identidade) -> None:
    conexao = conectar(banco_identidade)
    try:
        conexao.execute(
            """
            INSERT INTO usuarios (
                identificacao_acesso, perfil, senha_hash
            ) VALUES ('solto', 'ADMINISTRADOR', 'hash-invalido')
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(EstadoIdentidadeInconsistenteError):
        obter_estado_primeiro_acesso(banco_identidade)
    with pytest.raises(EstadoIdentidadeInconsistenteError):
        criar_admin(banco_identidade)


def test_administrador_configurado_nao_pode_ser_removido_normalmente(
    banco_identidade,
) -> None:
    usuario = criar_admin(banco_identidade)
    conexao = conectar(banco_identidade)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute("DELETE FROM usuarios WHERE id = ?", (usuario.id,))
        conexao.rollback()
    finally:
        conexao.close()
    assert obter_estado_primeiro_acesso(banco_identidade) == "CONFIGURADO"


def test_reset_superficial_do_marcador_nao_reabre_primeiro_acesso(
    banco_identidade,
) -> None:
    criar_admin(banco_identidade)
    conexao = conectar(banco_identidade)
    try:
        conexao.execute(
            """
            UPDATE estado_identidade
            SET administrador_inicial_id = NULL, configurado_em = NULL
            WHERE id = 1
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(EstadoIdentidadeInconsistenteError):
        obter_estado_primeiro_acesso(banco_identidade)
    with pytest.raises(EstadoIdentidadeInconsistenteError):
        criar_admin(banco_identidade)


def test_ausencia_inesperada_do_administrador_falha_sem_recriacao(
    banco_identidade,
) -> None:
    usuario = criar_admin(banco_identidade)
    conexao = sqlite3.connect(banco_identidade)
    try:
        conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("DELETE FROM usuarios WHERE id = ?", (usuario.id,))
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(EstadoIdentidadeInconsistenteError):
        obter_estado_primeiro_acesso(banco_identidade)
    with pytest.raises(EstadoIdentidadeInconsistenteError):
        criar_admin(banco_identidade)


def test_dialogo_oculta_senhas_valida_e_conclui_configuracao(
    qtbot,
    banco_identidade,
) -> None:
    dialogo = DialogoPrimeiroAcesso(banco_identidade)
    qtbot.addWidget(dialogo)
    dialogo.show()

    assert dialogo.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    assert dialogo.campo_confirmacao.echoMode() == QLineEdit.EchoMode.Password
    dialogo.campo_identificacao.setText("admin")
    dialogo.campo_senha.setText("curta")
    dialogo.campo_confirmacao.setText("curta")
    dialogo.criar_administrador()
    assert "ao menos 12" in dialogo.rotulo_mensagem.text()
    assert obter_estado_primeiro_acesso(banco_identidade) == "NAO_CONFIGURADO"

    dialogo.campo_senha.setText(SENHA_FORTE)
    dialogo.campo_confirmacao.setText(SENHA_FORTE)
    dialogo.criar_administrador()

    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert dialogo.campo_senha.text() == ""
    assert dialogo.campo_confirmacao.text() == ""
    assert obter_estado_primeiro_acesso(banco_identidade) == "CONFIGURADO"
