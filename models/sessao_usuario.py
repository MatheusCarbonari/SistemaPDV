from dataclasses import dataclass, field

from models.usuario import PerfilUsuario


@dataclass
class SessaoUsuario:
    """Identidade autenticada em memória, sem qualquer dado de senha."""

    usuario_id: int
    identificacao_acesso: str
    perfil: PerfilUsuario
    identificador_sessao: str
    _autenticada: bool = field(default=True, init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.usuario_id, int)
            or isinstance(self.usuario_id, bool)
            or self.usuario_id <= 0
        ):
            raise ValueError("O ID da sessão deve ser um inteiro positivo.")
        if (
            not isinstance(self.identificacao_acesso, str)
            or not self.identificacao_acesso.strip()
        ):
            raise ValueError("A identificação da sessão é obrigatória.")
        if self.perfil not in ("ADMINISTRADOR", "CAIXA"):
            raise ValueError("O perfil da sessão é inválido.")
        if (
            not isinstance(self.identificador_sessao, str)
            or len(self.identificador_sessao) < 32
        ):
            raise ValueError("O identificador da sessão é inválido.")

    @property
    def autenticada(self) -> bool:
        return self._autenticada

    def encerrar(self) -> None:
        self._autenticada = False
