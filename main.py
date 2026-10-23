from database.schema import criar_tabelas
from interface.produto_view import consultar_produto_interface
from services.produto_service import criar_produto
from repositories.produto_repository import salvar_produto


# Prepara o banco de dados e inicia a aplicação.
def main() -> None:
    criar_tabelas()
    print("Sistema do Açougue iniciado com sucesso.")
    print("Banco de dados preparado.")

    # produto, erros = criar_produto(
    #     "2",
    #     "Ancho",
    #     "Bovino",
    #     "Peso",
    #     12990,
    #     "Comprado",
    # )

    # if erros:
    #     print(erros)
    #     return

    # salvar_produto(produto)

    consultar_produto_interface()

# Executa a aplicação somente quando este arquivo é chamado diretamente.
if __name__ == "__main__":
    main()
