from dataclasses import dataclass
from datetime import datetime
from typing import Literal


PerfilUsuario = Literal["ADMINISTRADOR", "CAIXA"]


@dataclass(frozen=True)
class Usuario:
    id: int
    identificacao_acesso: str
    perfil: PerfilUsuario
    ativo: bool
    criado_em: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, int) or isinstance(self.id, bool) or self.id <= 0:
            raise ValueError("O ID do usuário deve ser um inteiro positivo.")
        if (
            not isinstance(self.identificacao_acesso, str)
            or not self.identificacao_acesso.strip()
        ):
            raise ValueError("A identificação de acesso não pode estar vazia.")
        if self.perfil not in ("ADMINISTRADOR", "CAIXA"):
            raise ValueError("O perfil do usuário é inválido.")
        if not isinstance(self.ativo, bool):
            raise ValueError("A situação do usuário deve ser booleana.")
        if not isinstance(self.criado_em, datetime):
            raise ValueError("A data de criação do usuário é inválida.")
