# Orientações gerais para agentes de IA

Este arquivo reúne regras válidas para praticamente todas as tarefas no projeto.
Procedimentos especializados ficam nas Skills indicadas ao final.

## Colaboração

- Explique decisões e mudanças relevantes de forma didática, pois o projeto
  também é usado para estudar programação.
- Quando o pedido for somente analisar, revisar ou explicar, não altere arquivos.
- Não implemente funcionalidades futuras sem solicitação explícita.
- Faça mudanças pequenas, coerentes e limitadas ao objetivo atual.
- Preserve alterações existentes que não pertençam ao escopo da tarefa.

## Arquitetura

- `interface/` apresenta dados e recebe ações do usuário.
- `services/` coordena regras de negócio, validações e fluxos da aplicação.
- `repositories/` acessa e modifica a persistência.
- `database/` configura conexão e schema.
- `models/` representa entidades e dados do domínio.
- `utils/` contém somente comportamentos com reutilização concreta.
- Respeite as responsabilidades das camadas e evite refatorações de arquitetura
  junto com mudanças não relacionadas.

## Git

- Não execute commit, push, merge ou outra operação irreversível sem solicitação
  explícita do usuário.
- Antes de concluir uma mudança, revise o diff e os testes apropriados.
- Quando solicitado, crie commits coerentes e use Conventional Commits.
- Separe mudanças independentes quando isso tornar o histórico mais claro.

## Documentação

- Mantenha a documentação consistente quando uma mudança alterar arquitetura,
  regras de negócio ou comportamento documentado.
- Não registre como implementada uma funcionalidade que exista apenas como plano.

## Procedimentos especializados

- Use a Skill `database-sqlite` em tarefas de SQLite, schema, SQL, repositories,
  persistência, transações, migrações ou integridade de dados.
- Use a Skill `testing-pytest` para criar, corrigir ou revisar testes com pytest.
- Use a Skill `review-change` em revisões finais, auditorias de alterações ou
  pedidos de análise de diff e estado do projeto.
