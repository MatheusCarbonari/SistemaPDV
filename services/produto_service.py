from models.produto import Produto
from database.conexao import CAMINHO_BANCO
from repositories.produto_repository import codigo_existe


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


# Valida se o código foi informado e contém somente números.
def validar_codigo(codigo):
    lista_de_erros = []

    if codigo == "":
        lista_de_erros.append("O código é obrigatório.")
    elif not codigo.isdigit():
        lista_de_erros.append("O código deve conter apenas números.")

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
