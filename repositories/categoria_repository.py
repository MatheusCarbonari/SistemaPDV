import sqlite3

from database.conexao import CAMINHO_BANCO, conectar
from models.categoria import Categoria


class NomeCategoriaEmUsoError(RuntimeError):
    pass


def listar_categorias_repository(
    caminho_banco=CAMINHO_BANCO,
    *,
    ativo: bool | None = None,
) -> tuple[Categoria, ...]:
    consulta = "SELECT id, nome, ativo FROM categorias"
    parametros = []
    if ativo is not None:
        consulta += " WHERE ativo = ?"
        parametros.append(int(ativo))
    consulta += " ORDER BY nome_chave, id"
    conexao = conectar(caminho_banco)
    try:
        linhas = conexao.execute(consulta, parametros).fetchall()
        return tuple(_montar_categoria(linha) for linha in linhas)
    finally:
        conexao.close()


def buscar_categoria_por_id_repository(
    categoria_id: int,
    caminho_banco=CAMINHO_BANCO,
) -> Categoria | None:
    conexao = conectar(caminho_banco)
    try:
        linha = conexao.execute(
            "SELECT id, nome, ativo FROM categorias WHERE id = ?",
            (categoria_id,),
        ).fetchone()
        return _montar_categoria(linha) if linha is not None else None
    finally:
        conexao.close()


def buscar_categoria_por_chave_repository(
    nome_chave: str,
    caminho_banco=CAMINHO_BANCO,
) -> Categoria | None:
    conexao = conectar(caminho_banco)
    try:
        linha = conexao.execute(
            "SELECT id, nome, ativo FROM categorias WHERE nome_chave = ?",
            (nome_chave,),
        ).fetchone()
        return _montar_categoria(linha) if linha is not None else None
    finally:
        conexao.close()


def criar_categoria_repository(
    nome: str,
    nome_chave: str,
    caminho_banco=CAMINHO_BANCO,
) -> Categoria:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        try:
            cursor = conexao.execute(
                """
                INSERT INTO categorias (nome, nome_chave)
                VALUES (?, ?)
                """,
                (nome, nome_chave),
            )
        except sqlite3.IntegrityError as erro:
            if "categorias.nome_chave" in str(erro):
                raise NomeCategoriaEmUsoError(
                    "Já existe uma categoria com esse nome."
                ) from erro
            raise
        linha = conexao.execute(
            "SELECT id, nome, ativo FROM categorias WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        conexao.commit()
        return _montar_categoria(linha)
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def renomear_categoria_repository(
    categoria_id: int,
    nome: str,
    nome_chave: str,
    caminho_banco=CAMINHO_BANCO,
) -> Categoria | None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        try:
            atualizado = conexao.execute(
                """
                UPDATE categorias
                SET nome = ?, nome_chave = ?
                WHERE id = ?
                """,
                (nome, nome_chave, categoria_id),
            )
        except sqlite3.IntegrityError as erro:
            if "categorias.nome_chave" in str(erro):
                raise NomeCategoriaEmUsoError(
                    "Já existe uma categoria com esse nome."
                ) from erro
            raise
        if atualizado.rowcount != 1:
            conexao.rollback()
            return None
        linha = conexao.execute(
            "SELECT id, nome, ativo FROM categorias WHERE id = ?",
            (categoria_id,),
        ).fetchone()
        conexao.commit()
        return _montar_categoria(linha)
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def alterar_situacao_categoria_repository(
    categoria_id: int,
    ativo: bool,
    caminho_banco=CAMINHO_BANCO,
) -> Categoria | None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        atualizado = conexao.execute(
            "UPDATE categorias SET ativo = ? WHERE id = ?",
            (int(ativo), categoria_id),
        )
        if atualizado.rowcount != 1:
            conexao.rollback()
            return None
        linha = conexao.execute(
            "SELECT id, nome, ativo FROM categorias WHERE id = ?",
            (categoria_id,),
        ).fetchone()
        conexao.commit()
        return _montar_categoria(linha)
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _montar_categoria(linha) -> Categoria:
    return Categoria(
        id=linha["id"],
        nome=linha["nome"],
        ativo=bool(linha["ativo"]),
    )
