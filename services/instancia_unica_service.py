"""Exclusividade processual do Sistema-PDV baseada em mutex do Windows."""

from __future__ import annotations

from contextlib import AbstractContextManager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
from typing import Protocol

from services.contexto_instalacao_service import (
    ContextoInstalacao,
    GRUPO_OPERADORES,
)


WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080
WAIT_TIMEOUT = 0x00000102
INFINITE_ZERO = 0
ERROR_INSUFFICIENT_BUFFER = 122
SYNCHRONIZE = 0x00100000
MUTEX_MODIFY_STATE = 0x0001


class InstanciaUnicaError(RuntimeError):
    pass


class InstanciaJaExecutandoError(InstanciaUnicaError):
    pass


class SegurancaMutexError(InstanciaUnicaError):
    pass


class BackendMutex(Protocol):
    def adquirir(
        self,
        nome: str,
        *,
        grupo_operadores: str | None,
    ) -> tuple[object, bool]: ...

    def liberar(self, recurso: object) -> None: ...


@dataclass(frozen=True, slots=True)
class EstadoExclusividade:
    nome: str
    mutex_abandonado: bool


class ExclusividadeInstancia(AbstractContextManager[EstadoExclusividade]):
    def __init__(
        self,
        contexto: ContextoInstalacao,
        *,
        backend: BackendMutex | None = None,
    ) -> None:
        self._contexto = contexto
        self._backend = backend or BackendMutexWindows()
        self._recursos: list[object] = []
        self._estado: EstadoExclusividade | None = None

    def __enter__(self) -> EstadoExclusividade:
        nome_instalacao = criar_nome_mutex(self._contexto)
        nomes = (
            (criar_nome_mutex_ambiente(self._contexto), nome_instalacao)
            if self._contexto.comercial
            else (nome_instalacao,)
        )
        abandonado = False
        try:
            for nome in nomes:
                recurso, mutex_abandonado = self._backend.adquirir(
                    nome,
                    grupo_operadores=(
                        GRUPO_OPERADORES if self._contexto.comercial else None
                    ),
                )
                self._recursos.append(recurso)
                abandonado = abandonado or mutex_abandonado
        except BaseException:
            self._liberar_recursos()
            raise
        self._estado = EstadoExclusividade(nome_instalacao, abandonado)
        return self._estado

    def __exit__(self, tipo, valor, traceback) -> None:
        self._liberar_recursos()
        return None

    def _liberar_recursos(self) -> None:
        while self._recursos:
            self._backend.liberar(self._recursos.pop())


def adquirir_instancia_unica(
    contexto: ContextoInstalacao,
    *,
    backend: BackendMutex | None = None,
) -> ExclusividadeInstancia:
    return ExclusividadeInstancia(contexto, backend=backend)


def criar_nome_mutex(contexto: ContextoInstalacao) -> str:
    if contexto.comercial:
        return (
            "Global\\Sistema-PDV-"
            f"{contexto.produto_id}-{contexto.ambiente_id}-"
            f"{contexto.instalacao_id}"
        )
    material = str(contexto.raiz_instalacao).casefold().encode("utf-8")
    identificador = hashlib.sha256(material).hexdigest()[:24]
    return f"Local\\Sistema-PDV-Desenvolvimento-{identificador}"


def criar_nome_mutex_ambiente(contexto: ContextoInstalacao) -> str:
    if not contexto.comercial:
        raise ValueError("O mutex de ambiente existe somente na instalação comercial.")
    return f"Global\\Sistema-PDV-{contexto.produto_id}-{contexto.ambiente_id}"


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class BackendMutexWindows:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise InstanciaUnicaError(
                "O mutex de instância única exige o runtime Windows."
            )
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._kernel32.CreateMutexExW.argtypes = (
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        self._kernel32.CreateMutexExW.restype = wintypes.HANDLE
        self._kernel32.WaitForSingleObject.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
        )
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        self._kernel32.ReleaseMutex.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.LocalFree.argtypes = (wintypes.LPVOID,)
        self._kernel32.LocalFree.restype = wintypes.LPVOID

    def adquirir(
        self,
        nome: str,
        *,
        grupo_operadores: str | None,
    ) -> tuple[object, bool]:
        descritor = None
        atributos = None
        try:
            if grupo_operadores is not None:
                descritor = self._criar_descritor_seguranca(grupo_operadores)
                atributos = _SECURITY_ATTRIBUTES(
                    ctypes.sizeof(_SECURITY_ATTRIBUTES),
                    descritor,
                    False,
                )
            handle = self._kernel32.CreateMutexExW(
                ctypes.byref(atributos) if atributos is not None else None,
                nome,
                0,
                SYNCHRONIZE | MUTEX_MODIFY_STATE,
            )
            if not handle:
                raise SegurancaMutexError(
                    "Não foi possível criar ou abrir o mutex da instalação."
                )
            resultado = self._kernel32.WaitForSingleObject(
                handle,
                INFINITE_ZERO,
            )
            if resultado == WAIT_TIMEOUT:
                self._kernel32.CloseHandle(handle)
                raise InstanciaJaExecutandoError(
                    "O Sistema-PDV já está em execução nesta instalação."
                )
            if resultado not in {WAIT_OBJECT_0, WAIT_ABANDONED}:
                self._kernel32.CloseHandle(handle)
                raise InstanciaUnicaError(
                    "Não foi possível adquirir a exclusividade da instalação."
                )
            return handle, resultado == WAIT_ABANDONED
        finally:
            if descritor:
                self._kernel32.LocalFree(descritor)

    def liberar(self, recurso: object) -> None:
        handle = recurso
        try:
            self._kernel32.ReleaseMutex(handle)
        finally:
            self._kernel32.CloseHandle(handle)

    def _criar_descritor_seguranca(self, grupo: str) -> wintypes.LPVOID:
        sid_textual = self._resolver_sid(grupo)
        mascara_operador = SYNCHRONIZE | MUTEX_MODIFY_STATE
        sddl = (
            "D:P"
            "(A;;GA;;;SY)"
            "(A;;GA;;;BA)"
            f"(A;;0x{mascara_operador:08x};;;{sid_textual})"
        )
        converter = self._advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        converter.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.DWORD),
        )
        converter.restype = wintypes.BOOL
        descritor = wintypes.LPVOID()
        if not converter(sddl, 1, ctypes.byref(descritor), None):
            raise SegurancaMutexError(
                "Não foi possível aplicar a ACL do mutex da instalação."
            )
        return descritor

    def _resolver_sid(self, conta: str) -> str:
        lookup = self._advapi32.LookupAccountNameW
        lookup.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        )
        lookup.restype = wintypes.BOOL
        tamanho_sid = wintypes.DWORD(0)
        tamanho_dominio = wintypes.DWORD(0)
        uso = wintypes.DWORD(0)
        lookup(
            None,
            conta,
            None,
            ctypes.byref(tamanho_sid),
            None,
            ctypes.byref(tamanho_dominio),
            ctypes.byref(uso),
        )
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
            raise SegurancaMutexError(
                "O grupo local de operadores não está disponível."
            )
        sid = ctypes.create_string_buffer(tamanho_sid.value)
        dominio = ctypes.create_unicode_buffer(tamanho_dominio.value)
        if not lookup(
            None,
            conta,
            sid,
            ctypes.byref(tamanho_sid),
            dominio,
            ctypes.byref(tamanho_dominio),
            ctypes.byref(uso),
        ):
            raise SegurancaMutexError(
                "O grupo local de operadores não pôde ser validado."
            )
        converter_sid = self._advapi32.ConvertSidToStringSidW
        converter_sid.argtypes = (wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR))
        converter_sid.restype = wintypes.BOOL
        texto = wintypes.LPWSTR()
        if not converter_sid(sid, ctypes.byref(texto)):
            raise SegurancaMutexError(
                "O SID do grupo local de operadores não pôde ser validado."
            )
        try:
            return texto.value
        finally:
            self._kernel32.LocalFree(texto)


def exibir_aviso_segunda_instancia() -> None:
    _exibir_mensagem_windows(
        "Sistema-PDV já está em execução",
        "Já existe uma instância desta instalação em execução. "
        "Feche a janela existente antes de tentar novamente.",
        icone=0x30,
    )


def exibir_erro_inicializacao_segura(mensagem: str) -> None:
    _exibir_mensagem_windows(
        "Sistema-PDV não pôde iniciar",
        mensagem,
        icone=0x10,
    )


def _exibir_mensagem_windows(titulo: str, mensagem: str, *, icone: int) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, mensagem, titulo, icone | 0x1000)
    else:
        print(f"{titulo}: {mensagem}", file=sys.stderr)
