from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Barrier, Event

import pytest
from PySide6.QtWidgets import QDialog, QLineEdit

import services.autorizacao_pontual_service as autorizacao_pontual_service
from database.conexao import conectar
from database.schema import criar_tabelas
from interface.dialogo_autorizacao_administrativa import (
    DialogoAutorizacaoAdministrativa,
)
from models.autorizacao_pontual import CapacidadeAutorizacao
from services.administrador_inicial_service import criar_administrador_inicial
from services.autenticacao_service import (
    CredenciaisInvalidasError,
    LimitadorTentativasLogin,
    autenticar_usuario,
    encerrar_sessao,
)
from services.autorizacao_pontual_service import (
    OPERACAO_CANCELAR_VENDA,
    AutorizacaoPontualConsumidaError,
    AutorizacaoPontualExpiradaError,
    AutorizacaoPontualInvalidaError,
    GerenciadorAutorizacoesPontuais,
)
from services.cancelamento_venda_service import cancelar_venda
from services.persistencia_venda_service import (
    gerar_identificador_tentativa,
    persistir_venda_confirmada_idempotente,
)
from services.senha_service import gerar_hash_senha
from services.usuario_service import criar_conta_caixa
from tests.test_cancelamento_vendas import criar_confirmacao


SENHA_ADMIN = "frase segura do administrador pontual 2026"
SENHA_CAIXA = "frase segura do caixa pontual 2026"


@pytest.fixture
def ambiente(tmp_path):
    caminho = tmp_path / "autorizacao_pontual.db"
    criar_tabelas(caminho)
    administrador, erros = criar_administrador_inicial(
        "administrador",
        SENHA_ADMIN,
        SENHA_ADMIN,
        caminho,
    )
    assert administrador is not None and erros == []
    sessao_admin = autenticar_usuario("administrador", SENHA_ADMIN, caminho)
    caixa, erros = criar_conta_caixa(
        sessao_admin,
        "caixa01",
        SENHA_CAIXA,
        SENHA_CAIXA,
        caminho,
    )
    assert caixa is not None and erros == []
    sessao_caixa = autenticar_usuario("caixa01", SENHA_CAIXA, caminho)
    gerenciador = GerenciadorAutorizacoesPontuais()
    return caminho, sessao_admin, sessao_caixa, gerenciador


def emitir(ambiente, venda_id, *, identificacao="administrador", senha=SENHA_ADMIN):
    caminho, _, sessao_caixa, gerenciador = ambiente
    return gerenciador.emitir(
        sessao_caixa,
        OPERACAO_CANCELAR_VENDA,
        venda_id,
        identificacao,
        senha,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )


def test_administrador_valido_emite_capacidade_minima_sem_elevar_caixa(
    ambiente,
) -> None:
    _, _, sessao_caixa, _ = ambiente
    capacidade = emitir(ambiente, 41)

    assert isinstance(capacidade, CapacidadeAutorizacao)
    assert set(vars(capacidade)) == {"identificador"}
    assert not hasattr(capacidade, "senha")
    assert sessao_caixa.perfil == "CAIXA"
    assert sessao_caixa.autenticada


@pytest.mark.parametrize(
    "identificacao, senha",
    (("administrador", "senha incorreta"), ("inexistente", SENHA_ADMIN)),
)
def test_credenciais_administrativas_invalidas_sao_rejeitadas(
    ambiente,
    identificacao,
    senha,
) -> None:
    with pytest.raises(CredenciaisInvalidasError):
        emitir(
            ambiente,
            42,
            identificacao=identificacao,
            senha=senha,
        )


def test_caixa_nao_pode_autorizar_operacao_critica(ambiente) -> None:
    with pytest.raises(CredenciaisInvalidasError):
        emitir(
            ambiente,
            43,
            identificacao="caixa01",
            senha=SENHA_CAIXA,
        )


def test_administrador_inativo_nao_autoriza(ambiente) -> None:
    caminho, _, _, _ = ambiente
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            INSERT INTO usuarios (identificacao_acesso, perfil, senha_hash, ativo)
            VALUES ('admin-inativo', 'ADMINISTRADOR', ?, 0)
            """,
            (gerar_hash_senha(SENHA_ADMIN),),
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(CredenciaisInvalidasError):
        emitir(ambiente, 44, identificacao="admin-inativo")


def test_capacidade_fabricada_e_rejeitada(ambiente) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    fabricada = CapacidadeAutorizacao("x" * 43)

    with pytest.raises(AutorizacaoPontualInvalidaError, match="não foi emitida"):
        gerenciador.consumir(
            fabricada,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            45,
            caminho,
        )


@pytest.mark.parametrize(
    "operacao, venda_id",
    ((OPERACAO_CANCELAR_VENDA, 47), ("ALTERAR_PRECO", 46)),
)
def test_vinculo_incorreto_invalida_capacidade(
    ambiente,
    operacao,
    venda_id,
) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    capacidade = emitir(ambiente, 46)

    with pytest.raises(AutorizacaoPontualInvalidaError, match="não corresponde"):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            operacao,
            venda_id,
            caminho,
        )
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            46,
            caminho,
        )


def test_expiracao_consumo_unico_e_rejeicao_posterior(ambiente) -> None:
    caminho, _, sessao_caixa, _ = ambiente
    instante = [100.0]
    gerenciador = GerenciadorAutorizacoesPontuais(
        validade_segundos=5,
        relogio=lambda: instante[0],
    )
    ambiente_expiracao = (caminho, None, sessao_caixa, gerenciador)
    capacidade = emitir(ambiente_expiracao, 48)
    instante[0] = 106.0

    with pytest.raises(AutorizacaoPontualExpiradaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            48,
            caminho,
        )
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            48,
            caminho,
        )


def test_consumo_concorrente_tem_um_unico_sucesso(ambiente) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    capacidade = emitir(ambiente, 49)
    barreira = Barrier(2)

    def consumir():
        barreira.wait()
        try:
            return gerenciador.consumir(
                capacidade,
                sessao_caixa,
                OPERACAO_CANCELAR_VENDA,
                49,
                caminho,
            )
        except AutorizacaoPontualConsumidaError:
            return "CONSUMIDA"

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = tuple(executor.map(lambda _: consumir(), range(2)))

    assert sorted(resultados) == ["CONSUMIDA", "administrador"]


def test_invalidacao_revoga_capacidade_solicitada_pelo_administrador(
    ambiente,
) -> None:
    caminho, sessao_admin, _, gerenciador = ambiente
    capacidade = gerenciador.emitir(
        sessao_admin,
        OPERACAO_CANCELAR_VENDA,
        501,
        "administrador",
        SENHA_ADMIN,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )

    gerenciador.invalidar_usuario(sessao_admin.usuario_id)

    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            sessao_admin,
            OPERACAO_CANCELAR_VENDA,
            501,
            caminho,
        )


def test_invalidacao_revoga_capacidade_concedida_a_outro_usuario(
    ambiente,
) -> None:
    caminho, sessao_admin, sessao_caixa, gerenciador = ambiente
    capacidade = emitir(ambiente, 502)

    gerenciador.invalidar_usuario(sessao_admin.usuario_id)

    assert sessao_caixa.perfil == "CAIXA"
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            502,
            caminho,
        )


def test_invalidacao_nao_afeta_capacidade_de_outro_administrador(
    ambiente,
) -> None:
    caminho, sessao_admin, sessao_caixa, gerenciador = ambiente
    conexao = conectar(caminho)
    try:
        cursor = conexao.execute(
            """
            INSERT INTO usuarios (identificacao_acesso, perfil, senha_hash, ativo)
            VALUES ('administrador-2', 'ADMINISTRADOR', ?, 1)
            """,
            (gerar_hash_senha(SENHA_ADMIN),),
        )
        administrador_2_id = cursor.lastrowid
        conexao.commit()
    finally:
        conexao.close()
    assert administrador_2_id is not None
    capacidade_admin_1 = emitir(ambiente, 503)
    capacidade_admin_2 = gerenciador.emitir(
        sessao_caixa,
        OPERACAO_CANCELAR_VENDA,
        504,
        "administrador-2",
        SENHA_ADMIN,
        caminho,
        limitador=LimitadorTentativasLogin(),
    )

    gerenciador.invalidar_usuario(sessao_admin.usuario_id)

    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade_admin_1,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            503,
            caminho,
        )
    assert gerenciador.consumir(
        capacidade_admin_2,
        sessao_caixa,
        OPERACAO_CANCELAR_VENDA,
        504,
        caminho,
    ) == "administrador-2"


def test_revogacao_concorrente_com_emissao_remove_capacidade_publicada(
    ambiente,
    monkeypatch,
) -> None:
    _, sessao_admin, _, gerenciador = ambiente
    validacao_iniciada = Event()
    liberar_validacao = Event()
    revogacao_iniciada = Event()
    validar_original = autorizacao_pontual_service.validar_credenciais_usuario

    def validar_com_pausa(*args, **kwargs):
        validacao_iniciada.set()
        assert liberar_validacao.wait(timeout=5)
        return validar_original(*args, **kwargs)

    monkeypatch.setattr(
        autorizacao_pontual_service,
        "validar_credenciais_usuario",
        validar_com_pausa,
    )

    def revogar():
        revogacao_iniciada.set()
        gerenciador.invalidar_usuario(sessao_admin.usuario_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        emissao = executor.submit(emitir, ambiente, 505)
        assert validacao_iniciada.wait(timeout=5)
        revogacao = executor.submit(revogar)
        assert revogacao_iniciada.wait(timeout=5)
        liberar_validacao.set()
        capacidade = emissao.result(timeout=5)
        revogacao.result(timeout=5)

    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            ambiente[2],
            OPERACAO_CANCELAR_VENDA,
            505,
            ambiente[0],
        )


def test_logout_invalida_capacidade_sem_elevar_sessao(ambiente) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    capacidade = emitir(ambiente, 50)
    encerrar_sessao(sessao_caixa)

    with pytest.raises(AutorizacaoPontualInvalidaError, match="sessão solicitante"):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            50,
            caminho,
        )
    assert sessao_caixa.perfil == "CAIXA"


def test_desativacao_da_conta_solicitante_consume_e_rejeita(ambiente) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    capacidade = emitir(ambiente, 51)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            "UPDATE usuarios SET ativo = 0 WHERE id = ?",
            (sessao_caixa.usuario_id,),
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(AutorizacaoPontualInvalidaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            51,
            caminho,
        )
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            51,
            caminho,
        )


def test_t43_consume_autorizacao_e_preserva_identidade(ambiente) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        gerar_identificador_tentativa(),
        caminho,
    )
    capacidade = emitir(ambiente, venda_id)

    resultado = cancelar_venda(
        venda_id,
        "operação autorizada",
        capacidade,
        sessao_caixa,
        caminho,
        gerenciador_autorizacoes=gerenciador,
    )

    assert resultado.identidade_autorizador == "administrador"
    assert sessao_caixa.perfil == "CAIXA"
    with pytest.raises(AutorizacaoPontualConsumidaError):
        gerenciador.consumir(
            capacidade,
            sessao_caixa,
            OPERACAO_CANCELAR_VENDA,
            venda_id,
            caminho,
        )


def test_falha_comercial_apos_consumo_nao_reabilita_capacidade(ambiente) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    venda_id = persistir_venda_confirmada_idempotente(
        criar_confirmacao(),
        gerar_identificador_tentativa(),
        caminho,
    )
    capacidade = emitir(ambiente, venda_id)
    conexao = conectar(caminho)
    try:
        conexao.execute(
            """
            CREATE TRIGGER falhar_cancelamento_t47
            BEFORE UPDATE OF status ON vendas
            BEGIN
                SELECT RAISE(ABORT, 'falha comercial t47');
            END
            """
        )
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha comercial t47"):
        cancelar_venda(
            venda_id,
            "falha depois do consumo",
            capacidade,
            sessao_caixa,
            caminho,
            gerenciador_autorizacoes=gerenciador,
        )
    with pytest.raises(AutorizacaoPontualConsumidaError):
        cancelar_venda(
            venda_id,
            "nova tentativa",
            capacidade,
            sessao_caixa,
            caminho,
            gerenciador_autorizacoes=gerenciador,
        )


def test_dialogo_emite_capacidade_sem_trocar_sessao(
    qtbot,
    ambiente,
) -> None:
    caminho, _, sessao_caixa, gerenciador = ambiente
    dialogo = DialogoAutorizacaoAdministrativa(
        sessao_caixa,
        OPERACAO_CANCELAR_VENDA,
        52,
        "Autorizar cancelamento da venda #000052",
        caminho,
        gerenciador=gerenciador,
        limitador=LimitadorTentativasLogin(),
    )
    qtbot.addWidget(dialogo)
    assert dialogo.campo_senha.echoMode() == QLineEdit.EchoMode.Password
    dialogo.campo_identificacao.setText("administrador")
    dialogo.campo_senha.setText(SENHA_ADMIN)
    dialogo.autorizar()

    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert isinstance(dialogo.capacidade, CapacidadeAutorizacao)
    assert dialogo.campo_senha.text() == ""
    assert sessao_caixa.perfil == "CAIXA"
