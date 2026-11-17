import json
from pathlib import Path
from uuid import uuid4

import pytest

from services.contexto_instalacao_service import (
    AMBIENTE_HOMOLOGACAO_ID,
    AMBIENTE_PRODUCAO_ID,
    CONTRATO_IDENTIDADE_VERSAO,
    CONTRATO_MANUTENCAO_VERSAO,
    GRUPO_OPERADORES,
    PRODUTO_ID,
    AmbienteInstalacao,
    EstadoManutencaoInvalidoError,
    IdentidadeInstalacaoAusenteError,
    IdentidadeInstalacaoDivergenteError,
    RegistroInstalacao,
    obter_contrato_acl,
    resolver_contexto_instalacao,
    verificar_estado_manutencao,
)


class RegistroMemoria:
    def __init__(self, *registros):
        self._registros = tuple(registros)

    def listar_instalacoes(self):
        return self._registros


def _criar_instalacao(
    tmp_path: Path,
    ambiente: AmbienteInstalacao,
):
    slug = "Producao" if ambiente is AmbienteInstalacao.PRODUCAO else "Homologacao"
    ambiente_id = (
        AMBIENTE_PRODUCAO_ID
        if ambiente is AmbienteInstalacao.PRODUCAO
        else AMBIENTE_HOMOLOGACAO_ID
    )
    instalacao_id = str(uuid4())
    raiz_instalacao = tmp_path / "Program Files" / f"Sistema-PDV-{slug}"
    executavel = raiz_instalacao / "Sistema-PDV" / "Sistema-PDV.exe"
    executavel.parent.mkdir(parents=True)
    executavel.write_bytes(b"executavel de teste")
    program_data = tmp_path / "ProgramData"
    administrativo = program_data / "Sistema-PDV" / slug / "administrative"
    administrativo.mkdir(parents=True)
    descriptor = {
        "contract_version": CONTRATO_IDENTIDADE_VERSAO,
        "product_id": PRODUTO_ID,
        "environment": ambiente.value,
        "environment_id": ambiente_id,
        "installation_id": instalacao_id,
        "install_root": str(raiz_instalacao.resolve()),
        "executable_path": str(executavel.resolve()),
    }
    (administrativo / "installation.json").write_text(
        json.dumps(descriptor),
        encoding="utf-8",
    )
    registro = RegistroInstalacao(
        produto_id=PRODUTO_ID,
        ambiente=ambiente.value,
        ambiente_id=ambiente_id,
        instalacao_id=instalacao_id,
        raiz_instalacao=str(raiz_instalacao.resolve()),
        caminho_executavel=str(executavel.resolve()),
    )
    return registro, executavel, program_data


def _resolver_comercial(registro, executavel, program_data):
    return resolver_contexto_instalacao(
        empacotado=True,
        caminho_executavel=executavel,
        provedor_registro=RegistroMemoria(registro),
        program_data=program_data,
        program_files=executavel.parents[2],
    )


def _gravar_estado_livre(contexto) -> None:
    contexto.caminhos.manutencao.mkdir(parents=True)
    contexto.caminhos.estado_manutencao.write_text(
        json.dumps(
            {
                "contract_version": CONTRATO_MANUTENCAO_VERSAO,
                "product_id": contexto.produto_id,
                "environment_id": contexto.ambiente_id,
                "installation_id": contexto.instalacao_id,
                "status": "IDLE",
            }
        ),
        encoding="utf-8",
    )


def test_desenvolvimento_preserva_caminhos_do_repositorio(tmp_path) -> None:
    raiz = tmp_path / "repositorio"
    contexto = resolver_contexto_instalacao(
        empacotado=False,
        caminho_executavel=tmp_path / "python.exe",
        raiz_repositorio=raiz,
    )

    assert contexto.ambiente is AmbienteInstalacao.DESENVOLVIMENTO
    assert contexto.comercial is False
    assert contexto.caminhos.dados == raiz / "data"
    assert contexto.caminhos.banco == raiz / "data" / "sistema_acougue.db"
    verificar_estado_manutencao(contexto)


def test_producao_e_homologacao_possuem_identidades_e_caminhos_distintos(
    tmp_path,
) -> None:
    prod = _criar_instalacao(tmp_path / "prod", AmbienteInstalacao.PRODUCAO)
    hom = _criar_instalacao(tmp_path / "hom", AmbienteInstalacao.HOMOLOGACAO)

    contexto_prod = _resolver_comercial(*prod)
    contexto_hom = _resolver_comercial(*hom)

    assert contexto_prod.ambiente_id == AMBIENTE_PRODUCAO_ID
    assert contexto_hom.ambiente_id == AMBIENTE_HOMOLOGACAO_ID
    assert contexto_prod.instalacao_id != contexto_hom.instalacao_id
    assert contexto_prod.caminhos.banco != contexto_hom.caminhos.banco
    assert contexto_prod.caminhos.logs != contexto_hom.caminhos.logs
    assert contexto_prod.caminhos.manutencao != contexto_hom.caminhos.manutencao


def test_execucao_comercial_sem_registro_nao_cai_em_desenvolvimento(
    tmp_path,
) -> None:
    executavel = tmp_path / "Sistema-PDV.exe"
    executavel.write_bytes(b"teste")

    with pytest.raises(IdentidadeInstalacaoAusenteError):
        resolver_contexto_instalacao(
            empacotado=True,
            caminho_executavel=executavel,
            provedor_registro=RegistroMemoria(),
            program_data=tmp_path / "ProgramData",
        )


def test_descritor_divergente_do_registro_e_recusado(tmp_path) -> None:
    registro, executavel, program_data = _criar_instalacao(
        tmp_path,
        AmbienteInstalacao.PRODUCAO,
    )
    descritor = (
        program_data
        / "Sistema-PDV"
        / "Producao"
        / "administrative"
        / "installation.json"
    )
    documento = json.loads(descritor.read_text(encoding="utf-8"))
    documento["installation_id"] = str(uuid4())
    descritor.write_text(json.dumps(documento), encoding="utf-8")

    with pytest.raises(IdentidadeInstalacaoDivergenteError):
        _resolver_comercial(registro, executavel, program_data)


def test_raiz_comercial_fora_de_program_files_e_recusada(tmp_path) -> None:
    registro, executavel, program_data = _criar_instalacao(
        tmp_path,
        AmbienteInstalacao.PRODUCAO,
    )

    with pytest.raises(IdentidadeInstalacaoDivergenteError):
        resolver_contexto_instalacao(
            empacotado=True,
            caminho_executavel=executavel,
            provedor_registro=RegistroMemoria(registro),
            program_data=program_data,
            program_files=tmp_path / "outra-raiz",
        )


def test_variaveis_de_ambiente_nao_alteram_instalacao_comercial(
    tmp_path,
    monkeypatch,
) -> None:
    registro, executavel, program_data = _criar_instalacao(
        tmp_path,
        AmbienteInstalacao.PRODUCAO,
    )
    hostil = tmp_path / "controlado-pelo-usuario"
    monkeypatch.setenv("PROGRAMDATA", str(hostil))
    monkeypatch.setenv("LOCALAPPDATA", str(hostil))
    monkeypatch.setenv("SISTEMA_PDV_LOG_DIR", str(hostil))

    contexto = _resolver_comercial(registro, executavel, program_data)

    assert contexto.caminhos.raiz_ambiente.is_relative_to(program_data)
    assert not contexto.caminhos.raiz_ambiente.is_relative_to(hostil)


def test_estado_de_manutencao_deve_existir_e_estar_livre(tmp_path) -> None:
    contexto = _resolver_comercial(
        *_criar_instalacao(tmp_path, AmbienteInstalacao.PRODUCAO)
    )

    with pytest.raises(EstadoManutencaoInvalidoError):
        verificar_estado_manutencao(contexto)

    _gravar_estado_livre(contexto)
    verificar_estado_manutencao(contexto)
    documento = json.loads(
        contexto.caminhos.estado_manutencao.read_text(encoding="utf-8")
    )
    documento["status"] = "ATUALIZACAO_INCOMPLETA"
    contexto.caminhos.estado_manutencao.write_text(
        json.dumps(documento),
        encoding="utf-8",
    )

    with pytest.raises(EstadoManutencaoInvalidoError):
        verificar_estado_manutencao(contexto)


def test_contrato_acl_separa_escrita_operacional_de_controle_administrativo(
    tmp_path,
) -> None:
    contexto = _resolver_comercial(
        *_criar_instalacao(tmp_path, AmbienteInstalacao.HOMOLOGACAO)
    )

    contrato = obter_contrato_acl(contexto)

    assert contrato.grupo_operadores == GRUPO_OPERADORES
    assert contexto.caminhos.dados in contrato.gravacao_operacional
    assert contexto.caminhos.logs in contrato.gravacao_operacional
    assert contexto.caminhos.administrativo in contrato.leitura_operacional
    assert contexto.caminhos.manutencao in contrato.leitura_operacional
    assert contexto.caminhos.administrativo in contrato.controle_administrativo
    assert contexto.caminhos.manutencao in contrato.controle_administrativo
    assert contexto.caminhos.administrativo not in contrato.gravacao_operacional
    assert contexto.caminhos.manutencao not in contrato.gravacao_operacional
