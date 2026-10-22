import sqlite3

from database.schema import criar_tabelas
from models.produto import Produto
from repositories.produto_repository import salvar_produto
from services import produto_service
from services.produto_service import criar_produto, atualizar_produto
from database.schema import criar_tabelas


# Cenário válido e normalização dos dados.
def test_criar_produto(tmp_path) -> None:

    caminho_banco = tmp_path / "teste_produto_service.db"

    criar_tabelas(caminho_banco)

    produto, erros = criar_produto(
        codigo=" 101 ",
        nome=" picanha ",
        categoria=" bovinos ",
        forma_venda=" peso ",
        preco_venda_centavos=7990,
        origem=" comprado ",
        caminho_banco=caminho_banco,
    )

    assert erros == []
    assert produto.codigo == "101"
    assert produto.nome == "Picanha"
    assert produto.categoria == "BOVINOS"
    assert produto.forma_venda == "PESO"
    assert produto.preco_venda_centavos == 7990
    assert produto.origem == "COMPRADO"


# Validações do código.
def test_criar_produto_com_codigo_vazio() -> None:
    produto, erros = criar_produto(
        codigo="",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O código é obrigatório." in erros


def test_criar_produto_com_codigo_nao_numerico() -> None:
    produto, erros = criar_produto(
        codigo="ABC",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O código deve conter apenas números." in erros


# Validações do nome.
def test_criar_produto_com_nome_vazio() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O nome é obrigatório." in erros


# Confirma que a limpeza transforma espaços em código vazio.
def test_criar_produto_com_codigo_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="   ",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O código é obrigatório." in erros


# Validações adicionais do nome após a limpeza.
def test_criar_produto_com_nome_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="   ",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O nome é obrigatório." in erros


def test_criar_produto_com_nome_apenas_numeros() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="123",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O nome não pode conter apenas números." in erros


# Validações da categoria.
def test_criar_produto_com_categoria_vazia() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A categoria é obrigatória." in erros


def test_criar_produto_com_categoria_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="   ",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A categoria é obrigatória." in erros


def test_criar_produto_com_categoria_apenas_numeros() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="123",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A categoria não pode conter apenas números." in erros


# Validações da forma de venda.
def test_criar_produto_com_forma_venda_vazia() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A forma de venda é obrigatória." in erros


def test_criar_produto_com_forma_venda_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="   ",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A forma de venda é obrigatória." in erros


def test_criar_produto_com_forma_venda_contendo_numero() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO2",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A forma de venda não permite números." in erros


def test_criar_produto_com_forma_venda_invalida() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="CAIXA",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "Forma de venda permite apenas 'PESO' e 'UNIDADE'." in erros


# Validações do preço em centavos.
def test_criar_produto_com_preco_none() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=None,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda é obrigatório." in erros


def test_criar_produto_com_preco_texto() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos="7990",
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser um número inteiro em centavos." in erros


def test_criar_produto_com_preco_decimal() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=79.90,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser um número inteiro em centavos." in erros


def test_criar_produto_com_preco_zero() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=0,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser maior que zero." in erros


def test_criar_produto_com_preco_negativo() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=-100,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser maior que zero." in erros


# Validações da origem do produto.
def test_criar_produto_com_origem_vazia() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="",
    )

    assert produto is None
    assert "A origem do produto é obrigatória." in erros


def test_criar_produto_com_origem_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="   ",
    )

    assert produto is None
    assert "A origem do produto é obrigatória." in erros


def test_criar_produto_com_origem_contendo_numero() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO2",
    )

    assert produto is None
    assert "A origem do produto não permite números." in erros


def test_criar_produto_com_origem_invalida() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="IMPORTADO",
    )

    assert produto is None
    assert "A origem do produto permite apenas 'COMPRADO' e 'PRODUZIDO'." in erros


# Garante que o serviço rejeite um código já persistido no banco.
def test_criar_produto_retorna_erro_quando_codigo_ja_existe(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"

    criar_tabelas(caminho_banco)

    conexao = sqlite3.connect(caminho_banco)

    try:
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo,
                nome,
                categoria,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "101",
                "Picanha",
                "BOVINOS",
                "PESO",
                7990,
                "COMPRADO",
            ),
        )

        conexao.commit()
    finally:
        conexao.close()

    produto, erros = criar_produto(
        codigo="101",
        nome="Alcatra",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=6990,
        origem="COMPRADO",
        caminho_banco=caminho_banco,
    )

    assert produto is None
    assert "Já existe um produto com esse código." in erros


# Confirma que o service padroniza a categoria antes de consultar o repository.
def test_listar_produtos_service_padroniza_categoria(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_listagem_produto_service.db"

    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto(
            codigo="201",
            nome="Alcatra",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=6990,
            origem="COMPRADO",
        ),
        caminho_banco,
    )
    salvar_produto(
        Produto(
            codigo="202",
            nome="Coxa de frango",
            categoria="AVES",
            forma_venda="PESO",
            preco_venda_centavos=1890,
            origem="COMPRADO",
        ),
        caminho_banco,
    )

    produtos, erros = produto_service.listar_produtos(
        categoria="  bovinos  ",
        caminho_banco=caminho_banco,
    )

    assert erros == []
    assert [produto.codigo for produto in produtos] == ["201"]


# Confirma que espaços externos não interferem na busca parcial pelo nome.
def test_listar_produtos_service_limpa_filtro_de_nome(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_listagem_produto_service.db"

    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto(
            codigo="203",
            nome="Alcatra",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=6990,
            origem="COMPRADO",
        ),
        caminho_banco,
    )
    salvar_produto(
        Produto(
            codigo="204",
            nome="Acem",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=3990,
            origem="COMPRADO",
        ),
        caminho_banco,
    )

    produtos, erros = produto_service.listar_produtos(
        nome="  catr  ",
        caminho_banco=caminho_banco,
    )

    assert erros == []
    assert [produto.codigo for produto in produtos] == ["203"]


# Trata um nome composto apenas por espaços como ausência do filtro.
def test_listar_produtos_service_ignora_nome_vazio(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_listagem_produto_service.db"

    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto(
            codigo="205",
            nome="Alcatra",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=6990,
            origem="COMPRADO",
        ),
        caminho_banco,
    )
    salvar_produto(
        Produto(
            codigo="206",
            nome="Coxa de frango",
            categoria="AVES",
            forma_venda="PESO",
            preco_venda_centavos=1890,
            origem="COMPRADO",
        ),
        caminho_banco,
    )

    produtos, erros = produto_service.listar_produtos(
        nome="   ",
        caminho_banco=caminho_banco,
    )

    assert erros == []
    assert [produto.codigo for produto in produtos] == ["205", "206"]


# Trata uma categoria composta apenas por espaços como ausência do filtro.
def test_listar_produtos_service_ignora_categoria_vazia(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_listagem_produto_service.db"

    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto(
            codigo="207",
            nome="Alcatra",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=6990,
            origem="COMPRADO",
        ),
        caminho_banco,
    )
    salvar_produto(
        Produto(
            codigo="208",
            nome="Coxa de frango",
            categoria="AVES",
            forma_venda="PESO",
            preco_venda_centavos=1890,
            origem="COMPRADO",
        ),
        caminho_banco,
    )

    produtos, erros = produto_service.listar_produtos(
        categoria="   ",
        caminho_banco=caminho_banco,
    )

    assert erros == []
    assert [produto.codigo for produto in produtos] == ["207", "208"]


# Considera normal uma consulta válida que não encontra produtos.
def test_listar_produtos_service_retorna_lista_vazia_quando_banco_esta_vazio(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_listagem_produto_service.db"

    criar_tabelas(caminho_banco)

    produtos, erros = produto_service.listar_produtos(
        caminho_banco=caminho_banco,
    )

    assert produtos == []
    assert erros == []


# Impede que valores diferentes de True, False ou None cheguem ao repository.
def test_listar_produtos_service_rejeita_ativo_invalido(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_listagem_produto_service.db"

    criar_tabelas(caminho_banco)

    produtos, erros = produto_service.listar_produtos(
        ativo="ATIVOS",
        caminho_banco=caminho_banco,
    )

    assert produtos == []
    assert erros == ["A situação informada para a listagem é inválida."]


# Confirma que o service solicita a inativação de um produto existente.
def test_alterar_situacao_produto_service_inativa_produto_existente(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    produto = salvar_produto(
        Produto("209", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )

    foi_atualizado, erros = produto_service.alterar_situacao_produto(
        produto_id=produto.id,
        ativo=False,
        caminho_banco=caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        situacao_salva = conexao.execute(
            "SELECT ativo FROM produtos WHERE id = ?",
            (produto.id,),
        ).fetchone()
    finally:
        conexao.close()

    assert foi_atualizado is True
    assert erros == []
    assert situacao_salva[0] == 0


# Impede que um identificador inválido seja enviado ao repository.
def test_alterar_situacao_produto_service_rejeita_id_invalido(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    foi_atualizado, erros = produto_service.alterar_situacao_produto(
        produto_id="1",
        ativo=False,
        caminho_banco=caminho_banco,
    )

    assert foi_atualizado is False
    assert erros == ["O identificador do produto é inválido."]


# Impede que uma situação diferente de True ou False chegue ao repository.
def test_alterar_situacao_produto_service_rejeita_ativo_invalido(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    foi_atualizado, erros = produto_service.alterar_situacao_produto(
        produto_id=1,
        ativo=None,
        caminho_banco=caminho_banco,
    )

    assert foi_atualizado is False
    assert erros == ["A situação do produto é inválida."]


# Informa quando os dados são válidos, mas o produto não existe.
def test_alterar_situacao_produto_service_retorna_erro_para_id_inexistente(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    foi_atualizado, erros = produto_service.alterar_situacao_produto(
        produto_id=999,
        ativo=False,
        caminho_banco=caminho_banco,
    )

    assert foi_atualizado is False
    assert erros == ["Produto não encontrado."]


def test_atualizar_produto_com_dados_validos(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    produto_salvo = salvar_produto(produto, caminho_banco)

    produto_atualizado, erros = atualizar_produto(
        produto_id=produto_salvo.id,
        codigo=" 101 ",
        nome=" picanha maturada ",
        categoria=" bovinos ",
        forma_venda=" peso ",
        preco_venda_centavos=8490,
        origem=" comprado ",
        caminho_banco=caminho_banco,
    )

    assert erros == []
    assert produto_atualizado is not None
    assert produto_atualizado.id == produto_salvo.id
    assert produto_atualizado.codigo == "101"
    assert produto_atualizado.nome == "Picanha maturada"
    assert produto_atualizado.categoria == "BOVINOS"
    assert produto_atualizado.forma_venda == "PESO"
    assert produto_atualizado.preco_venda_centavos == 8490
    assert produto_atualizado.origem == "COMPRADO"


def test_atualizar_produto_retorna_erro_quando_produto_nao_existe(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    produto_atualizado, erros = atualizar_produto(
        produto_id=999,
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
        caminho_banco=caminho_banco,
    )

    assert produto_atualizado is None
    assert "Produto não encontrado." in erros


def test_atualizar_produto_retorna_erro_quando_codigo_pertence_a_outro_produto(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    produto_1 = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    produto_2 = Produto(
        codigo="202",
        nome="Alcatra",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=6990,
        origem="COMPRADO",
    )

    produto_1_salvo = salvar_produto(produto_1, caminho_banco)
    produto_2_salvo = salvar_produto(produto_2, caminho_banco)

    produto_atualizado, erros = atualizar_produto(
        produto_id=produto_2_salvo.id,
        codigo=produto_1_salvo.codigo,
        nome="Alcatra",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=6990,
        origem="COMPRADO",
        caminho_banco=caminho_banco,
    )

    assert produto_atualizado is None
    assert "Já existe outro produto com esse código." in erros


def test_atualizar_produto_retorna_erro_quando_preco_invalido(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    produto_salvo = salvar_produto(produto, caminho_banco)

    produto_atualizado, erros = atualizar_produto(
        produto_id=produto_salvo.id,
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=0,
        origem="COMPRADO",
        caminho_banco=caminho_banco,
    )

    assert produto_atualizado is None
    assert "O preço de venda deve ser maior que zero." in erros


def test_atualizar_produto_retorna_erro_quando_forma_venda_invalida(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_service.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    produto_salvo = salvar_produto(produto, caminho_banco)

    produto_atualizado, erros = atualizar_produto(
        produto_id=produto_salvo.id,
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="a prazo",
        preco_venda_centavos=7990,
        origem="COMPRADO",
        caminho_banco=caminho_banco,
    )

    assert produto_atualizado is None
    assert "Forma de venda permite apenas 'PESO' e 'UNIDADE'." in erros