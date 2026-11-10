from models.produto import Produto
from models.comando_produto import (
    CategoriaAprovada,
    ComandoCadastroProduto,
    ComandoEdicaoProduto,
    EstadoBaseProduto,
)
from models.sessao_usuario import SessaoUsuario
from database.conexao import CAMINHO_BANCO
from models.categoria import normalizar_identidade_categoria
from repositories.categoria_repository import (
    buscar_categoria_por_chave_repository,
    buscar_categoria_por_id_repository,
)
from repositories.produto_repository import (
    alterar_situacao_produto_repository,
    codigo_existe,
    listar_produtos_repository,
    buscar_produto_banco_pelo_id,
    buscar_produto_por_codigo,
    cadastrar_produto_comando_repository,
    editar_produto_comando_repository,
)
from services.autenticacao_service import autorizar_sessao
from services.autorizacao_pontual_service import (
    GERENCIADOR_AUTORIZACOES,
    GerenciadorAutorizacoesPontuais,
)


# Normaliza e valida os dados antes de criar um produto.
def criar_produto(
    codigo,
    nome,
    categoria,
    forma_venda,
    preco_venda_centavos,
    origem,
    caminho_banco=CAMINHO_BANCO,
    *,
    categoria_id=None,
    _exigir_categoria_existente=False,
):

    codigo_limpo = limpar_codigo(codigo) 
    lista_de_erros = validar_codigo(codigo_limpo)

    nome_limpo = limpar_nome(nome)
    lista_de_erros.extend(validar_nome(nome_limpo))

    categoria_selecionada, erros_categoria = _resolver_categoria(
        categoria,
        categoria_id,
        caminho_banco,
        permitir_ausente=not _exigir_categoria_existente,
    )
    lista_de_erros.extend(erros_categoria)

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
        categoria=categoria_selecionada[0],
        forma_venda=forma_venda_limpa,
        preco_venda_centavos=preco_venda_centavos,
        origem=origem_limpa,
        categoria_id=categoria_selecionada[1],
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
    *,
    categoria_id=None,
    sessao_solicitante: SessaoUsuario,
    capacidade=None,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
):
    comando, erros = preparar_comando_cadastro_produto(
        codigo,
        nome,
        categoria,
        forma_venda,
        preco_venda_centavos,
        origem,
        caminho_banco,
        categoria_id=categoria_id,
    )
    if erros:
        return None, erros
    return executar_cadastro_produto(
        comando,
        sessao_solicitante,
        caminho_banco,
        capacidade=capacidade,
        gerenciador_autorizacoes=gerenciador_autorizacoes,
    ), []


def preparar_comando_cadastro_produto(
    codigo,
    nome,
    categoria,
    forma_venda,
    preco_venda_centavos,
    origem,
    caminho_banco=CAMINHO_BANCO,
    *,
    categoria_id=None,
):
    produto, erros = criar_produto(
        codigo,
        nome,
        categoria,
        forma_venda,
        preco_venda_centavos,
        origem,
        caminho_banco,
        categoria_id=categoria_id,
        _exigir_categoria_existente=True,
    )
    if erros:
        return None, erros
    categoria_aprovada = _categoria_aprovada(
        produto.categoria_id,
        caminho_banco,
    )
    if categoria_aprovada is None or not categoria_aprovada.ativo:
        return None, ["Selecione uma categoria ativa."]
    return ComandoCadastroProduto(
        codigo=produto.codigo,
        nome=produto.nome,
        categoria=categoria_aprovada,
        forma_venda=produto.forma_venda,
        preco_venda_centavos=produto.preco_venda_centavos,
        origem=produto.origem,
    ), []


def executar_cadastro_produto(
    comando: ComandoCadastroProduto,
    sessao_solicitante: SessaoUsuario,
    caminho_banco=CAMINHO_BANCO,
    *,
    capacidade=None,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
) -> Produto:
    if not isinstance(comando, ComandoCadastroProduto):
        raise TypeError("O comando de cadastro de produto é inválido.")
    _autorizar_comando_produto(
        comando,
        sessao_solicitante,
        capacidade,
        caminho_banco,
        gerenciador_autorizacoes,
    )
    return cadastrar_produto_comando_repository(comando, caminho_banco)


# Prepara os filtros e solicita ao repository a listagem de produtos.
def listar_produtos(
    ativo: bool | None = True,
    categoria: str | None = None,
    nome: str | None = None,
    caminho_banco=CAMINHO_BANCO,
    termo: str | None = None,
    categoria_id: int | None = None,
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
        categoria_id=categoria_id,
    )

    return produtos, []


# Solicita ao repository a alteração da situação de um produto.
def alterar_situacao_produto(
    produto_id: int,
    ativo: bool,
    caminho_banco=CAMINHO_BANCO,
    *,
    sessao_solicitante: SessaoUsuario,
):
    autorizar_sessao(
        sessao_solicitante,
        ("ADMINISTRADOR",),
        caminho_banco,
    )
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


def _resolver_categoria(
    categoria,
    categoria_id,
    caminho_banco,
    *,
    categoria_atual_id=None,
    permitir_ausente=False,
):
    if categoria_id is not None:
        if (
            not isinstance(categoria_id, int)
            or isinstance(categoria_id, bool)
            or categoria_id <= 0
        ):
            return None, ["A categoria selecionada é inválida."]
        encontrada = buscar_categoria_por_id_repository(
            categoria_id,
            caminho_banco,
        )
    else:
        nome, chave = normalizar_identidade_categoria(categoria)
        erros = validar_categoria(nome)
        if erros:
            return None, erros
        if permitir_ausente:
            return (nome.upper(), None), []
        encontrada = buscar_categoria_por_chave_repository(
            chave,
            caminho_banco,
        )

    if encontrada is None:
        return None, ["A categoria selecionada não foi encontrada."]
    if not encontrada.ativo and encontrada.id != categoria_atual_id:
        return None, ["Selecione uma categoria ativa."]
    return (encontrada.nome, encontrada.id), []


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


def preparar_comando_edicao_produto(
    produto_id,
    codigo,
    nome,
    categoria,
    forma_venda,
    preco_venda_centavos,
    origem,
    caminho_banco=CAMINHO_BANCO, 
    *,
    categoria_id=None,
):
    produto_atual = buscar_produto_banco_pelo_id(
        produto_id,
        caminho_banco,
    )

    if produto_atual is None:
        return None, ["Produto não encontrado."]

    codigo_limpo = limpar_codigo(codigo)
    nome_limpo = limpar_nome(nome)
    forma_venda_limpa = limpar_forma_venda(forma_venda)
    origem_limpa = limpar_origem(origem)

    lista_de_erros = []

    lista_de_erros.extend(validar_codigo(codigo_limpo))
    lista_de_erros.extend(validar_nome(nome_limpo))
    lista_de_erros.extend(validar_forma_venda(forma_venda_limpa))
    lista_de_erros.extend(validar_origem(origem_limpa))
    lista_de_erros.extend(validar_preco_venda_centavos(preco_venda_centavos))

    if lista_de_erros:
        return None, lista_de_erros

    categoria_selecionada, erros_categoria = _resolver_categoria(
        categoria,
        categoria_id,
        caminho_banco,
        categoria_atual_id=produto_atual["categoria_id"],
    )
    if erros_categoria:
        return None, erros_categoria

    produto_com_mesmo_codigo = buscar_produto_por_codigo(
        codigo_limpo,
        caminho_banco
    )

    if(
        produto_com_mesmo_codigo is not None
        and produto_com_mesmo_codigo.id != produto_id
    ):
        return None, ["Já existe outro produto com esse código."]

    categoria_base = _categoria_aprovada(
        produto_atual["categoria_id"],
        caminho_banco,
    )
    categoria_nova = _categoria_aprovada(
        categoria_selecionada[1],
        caminho_banco,
    )
    if categoria_base is None or categoria_nova is None:
        return None, ["A categoria selecionada não foi encontrada."]
    return ComandoEdicaoProduto(
        estado_base=EstadoBaseProduto(
            id=produto_atual["id"],
            codigo=produto_atual["codigo"],
            nome=produto_atual["nome"],
            categoria=categoria_base,
            forma_venda=produto_atual["forma_venda"],
            preco_venda_centavos=produto_atual["preco_venda_centavos"],
            origem=produto_atual["origem"],
            ativo=bool(produto_atual["ativo"]),
        ),
        codigo=codigo_limpo,
        nome=nome_limpo,
        categoria=categoria_nova,
        forma_venda=forma_venda_limpa,
        preco_venda_centavos=preco_venda_centavos,
        origem=origem_limpa,
    ), []

def atualizar_produto(
    produto_id,
    codigo,
    nome,
    categoria,
    forma_venda,
    preco_venda_centavos,
    origem,
    caminho_banco=CAMINHO_BANCO,
    *,
    categoria_id=None,
    sessao_solicitante: SessaoUsuario,
    capacidade=None,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
):
    comando, erros = preparar_comando_edicao_produto(
        produto_id,
        codigo,
        nome,
        categoria,
        forma_venda,
        preco_venda_centavos,
        origem,
        caminho_banco,
        categoria_id=categoria_id,
    )
    if erros:
        return None, erros
    return executar_edicao_produto(
        comando,
        sessao_solicitante,
        caminho_banco,
        capacidade=capacidade,
        gerenciador_autorizacoes=gerenciador_autorizacoes,
    ), []


def executar_edicao_produto(
    comando: ComandoEdicaoProduto,
    sessao_solicitante: SessaoUsuario,
    caminho_banco=CAMINHO_BANCO,
    *,
    capacidade=None,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
) -> Produto:
    if not isinstance(comando, ComandoEdicaoProduto):
        raise TypeError("O comando de edição de produto é inválido.")
    _autorizar_comando_produto(
        comando,
        sessao_solicitante,
        capacidade,
        caminho_banco,
        gerenciador_autorizacoes,
    )
    return editar_produto_comando_repository(comando, caminho_banco)


def _categoria_aprovada(categoria_id, caminho_banco):
    categoria = buscar_categoria_por_id_repository(categoria_id, caminho_banco)
    if categoria is None:
        return None
    _, chave = normalizar_identidade_categoria(categoria.nome)
    return CategoriaAprovada(
        id=categoria.id,
        nome=categoria.nome,
        nome_chave=chave,
        ativo=categoria.ativo,
    )


def _autorizar_comando_produto(
    comando,
    sessao_solicitante,
    capacidade,
    caminho_banco,
    gerenciador_autorizacoes,
) -> None:
    usuario = autorizar_sessao(
        sessao_solicitante,
        ("ADMINISTRADOR", "CAIXA"),
        caminho_banco,
    )
    if usuario.perfil == "ADMINISTRADOR":
        if capacidade is not None:
            raise ValueError(
                "A sessão Administrador não utiliza autorização pontual."
            )
        return
    if type(gerenciador_autorizacoes) is not GerenciadorAutorizacoesPontuais:
        raise TypeError("A operação exige um gerenciador confiável.")
    gerenciador_autorizacoes.consumir(
        capacidade,
        sessao_solicitante,
        comando.operacao,
        comando.recurso_id,
        caminho_banco,
        dados_autorizados_hash=comando.dados_autorizados_hash,
    )


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
