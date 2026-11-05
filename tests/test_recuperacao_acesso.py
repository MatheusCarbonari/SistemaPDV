from concurrent.futures import ThreadPoolExecutor
import re
import sqlite3

import pytest
from PySide6.QtWidgets import QDialog

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from interface.dialogo_codigos_recuperacao import DialogoCodigosRecuperacao
from interface.dialogo_login import DialogoLogin
from models.sessao_usuario import SessaoUsuario
from services.administrador_inicial_service import (
    criar_administrador_inicial,
    obter_estado_primeiro_acesso,
)
from services.autenticacao_service import (
    CredenciaisInvalidasError,
    GerenciadorSessoes,
    LimitadorTentativasLogin,
    SessaoInvalidaError,
    TentativasLoginExcedidasError,
    autenticar_usuario,
)
from services.autorizacao_pontual_service import (
    OPERACAO_CANCELAR_VENDA,
    AutorizacaoPontualConsumidaError,
    GerenciadorAutorizacoesPontuais,
)
from services.recuperacao_acesso_service import (
    QUANTIDADE_CODIGOS,
    NovaSenhaInvalidaError,
    RecuperacaoAcessoInvalidaError,
    emitir_ou_rotacionar_codigos,
    recuperar_acesso_administrativo,
)


SENHA_ANTIGA = "frase administrativa original 2026"
SENHA_NOVA = "frase administrativa recuperada 2026"
PADRAO_CODIGO = re.compile(r"^[2-9A-HJ-NP-Z]{8}(?:-[2-9A-HJ-NP-Z]{8}){3}$")


@pytest.fixture
def ambiente(tmp_path):
    caminho = tmp_path / "recuperacao_acesso.db"
    criar_tabelas(caminho)
    usuario, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ANTIGA,
        SENHA_ANTIGA,
        caminho,
    )
    assert usuario is not None and erros == []
    gerenciador_sessoes = GerenciadorSessoes()
    sessao = autenticar_usuario(
        "administrador",
        SENHA_ANTIGA,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    gerenciador_autorizacoes = GerenciadorAutorizacoesPontuais(
        gerenciador_sessoes=gerenciador_sessoes,
    )
    return (
        caminho,
        usuario,
        sessao,
        gerenciador_sessoes,
        gerenciador_autorizacoes,
    )


def emitir(ambiente):
    caminho, _, sessao, gerenciador_sessoes, _ = ambiente
    return emitir_ou_rotacionar_codigos(
        sessao,
        SENHA_ANTIGA,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
        limitador=LimitadorTentativasLogin(),
    )


def recuperar(ambiente, codigo, nova_senha=SENHA_NOVA, *, limitador=None):
    caminho, _, _, gerenciador_sessoes, gerenciador_autorizacoes = ambiente
    recuperar_acesso_administrativo(
        "administrador",
        codigo,
        nova_senha,
        nova_senha,
        caminho,
        limitador=limitador or LimitadorTentativasLogin(),
        gerenciador_sessoes=gerenciador_sessoes,
        gerenciador_autorizacoes=gerenciador_autorizacoes,
    )


def test_geracao_produz_codigos_unicos_com_160_bits(ambiente) -> None:
    primeiro = emitir(ambiente)

    assert len(primeiro.codigos) == QUANTIDADE_CODIGOS
    assert len(set(primeiro.codigos)) == QUANTIDADE_CODIGOS
    assert all(PADRAO_CODIGO.fullmatch(codigo) for codigo in primeiro.codigos)


def test_banco_armazena_somente_verificadores(ambiente) -> None:
    caminho, _, _, _, _ = ambiente
    conjunto = emitir(ambiente)
    conexao = conectar(caminho)
    try:
        linhas = conexao.execute(
            "SELECT verificador, conjunto_id FROM codigos_recuperacao"
        ).fetchall()
    finally:
        conexao.close()

    assert len(linhas) == QUANTIDADE_CODIGOS
    assert all(len(linha["verificador"]) == 64 for linha in linhas)
    assert len({linha["conjunto_id"] for linha in linhas}) == 1
    serializado = repr(tuple(tuple(linha) for linha in linhas))
    assert all(codigo not in serializado for codigo in conjunto.codigos)
    assert all(codigo not in repr(conjunto) for codigo in conjunto.codigos)


def test_dialogo_apresenta_codigos_somente_na_emissao(
    ambiente,
    qtbot,
) -> None:
    caminho, _, sessao, gerenciador_sessoes, _ = ambiente
    dialogo = DialogoCodigosRecuperacao(
        sessao,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
        limitador=LimitadorTentativasLogin(),
    )
    qtbot.addWidget(dialogo)
    dialogo.show()
    dialogo.campo_senha.setText(SENHA_ANTIGA)

    dialogo.emitir()

    apresentados = tuple(dialogo.campo_codigos.toPlainText().splitlines())
    assert len(apresentados) == QUANTIDADE_CODIGOS
    assert dialogo.campo_codigos.isVisible()
    assert not dialogo.botao_emitir.isEnabled()
    dialogo.reject()
    assert dialogo.campo_codigos.toPlainText() == ""

    novo_dialogo = DialogoCodigosRecuperacao(
        sessao,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
        limitador=LimitadorTentativasLogin(),
    )
    qtbot.addWidget(novo_dialogo)
    assert novo_dialogo.campo_codigos.toPlainText() == ""
    assert not novo_dialogo.campo_codigos.isVisible()


def test_recuperacao_valida_troca_senha_sem_login_automatico(ambiente) -> None:
    caminho, _, sessao, gerenciador_sessoes, _ = ambiente
    codigo = emitir(ambiente).codigos[0]

    recuperar(ambiente, codigo)

    assert not sessao.autenticada
    with pytest.raises(CredenciaisInvalidasError):
        autenticar_usuario(
            "administrador",
            SENHA_ANTIGA,
            caminho,
            limitador=LimitadorTentativasLogin(),
            gerenciador_sessoes=gerenciador_sessoes,
        )
    nova_sessao = autenticar_usuario(
        "administrador",
        SENHA_NOVA,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    assert nova_sessao.autenticada


@pytest.mark.parametrize("codigo", ["", "CODIGO-INEXISTENTE", "x" * 32])
def test_codigo_incorreto_usa_resposta_generica(ambiente, codigo) -> None:
    emitir(ambiente)

    with pytest.raises(
        RecuperacaoAcessoInvalidaError,
        match="Não foi possível validar os dados",
    ):
        recuperar(ambiente, codigo)


def test_codigo_consumido_nao_pode_ser_reutilizado(ambiente) -> None:
    codigo = emitir(ambiente).codigos[0]
    recuperar(ambiente, codigo)

    with pytest.raises(RecuperacaoAcessoInvalidaError):
        recuperar(ambiente, codigo, "outra frase administrativa 2026")


def test_consumo_concorrente_tem_um_unico_sucesso(ambiente) -> None:
    codigo = emitir(ambiente).codigos[0]

    def tentar(indice):
        try:
            recuperar(
                ambiente,
                codigo,
                f"frase recuperada concorrente numero {indice}",
            )
            return "SUCESSO"
        except RecuperacaoAcessoInvalidaError:
            return "REJEITADO"

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = tuple(executor.map(tentar, (1, 2)))

    assert sorted(resultados) == ["REJEITADO", "SUCESSO"]


def test_falha_na_atualizacao_reverte_consumo_e_senha(ambiente) -> None:
    caminho, _, _, _, _ = ambiente
    codigo = emitir(ambiente).codigos[0]
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_recuperacao_senha
            BEFORE UPDATE OF senha_hash ON usuarios
            BEGIN
                SELECT RAISE(ABORT, 'falha senha t48');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha senha t48"):
        recuperar(ambiente, codigo)

    conexao = conectar(caminho)
    try:
        consumidos = conexao.execute(
            "SELECT COUNT(*) FROM codigos_recuperacao WHERE consumido_em IS NOT NULL"
        ).fetchone()[0]
    finally:
        conexao.close()
    assert consumidos == 0
    autenticar_usuario(
        "administrador",
        SENHA_ANTIGA,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )


def test_rotacao_revoga_conjunto_anterior(ambiente) -> None:
    caminho, _, _, _, _ = ambiente
    antigo = emitir(ambiente)
    novo = emitir(ambiente)

    assert set(antigo.codigos).isdisjoint(novo.codigos)
    with pytest.raises(RecuperacaoAcessoInvalidaError):
        recuperar(ambiente, antigo.codigos[0])
    recuperar(ambiente, novo.codigos[0])

    conexao = conectar(caminho)
    try:
        revogados = conexao.execute(
            "SELECT COUNT(*) FROM codigos_recuperacao WHERE revogado_em IS NOT NULL"
        ).fetchone()[0]
    finally:
        conexao.close()
    assert revogados == QUANTIDADE_CODIGOS


def test_emissao_exige_admin_autenticado_e_senha_atual(ambiente) -> None:
    caminho, _, sessao, gerenciador_sessoes, _ = ambiente
    with pytest.raises(CredenciaisInvalidasError):
        emitir_ou_rotacionar_codigos(
            sessao,
            "senha atual incorreta",
            caminho,
            gerenciador_sessoes=gerenciador_sessoes,
            limitador=LimitadorTentativasLogin(),
        )

    fabricada = SessaoUsuario(1, "administrador", "ADMINISTRADOR", "x" * 43)
    with pytest.raises(SessaoInvalidaError):
        emitir_ou_rotacionar_codigos(
            fabricada,
            SENHA_ANTIGA,
            caminho,
            gerenciador_sessoes=gerenciador_sessoes,
        )


@pytest.mark.parametrize(
    "senha, confirmacao",
    (("curta", "curta"), (SENHA_NOVA, "confirmação diferente")),
)
def test_nova_senha_respeita_politica(ambiente, senha, confirmacao) -> None:
    caminho, _, _, gerenciador_sessoes, gerenciador_autorizacoes = ambiente
    codigo = emitir(ambiente).codigos[0]

    with pytest.raises(NovaSenhaInvalidaError):
        recuperar_acesso_administrativo(
            "administrador",
            codigo,
            senha,
            confirmacao,
            caminho,
            limitador=LimitadorTentativasLogin(),
            gerenciador_sessoes=gerenciador_sessoes,
            gerenciador_autorizacoes=gerenciador_autorizacoes,
        )


def test_recuperacao_invalida_sessoes_e_autorizacoes_da_identidade(
    ambiente,
) -> None:
    caminho, _, sessao, gerenciador_sessoes, gerenciador_autorizacoes = ambiente
    segunda_sessao = autenticar_usuario(
        "administrador",
        SENHA_ANTIGA,
        caminho,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    capacidade = gerenciador_autorizacoes.emitir(
        sessao,
        OPERACAO_CANCELAR_VENDA,
        123,
        "administrador",
        SENHA_ANTIGA,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )
    codigo = emitir(ambiente).codigos[0]

    recuperar(ambiente, codigo)

    assert not sessao.autenticada
    assert not segunda_sessao.autenticada
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador_autorizacoes.consumir(
            capacidade,
            sessao,
            OPERACAO_CANCELAR_VENDA,
            123,
            caminho,
        )


def test_tentativas_repetidas_aplicam_espera_temporaria(ambiente) -> None:
    emitir(ambiente)
    instante = [100.0]
    limitador = LimitadorTentativasLogin(
        maximo_falhas=5,
        janela_segundos=300,
        espera_segundos=60,
        relogio=lambda: instante[0],
    )
    for _ in range(5):
        with pytest.raises(RecuperacaoAcessoInvalidaError):
            recuperar(ambiente, "codigo incorreto", limitador=limitador)

    with pytest.raises(TentativasLoginExcedidasError):
        recuperar(ambiente, "codigo incorreto", limitador=limitador)


def test_dialogo_login_recupera_sem_autenticar_automaticamente(
    tmp_path,
    qtbot,
) -> None:
    caminho = tmp_path / "recuperacao_login.db"
    criar_tabelas(caminho)
    usuario, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ANTIGA,
        SENHA_ANTIGA,
        caminho,
    )
    assert usuario is not None and erros == []
    sessao = autenticar_usuario("administrador", SENHA_ANTIGA, caminho)
    codigo = emitir_ou_rotacionar_codigos(
        sessao,
        SENHA_ANTIGA,
        caminho,
        limitador=LimitadorTentativasLogin(),
    ).codigos[0]
    dialogo = DialogoLogin(
        caminho,
        limitador=LimitadorTentativasLogin(),
        limitador_recuperacao=LimitadorTentativasLogin(),
    )
    qtbot.addWidget(dialogo)
    dialogo.abrir_recuperacao()
    recuperacao = dialogo.dialogo_recuperacao
    recuperacao.campo_identificacao.setText("administrador")
    recuperacao.campo_codigo.setText(codigo)
    recuperacao.campo_nova_senha.setText(SENHA_NOVA)
    recuperacao.campo_confirmacao.setText(SENHA_NOVA)

    recuperacao.recuperar()

    assert dialogo.sessao is None
    assert dialogo.result() != QDialog.DialogCode.Accepted
    assert "Entre novamente" in dialogo.rotulo_mensagem.text()
    dialogo.campo_identificacao.setText("administrador")
    dialogo.campo_senha.setText(SENHA_NOVA)
    dialogo.entrar()
    assert dialogo.result() == QDialog.DialogCode.Accepted


def test_recuperacao_preserva_estado_de_primeiro_acesso(ambiente) -> None:
    codigo = emitir(ambiente).codigos[0]
    recuperar(ambiente, codigo)

    assert obter_estado_primeiro_acesso(ambiente[0]) == "CONFIGURADO"


def test_migracao_v8_v9_preserva_usuario_e_cria_indice(tmp_path) -> None:
    caminho = tmp_path / "migracao_v8_v9.db"
    criar_tabelas(caminho)
    usuario, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ANTIGA,
        SENHA_ANTIGA,
        caminho,
    )
    assert usuario is not None and erros == []
    conexao = conectar(caminho)
    try:
        conexao.execute("DROP TABLE codigos_recuperacao")
        conexao.execute("PRAGMA user_version = 8")
        conexao.commit()
    finally:
        conexao.close()

    criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 9
        assert conexao.execute(
            "SELECT identificacao_acesso FROM usuarios WHERE id = ?",
            (usuario.id,),
        ).fetchone()[0] == "administrador"
        indice = conexao.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'index'
              AND name = 'ix_codigos_recuperacao_usuario_conjunto'
            """
        ).fetchone()
        assert indice is not None
    finally:
        conexao.close()


def test_falha_na_migracao_v9_reverte_tabela_e_versao(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_migracao_v9.db"
    criar_tabelas(caminho)
    conexao = conectar(caminho)
    try:
        conexao.execute("DROP TABLE codigos_recuperacao")
        conexao.execute("PRAGMA user_version = 8")
        conexao.commit()
    finally:
        conexao.close()
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_INDICE_CODIGOS_RECUPERACAO",
        "CREATE INDEX indice_invalido ON tabela_inexistente (id)",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 8
        tabela = conexao.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'codigos_recuperacao'
            """
        ).fetchone()
        assert tabela is None
    finally:
        conexao.close()
