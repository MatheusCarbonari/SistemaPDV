from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from database.schema import VERSAO_ESQUEMA
from services.contexto_instalacao_service import (
    AMBIENTE_HOMOLOGACAO_ID,
    AMBIENTE_PRODUCAO_ID,
    PRODUTO_ID,
    AmbienteInstalacao,
    CaminhosInstalacao,
    ContextoInstalacao,
)
from services.manifesto_pacote_service import (
    NOME_ASSINATURA,
    NOME_MANIFESTO,
    AssinaturaPacoteInvalidaError,
    CompatibilidadePacoteError,
    IntegridadePacoteError,
    ManifestoInvalidoError,
    OrigemCompativel,
    gerar_manifesto,
    gravar_manifesto,
    serializar_json_canonico,
    validar_conteudo_manifesto_nao_confiavel,
    verificar_pacote_assinado,
)
import services.manifesto_pacote_service as manifesto_module
from tools.manifesto_pacote import (
    assinar_manifesto,
    gerar_chave_efemera_para_testes,
)


VERSAO_ORIGEM = "0.1.0"
BUILD_ID = "win-t60-b4-teste"
CHAVE_ID = "teste-efemero-1"


def _contexto(tmp_path: Path, ambiente=AmbienteInstalacao.PRODUCAO):
    ambiente_id = (
        AMBIENTE_PRODUCAO_ID
        if ambiente is AmbienteInstalacao.PRODUCAO
        else AMBIENTE_HOMOLOGACAO_ID
    )
    raiz = tmp_path / ambiente.value
    caminhos = CaminhosInstalacao(
        raiz,
        raiz / "data",
        raiz / "data" / "sistema_acougue.db",
        raiz / "logs",
        raiz / "config",
        raiz / "administrative",
        raiz / "administrative" / "installation.json",
        raiz / "administrative" / "manifests",
        raiz / "maintenance",
        raiz / "maintenance" / "state.json",
    )
    return ContextoInstalacao(
        PRODUTO_ID,
        ambiente,
        ambiente_id,
        "98dd1496-790b-4c9a-bbc5-f29d475e33b3",
        True,
        tmp_path / "ProgramFiles" / "Sistema-PDV.exe",
        tmp_path / "ProgramFiles",
        caminhos,
    )


def _criar_raiz_pacote(tmp_path: Path, *, build_id=BUILD_ID) -> Path:
    raiz = tmp_path / "pacote"
    aplicacao = raiz / "Sistema-PDV"
    aplicacao.mkdir(parents=True)
    (aplicacao / "Sistema-PDV.exe").write_bytes(b"executavel de teste")
    (aplicacao / "_internal").mkdir()
    (aplicacao / "_internal" / "python314.dll").write_bytes(b"runtime")
    (raiz / "build-report.json").write_text(
        json.dumps(
            {
                "aplicativo": "Sistema-PDV",
                "versao_aplicativo": VERSAO_ORIGEM,
                "build_id": build_id,
                "commit_git": "0123456789abcdef0123456789abcdef01234567",
                "executavel_sha256": "apenas-relatorio-t59",
                "distribuicao": "Sistema-PDV",
            }
        ),
        encoding="utf-8",
    )
    return raiz


def _manifesto(
    raiz: Path,
    *,
    ambiente="PRODUCAO",
    build_id=BUILD_ID,
    origens=None,
):
    return gerar_manifesto(
        raiz,
        ambiente=ambiente,
        pacote_id="sistema-pdv-producao-0.1.0-teste",
        versao_pacote="0.1.0",
        versao_aplicativo=VERSAO_ORIGEM,
        build_id=build_id,
        commit_git="0123456789abcdef0123456789abcdef01234567",
        origens_permitidas=origens
        or (OrigemCompativel(VERSAO_ORIGEM, VERSAO_ESQUEMA),),
        versao_schema_exigida=VERSAO_ESQUEMA,
        politica_atualizacao_id="T60-SEM-MIGRACAO-V1",
        compatibilidade_anterior_declarada=True,
        referencia_homologacao="HOMOLOG-T60-B4-TESTE",
    )


def _preparar_assinado(tmp_path: Path, *, ambiente="PRODUCAO"):
    raiz = _criar_raiz_pacote(tmp_path)
    gravar_manifesto(raiz, _manifesto(raiz, ambiente=ambiente))
    privada_pem, publica = gerar_chave_efemera_para_testes()
    chave = tmp_path / "chave-externa.pem"
    chave.write_bytes(privada_pem)
    assinar_manifesto(raiz, chave, CHAVE_ID)
    privada = serialization.load_pem_private_key(privada_pem, password=None)
    return raiz, privada, publica


def _verificar(raiz, publica, contexto, **kwargs):
    anterior = manifesto_module.CHAVES_PUBLICAS_COMERCIAIS
    manifesto_module.CHAVES_PUBLICAS_COMERCIAIS = {CHAVE_ID: publica}
    try:
        return verificar_pacote_assinado(
            raiz,
            contexto=contexto,
            versao_aplicativo_origem=kwargs.pop("versao", VERSAO_ORIGEM),
            versao_schema_origem=kwargs.pop("schema", VERSAO_ESQUEMA),
            plataforma_atual=kwargs.pop("plataforma_atual", "windows"),
            arquitetura_atual=kwargs.pop("arquitetura_atual", "x86_64"),
            **kwargs,
        )
    finally:
        manifesto_module.CHAVES_PUBLICAS_COMERCIAIS = anterior


def _reescrever_e_assinar(raiz: Path, manifesto: dict, privada: Ed25519PrivateKey):
    (raiz / NOME_MANIFESTO).write_bytes(serializar_json_canonico(manifesto) + b"\n")
    assinatura = json.loads((raiz / NOME_ASSINATURA).read_text(encoding="utf-8"))
    import base64

    assinatura["signature"] = base64.b64encode(
        privada.sign(serializar_json_canonico(manifesto))
    ).decode("ascii")
    (raiz / NOME_ASSINATURA).write_bytes(
        serializar_json_canonico(assinatura) + b"\n"
    )


def test_pacote_integro_assinado_e_autenticado_sem_autorizar_atualizacao(tmp_path):
    raiz, _, publica = _preparar_assinado(tmp_path)

    resultado = _verificar(raiz, publica, _contexto(tmp_path))

    assert resultado.integridade_comprovada is True
    assert resultado.compatibilidade_declarada is True
    assert resultado.atualizacao_coordenada_autorizada is False
    assert resultado.chave_id == CHAVE_ID


def test_alteracao_de_um_byte_e_detectada(tmp_path):
    raiz, _, publica = _preparar_assinado(tmp_path)
    executavel = raiz / "Sistema-PDV" / "Sistema-PDV.exe"
    executavel.write_bytes(executavel.read_bytes() + b"x")

    with pytest.raises(IntegridadePacoteError):
        _verificar(raiz, publica, _contexto(tmp_path))


@pytest.mark.parametrize("alvo", [NOME_MANIFESTO, NOME_ASSINATURA])
def test_manifesto_ou_assinatura_adulterados_sao_recusados(tmp_path, alvo):
    raiz, _, publica = _preparar_assinado(tmp_path)
    caminho = raiz / alvo
    conteudo = bytearray(caminho.read_bytes())
    conteudo[len(conteudo) // 2] ^= 1
    caminho.write_bytes(conteudo)

    with pytest.raises((ManifestoInvalidoError, AssinaturaPacoteInvalidaError)):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_chave_publica_nao_confiavel_e_recusada(tmp_path):
    raiz, _, _ = _preparar_assinado(tmp_path)
    _, publica_alheia = gerar_chave_efemera_para_testes()

    with pytest.raises(AssinaturaPacoteInvalidaError):
        _verificar(raiz, publica_alheia, _contexto(tmp_path))


def test_chave_publica_fornecida_pelo_pacote_nao_cria_confianca(tmp_path):
    raiz, _, publica = _preparar_assinado(tmp_path)
    (raiz / "public-key.bin").write_bytes(publica)

    with pytest.raises(AssinaturaPacoteInvalidaError, match="não é confiável"):
        verificar_pacote_assinado(
            raiz,
            contexto=_contexto(tmp_path),
            versao_aplicativo_origem=VERSAO_ORIGEM,
            versao_schema_origem=VERSAO_ESQUEMA,
            plataforma_atual="windows",
            arquitetura_atual="x86_64",
        )


@pytest.mark.parametrize("operacao", ["ausente", "inesperado"])
def test_arquivo_ausente_ou_inesperado_e_recusado(tmp_path, operacao):
    raiz, _, publica = _preparar_assinado(tmp_path)
    if operacao == "ausente":
        (raiz / "Sistema-PDV" / "_internal" / "python314.dll").unlink()
    else:
        (raiz / "Sistema-PDV" / "inesperado.txt").write_text("x")

    with pytest.raises(IntegridadePacoteError):
        _verificar(raiz, publica, _contexto(tmp_path))


@pytest.mark.parametrize("caminho", ["../fora.exe", "/absoluto.exe", "A\\B.exe"])
def test_caminho_malicioso_assinado_e_recusado(tmp_path, caminho):
    raiz, privada, publica = _preparar_assinado(tmp_path)
    manifesto = json.loads((raiz / NOME_MANIFESTO).read_text(encoding="utf-8"))
    manifesto["files"][0]["path"] = caminho
    _reescrever_e_assinar(raiz, manifesto, privada)

    with pytest.raises(ManifestoInvalidoError):
        _verificar(raiz, publica, _contexto(tmp_path))


@pytest.mark.parametrize(
    "caminho",
    [
        "CON",
        "con.txt",
        "PRN.dll",
        "AUX.exe",
        "NUL.bin",
        "COM1.exe",
        "com9.txt",
        "LPT1",
        "lpt9.dll",
        "COM¹.txt",
        "nome.",
        "nome ",
        "nome<ruim>.txt",
        'nome"ruim.txt',
        "nome|ruim.txt",
        "nome?ruim.txt",
        "nome*ruim.txt",
        "controle\u0001.txt",
        "e\u0301.txt",
    ],
)
def test_nome_incompativel_com_windows_assinado_e_recusado(tmp_path, caminho):
    raiz, privada, publica = _preparar_assinado(tmp_path)
    manifesto = json.loads((raiz / NOME_MANIFESTO).read_text(encoding="utf-8"))
    manifesto["files"][0]["path"] = caminho
    _reescrever_e_assinar(raiz, manifesto, privada)

    with pytest.raises(ManifestoInvalidoError):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_caminhos_duplicados_sem_distincao_de_caixa_sao_recusados(tmp_path):
    raiz, privada, publica = _preparar_assinado(tmp_path)
    manifesto = json.loads((raiz / NOME_MANIFESTO).read_text(encoding="utf-8"))
    duplicado = dict(manifesto["files"][0])
    duplicado["path"] = duplicado["path"].swapcase()
    manifesto["files"].append(duplicado)
    _reescrever_e_assinar(raiz, manifesto, privada)

    with pytest.raises(ManifestoInvalidoError):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_link_simbolico_no_pacote_e_recusado(tmp_path):
    raiz = _criar_raiz_pacote(tmp_path)
    externo = tmp_path / "externo.bin"
    externo.write_bytes(b"externo")
    link = raiz / "Sistema-PDV" / "link.bin"
    try:
        link.symlink_to(externo)
    except OSError:
        pytest.skip("Ambiente Windows sem privilégio para criar link simbólico.")

    with pytest.raises(IntegridadePacoteError):
        _manifesto(raiz)


def test_pacote_homologacao_nao_e_aceito_em_producao(tmp_path):
    raiz, _, publica = _preparar_assinado(tmp_path, ambiente="HOMOLOGACAO")

    with pytest.raises(CompatibilidadePacoteError, match="ambiente"):
        _verificar(raiz, publica, _contexto(tmp_path))


@pytest.mark.parametrize(
    ("versao", "schema"),
    [("9.9.9", VERSAO_ESQUEMA), (VERSAO_ORIGEM, VERSAO_ESQUEMA - 1)],
)
def test_versao_ou_schema_nao_homologados_sao_recusados(tmp_path, versao, schema):
    raiz, _, publica = _preparar_assinado(tmp_path)

    with pytest.raises(CompatibilidadePacoteError):
        _verificar(
            raiz,
            publica,
            _contexto(tmp_path),
            versao=versao,
            schema=schema,
        )


def test_declaracao_de_compatibilidade_ausente_e_recusada(tmp_path):
    raiz, privada, publica = _preparar_assinado(tmp_path)
    manifesto = json.loads((raiz / NOME_MANIFESTO).read_text(encoding="utf-8"))
    del manifesto["compatibility"]["previous_application_compatibility"]
    _reescrever_e_assinar(raiz, manifesto, privada)

    with pytest.raises(ManifestoInvalidoError):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_versao_desconhecida_do_contrato_e_recusada(tmp_path):
    raiz, privada, publica = _preparar_assinado(tmp_path)
    manifesto = json.loads((raiz / NOME_MANIFESTO).read_text(encoding="utf-8"))
    manifesto["contract_version"] = 999
    _reescrever_e_assinar(raiz, manifesto, privada)

    with pytest.raises(ManifestoInvalidoError):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_arquitetura_incompativel_e_recusada(tmp_path):
    raiz, _, publica = _preparar_assinado(tmp_path)

    with pytest.raises(CompatibilidadePacoteError, match="arquitetura"):
        _verificar(
            raiz,
            publica,
            _contexto(tmp_path),
            arquitetura_atual="arm64",
        )


def test_identificador_build_divergente_e_recusado(tmp_path):
    raiz, privada, publica = _preparar_assinado(tmp_path)
    manifesto = json.loads((raiz / NOME_MANIFESTO).read_text(encoding="utf-8"))
    manifesto["application"]["build_id"] = "build-divergente"
    _reescrever_e_assinar(raiz, manifesto, privada)

    with pytest.raises(ManifestoInvalidoError, match="build"):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_geracao_do_manifesto_e_deterministica(tmp_path):
    raiz_a = _criar_raiz_pacote(tmp_path / "a")
    raiz_b = _criar_raiz_pacote(tmp_path / "b")

    primeiro = serializar_json_canonico(_manifesto(raiz_a))
    segundo = serializar_json_canonico(_manifesto(raiz_b))

    assert primeiro == segundo


def test_inspecao_nao_altera_banco_comercial_isolado(tmp_path):
    banco = tmp_path / "operacional-isolado.db"
    with sqlite3.connect(banco) as conexao:
        conexao.execute("CREATE TABLE marcador (valor TEXT)")
        conexao.execute("INSERT INTO marcador VALUES ('intacto')")
    antes = banco.read_bytes()
    raiz, _, publica = _preparar_assinado(tmp_path / "artefatos")

    _verificar(raiz, publica, _contexto(tmp_path / "contexto"))

    assert banco.read_bytes() == antes
    with sqlite3.connect(banco) as conexao:
        assert conexao.execute("SELECT valor FROM marcador").fetchone()[0] == "intacto"


def test_chave_privada_dentro_do_pacote_e_recusada(tmp_path):
    raiz = _criar_raiz_pacote(tmp_path)
    gravar_manifesto(raiz, _manifesto(raiz))
    privada_pem, _ = gerar_chave_efemera_para_testes()
    chave = raiz / "nao-permitida.pem"
    chave.write_bytes(privada_pem)

    with pytest.raises(ManifestoInvalidoError, match="dentro do pacote"):
        assinar_manifesto(raiz, chave, CHAVE_ID)


def test_manifesto_sem_assinatura_nao_e_confiavel(tmp_path):
    raiz = _criar_raiz_pacote(tmp_path)
    gravar_manifesto(raiz, _manifesto(raiz))
    _, publica = gerar_chave_efemera_para_testes()

    validar_conteudo_manifesto_nao_confiavel(raiz)
    with pytest.raises(AssinaturaPacoteInvalidaError):
        _verificar(raiz, publica, _contexto(tmp_path))


def test_relatorio_build_utf8_sem_bom_e_lido_pelo_servico(tmp_path):
    raiz = _criar_raiz_pacote(tmp_path)
    relatorio = (raiz / "build-report.json").read_bytes()

    assert not relatorio.startswith(b"\xef\xbb\xbf")
    manifesto = _manifesto(raiz)
    assert manifesto["application"]["build_id"] == BUILD_ID


@pytest.mark.parametrize(
    "nome_metadata",
    [NOME_MANIFESTO, NOME_ASSINATURA, "build-report.json"],
)
def test_metadata_em_hard_link_e_recusado(tmp_path, nome_metadata):
    raiz, _, publica = _preparar_assinado(tmp_path)
    metadata = raiz / nome_metadata
    externo = tmp_path / f"externo-{nome_metadata}"
    externo.write_bytes(metadata.read_bytes())
    metadata.unlink()
    os.link(externo, metadata)

    with pytest.raises(IntegridadePacoteError):
        _verificar(raiz, publica, _contexto(tmp_path))


@pytest.mark.parametrize(
    "nome_metadata",
    [NOME_MANIFESTO, NOME_ASSINATURA, "build-report.json"],
)
def test_metadata_em_link_simbolico_e_recusado(tmp_path, nome_metadata):
    raiz, _, publica = _preparar_assinado(tmp_path)
    metadata = raiz / nome_metadata
    externo = tmp_path / f"externo-link-{nome_metadata}"
    externo.write_bytes(metadata.read_bytes())
    metadata.unlink()
    try:
        metadata.symlink_to(externo)
    except OSError:
        pytest.skip("Ambiente Windows sem privilégio para criar link simbólico.")

    with pytest.raises(IntegridadePacoteError):
        _verificar(raiz, publica, _contexto(tmp_path))


@pytest.mark.parametrize(
    "nome_metadata",
    [NOME_MANIFESTO, NOME_ASSINATURA, "build-report.json"],
)
def test_metadata_com_reparse_point_windows_simulado_e_recusado(
    tmp_path,
    monkeypatch,
    nome_metadata,
):
    raiz, _, publica = _preparar_assinado(tmp_path)
    metadata = raiz / nome_metadata
    lstat_original = manifesto_module.os.lstat

    class EstadoReparse:
        st_file_attributes = 0x400

        def __init__(self, estado):
            self._estado = estado

        def __getattr__(self, nome):
            return getattr(self._estado, nome)

    def lstat_com_reparse(caminho):
        estado = lstat_original(caminho)
        if Path(caminho) == metadata:
            return EstadoReparse(estado)
        return estado

    monkeypatch.setattr(manifesto_module.os, "lstat", lstat_com_reparse)

    with pytest.raises(IntegridadePacoteError):
        _verificar(raiz, publica, _contexto(tmp_path))
