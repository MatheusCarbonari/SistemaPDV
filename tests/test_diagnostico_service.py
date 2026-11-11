from datetime import UTC, datetime
import json
from types import SimpleNamespace
import zipfile

import pytest

import interface.pagina_administracao as pagina_administracao_module
import services.diagnostico_service as diagnostico_service
import services.logging_service as logging_service
from services.autenticacao_service import PermissaoNegadaError, autenticar_usuario
from services.diagnostico_service import exportar_diagnostico
from services.usuario_service import criar_conta_caixa
from tests.helpers_identidade import (
    SENHA_ADMIN_TESTE,
    criar_janela_autenticada,
    criar_sessao_admin_teste,
)


SENHA_CAIXA = "frase segura exclusiva caixa diagnostico 2026"


@pytest.fixture(autouse=True)
def limpar_logging():
    logging_service.encerrar_logging()
    yield
    logging_service.encerrar_logging()


@pytest.fixture
def ambiente(tmp_path):
    banco = tmp_path / "diagnostico.db"
    sessao = criar_sessao_admin_teste(banco)
    diretorio_logs = tmp_path / "logs"
    caminho_log = logging_service.configurar_logging(diretorio_logs)
    return banco, sessao, diretorio_logs, caminho_log


def _ler_pacote(caminho):
    with zipfile.ZipFile(caminho) as pacote:
        nomes = pacote.namelist()
        manifesto = json.loads(pacote.read("manifesto.json"))
        eventos = [
            json.loads(linha)
            for linha in pacote.read("eventos.jsonl").decode("utf-8").splitlines()
        ]
    return nomes, manifesto, eventos


def _evento_valido(evento="inicializacao_iniciada"):
    contrato = logging_service.obter_contrato_evento_tecnico(evento)
    return {
        "timestamp": "2026-11-11T12:00:00.000+00:00",
        "level": contrato.nivel,
        "component": contrato.componente,
        "event": evento,
        "message": contrato.mensagem,
    }


def test_exporta_zip_estruturado_com_eventos_reconstruidos(ambiente, tmp_path) -> None:
    banco, sessao, _, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    logging_service.registrar_evento("inicializacao_iniciada")
    logging_service.registrar_evento(
        "resultado_cancelamento_incerto",
        identificador_operacao="venda:42",
        venda_id=42,
        erro_tipo="RuntimeError",
        resultado="incerto",
    )

    caminho = exportar_diagnostico(destino, sessao, banco)

    nomes, manifesto, eventos = _ler_pacote(caminho)
    assert nomes == ["manifesto.json", "eventos.jsonl"]
    assert caminho.name.startswith("sistema-pdv-diagnostico-")
    assert caminho.suffix == ".zip"
    assert manifesto["versao_contrato"] == 1
    assert manifesto["aplicativo"]["versao_aplicativo"] == "0.1.0"
    assert manifesto["aplicativo"]["build_id"] == "desconhecido"
    assert manifesto["logging"]["status"] == "DISPONIVEL"
    assert {evento["event"] for evento in eventos} == {
        "inicializacao_iniciada",
        "resultado_cancelamento_incerto",
    }
    assert all("operation_id" not in evento for evento in eventos)
    assert all("venda_id" not in evento for evento in eventos)


def test_exportacao_sem_logs_cria_pacote_util(ambiente, tmp_path) -> None:
    banco, sessao, _, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, eventos = _ler_pacote(caminho)
    assert eventos == []
    assert manifesto["eventos"]["arquivos_lidos"] == 0
    assert manifesto["eventos"]["registros_exportados"] == 0
    assert manifesto["logging"]["status"] == "DISPONIVEL"


def test_logs_corrompidos_e_campos_maliciosos_nao_vazam(
    ambiente,
    tmp_path,
) -> None:
    banco, sessao, _, caminho_log = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    valido = _evento_valido()
    valido.update(
        {
            "senha": "SEGREDO",
            "operation_id": "token:TOKEN_SECRETO",
            "venda_id": 999,
            "objeto_comercial": {"total": 12345},
        }
    )
    forjado = _evento_valido()
    forjado["message"] = "senha=SEGREDO mensagem forjada"
    caminho_log.write_text(
        "\n".join(
            [
                json.dumps(valido),
                json.dumps(forjado),
                "{json corrompido",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, eventos = _ler_pacote(caminho)
    with zipfile.ZipFile(caminho) as pacote:
        conteudo = pacote.read("manifesto.json") + pacote.read("eventos.jsonl")
    assert len(eventos) == 1
    assert eventos[0] == _evento_valido()
    assert manifesto["eventos"]["registros_descartados"] == 2
    for segredo in (b"SEGREDO", b"TOKEN_SECRETO", b"objeto_comercial"):
        assert segredo not in conteudo


@pytest.mark.parametrize("evento_invalido", [[], {}, 42, None])
def test_tipo_inesperado_no_event_e_descartado_sem_perder_evento_valido(
    ambiente,
    tmp_path,
    evento_invalido,
) -> None:
    banco, sessao, _, caminho_log = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    invalido = _evento_valido()
    invalido["event"] = evento_invalido
    caminho_log.write_text(
        f"{json.dumps(invalido)}\n{json.dumps(_evento_valido())}\n",
        encoding="utf-8",
    )

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, eventos = _ler_pacote(caminho)
    assert eventos == [_evento_valido()]
    assert manifesto["eventos"]["registros_descartados"] == 1


def test_json_excessivamente_aninhado_e_descartado_sem_interromper_exportacao(
    ambiente,
    tmp_path,
) -> None:
    banco, sessao, _, caminho_log = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    aninhado = "[" * 2000 + "0" + "]" * 2000
    caminho_log.write_text(
        f"{aninhado}\n{json.dumps(_evento_valido())}\n",
        encoding="utf-8",
    )

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, eventos = _ler_pacote(caminho)
    assert eventos == [_evento_valido()]
    assert manifesto["eventos"]["registros_descartados"] == 1


def test_arquivos_arbitrarios_e_rotacao_fora_do_limite_sao_ignorados(
    ambiente,
    tmp_path,
) -> None:
    banco, sessao, diretorio_logs, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    (diretorio_logs / "segredo.txt").write_text(
        "senha=ARQUIVO_NAO_AUTORIZADO",
        encoding="utf-8",
    )
    (diretorio_logs / "sistema-pdv.log.6").write_text(
        "token=ROTACAO_FORA_DO_CONTRATO",
        encoding="utf-8",
    )

    caminho = exportar_diagnostico(destino, sessao, banco)

    with zipfile.ZipFile(caminho) as pacote:
        conteudo = pacote.read("manifesto.json") + pacote.read("eventos.jsonl")
    assert b"ARQUIVO_NAO_AUTORIZADO" not in conteudo
    assert b"ROTACAO_FORA_DO_CONTRATO" not in conteudo
    with pytest.raises(TypeError):
        exportar_diagnostico(
            destino,
            sessao,
            banco,
            diretorio_logs=tmp_path.parent,
        )


@pytest.mark.parametrize("destino", ["ausente", "arquivo"])
def test_destino_invalido_e_recusado(ambiente, tmp_path, destino) -> None:
    banco, sessao, _, _ = ambiente
    caminho = tmp_path / destino
    if destino == "arquivo":
        caminho.write_text("não é diretório", encoding="utf-8")

    with pytest.raises(diagnostico_service.DestinoDiagnosticoInvalidoError):
        exportar_diagnostico(caminho, sessao, banco)


def test_falha_ao_escrever_zip_remove_temporario(
    ambiente,
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, _, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()

    def falhar_escrita(*args, **kwargs):
        raise OSError("falha simulada ao escrever zip")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", falhar_escrita)

    with pytest.raises(OSError, match="falha simulada"):
        exportar_diagnostico(destino, sessao, banco)

    assert list(destino.glob(f"{diagnostico_service.PREFIXO_TEMPORARIO}*")) == []
    assert list(destino.glob("*.zip")) == []


def test_pacote_existente_nao_e_sobrescrito(
    ambiente,
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, _, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    nome = "sistema-pdv-diagnostico-existente.zip"
    existente = destino / nome
    conteudo_anterior = b"pacote anterior preservado"
    existente.write_bytes(conteudo_anterior)
    monkeypatch.setattr(
        diagnostico_service,
        "gerar_nome_arquivo_diagnostico",
        lambda instante=None: nome,
    )

    with pytest.raises(diagnostico_service.DiagnosticoJaExisteError):
        exportar_diagnostico(destino, sessao, banco)

    assert existente.read_bytes() == conteudo_anterior
    assert list(destino.glob(f"{diagnostico_service.PREFIXO_TEMPORARIO}*")) == []
    assert list(destino.glob("*.zip")) == [existente]


def test_falha_na_finalizacao_remove_temporario_e_nao_publica_zip(
    ambiente,
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, _, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()

    def falhar_finalizacao(*args, **kwargs):
        raise OSError("falha simulada na finalização")

    monkeypatch.setattr(diagnostico_service.os, "rename", falhar_finalizacao)

    with pytest.raises(OSError, match="falha simulada na finalização"):
        exportar_diagnostico(destino, sessao, banco)

    assert list(destino.glob(f"{diagnostico_service.PREFIXO_TEMPORARIO}*")) == []
    assert list(destino.glob("*.zip")) == []


def test_limite_de_registros_preserva_os_mais_recentes(
    ambiente,
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, _, caminho_log = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    linhas = []
    for indice in range(5):
        evento = _evento_valido()
        evento["timestamp"] = f"2026-11-11T12:00:0{indice}.000+00:00"
        linhas.append(json.dumps(evento))
    caminho_log.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    monkeypatch.setattr(diagnostico_service, "MAX_EVENTOS", 3)

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, eventos = _ler_pacote(caminho)
    assert len(eventos) == 3
    assert [evento["timestamp"] for evento in eventos] == [
        "2026-11-11T12:00:02.000+00:00",
        "2026-11-11T12:00:03.000+00:00",
        "2026-11-11T12:00:04.000+00:00",
    ]
    assert manifesto["eventos"]["truncado"] is True


def test_limite_de_leitura_descarta_fragmento_grande_sem_vazar(
    ambiente,
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, _, caminho_log = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    valido = json.dumps(_evento_valido())
    caminho_log.write_text(
        f"senha={'SEGREDO' * 200}\n{valido}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(diagnostico_service, "MAX_BYTES_POR_ARQUIVO", 512)
    monkeypatch.setattr(diagnostico_service, "MAX_BYTES_LINHA", 384)

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, eventos = _ler_pacote(caminho)
    with zipfile.ZipFile(caminho) as pacote:
        conteudo = pacote.read("manifesto.json") + pacote.read("eventos.jsonl")
    assert eventos == [_evento_valido()]
    assert manifesto["eventos"]["truncado"] is True
    assert b"SEGREDO" not in conteudo


def test_estado_desconhecido_e_declarado_sem_inferencia(
    ambiente,
    tmp_path,
    monkeypatch,
) -> None:
    banco, sessao, _, _ = ambiente
    destino = tmp_path / "destino"
    destino.mkdir()
    monkeypatch.setattr(
        diagnostico_service,
        "obter_estado_logging",
        lambda: SimpleNamespace(status="DESCONHECIDO"),
    )

    caminho = exportar_diagnostico(destino, sessao, banco)

    _, manifesto, _ = _ler_pacote(caminho)
    assert manifesto["logging"] == {"status": "DESCONHECIDO"}


def test_caixa_nao_pode_exportar_diagnostico(ambiente, tmp_path) -> None:
    banco, sessao_admin, _, _ = ambiente
    usuario, erros = criar_conta_caixa(
        sessao_admin,
        "caixa.diagnostico",
        SENHA_CAIXA,
        SENHA_CAIXA,
        banco,
    )
    assert usuario is not None and erros == []
    sessao_caixa = autenticar_usuario("caixa.diagnostico", SENHA_CAIXA, banco)

    with pytest.raises(PermissaoNegadaError):
        exportar_diagnostico(tmp_path / "destino", sessao_caixa, banco)

    assert list((tmp_path / "destino").glob("*.zip")) == []


def test_interface_administrativa_exporta_somente_por_acao_explicita(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    janela = criar_janela_autenticada(tmp_path / "interface.db")
    qtbot.addWidget(janela)
    pagina = janela.pagina_administracao
    destino = tmp_path / "destino"
    destino.mkdir()
    esperado = destino / "sistema-pdv-diagnostico-teste.zip"
    chamadas = []
    mensagens = []
    monkeypatch.setattr(
        pagina_administracao_module.QFileDialog,
        "getExistingDirectory",
        lambda *args: str(destino),
    )
    monkeypatch.setattr(
        pagina_administracao_module,
        "exportar_diagnostico",
        lambda diretorio, sessao, banco: (
            chamadas.append((diretorio, sessao, banco)) or esperado
        ),
    )
    monkeypatch.setattr(
        pagina_administracao_module.QMessageBox,
        "information",
        lambda parent, titulo, mensagem: mensagens.append((titulo, mensagem)),
    )

    assert chamadas == []
    pagina.botao_exportar_diagnostico.click()

    assert chamadas == [(str(destino), janela.sessao, janela.caminho_banco)]
    assert mensagens == [
        ("Diagnóstico exportado", f"Pacote criado em:\n{esperado}")
    ]


def test_interface_informa_falha_sem_propagar_excecao(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    janela = criar_janela_autenticada(tmp_path / "interface_falha.db")
    qtbot.addWidget(janela)
    pagina = janela.pagina_administracao
    destino = tmp_path / "destino"
    destino.mkdir()
    mensagens = []
    monkeypatch.setattr(
        pagina_administracao_module.QFileDialog,
        "getExistingDirectory",
        lambda *args: str(destino),
    )
    monkeypatch.setattr(
        pagina_administracao_module,
        "exportar_diagnostico",
        lambda *args: (_ for _ in ()).throw(OSError("falha com segredo")),
    )
    monkeypatch.setattr(
        pagina_administracao_module.QMessageBox,
        "critical",
        lambda parent, titulo, mensagem: mensagens.append((titulo, mensagem)),
    )

    pagina.botao_exportar_diagnostico.click()

    assert mensagens == [
        (
            "Falha ao exportar diagnóstico",
            "Não foi possível gerar o pacote de diagnóstico. "
            "Confirme a sessão, o destino e tente novamente.",
        )
    ]


def test_hook_de_thread_registra_tipo_e_preserva_hook_anterior(
    tmp_path,
    monkeypatch,
) -> None:
    caminho_log = logging_service.configurar_logging(tmp_path / "logs")
    chamadas = []
    hook_anterior = lambda argumentos: chamadas.append(argumentos)
    monkeypatch.setattr(
        logging_service,
        "_HOOK_THREAD_ANTERIOR",
        hook_anterior,
    )
    argumentos = SimpleNamespace(exc_type=RuntimeError)

    logging_service._tratar_erro_thread_nao_tratado(argumentos)

    documento = json.loads(caminho_log.read_text(encoding="utf-8"))
    assert documento["event"] == "erro_thread_nao_tratado"
    assert documento["erro_tipo"] == "RuntimeError"
    assert chamadas == [argumentos]


def test_hook_de_thread_nao_registra_system_exit_e_preserva_hook(
    tmp_path,
    monkeypatch,
) -> None:
    caminho_log = logging_service.configurar_logging(tmp_path / "logs")
    chamadas = []
    argumentos = SimpleNamespace(exc_type=SystemExit)
    monkeypatch.setattr(
        logging_service,
        "_HOOK_THREAD_ANTERIOR",
        lambda recebido: chamadas.append(recebido),
    )

    logging_service._tratar_erro_thread_nao_tratado(argumentos)

    assert not caminho_log.exists()
    assert chamadas == [argumentos]


def test_nome_do_pacote_nao_contem_dados_de_operador() -> None:
    nome = diagnostico_service.gerar_nome_arquivo_diagnostico(
        datetime(2026, 11, 11, 12, 34, 56, tzinfo=UTC)
    )

    assert nome == "sistema-pdv-diagnostico-20261111T123456000000Z.zip"
    assert "administrador" not in nome
    assert SENHA_ADMIN_TESTE not in nome
