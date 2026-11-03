from interface.aplicacao import executar_aplicacao


def main() -> int:
    """Inicia a aplicação desktop do Sistema-PDV."""
    return executar_aplicacao()


if __name__ == "__main__":
    raise SystemExit(main())
