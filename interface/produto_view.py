from services.produto_service import consultar_produto_por_codigo
import customtkinter as ctk


def consultar_produto_interface():
    codigo = input("Digite o código do produto: ")

    produto, erros = consultar_produto_por_codigo(codigo)

    if erros:
        for erro in erros:
            print(erro)
        return

    print("Produto encontrado:")
    print(f"Código: {produto.codigo}")
    print(f"Nome: {produto.nome}")
    print(f"Categoria: {produto.categoria}")
    print(f"Forma de venda: {produto.forma_venda}")
    print(f"Preço: {formatar_preco(produto.preco_venda_centavos)}")
    print(f"Origem: {produto.origem}")


def formatar_preco(preco_centavos: int) -> str:
    valor = preco_centavos / 100
    return f"R$ {valor:.2f}".replace("." , ",")


def abrir_tela_consulta_produto():
    janela = ctk.CTk()
    janela.title("Consulta de Produto")
    janela.geometry("500x300")

    titulo = ctk.CTkLabel(
        janela,
        text="Consultar Produto",
        font=ctk.CTkFont(size=22, weight="bold")
    )
    titulo.pack(pady=(30, 20))

    campo_codigo = ctk.CTkEntry(
        janela,
        placeholder_text="Digite o código do produto",
        width=250,
    )
    campo_codigo.pack(pady=10)

    def buscar_produto():
        codigo = campo_codigo.get()

        produto, erros = consultar_produto_por_codigo(codigo)

        if erros:
            resultado_label.configure(
                text="\n".join(erros)
            )
            return

        resultado_label.configure(
            text=(
                f"Código: {produto.codigo}\n"
                f"Nome: {produto.nome}\n"
                f"Categoria: {produto.categoria}\n"
                f"Forma de venda: {produto.forma_venda}\n"
                f"Preço: {formatar_preco(produto.preco_venda_centavos)}\n"
                f"Origem: {produto.origem}"
            )
        )

    botao_buscar = ctk.CTkButton(
        janela,
        text="Buscar",
        command=buscar_produto,
    )
    botao_buscar.pack(pady=10)

    resultado_label = ctk.CTkLabel(
        janela,
        text="",
        justify="left"
    )
    resultado_label.pack(pady=20)

    janela.mainloop()