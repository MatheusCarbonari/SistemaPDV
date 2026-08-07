from database.schema import criar_tabelas


# Prepara o banco de dados e inicia a aplicação.
def main() -> None:
    criar_tabelas()
    print("Sistema do Açougue iniciado com sucesso.")
    print("Banco de dados preparado.")


# Executa a aplicação somente quando este arquivo é chamado diretamente.
if __name__ == "__main__":
    main()
