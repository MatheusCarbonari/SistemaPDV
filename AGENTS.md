# Sistema-PDV — orientações de desenvolvimento

Fonte de verdade do planejamento: `docs/README.md`, `docs/DECISOES.md`, `docs/REVISOES.md`, `docs/ESCOPO.md` e `docs/TICKETS.md`.
O código legado deve ser examinado antes de qualquer alteração. Planejado NÃO significa implementado.

## Método de colaboração
- Um ticket pequeno por vez; evitar misturar GUI, modelo de dados, migrações e regra de negócio na mesma entrega quando puder separar.
- Antes de implementar: explicar objetivo comercial, conceito técnico empregado, alternativas, arquivos afetados, critérios de aceitação e testes.
- Explicar *por que* uma classe, composição, herança, transação, evento ou padrão seria necessário; não introduzir abstrações por exibicionismo.
- Se pedido for análise ou documentação: não alterar código. Não iniciar implementação sem autorização.
- Prompts para Codex: concisos, com restrições, testes e escopo explícito.
- Testes SQLite sempre isolados em `tmp_path`; nunca usar o banco principal. Exigir teste de regressão para erro corrigido.
- Preservar dados do estabelecimento; nunca apagar ou recriar um banco real como atalho.
- Não executar commit, push, merge ou alterações destrutivas fora do pedido.
- Executar e relatar testes pertinentes; distinguir não testado de aprovado.
- Criar ou atualizar documentação quando uma decisão mudar.

## Arquitetura-alvo (não necessariamente implementada)
Windows, Python, PySide6 Qt Widgets, SQLite, monólito modular, dinheiro em centavos, divisão clara entre interface/domínio/persistência. Nenhuma venda fiscal na V1.

## Situação do repositório recebido
Há código com `customtkinter`, módulos de cadastro e testes; `requirements.txt` ainda não inclui PySide6. Não afirmar que a migração já ocorreu. Primeiro trabalho: auditoria somente leitura em `T01`.

## Referências históricas
Arquivos anteriores em `docs/legado/` são material de referência do projeto antigo, não fonte normativa do planejamento novo.
