# Regras de negócio

Este documento registra o comportamento atual do sistema. Itens planejados são
identificados separadamente para não serem confundidos com código já pronto.

## Produto

Um produto possui:

- código;
- nome;
- categoria;
- forma de venda;
- preço de venda em centavos;
- origem;
- situação ativa ou inativa;
- identificador e datas controlados pelo banco.

## Cadastro

As seguintes regras estão implementadas:

- o código é obrigatório, deve conter somente números e deve ser único;
- o nome é obrigatório e não pode conter somente números;
- a categoria é obrigatória e não pode conter somente números;
- a forma de venda aceita somente `PESO` ou `UNIDADE`;
- o preço é armazenado como número inteiro em centavos e deve ser maior que zero;
- a origem aceita somente `COMPRADO` ou `PRODUZIDO`;
- novos produtos são gravados como ativos;
- o banco atribui automaticamente o identificador e as datas de criação e
  atualização.

O service normaliza os dados de cadastro:

- remove espaços externos do código e do nome;
- capitaliza o nome;
- converte categoria, forma de venda e origem para letras maiúsculas;
- verifica duplicidade do código somente depois das validações básicas.

Após o `commit`, se a releitura pelo ID não encontrar o registro, o cadastro
permanece válido. Nesse caso, `salvar_produto()` devolve o objeto original com o
ID gerado, mesmo que as datas automáticas ainda não tenham sido carregadas.

## Consulta

As seguintes consultas estão implementadas no repository:

- verificar se um código já existe;
- buscar um produto pelo identificador;
- buscar um produto pelo código;
- listar produtos ordenados pelo nome;
- filtrar a listagem por situação, categoria e trecho do nome.

Na listagem:

- o comportamento padrão retorna somente produtos ativos;
- `ativo=False` retorna somente inativos;
- `ativo=None` não filtra pela situação;
- categoria usa correspondência exata;
- nome usa busca parcial com `LIKE`;
- filtros informados são combinados com `AND`;
- ausência de resultados produz uma lista vazia.

## Garantias do banco

O schema também protege:

- código único e não nulo;
- nome e categoria não nulos;
- valores permitidos para forma de venda, origem e situação;
- preço estritamente maior que zero.

Essas garantias complementam as mensagens amigáveis produzidas pelo service.

## Planejado, mas ainda não implementado

- cadastro próprio de categorias;
- atualização de produtos;
- inativação e reativação por uma operação do sistema;
- filtros por múltiplas categorias;
- tratamento específico de erros operacionais do SQLite;
- interface gráfica de cadastro e consulta.

Ao implementar um desses itens, mova-o para a seção correspondente ao
comportamento atual e registre suas novas regras.
