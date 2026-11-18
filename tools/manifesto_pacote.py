"""Ferramenta separada de geração e assinatura de manifestos T60-B.4."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.manifesto_pacote_service import (
    ALGORITMO_ASSINATURA,
    CONTRATO_ASSINATURA_VERSAO,
    NOME_ASSINATURA,
    NOME_MANIFESTO,
    ManifestoInvalidoError,
    OrigemCompativel,
    gerar_manifesto,
    gravar_manifesto,
    serializar_json_canonico,
    validar_conteudo_manifesto_nao_confiavel,
)


_CAMPOS_CONFIGURACAO = {
    "environment",
    "package_id",
    "package_version",
    "application_version",
    "build_id",
    "commit_git",
    "allowed_sources",
    "required_schema_version",
    "update_policy_id",
    "previous_application_compatibility_declared",
    "homologation_reference",
    "schema_migrations",
}
_CHAVE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def gerar_manifesto_de_configuracao(
    raiz_pacote: Path,
    caminho_configuracao: Path,
) -> Path:
    configuracao = _ler_configuracao(caminho_configuracao)
    manifesto = gerar_manifesto(
        raiz_pacote,
        ambiente=configuracao["environment"],
        pacote_id=configuracao["package_id"],
        versao_pacote=configuracao["package_version"],
        versao_aplicativo=configuracao["application_version"],
        build_id=configuracao["build_id"],
        commit_git=configuracao["commit_git"],
        origens_permitidas=(
            OrigemCompativel(
                item["application_version"],
                item["schema_version"],
            )
            for item in configuracao["allowed_sources"]
        ),
        versao_schema_exigida=configuracao["required_schema_version"],
        politica_atualizacao_id=configuracao["update_policy_id"],
        compatibilidade_anterior_declarada=configuracao[
            "previous_application_compatibility_declared"
        ],
        referencia_homologacao=configuracao["homologation_reference"],
        migracoes_schema=configuracao["schema_migrations"],
    )
    return gravar_manifesto(raiz_pacote, manifesto)


def assinar_manifesto(
    raiz_pacote: Path,
    caminho_chave_privada: Path,
    chave_id: str,
) -> Path:
    """Assina somente com chave externa; nunca copia a chave ao pacote."""
    if not isinstance(chave_id, str) or not _CHAVE_ID.fullmatch(chave_id):
        raise ManifestoInvalidoError("O identificador da chave é inválido.")
    raiz = raiz_pacote.resolve(strict=True)
    chave = caminho_chave_privada.resolve(strict=True)
    try:
        if os.path.commonpath((str(raiz), str(chave))) == str(raiz):
            raise ManifestoInvalidoError(
                "A chave privada não pode estar dentro do pacote."
            )
    except ValueError:
        pass
    manifesto = validar_conteudo_manifesto_nao_confiavel(raiz)
    destino = raiz / NOME_ASSINATURA
    if destino.exists():
        raise ManifestoInvalidoError("A assinatura existente não será sobrescrita.")
    try:
        privada = serialization.load_pem_private_key(
            chave.read_bytes(),
            password=None,
        )
    except (OSError, ValueError, TypeError) as erro:
        raise ManifestoInvalidoError("A chave privada externa é inválida.") from erro
    if not isinstance(privada, Ed25519PrivateKey):
        raise ManifestoInvalidoError("A chave privada deve usar Ed25519.")
    assinatura = privada.sign(serializar_json_canonico(manifesto))
    documento = {
        "algorithm": ALGORITMO_ASSINATURA,
        "contract_version": CONTRATO_ASSINATURA_VERSAO,
        "key_id": chave_id,
        "signature": base64.b64encode(assinatura).decode("ascii"),
    }
    destino.write_bytes(serializar_json_canonico(documento) + b"\n")
    return destino


def gerar_chave_efemera_para_testes() -> tuple[bytes, bytes]:
    """Retorna PEM privada e chave pública bruta; não persiste material."""
    privada = Ed25519PrivateKey.generate()
    privada_pem = privada.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    publica = privada.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return privada_pem, publica


def _ler_configuracao(caminho: Path) -> dict:
    try:
        conteudo = caminho.resolve(strict=True).read_bytes()
        if len(conteudo) > 64 * 1024:
            raise ValueError
        documento = json.loads(conteudo)
    except (OSError, ValueError, json.JSONDecodeError) as erro:
        raise ManifestoInvalidoError(
            "A configuração externa do manifesto é inválida."
        ) from erro
    if not isinstance(documento, dict) or set(documento) != _CAMPOS_CONFIGURACAO:
        raise ManifestoInvalidoError(
            "A configuração externa do manifesto é incompleta."
        )
    return documento


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    comandos = parser.add_subparsers(dest="comando", required=True)
    gerar = comandos.add_parser("gerar")
    gerar.add_argument("--raiz", required=True, type=Path)
    gerar.add_argument("--configuracao", required=True, type=Path)
    assinar = comandos.add_parser("assinar")
    assinar.add_argument("--raiz", required=True, type=Path)
    assinar.add_argument("--chave-privada", required=True, type=Path)
    assinar.add_argument("--chave-id", required=True)
    auditar = comandos.add_parser("auditar-conteudo")
    auditar.add_argument("--raiz", required=True, type=Path)
    return parser


def main() -> int:
    argumentos = _criar_parser().parse_args()
    if argumentos.comando == "gerar":
        gerar_manifesto_de_configuracao(argumentos.raiz, argumentos.configuracao)
        validar_conteudo_manifesto_nao_confiavel(argumentos.raiz)
    elif argumentos.comando == "assinar":
        assinar_manifesto(
            argumentos.raiz,
            argumentos.chave_privada,
            argumentos.chave_id,
        )
    else:
        validar_conteudo_manifesto_nao_confiavel(argumentos.raiz)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
