import base64
import binascii
import hashlib
import hmac
import secrets


ALGORITMO = "scrypt"
VERSAO_FORMATO = 1
PARAMETRO_N = 2**14
PARAMETRO_R = 8
PARAMETRO_P = 5
TAMANHO_SALT = 16
TAMANHO_CHAVE = 32
LIMITE_MEMORIA = 32 * 1024 * 1024


def gerar_hash_senha(senha: str) -> str:
    if not isinstance(senha, str):
        raise TypeError("A senha deve ser textual.")
    salt = secrets.token_bytes(TAMANHO_SALT)
    derivada = _derivar(senha, salt)
    parametros = (
        f"n={PARAMETRO_N},r={PARAMETRO_R},p={PARAMETRO_P},"
        f"dklen={TAMANHO_CHAVE}"
    )
    return "$".join(
        (
            ALGORITMO,
            f"v={VERSAO_FORMATO}",
            parametros,
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derivada).decode("ascii"),
        )
    )


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    if not isinstance(senha, str) or not isinstance(hash_armazenado, str):
        return False
    try:
        partes = hash_armazenado.split("$")
        if len(partes) != 5 or partes[0] != ALGORITMO:
            return False
        if partes[1] != f"v={VERSAO_FORMATO}":
            return False
        parametros = _ler_parametros(partes[2])
        if parametros != {
            "n": PARAMETRO_N,
            "r": PARAMETRO_R,
            "p": PARAMETRO_P,
            "dklen": TAMANHO_CHAVE,
        }:
            return False
        salt = base64.b64decode(partes[3], validate=True)
        esperado = base64.b64decode(partes[4], validate=True)
        if len(salt) != TAMANHO_SALT or len(esperado) != TAMANHO_CHAVE:
            return False
        calculado = _derivar(senha, salt)
    except (ValueError, TypeError, binascii.Error, OverflowError):
        return False
    return hmac.compare_digest(calculado, esperado)


def _ler_parametros(texto: str) -> dict[str, int]:
    parametros = {}
    for parte in texto.split(","):
        nome, separador, valor = parte.partition("=")
        if not separador or nome in parametros:
            raise ValueError("Parâmetros inválidos.")
        parametros[nome] = int(valor)
    return parametros


def _derivar(senha: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"),
        salt=salt,
        n=PARAMETRO_N,
        r=PARAMETRO_R,
        p=PARAMETRO_P,
        dklen=TAMANHO_CHAVE,
        maxmem=LIMITE_MEMORIA,
    )
