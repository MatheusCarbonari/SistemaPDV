from dataclasses import dataclass
import unicodedata


NOME_CATEGORIA_LEGADA = "SEM CATEGORIA (LEGADO)"


@dataclass(frozen=True)
class Categoria:
    id: int
    nome: str
    ativo: bool

    def __post_init__(self) -> None:
        if not isinstance(self.id, int) or isinstance(self.id, bool) or self.id <= 0:
            raise ValueError("O ID da categoria deve ser um inteiro positivo.")
        nome, _ = normalizar_identidade_categoria(self.nome)
        if not nome:
            raise ValueError("O nome da categoria é obrigatório.")
        if not isinstance(self.ativo, bool):
            raise ValueError("A situação da categoria deve ser booleana.")


def normalizar_identidade_categoria(valor) -> tuple[str, str]:
    if not isinstance(valor, str):
        return "", ""
    normalizado = unicodedata.normalize("NFKC", valor)
    nome = " ".join(normalizado.split())
    return nome, nome.casefold()


def validar_nome_categoria(valor) -> tuple[str, str, tuple[str, ...]]:
    nome, chave = normalizar_identidade_categoria(valor)
    erros = []
    if not nome:
        erros.append("O nome da categoria é obrigatório.")
    elif nome.isdigit():
        erros.append("O nome da categoria não pode conter apenas números.")
    return nome, chave, tuple(erros)
