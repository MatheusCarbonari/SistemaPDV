"""Snapshot imutável do catálogo essencial de produtos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Mapping

from database.conexao import CAMINHO_BANCO
from models.produto import Produto
from repositories.produto_repository import listar_produtos_repository


CATALOGO_DESCONHECIDO = "DESCONHECIDO"
CATALOGO_DISPONIVEL = "DISPONIVEL"
CATALOGO_INDISPONIVEL = "INDISPONIVEL"


class CatalogoIndisponivelError(RuntimeError):
    pass


class CatalogoInconsistenteError(RuntimeError):
    pass


class CatalogoBancoDivergenteError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProdutoCatalogo:
    """Dados comerciais mínimos preservados pelo catálogo em memória."""

    id: int
    codigo: str
    nome: str
    forma_venda: str
    preco_venda_centavos: int
    ativo: bool


@dataclass(frozen=True, slots=True)
class EstadoCatalogo:
    status: str
    geracao: int
    quantidade_produtos: int
    carregado_em: datetime | None
    motivo_indisponibilidade: str | None


@dataclass(frozen=True, slots=True)
class _SnapshotCatalogo:
    geracao: int
    carregado_em: datetime
    produtos_por_codigo: Mapping[str, ProdutoCatalogo]


@dataclass(frozen=True, slots=True)
class _IdentidadeBanco:
    caminho_resolvido: Path
    chave_normalizada: str

    def corresponde(self, outra: _IdentidadeBanco) -> bool:
        if self.chave_normalizada == outra.chave_normalizada:
            return True
        try:
            return os.path.samefile(
                self.caminho_resolvido,
                outra.caminho_resolvido,
            )
        except OSError:
            return False


class CatalogoProdutosMemoria:
    """Publica snapshots integrais; nunca mantém uma carga parcial ou antiga."""

    def __init__(self) -> None:
        self._bloqueio = RLock()
        self._snapshot: _SnapshotCatalogo | None = None
        self._geracao = 0
        self._status = CATALOGO_DESCONHECIDO
        self._motivo_indisponibilidade: str | None = None
        self._identidade_banco: _IdentidadeBanco | None = None

    def carregar(
        self,
        caminho_banco: str | Path = CAMINHO_BANCO,
    ) -> EstadoCatalogo:
        """Lê o SQLite uma vez e publica somente depois de validar tudo."""
        with self._bloqueio:
            self.vincular_ou_validar_banco(caminho_banco)
            try:
                produtos = listar_produtos_repository(
                    caminho_banco=caminho_banco,
                    ativo=None,
                )
                entradas = self._construir_entradas(produtos)
            except Exception as erro:
                self.invalidar(f"FALHA_CARGA:{type(erro).__name__}")
                raise

            self._geracao += 1
            self._snapshot = _SnapshotCatalogo(
                geracao=self._geracao,
                carregado_em=datetime.now(UTC),
                produtos_por_codigo=MappingProxyType(entradas),
            )
            self._status = CATALOGO_DISPONIVEL
            self._motivo_indisponibilidade = None
            return self._estado_sem_bloquear()

    def atualizar_apos_mutacao(
        self,
        caminho_banco: str | Path = CAMINHO_BANCO,
    ) -> bool:
        """Recarrega tudo; uma falha invalida o snapshot em vez de envelhecê-lo."""
        self.vincular_ou_validar_banco(caminho_banco)
        self.invalidar("ATUALIZACAO_EM_ANDAMENTO")
        try:
            self.carregar(caminho_banco)
        except Exception:
            return False
        return True

    def invalidar(self, motivo: str = "INVALIDADO") -> None:
        """Descarta qualquer snapshot para impedir uso silencioso de dados antigos."""
        with self._bloqueio:
            self._snapshot = None
            self._status = CATALOGO_INDISPONIVEL
            self._motivo_indisponibilidade = motivo

    def obter_estado(self) -> EstadoCatalogo:
        with self._bloqueio:
            return self._estado_sem_bloquear()

    def vincular_ou_validar_banco(
        self,
        caminho_banco: str | Path,
    ) -> None:
        """Vincula uma vez e rejeita outra origem sem expor seu caminho."""
        identidade = _identificar_banco(caminho_banco)
        with self._bloqueio:
            if self._identidade_banco is None:
                self._identidade_banco = identidade
                return
            if not self._identidade_banco.corresponde(identidade):
                raise CatalogoBancoDivergenteError(
                    "O catálogo em memória pertence a outro banco SQLite."
                )

    def consultar_produto(self, codigo: str) -> ProdutoCatalogo | None:
        """Consulta explicitamente o snapshot imutável pelo código exato."""
        if not isinstance(codigo, str):
            raise TypeError("O código do produto deve ser texto.")
        with self._bloqueio:
            snapshot = self._exigir_snapshot_sem_bloquear()
            return snapshot.produtos_por_codigo.get(codigo)

    def listar_entradas(self) -> tuple[ProdutoCatalogo, ...]:
        """Expõe valores imutáveis, sem entregar o mapa interno."""
        with self._bloqueio:
            snapshot = self._exigir_snapshot_sem_bloquear()
            return tuple(snapshot.produtos_por_codigo.values())

    def _construir_entradas(
        self,
        produtos: list[Produto],
    ) -> dict[str, ProdutoCatalogo]:
        entradas: dict[str, ProdutoCatalogo] = {}
        for produto in produtos:
            entrada = _criar_entrada_validada(produto)
            if entrada.codigo in entradas:
                raise CatalogoInconsistenteError(
                    "O catálogo contém códigos de produto duplicados."
                )
            entradas[entrada.codigo] = entrada
        return entradas

    def _exigir_snapshot_sem_bloquear(self) -> _SnapshotCatalogo:
        if self._status != CATALOGO_DISPONIVEL or self._snapshot is None:
            raise CatalogoIndisponivelError(
                "O catálogo em memória não está disponível para consulta."
            )
        return self._snapshot

    def _estado_sem_bloquear(self) -> EstadoCatalogo:
        snapshot = self._snapshot
        return EstadoCatalogo(
            status=self._status,
            geracao=self._geracao,
            quantidade_produtos=(
                len(snapshot.produtos_por_codigo) if snapshot is not None else 0
            ),
            carregado_em=(snapshot.carregado_em if snapshot is not None else None),
            motivo_indisponibilidade=self._motivo_indisponibilidade,
        )


def _criar_entrada_validada(produto: Produto) -> ProdutoCatalogo:
    if not isinstance(produto, Produto):
        raise CatalogoInconsistenteError("O catálogo retornou um produto inválido.")
    if (
        not isinstance(produto.id, int)
        or isinstance(produto.id, bool)
        or produto.id <= 0
        or not isinstance(produto.codigo, str)
        or not produto.codigo
        or not isinstance(produto.nome, str)
        or not produto.nome
        or produto.forma_venda not in {"PESO", "UNIDADE"}
        or not isinstance(produto.preco_venda_centavos, int)
        or isinstance(produto.preco_venda_centavos, bool)
        or produto.preco_venda_centavos <= 0
        or not isinstance(produto.ativo, bool)
    ):
        raise CatalogoInconsistenteError(
            "O catálogo contém dados comerciais inconsistentes."
        )
    return ProdutoCatalogo(
        id=produto.id,
        codigo=produto.codigo,
        nome=produto.nome,
        forma_venda=produto.forma_venda,
        preco_venda_centavos=produto.preco_venda_centavos,
        ativo=produto.ativo,
    )


def _identificar_banco(caminho_banco: str | Path) -> _IdentidadeBanco:
    if not isinstance(caminho_banco, (str, Path)):
        raise TypeError("O caminho do banco deve ser texto ou Path.")
    try:
        resolvido = Path(caminho_banco).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as erro:
        raise ValueError("Não foi possível identificar o banco SQLite.") from erro
    return _IdentidadeBanco(
        caminho_resolvido=resolvido,
        chave_normalizada=os.path.normcase(os.fspath(resolvido)),
    )
