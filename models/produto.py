from dataclasses import dataclass
from datetime import datetime

@dataclass
class Produto:
    codigo: str
    nome: str
    categoria: str
    forma_venda: str
    preco_venda_centavos: int
    origem: str
    ativo: bool = True
    id: int | None = None
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None