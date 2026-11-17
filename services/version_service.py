"""Identificação offline da versão e da origem do build do Sistema-PDV."""

from __future__ import annotations

from dataclasses import dataclass
import re


NOME_APLICATIVO = "Sistema-PDV"
VERSAO_APLICATIVO = "0.1.0"

# O T59 deverá preencher estes valores em uma cópia de build, antes de gerar o
# executável. Eles permanecem ausentes no código-fonte de desenvolvimento para
# não publicar metadados falsos ou vinculados ao schema SQLite.
IDENTIFICADOR_BUILD_EMBUTIDO: str | None = None
COMMIT_GIT_EMBUTIDO: str | None = None

METADADO_DESCONHECIDO = "desconhecido"

_VERSAO_SEMANTICA = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_IDENTIFICADOR_BUILD_VALIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_COMMIT_GIT_VALIDO = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class IdentificacaoAplicativo:
    """Metadados técnicos imutáveis disponíveis no processo atual."""

    nome: str
    versao: str
    identificador_build: str | None
    commit_git: str | None

    @property
    def build_exibicao(self) -> str:
        return self.identificador_build or METADADO_DESCONHECIDO

    @property
    def commit_exibicao(self) -> str:
        return self.commit_git or METADADO_DESCONHECIDO

    def dados_diagnostico(self) -> dict[str, str]:
        """Expõe somente os campos técnicos destinados a suporte e logging."""
        return {
            "nome_aplicativo": self.nome,
            "versao_aplicativo": self.versao,
            "build_id": self.build_exibicao,
            "commit_git": self.commit_exibicao,
        }


def obter_identificacao_aplicativo() -> IdentificacaoAplicativo:
    """Retorna somente os metadados embutidos, sem consultar Git ou rede."""
    if not _VERSAO_SEMANTICA.fullmatch(VERSAO_APLICATIVO):
        raise RuntimeError("A versão oficial do aplicativo é inválida.")

    return IdentificacaoAplicativo(
        nome=NOME_APLICATIVO,
        versao=VERSAO_APLICATIVO,
        identificador_build=_normalizar_metadado(
            IDENTIFICADOR_BUILD_EMBUTIDO,
            _IDENTIFICADOR_BUILD_VALIDO,
        ),
        commit_git=_normalizar_metadado(
            COMMIT_GIT_EMBUTIDO,
            _COMMIT_GIT_VALIDO,
        ),
    )


def validar_metadados_build(
    identificador_build: str | None,
    commit_git: str | None,
) -> tuple[str | None, str | None]:
    """Valida os valores que o T59 incorporará à cópia temporária de build."""
    return (
        _validar_metadado_informado(
            identificador_build,
            _IDENTIFICADOR_BUILD_VALIDO,
            "identificador do build",
        ),
        _validar_metadado_informado(
            commit_git,
            _COMMIT_GIT_VALIDO,
            "commit Git",
        ),
    )


def formatar_informacoes_sobre(
    identificacao: IdentificacaoAplicativo | None = None,
) -> str:
    """Produz o texto técnico exibido no Sobre, sem versão do schema SQLite."""
    dados = identificacao or obter_identificacao_aplicativo()
    return (
        f"Versão do aplicativo: {dados.versao}\n"
        f"Identificador do build: {dados.build_exibicao}\n"
        f"Commit Git de origem: {dados.commit_exibicao}"
    )


def _normalizar_metadado(valor: str | None, padrao: re.Pattern[str]) -> str | None:
    if not isinstance(valor, str):
        return None
    normalizado = valor.strip()
    return normalizado if padrao.fullmatch(normalizado) else None


def _validar_metadado_informado(
    valor: str | None,
    padrao: re.Pattern[str],
    nome: str,
) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise TypeError(f"O {nome} deve ser textual.")
    normalizado = valor.strip()
    if not padrao.fullmatch(normalizado):
        raise ValueError(f"O {nome} informado é inválido.")
    return normalizado
