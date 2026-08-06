from database.schema import criar_tabelas


def main() -> None:
    criar_tabelas()
    print("Sistema do Açougue iniciado com sucesso.")
    print("Banco de dados preparado.")


if __name__ == "__main__":
    main()
