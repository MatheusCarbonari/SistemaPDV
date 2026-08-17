# Regras de uso do banco de dados

Este documento complementa `ARQUITETURA.md` e `REGRAS_NEGOCIO.md`. Ele define
como o projeto deve utilizar o SQLite e separa práticas obrigatórias atuais de
requisitos para evoluções futuras.

## Responsabilidades

- A interface não executa SQL.
- O service limpa e valida entradas, aplica regras de negócio e coordena a
  operação, mas não escreve SQL.
- O repository concentra consultas e persistência das entidades.
- `database/` centraliza conexão, configuração do SQLite, schema, constraints e
  futuras migrações.

## Conexões

- Código de produção deve usar `conectar()` de `database/conexao.py`.
- Criar uma conexão SQLite diretamente é aceitável em testes que precisam
  verificar o banco de maneira independente da função testada.
- Toda conexão deve ser fechada mesmo quando ocorrer uma exceção. Use
  `try/finally` ou outro mecanismo que garanta o fechamento.
- Não mantenha uma conexão global aberta durante toda a execução. Abra-a para
  uma operação ou transação coerente e feche-a ao terminar.
- Mantenha `PRAGMA foreign_keys = ON` em todas as conexões criadas pela aplicação.

## Transações

- Operações de escrita, como `INSERT`, `UPDATE` e `DELETE`, devem ser confirmadas
  com `commit()` somente depois que todas as etapas necessárias forem concluídas.
- Uma operação com várias escritas relacionadas deve ser atômica: ou todas as
  etapas são persistidas, ou nenhuma delas é.
- Quando uma etapa crítica falhar antes do commit, faça rollback ou use um
  contexto transacional apropriado.
- Não faça commits intermediários que possam deixar uma operação de negócio pela
  metade.

Exemplos futuros que exigirão uma única transação incluem compra com seus itens,
movimentações de estoque e registros financeiros relacionados.

## Consultas seguras e explícitas

- Passe valores externos por placeholders. Nunca concatene ou interpole dados do
  usuário no texto SQL.
- Mantenha os parâmetros na mesma ordem dos placeholders ou use parâmetros
  nomeados quando isso tornar uma consulta complexa mais clara.
- Evite `SELECT *` quando as colunas necessárias forem conhecidas.
- Para responder apenas se um registro existe, prefira `SELECT 1 ... LIMIT 1`.
- Dê às funções nomes e contratos específicos. Evite funções genéricas como
  `buscar(parametro)` quando entidade, campo e retorno não estiverem claros.
- Centralize a conversão de `sqlite3.Row` em objetos do domínio. Para produtos,
  reutilize `montar_produto()` em vez de repetir o mapeamento.

## Contratos de retorno e erros

- Uma busca por um único registro deve retornar o objeto ou `None` quando ele não
  existir.
- Uma listagem deve retornar uma lista; quando não houver registros, retorne `[]`.
- Não misture `False`, textos, listas vazias e `None` para representar a mesma
  situação.
- Não mostre diretamente ao usuário mensagens técnicas ou rastros do SQLite.
- Situações previsíveis devem ser traduzidas pelo service para mensagens claras,
  sem remover constraints que ainda protegem o banco.
- Erros técnicos inesperados devem preservar informações úteis para diagnóstico,
  sem expor dados sensíveis ao usuário ou aos logs.

## Integridade e identificadores

- Validações do service melhoram a experiência; constraints do schema são a
  proteção final contra dados estruturalmente inválidos. As duas devem coexistir.
- `id` é um identificador interno controlado pelo banco e não deve ser digitado
  pelo usuário.
- `codigo` é o identificador operacional do produto e deve permanecer único.
- Nunca trate `id` e `codigo` como equivalentes.
- Relacionamentos futuros devem usar chaves estrangeiras reais, evitando duplicar
  dados que deveriam ser referenciados.
- Toda constraint crítica nova deve possuir teste próprio, mantendo os demais
  campos válidos para evitar falso positivo.

## Atualizações, exclusões e histórico

- Valide novos dados antes de executar um `UPDATE`.
- Ao atualizar um registro, mantenha `atualizado_em` coerente com a alteração.
- Entidades envolvidas em vendas, compras, perdas ou relatórios não devem ser
  apagadas fisicamente sem uma regra explícita.
- Para produtos, a direção planejada é usar inativação (`ativo = 0`) em vez de
  `DELETE`, preservando histórico e relacionamentos.
- Valores históricos não podem depender de valores atuais. Alterar o preço de um
  produto não deve modificar o preço registrado em vendas antigas.
- Informações relevantes para auditoria não devem ser sobrescritas quando
  precisarem permanecer como evidência histórica.

As operações de atualização, inativação e auditoria ainda não estão implementadas.
Estas regras orientam sua implementação futura.

## Valores, pesos e datas

- Nunca armazene dinheiro como `float`. Use números inteiros em centavos.
- Registre explicitamente a unidade de todo campo quantitativo. Prefira nomes
  como `peso_gramas` em vez de `peso` quando o significado puder ser ambíguo.
- Antes de implementar estoque por peso ou integração com balança, defina um
  padrão único para gramas, quilogramas e unidades.
- Datas automáticas definidas no schema podem usar `CURRENT_TIMESTAMP`.
- Converta textos de data retornados pelo SQLite para `datetime` quando o modelo
  Python declarar esse tipo; não suponha conversão automática.

## Testes isolados

- Nenhum teste automatizado pode acessar `data/sistema_acougue.db`.
- Use `tmp_path` para que cada teste tenha seu próprio banco temporário.
- Cada teste cria suas tabelas e seus próprios dados; não dependa de registros
  produzidos por outro teste.
- Testes de repository podem consultar diretamente o SQLite para comprovar a
  persistência sem depender do retorno da função testada.
- Testes devem usar dados fictícios e nunca alterar o ambiente real.

## Schema e migrações futuras

- Não altere silenciosamente a estrutura de um banco que já contém dados reais.
- Antes de aplicar uma mudança estrutural:
  1. faça backup;
  2. identifique a versão atual do schema;
  3. defina a transformação dos dados;
  4. teste a migração em uma cópia;
  5. aplique ao banco real somente depois da validação.
- Adição de chaves estrangeiras, alteração de constraints, remoção de colunas e
  divisão de tabelas exigem estratégia de migração.
- A futura transformação de categoria textual em uma entidade própria também
  exigirá migração dos registros existentes.

O projeto ainda não possui um sistema de versionamento ou migração do schema.

## Backup e arquivos SQLite

- O banco real e seus arquivos auxiliares não devem ser versionados no Git.
- Mantenha ignorados arquivos `.db`, `.db-wal` e `.db-shm` de dados reais e de
  testes.
- Antes de o sistema ser usado com dados reais, implemente backup periódico.
- O backup deverá gerar cópias datadas, manter mais de uma versão, registrar
  falhas e ter restauração testada.
- Evite copiar o arquivo do SQLite no meio de uma escrita; use um procedimento de
  backup compatível com o banco em uso.

Backup automático ainda é um requisito futuro, não uma funcionalidade atual.

## Privacidade, senhas e auditoria futuras

- Não coloque dados pessoais, financeiros ou credenciais em commits, screenshots,
  mensagens de erro, fixtures ou logs sem necessidade.
- Use somente dados fictícios nos testes.
- Senhas nunca podem ser armazenadas em texto puro. Uma futura autenticação deve
  usar biblioteca confiável de hash de senha com salt.
- Operações sensíveis futuras devem registrar usuário, ação, data, entidade e
  identificador necessários para auditoria.
- Logs devem ajudar no diagnóstico sem registrar dados privados completos.

## Limites do SQLite

SQLite é adequado ao cenário atual de aplicação local, poucos usuários e baixo
volume simultâneo de escrita. Reavalie a tecnologia se o sistema passar a operar
em vários computadores, pela internet, com muitas escritas concorrentes ou com
múltiplas filiais.

## Checklist para novas operações

Antes de considerar uma operação de banco concluída, confirme:

- [ ] O SQL está no repository, no schema ou em uma futura migração apropriada.
- [ ] Valores externos usam placeholders.
- [ ] A conexão é sempre fechada.
- [ ] Escritas usam commit e transação coerentes.
- [ ] Falhas não deixam dados parcialmente persistidos.
- [ ] O contrato de retorno é claro.
- [ ] Registro inexistente possui comportamento definido.
- [ ] Constraints críticas existem e possuem testes.
- [ ] Valores monetários usam centavos inteiros.
- [ ] Testes usam `tmp_path` e não acessam o banco principal.
- [ ] Mudanças de schema possuem plano de migração e backup.
- [ ] Dados sensíveis não aparecem em logs, testes ou commits.
