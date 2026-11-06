from dataclasses import asdict, dataclass
import hashlib
import json


OPERACAO_CADASTRAR_PRODUTO = "CADASTRAR_PRODUTO"
OPERACAO_EDITAR_PRODUTO = "EDITAR_PRODUTO"
RECURSO_CATALOGO_PRODUTOS = 1
VERSAO_COMANDO_PRODUTO = 1


@dataclass(frozen=True)
class CategoriaAprovada:
    id: int
    nome: str
    nome_chave: str
    ativo: bool


@dataclass(frozen=True)
class EstadoBaseProduto:
    id: int
    codigo: str
    nome: str
    categoria: CategoriaAprovada
    forma_venda: str
    preco_venda_centavos: int
    origem: str
    ativo: bool


@dataclass(frozen=True)
class ComandoCadastroProduto:
    codigo: str
    nome: str
    categoria: CategoriaAprovada
    forma_venda: str
    preco_venda_centavos: int
    origem: str

    @property
    def operacao(self) -> str:
        return OPERACAO_CADASTRAR_PRODUTO

    @property
    def recurso_id(self) -> int:
        return RECURSO_CATALOGO_PRODUTOS

    @property
    def dados_autorizados_hash(self) -> str:
        return calcular_hash_comando_produto(self)


@dataclass(frozen=True)
class ComandoEdicaoProduto:
    estado_base: EstadoBaseProduto
    nome: str
    categoria: CategoriaAprovada
    forma_venda: str
    preco_venda_centavos: int
    origem: str

    @property
    def operacao(self) -> str:
        return OPERACAO_EDITAR_PRODUTO

    @property
    def recurso_id(self) -> int:
        return self.estado_base.id

    @property
    def dados_autorizados_hash(self) -> str:
        return calcular_hash_comando_produto(self)


ComandoProduto = ComandoCadastroProduto | ComandoEdicaoProduto


def calcular_hash_comando_produto(comando: ComandoProduto) -> str:
    if not isinstance(comando, (ComandoCadastroProduto, ComandoEdicaoProduto)):
        raise TypeError("O comando de produto é inválido.")
    representacao = {
        "versao": VERSAO_COMANDO_PRODUTO,
        "operacao": comando.operacao,
        "recurso_id": comando.recurso_id,
        "dados": asdict(comando),
    }
    canonico = json.dumps(
        representacao,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonico).hexdigest()
