---
name: testing-pytest
description: Create, fix, or review pytest tests in Sistema-Acougue, including unit, service, repository, schema, regression, and temporary-database scenarios.
metadata:
  short-description: Práticas de testes com pytest
---

# Testes com pytest

Use estas instruções para criar, corrigir ou revisar testes do projeto.

## Escolha dos cenários

- Teste comportamento observável e contratos relevantes, não detalhes internos
  sem valor de regressão.
- Dê a cada teste um motivo principal para falhar.
- Em testes de validação, mantenha somente um dado inválido por cenário para
  evitar falso positivo causado pelo erro errado.
- Evite duplicar cobertura já garantida por outra camada sem ganho concreto.
- Para bugs corrigidos, crie um teste de regressão quando ele proteger o
  comportamento que falhou.

## Isolamento

- Garanta independência: cada teste prepara seus próprios dados e não depende da
  ordem de execução.
- Nunca use o banco principal. Para SQLite e outros recursos temporários, use
  `tmp_path`.
- Não dependa de dados, arquivos, rede ou processos externos sem necessidade
  explícita do cenário.
- Ao comprovar persistência, prefira uma verificação independente do retorno da
  função testada.

## Implementação e diagnóstico

- Para comportamento novo, prefira demonstrar primeiro a falha esperada e então
  implementar o mínimo necessário.
- Não altere código de produção apenas para fazer o teste passar sem investigar
  a causa da falha.
- Diferencie falha real do projeto de erro do ambiente de execução antes de
  modificar arquivos.

## Execução

Quando fizer sentido para o tamanho e risco da mudança, execute nesta ordem:

1. o teste específico;
2. o arquivo de testes afetado;
3. a suíte completa.

Ao concluir, informe quais testes foram criados ou alterados, por que agregam
cobertura e os resultados das execuções realizadas.
