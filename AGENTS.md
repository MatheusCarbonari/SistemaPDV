# Orientações para agentes de IA

Este arquivo define como trabalhar neste repositório. Antes de alterar código,
consulte também:

- `docs/ARQUITETURA.md` quando a tarefa envolver responsabilidades das camadas;
- `docs/REGRAS_NEGOCIO.md` quando a tarefa envolver comportamento de produtos;
- `docs/REGRAS_BANCO_DADOS.md` antes de criar ou modificar persistência, schema,
  migrações, transações ou testes de banco.

## Forma de colaboração

- Explique decisões e mudanças de maneira didática, pois este projeto também é
  usado para estudar programação.
- Quando o pedido for somente analisar, revisar ou explicar, não altere arquivos.
- Não implemente funcionalidades futuras descritas em `docs/` sem solicitação.
- Faça mudanças pequenas e focadas. Evite refatorações de arquitetura junto com
  uma funcionalidade, salvo quando forem indispensáveis.
- Preserve alterações existentes que não pertencem à tarefa atual.

## Arquitetura

- `models/` representa os dados usados pelo sistema.
- `services/` limpa entradas, valida dados e aplica regras de negócio.
- `repositories/` contém consultas e operações de persistência.
- `database/` configura conexões e define o schema.
- `interface/` será responsável pela interação e apresentação ao usuário.
- `utils/` deve conter somente funções realmente genéricas e reutilizadas.
- Não coloque SQL na interface ou regras visuais no repository.

## Banco de dados

- Use consultas parametrizadas; nunca concatene valores recebidos pelo usuário
  diretamente no SQL.
- Feche toda conexão SQLite, inclusive quando uma operação gerar erro.
- Preserve o parâmetro `caminho_banco` nas operações que precisam ser testáveis.
- Testes nunca podem acessar ou modificar o banco principal em `data/`.
- Em testes, use `tmp_path` para criar bancos temporários e isolados.

## Testes

- Para comportamentos novos, prefira criar primeiro um teste que falhe pelo
  motivo esperado e depois implementar o mínimo necessário para fazê-lo passar.
- Mantenha somente um dado inválido por teste de validação.
- Evite repetir no repository regras já cobertas pelo schema ou pelo service.
- Verifique persistência com uma consulta independente quando o objetivo for
  comprovar que dados foram realmente gravados.
- Execute primeiro o arquivo diretamente relacionado à mudança e depois a suíte
  completa.
- Comandos recomendados:
  - teste específico: `python -m pytest tests/arquivo_de_teste.py -v`;
  - suíte completa: `python -m pytest -v`.

## Comentários e documentação

- Escreva comentários curtos que expliquem a finalidade, não cada instrução óbvia.
- Atualize a documentação quando uma regra de negócio ou responsabilidade de
  camada mudar.
- Não mova funções para `utils/` até existir reutilização concreta em mais de um
  módulo.

## Git

- Não crie commits sem autorização explícita do usuário.
- Antes de sugerir ou criar um commit, revise o diff e confirme os testes.
- Use Conventional Commits em português:
  - `feat:` para funcionalidade;
  - `fix:` para correção;
  - `test:` para mudanças somente em testes;
  - `refactor:` para reorganização sem mudança de comportamento;
  - `docs:` para comentários e documentação.
- Mantenha mudanças independentes em commits separados quando isso facilitar o
  entendimento do histórico.
