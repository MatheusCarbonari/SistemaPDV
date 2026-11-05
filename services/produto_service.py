from models.produto import Produto
from database.conexao import CAMINHO_BANCO
from repositories.produto_repository import (
    alterar_situacao_produto_repository,
    codigo_existe,
    listar_produtos_repository,
    salvar_produto,
    buscar_produto_banco_pelo_id,
    buscar_produto_por_codigo,
    atualizar_produto_repository
)


# Normaliza e valida os dados antes de criar um produto.
def criar_produto(codigo, nome, categoria, forma_venda, preco_venda_centavos, origem, caminho_banco=CAMINHO_BANCO):

    codigo_limpo = limpar_codigo(codigo) 
    lista_de_erros = validar_codigo(codigo_limpo)

    nome_limpo = limpar_nome(nome)
    lista_de_erros.extend(validar_nome(nome_limpo))

    categoria_limpa = limpar_categoria(categoria)
    lista_de_erros.extend(validar_categoria(categoria_limpa))

    forma_venda_limpa = limpar_forma_venda(forma_venda)
    lista_de_erros.extend(validar_forma_venda(forma_venda_limpa))

    lista_de_erros.extend(validar_preco_venda_centavos(preco_venda_centavos))

    origem_limpa = limpar_origem(origem)
    lista_de_erros.extend(validar_origem(origem_limpa))

    if lista_de_erros:
        return None, lista_de_erros

    # Consulta duplicidade somente depois que os dados básicos são válidos.
    if codigo_existe(codigo_limpo, caminho_banco):
        lista_de_erros.append("Já existe um produto com esse código.")

    if lista_de_erros:
        return None, lista_de_erros
    
    produto = Produto(
        codigo=codigo_limpo,
        nome=nome_limpo,
        categoria=categoria_limpa,
        forma_venda=forma_venda_limpa,
        preco_venda_centavos=preco_venda_centavos,
        origem=origem_limpa,
    )

    return produto, []


# Valida e persiste um novo produto em uma única operação de serviço.
def cadastrar_produto(
    codigo,
    nome,
    categoria,
    forma_venda,
    preco_venda_centavos,
    origem,
    caminho_banco=CAMINHO_BANCO,
):
    produto, erros = criar_produto(
        codigo,
        nome,
        categoria,
        forma_venda,
        preco_venda_centavos,
        origem,
        caminho_banco,
    )
    if erros:
        return None, erros

    return salvar_produto(produto, caminho_banco), []


# Prepara os filtros e solicita ao repository a listagem de produtos.
def listar_produtos(
    ativo: bool | None = True,
    categoria: str | None = None,
    nome: str | None = None,
    caminho_banco=CAMINHO_BANCO,
    termo: str | None = None,
):
    if ativo is not None and not isinstance(ativo, bool):
        return [], ["A situação informada para a listagem é inválida."]

    categoria_limpa = (
        limpar_categoria(categoria) or None
        if categoria is not None
        else None
    )
    nome_limpo = (
        nome.strip() or None
        if nome is not None
        else None
    )
    termo_limpo = termo.strip() or None if termo is not None else None

    produtos = listar_produtos_repository(
        caminho_banco=caminho_banco,
        ativo=ativo,
        categoria=categoria_limpa,
        nome=nome_limpo,
        termo=termo_limpo,
    )

    return produtos, []


# Solicita ao repository a alteração da situação de um produto.
def alterar_situacao_produto(
    produto_id: int,
    ativo: bool,
    caminho_banco=CAMINHO_BANCO,
):
    erros = []

    if (
        not isinstance(produto_id, int)
        or isinstance(produto_id, bool)
        or produto_id <= 0
    ):
        erros.append("O identificador do produto é inválido.")

    if not isinstance(ativo, bool):
        erros.append("A situação do produto é inválida.")

    if erros:
        return False, erros

    foi_atualizado = alterar_situacao_produto_repository(
        produto_id=produto_id,
        ativo=ativo,
        caminho_banco=caminho_banco,
    )

    if not foi_atualizado:
        return False, ["Produto não encontrado."]

    return foi_atualizado, [] ####### devolver produto? para mostrar ao cliente.


# Valida se o código foi informado e contém somente números.
def validar_codigo(codigo):
    lista_de_erros = []

    if codigo == "":
        lista_de_erros.append("O código é obrigatório.")
    elif not codigo.isdigit():
        lista_de_erros.append("O código deve conter apenas números.")
    elif codigo == "9999":
        lista_de_erros.append("O código 9999 é reservado para a função Diversos.")

    return lista_de_erros


# Remove espaços extras e converte valores ausentes em texto vazio.
def limpar_codigo(codigo):
    if codigo is None:
        return ""
    
    codigo_limpo = codigo.strip()

    return codigo_limpo


# Valida se o nome foi informado e não é exclusivamente numérico.
def validar_nome(nome):
    lista_de_erros = []

    if nome == "":
        lista_de_erros.append("O nome é obrigatório.")
    elif nome.isdigit():
        lista_de_erros.append("O nome não pode conter apenas números.")

    return lista_de_erros


# Remove espaços extras e padroniza a capitalização do nome.
def limpar_nome(nome):
    if nome is None:
        return ""

    nome_limpo = nome.strip().capitalize()

    return nome_limpo


# Remove espaços extras e padroniza a categoria em letras maiúsculas.
def limpar_categoria(categoria):
    if categoria is None:
        return ""

    categoria_limpa = categoria.strip().upper()

    return categoria_limpa


# Valida se a categoria foi informada e não é exclusivamente numérica.
def validar_categoria(categoria):
    lista_de_erros = []

    if categoria == "":
        lista_de_erros.append("A categoria é obrigatória.")
    elif categoria.isdigit():
        lista_de_erros.append("A categoria não pode conter apenas números.")

    return lista_de_erros


# Remove espaços extras e padroniza a forma de venda em letras maiúsculas.
def limpar_forma_venda(forma_venda):
    if forma_venda is None:
        return ""

    forma_venda_limpa = forma_venda.strip().upper()

    return forma_venda_limpa


# Restringe a forma de venda aos valores PESO e UNIDADE.
def validar_forma_venda(forma_venda):
    lista_de_erros =[]

    if forma_venda == "":
        lista_de_erros.append("A forma de venda é obrigatória.")
        return lista_de_erros

    if any(caractere.isdigit() for caractere in forma_venda):
        lista_de_erros.append("A forma de venda não permite números.")
        return lista_de_erros

    if forma_venda not in ["PESO", "UNIDADE"]:
        lista_de_erros.append("Forma de venda permite apenas 'PESO' e 'UNIDADE'.")

    return lista_de_erros


# Exige um preço inteiro em centavos e maior que zero.
def validar_preco_venda_centavos(preco_venda_centavos):
    lista_de_erros = []

    if preco_venda_centavos is None:
        lista_de_erros.append("O preço de venda é obrigatório.")
        return lista_de_erros

    if not isinstance(preco_venda_centavos, int):
        lista_de_erros.append("O preço de venda deve ser um número inteiro em centavos.")
        return lista_de_erros

    if preco_venda_centavos <= 0:
        lista_de_erros.append("O preço de venda deve ser maior que zero.")

    return lista_de_erros


# Remove espaços extras e padroniza a origem em letras maiúsculas.
def limpar_origem(origem):
    if origem is None:
        return ""

    origem_limpa = origem.strip().upper()

    return origem_limpa


# Restringe a origem aos valores COMPRADO e PRODUZIDO.
def validar_origem(origem):
    lista_de_erros = []

    if origem == "":
        lista_de_erros.append("A origem do produto é obrigatória.")
        return lista_de_erros

    if any(caractere.isdigit() for caractere in origem):
        lista_de_erros.append("A origem do produto não permite números.")
        return lista_de_erros

    if origem not in ["COMPRADO", "PRODUZIDO"]:
        lista_de_erros.append("A origem do produto permite apenas 'COMPRADO' e 'PRODUZIDO'.")

    return lista_de_erros


def atualizar_produto(
    produto_id,
    codigo,
    nome,
    categoria,
    forma_venda,
    preco_venda_centavos,
    origem,
    caminho_banco=CAMINHO_BANCO, 
):
    produto_atual = buscar_produto_banco_pelo_id(
        produto_id,
        caminho_banco,
    )

    if produto_atual is None:
        return None, ["Produto não encontrado."]

    codigo_limpo = limpar_codigo(codigo)
    nome_limpo = limpar_nome(nome)
    categoria_limpa = limpar_categoria(categoria)
    forma_venda_limpa = limpar_forma_venda(forma_venda)
    origem_limpa = limpar_origem(origem)

    lista_de_erros = []

    lista_de_erros.extend(validar_codigo(codigo_limpo))
    lista_de_erros.extend(validar_nome(nome_limpo))
    lista_de_erros.extend(validar_categoria(categoria_limpa))
    lista_de_erros.extend(validar_forma_venda(forma_venda_limpa))
    lista_de_erros.extend(validar_origem(origem_limpa))
    lista_de_erros.extend(validar_preco_venda_centavos(preco_venda_centavos))

    if lista_de_erros:
        return None, lista_de_erros

    produto_com_mesmo_codigo = buscar_produto_por_codigo(
        codigo_limpo,
        caminho_banco
    )

    if(
        produto_com_mesmo_codigo is not None
        and produto_com_mesmo_codigo.id != produto_id
    ):
        return None, ["Já existe outro produto com esse código."]

    produto_atualizado = Produto(
        id=produto_id,
        codigo=codigo_limpo,
        nome=nome_limpo,
        categoria=categoria_limpa,
        forma_venda=forma_venda_limpa,
        preco_venda_centavos=preco_venda_centavos,
        origem=origem_limpa,
    )

    produto_salvo = atualizar_produto_repository(
        produto_atualizado,
        caminho_banco
    )

    if produto_salvo is None:
        return None, ["Não foi possivel atualizar o produto."]

    return produto_salvo, []


def consultar_produto_por_codigo(
        codigo,
        caminho_banco=CAMINHO_BANCO
):
    codigo_limpo = limpar_codigo(codigo)
    erros_codigo = validar_codigo(codigo_limpo)

    if erros_codigo:
        return None, erros_codigo

    produto_buscado = buscar_produto_por_codigo(codigo_limpo, caminho_banco)

    if produto_buscado is None:
        return None, ["Produto não encontrado."]

    return produto_buscado, []
