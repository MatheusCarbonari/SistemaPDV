---
name: database-sqlite
description: Implement or review SQLite persistence, schema, SQL, repositories, transactions, migrations, test databases, and data-integrity changes in Sistema-Acougue.
metadata:
  short-description: Regras de persistência SQLite
---

# Banco de dados SQLite

Use estas instruções quando a tarefa modificar ou revisar persistência SQLite.
Antes de agir, leia `docs/REGRAS_BANCO_DADOS.md` e confira o código atual; não
trate afirmações históricas ou itens futuros do documento como já implementados.

## Limites das camadas

- Centralize conexões da aplicação em `database/conexao.py`.
- Mantenha SQL em `repositories/`, `database/` ou em uma migração apropriada.
- Não mova regras de apresentação para o repository nem SQL para a interface.
- Evite refatorações fora do escopo da operação solicitada.

## SQL e conexões

- Passe dados externos por placeholders; nunca concatene ou interpole valores no
  texto SQL.
- Mantenha valores na mesma ordem dos placeholders ou use parâmetros nomeados
  quando isso melhorar a clareza.
- Garanta `PRAGMA foreign_keys = ON` nas conexões da aplicação.
- Feche toda conexão, inclusive quando ocorrer exceção, com `try/finally` ou
  mecanismo equivalente.
- Reutilize conversores de `sqlite3.Row` para models, como `montar_produto()`,
  quando já existirem.

## Escritas e integridade

- Trate escritas relacionadas como uma única transação coerente.
- Execute `commit()` somente depois que todas as etapas necessárias terminarem.
- Em falha antes do commit, use rollback quando apropriado e sempre feche a
  conexão; não deixe uma operação parcialmente persistida.
- Preserve constraints críticas no schema mesmo quando o service também valida.
- Armazene valores monetários como inteiros em centavos, nunca como `float`.
- Mantenha contratos de retorno explícitos e consistentes: registro ou `None`
  para busca única, lista para listagem e resultado definido para escritas.
- Defina o comportamento para registros inexistentes e traduza mensagens
  amigáveis no service, sem expor erros técnicos ao usuário.

## Testes de persistência

- Nunca acesse o banco principal em testes.
- Use `tmp_path` para criar um banco isolado por teste, com suas próprias tabelas
  e dados fictícios.
- Não dependa de arquivos, registros ou processos externos ao teste.
- Quando o objetivo for comprovar persistência, consulte o SQLite de forma
  independente do retorno da função testada.

## Schema e migrações

- Não altere silenciosamente um banco existente com dados reais.
- Para mudança estrutural, defina versão, backup, transformação e validação em
  uma cópia antes de qualquer aplicação real.
- Verifique constraints, chaves estrangeiras, compatibilidade dos dados e plano
  de rollback proporcional ao risco.
