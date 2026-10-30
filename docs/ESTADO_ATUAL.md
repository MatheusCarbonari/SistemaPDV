# Inventário preliminar do ZIP fornecido

**Fonte:** `Sistema-PDV.zip` recebido em 30/10/2026. **Não substitui o ticket T01 de auditoria.** Esta inspeção foi estática; nenhum teste foi executado aqui.

## Observado
- Código-fonte em `main.py`, `models/`, `services/`, `repositories/`, `database/`, `interface/`, `utils/`.
- Testes pytest em `tests/` para cadastro, service, repository, conexão e schema.
- `database/schema.py` cria uma tabela `produtos` com `id`, `codigo` único, `nome`, `categoria`, `forma_venda` PESO/UNIDADE, `preco_venda_centavos`, `origem`, `ativo`, timestamps.
- `interface/produto_view.py` importa **customtkinter**, e `requirements.txt` lista `customtkinter`, `pillow`, `pytest`; ainda não é a UI PySide6 aprovada.
- Há arquivo `data/sistema_acougue.db` no pacote; **nunca utilizá-lo nos testes nem apagar sem auditoria/backup**.
- Existiam três skills locais (`database-sqlite`, `review-change`, `testing-pytest`) e um agente `.codex/agents/reviewer.toml`; removidos **somente desta cópia documentada**; regras gerais relevantes foram consolidadas em `AGENTS.md`.
- Os três documentos técnicos anteriores foram preservados em `docs/legado/`.
- O histórico `.git` foi preservado no pacote gerado, sem commit/alteração no histórico.

## Não verificado
Execução da suíte pytest, estado de branches, qualidade do domínio existente, integridade do arquivo SQLite, compatibilidade de instalações, e eventual alteração posterior ao ZIP. Estes são objetivos do T01.
