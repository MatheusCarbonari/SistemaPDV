---
name: review-change
description: Review local changes, diffs, project state, regressions, architecture, documentation, and test evidence in Sistema-Acougue without editing unless explicitly requested.
metadata:
  short-description: Revisão final de alterações
---

# Revisão de alterações

Use estas instruções para revisar uma mudança concluída, um diff ou o estado do
projeto. Uma solicitação somente de revisão é somente leitura: não altere código,
testes ou documentação sem autorização explícita.

## Verificações

1. Compare o resultado com o escopo solicitado.
2. Liste os arquivos modificados e identifique mudanças fora do escopo.
3. Confirme que as responsabilidades de interface, service, repository,
   database, models e utils continuam respeitadas.
4. Verifique regras de negócio afetadas e comportamentos de erro.
5. Em persistência ou entradas externas, revise parametrização, validação,
   transações, fechamento de recursos e exposição de dados.
6. Avalie se os testes existentes e novos cobrem o comportamento sem falso
   positivo ou duplicação desnecessária.
7. Procure regressões plausíveis e caminhos ainda não tratados.
8. Confirme se arquitetura e regras documentadas continuam consistentes.
9. Revise o diff final, incluindo formatação e artefatos temporários.

Execute verificações e testes proporcionais ao pedido. Não trate a revisão como
autorização para corrigir problemas encontrados; relate-os e aguarde solicitação
quando a tarefa for apenas revisar.

## Relatório final

Informe objetivamente:

- arquivos alterados;
- comportamento alterado;
- testes executados e resultados;
- problemas encontrados;
- riscos restantes;
- existência ou ausência de mudanças fora do escopo.
