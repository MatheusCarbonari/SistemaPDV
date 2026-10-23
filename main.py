from database.schema import criar_tabelas
from interface.produto_view import consultar_produto_interface
from services.produto_service import criar_produto
from repositories.produto_repository import salvar_produto
from interface.produto_view import abrir_tela_consulta_produto


# Prepara o banco de dados e inicia a aplicação.
def main() -> None:
    criar_tabelas()
    print("Sistema do Açougue iniciado com sucesso.")
    print("Banco de dados preparado.")
    print()

    abrir_tela_consulta_produto()

# Executa a aplicação somente quando este arquivo é chamado diretamente.
if __name__ == "__main__":
    main()
