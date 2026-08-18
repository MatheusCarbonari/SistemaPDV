# Arquitetura do projeto

O projeto separa responsabilidades em camadas. Essa divisão facilita testes,
manutenção e evolução da interface sem misturar regras de negócio com SQL.

## Estrutura

### `models/`

Contém os objetos que representam os dados do domínio. Atualmente, `Produto`
reúne os campos usados pelas demais camadas.

### `services/`

Recebe dados vindos da interface, limpa valores, valida regras de negócio e
coordena o fluxo da operação. O service não deve escrever SQL.

Exemplo: ao cadastrar um produto, o service normaliza os campos, reúne mensagens
de erro, verifica duplicidade e cria o objeto `Produto` somente quando os dados
são válidos.

### `repositories/`

Faz a comunicação com o banco. É responsável por consultas, inserções e
conversão das linhas retornadas pelo SQLite em objetos do domínio.

O repository recebe dados já preparados pelo service. Ele não deve decidir como
uma mensagem será exibida ao usuário nem aplicar formatação visual.

### `database/`

Centraliza a conexão SQLite, o caminho do banco principal e a criação das
tabelas. As operações aceitam outro caminho quando necessário para permitir
testes isolados.

Regras detalhadas de conexão, transações, migrações, backup e segurança estão em
`docs/REGRAS_BANCO_DADOS.md`.

### `interface/`

Será responsável por campos, botões, tabelas, mensagens e formatação apresentada
ao usuário. A interface deverá chamar o service, e não executar SQL diretamente.

### `utils/`

É reservado para comportamentos genéricos realmente reutilizados em diferentes
módulos. Uma função não deve ser movida para `utils/` apenas por parecer genérica;
primeiro deve existir uma necessidade concreta de reutilização.

### `tests/`

Contém testes separados por camada. Bancos de teste devem ser criados com
`tmp_path`, garantindo que cada teste tenha seu próprio arquivo temporário.

## Fluxos atuais

### Cadastro de produto

```text
interface futura
    -> produto_service limpa e valida
    -> Produto é criado
    -> produto_repository persiste
    -> SQLite armazena e aplica constraints
```

### Consulta de produtos

```text
interface futura
    -> produto_service prepara e valida os filtros
    -> produto_repository monta a consulta parametrizada
    -> SQLite retorna as linhas
    -> repository converte as linhas em objetos Produto
    -> interface apresenta o resultado
```

### Alteração da situação do produto

```text
interface futura mantém o ID do produto selecionado
    -> produto_service valida o ID e a nova situação
    -> produto_repository atualiza o registro pelo ID
    -> SQLite preserva o produto e altera sua situação
    -> interface recebe sucesso ou uma mensagem de erro
```

## Princípios adotados

- Dependências apontam da interface para o service e do service para o
  repository, não no sentido contrário.
- SQL fica concentrado no repository e no schema.
- Regras amigáveis ficam no service; constraints preservam a integridade final
  no banco.
- Conexões devem ser fechadas em qualquer resultado da operação.
- Consultas recebem parâmetros separadamente do texto SQL.
- Testes de banco usam arquivos temporários e nunca o banco principal.
- Mudanças devem ser pequenas, verificáveis e acompanhadas pelos testes
  apropriados.
