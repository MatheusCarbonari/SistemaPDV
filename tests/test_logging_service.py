import json
import logging
from types import SimpleNamespace

import pytest

import services.logging_service as logging_service


@pytest.fixture(autouse=True)
def limpar_logging():
    logging_service.encerrar_logging()
    yield
    logging_service.encerrar_logging()


def _ler_documentos(caminho):
    return [
        json.loads(linha)
        for linha in caminho.read_text(encoding="utf-8").splitlines()
    ]


def test_catalogo_define_nivel_componente_mensagem_e_campos(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path)
    logging_service.registrar_evento(
        "preparacao_banco_concluida",
        banco_novo=True,
        versao_inicial=9,
        versao_final=10,
        backup_criado=True,
        resultado="sucesso",
    )

    documento = _ler_documentos(caminho)[0]
    assert documento["level"] == "INFO"
    assert documento["component"] == "banco"
    assert documento["event"] == "preparacao_banco_concluida"
    assert documento["message"] == "A preparação técnica do banco foi concluída."
    assert documento["banco_novo"] is True
    assert documento["versao_inicial"] == 9
    assert documento["versao_final"] == 10
    assert documento["backup_criado"] is True
    assert documento["resultado"] == "sucesso"


def test_catalogo_preserva_eventos_e_componentes_instrumentados() -> None:
    esperados = {
        "inicializacao_iniciada": "aplicacao",
        "preparacao_banco_falhou": "banco",
        "identidade_inconsistente": "identidade",
        "persistencia_venda_falhou": "persistencia_venda",
        "commit_venda_exigiu_verificacao": "persistencia_venda",
        "commit_cancelamento_exigiu_verificacao": "cancelamento_venda",
        "resultado_cancelamento_incerto": "cancelamento_venda",
        "erro_nao_tratado": "runtime",
    }

    assert {
        evento: logging_service._CATALOGO_EVENTOS[evento][0]
        for evento in esperados
    } == esperados


def test_mensagem_arbitraria_em_evento_controlado_e_ignorada(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path)
    logging_service.registrar_evento(
        "inicializacao_iniciada",
        mensagem="senha=SEGREDO mensagem escolhida pelo chamador",
        token="TOKEN_SECRETO",
    )

    conteudo = caminho.read_text(encoding="utf-8")
    assert "SEGREDO" not in conteudo
    assert "TOKEN_SECRETO" not in conteudo
    documento = json.loads(conteudo)
    assert documento["event"] == "inicializacao_iniciada"
    assert documento["message"] == "A inicialização do Sistema-PDV foi iniciada."


def test_evento_desconhecido_e_logging_direto_sao_neutralizados(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path)
    logging_service.registrar_evento(
        "evento_senha=SEGREDO",
        identificador_operacao="token:TOKEN_SECRETO",
        resultado="sucesso",
    )
    logging.getLogger("sistema_pdv.modulo_livre").error(
        "SQL SELECT segredo FROM credenciais WHERE senha='SEGREDO'"
    )
    logging.getLogger("sistema_pdv.outro_modulo").error(
        "capacidade=CAPACIDADE_DIRETA"
    )

    conteudo = caminho.read_text(encoding="utf-8")
    assert "SEGREDO" not in conteudo
    assert "TOKEN_SECRETO" not in conteudo
    assert "CAPACIDADE_DIRETA" not in conteudo
    assert "SELECT" not in conteudo
    documentos = _ler_documentos(caminho)
    assert documentos[0]["event"] == "registro_nao_catalogado"
    assert documentos[0]["component"] == "logging"
    assert documentos[1]["event"] == "registro_nao_catalogado"
    assert documentos[1]["component"] == "logging"
    assert documentos[2]["event"] == "registro_nao_catalogado"
    assert documentos[2]["component"] == "logging"


def test_chamada_direta_nao_falsifica_evento_catalogado(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path)

    logging.getLogger("sistema_pdv.banco").critical(
        "senha=SEGREDO mensagem forjada",
        extra={
            "origem_registro_api": object(),
            "evento_catalogado": "preparacao_banco_concluida",
            "identificador_operacao": "venda:123",
            "campos_seguros": {
                "banco_novo": True,
                "resultado": "sucesso",
            },
        },
    )

    conteudo = caminho.read_text(encoding="utf-8")
    assert "SEGREDO" not in conteudo
    documento = json.loads(conteudo)
    assert documento == {
        "timestamp": documento["timestamp"],
        "level": "WARNING",
        "component": "logging",
        "event": "registro_nao_catalogado",
        "message": "Uma tentativa de registro fora do catálogo foi neutralizada.",
    }


def test_valores_tecnicos_invalidos_sao_omitidos(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path)
    logging_service.registrar_evento(
        "commit_cancelamento_exigiu_verificacao",
        identificador_operacao="token:TOKEN_SECRETO",
        venda_id=True,
        erro_tipo="RuntimeError senha=SEGREDO",
        resultado="resultado_livre",
    )

    documento = _ler_documentos(caminho)[0]
    assert "operation_id" not in documento
    assert "venda_id" not in documento
    assert "erro_tipo" not in documento
    assert "resultado" not in documento


def test_diretorio_configuravel_por_argumento_e_variavel(tmp_path, monkeypatch) -> None:
    explicito = tmp_path / "explicito"
    assert logging_service.configurar_logging(explicito) == (
        explicito / logging_service.NOME_ARQUIVO_LOG
    )

    logging_service.encerrar_logging()
    configurado = tmp_path / "variavel"
    monkeypatch.setenv(logging_service.VARIAVEL_DIRETORIO_LOG, str(configurado))
    assert logging_service.configurar_logging() == (
        configurado / logging_service.NOME_ARQUIVO_LOG
    )


@pytest.mark.parametrize("valor", [0, -1, True, False, 1.5, "5"])
def test_backup_count_exige_inteiro_positivo(tmp_path, valor) -> None:
    with pytest.raises(ValueError, match="inteira e positiva"):
        logging_service.configurar_logging(tmp_path, backup_count=valor)


@pytest.mark.parametrize("valor", [0, -1, True, False, 1.5, "1024"])
def test_max_bytes_exige_inteiro_positivo(tmp_path, valor) -> None:
    with pytest.raises(ValueError, match="inteiro positivo"):
        logging_service.configurar_logging(tmp_path, max_bytes=valor)


def test_configuracao_padrao_preserva_limites_de_rotacao(tmp_path) -> None:
    logging_service.configurar_logging(tmp_path)
    handler = next(
        handler
        for handler in logging_service._LOGGER_RAIZ.handlers
        if getattr(handler, "_sistema_pdv_handler", False)
    )
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 5


def test_rotacao_limita_quantidade_de_arquivos(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path, max_bytes=300, backup_count=2)
    for _ in range(30):
        logging_service.registrar_evento("inicializacao_iniciada")

    arquivos = sorted(tmp_path.glob(f"{caminho.name}*"))
    assert caminho in arquivos
    assert any(arquivo.name.endswith(".1") for arquivo in arquivos)
    assert len(arquivos) <= 3


def test_configuracao_repetida_nao_duplica_handlers_nem_eventos(tmp_path) -> None:
    caminho = logging_service.configurar_logging(tmp_path)
    logging_service.configurar_logging(tmp_path)
    logging_service.registrar_evento("inicializacao_iniciada")

    handlers = [
        handler
        for handler in logging_service._LOGGER_RAIZ.handlers
        if getattr(handler, "_sistema_pdv_handler", False)
    ]
    assert len(handlers) == 1
    assert len(_ler_documentos(caminho)) == 1


def test_falha_ao_criar_log_nao_interrompe_operacao(tmp_path) -> None:
    caminho_invalido = tmp_path / "arquivo"
    caminho_invalido.write_text("não é diretório", encoding="utf-8")

    resultado = logging_service.configurar_logging(caminho_invalido)
    valor_comercial = 10 + 20
    logging_service.registrar_evento("inicializacao_iniciada")

    assert resultado is None
    assert valor_comercial == 30


def test_falha_de_escrita_do_handler_e_suprimida(tmp_path, monkeypatch) -> None:
    logging_service.configurar_logging(tmp_path)
    handler = next(
        handler
        for handler in logging_service._LOGGER_RAIZ.handlers
        if getattr(handler, "_sistema_pdv_handler", False)
    )

    def falhar_abertura():
        raise OSError("falha simulada com senha=SEGREDO")

    monkeypatch.setattr(handler, "_open", falhar_abertura)
    logging_service.registrar_evento("inicializacao_iniciada")


def test_erro_nao_tratado_registra_somente_tipo_seguro(
    tmp_path, monkeypatch
) -> None:
    caminho = logging_service.configurar_logging(tmp_path)
    erro = RuntimeError("senha=NAO_DEVE_APARECER")

    monkeypatch.setattr(logging_service, "_HOOK_ANTERIOR", lambda *_: None)
    logging_service._tratar_erro_nao_tratado(RuntimeError, erro, None)

    conteudo = caminho.read_text(encoding="utf-8")
    assert "NAO_DEVE_APARECER" not in conteudo
    documento = json.loads(conteudo)
    assert documento["event"] == "erro_nao_tratado"
    assert documento["erro_tipo"] == "RuntimeError"


def test_servicos_instrumentados_nao_registram_mensagem_das_excecoes(
    tmp_path, monkeypatch
) -> None:
    import services.cancelamento_venda_service as cancelamento_service
    import services.persistencia_venda_service as persistencia_service

    caminho = logging_service.configurar_logging(tmp_path)

    def falhar_conexao(*_):
        raise RuntimeError("senha=SEGREDO token=TOKEN_SECRETO SQL SELECT credenciais")

    monkeypatch.setattr(persistencia_service, "conectar", falhar_conexao)
    with pytest.raises(persistencia_service.CommitVendaIncertoError):
        persistencia_service._verificar_apos_falha(
            SimpleNamespace(),
            "00000000-0000-0000-0000-000000000001",
            tmp_path / "venda.sqlite3",
            RuntimeError("hash=HASH_SECRETO"),
        )

    monkeypatch.setattr(cancelamento_service, "conectar", falhar_conexao)
    with pytest.raises(cancelamento_service.CancelamentoVendaIncertoError):
        cancelamento_service._reconciliar_apos_falha_commit(
            SimpleNamespace(venda_id=1),
            "2026-11-11 12:00:00",
            tmp_path / "cancelamento.sqlite3",
            RuntimeError("capacidade=CAPACIDADE_SECRETA"),
        )

    conteudo = caminho.read_text(encoding="utf-8")
    for segredo in (
        "SEGREDO",
        "TOKEN_SECRETO",
        "HASH_SECRETO",
        "CAPACIDADE_SECRETA",
        "SELECT",
    ):
        assert segredo not in conteudo
    assert {item["event"] for item in _ler_documentos(caminho)} == {
        "resultado_fechamento_incerto",
        "resultado_cancelamento_incerto",
    }
