from dataclasses import dataclass
from datetime import datetime


# Representa um produto usado pelas demais camadas do sistema.
@dataclass
class Produto:
    # Dados informados durante o cadastro.
    codigo: str
    nome: str
    categoria: str
    forma_venda: str
    preco_venda_centavos: int
    origem: str

    # Dados controlados pelo sistema e pelo banco.
    ativo: bool = True
    id: int | None = None
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
    categoria_id: int | None = None
