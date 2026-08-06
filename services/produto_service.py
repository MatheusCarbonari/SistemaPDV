
# categoria, forma_venda, preco_venda_centavos, origem
def criar_produto(codigo, nome):

    codigo_limpo = limpar_codigo(codigo) 
    lista_de_erros = validar_codigo(codigo_limpo)

    nome_limpo = limpar_nome(nome)
    lista_de_erros.extend(validar_nome(nome_limpo))

    if lista_de_erros:
        return None, lista_de_erros
    

    return (codigo_limpo, nome_limpo), []


def validar_codigo(codigo):
    lista_de_erros = []

    if codigo == "":
        lista_de_erros.append("O código é obrigatório.")
    elif not codigo.isdigit():
        lista_de_erros.append("O código deve conter apenas números.")

    return lista_de_erros

def limpar_codigo(codigo):
    if codigo is None:
        return ""
    
    codigo_limpo = codigo.strip()

    return codigo_limpo

def validar_nome(nome):
    lista_de_erros = []

    if nome == "":
        lista_de_erros.append("O nome é obrigatório.")
    elif nome.isdigit():
        lista_de_erros.append("O nome não pode conter apenas números.")

    return lista_de_erros

def limpar_nome(nome):
    if nome is None:
        return ""

    nome_limpo = nome.strip().capitalize()

    return nome_limpo

