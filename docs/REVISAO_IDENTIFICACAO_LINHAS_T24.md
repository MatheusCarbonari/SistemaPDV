# T24 — Revisão da identificação e remoção de linhas

## Conclusão

A remoção por índice e o desfazer de uma etapa já atendem com segurança às
necessidades atuais do PDV. Não foi encontrada falha concreta que justifique
alterar modelos, serviços ou testes, e não será acrescentado identificador de
linha no MVP.

Essa decisão depende de a futura interface manter a lista visual sincronizada
com a ordem de `VendaEmAndamento.itens`. Caso a apresentação passe a ordenar,
filtrar ou atualizar linhas independentemente do modelo, a decisão deverá ser
reavaliada.

## Avaliação das operações existentes

| Operação ou requisito | Evidência | Avaliação |
|---|---|---|
| Remover a linha selecionada | `remover_item()` valida o índice e remove somente a posição indicada por slicing | Atendido. A posição distingue inclusive objetos iguais. |
| Preservar ordem e duplicatas | Os testes removem primeiro, meio e fim, além de objetos iguais e da mesma instância repetida | Atendido. Os itens restantes mantêm ordem, conteúdo e identidade. |
| Desfazer na posição original | `remover_com_desfazer()` guarda item e índice; `desfazer_ultima_remocao()` reutiliza `inserir_item()` | Atendido. Os testes comprovam restauração da ordem e consumo do registro. |
| Desfazer somente a última remoção | Nova remoção substitui a anterior; adicionar ou inserir invalida a remoção pendente | Atendido conforme DEC-014. |
| Remover o último item sem seleção | Não pertence ao serviço atual; a interface pode usar `len(venda.itens) - 1` quando houver itens | Futuro no T29, sem necessidade de novo contrato de domínio. |
| Limpar seleção após remover | Seleção ainda não existe no domínio e não deve ser armazenada nele | Futuro no T29/T30. A interface deverá limpar a seleção após reconstruir a lista. |

## Índice versus identificador estável

O índice representa diretamente a posição na tupla imutável da venda. No fluxo
atual, cada operação recebe uma versão específica de `VendaEmAndamento`, produz
outra versão e preserva a ordem. Isso torna o índice suficiente e evita estado
adicional.

Um identificador estável seria útil se uma linha precisasse ser localizada após
ordenação, filtragem, paginação, atualizações assíncronas ou persistência
independente da posição. Nenhum desses comportamentos existe no MVP atual.
Adicionar o identificador agora exigiria definir geração, unicidade, cópia,
serialização e relação com o futuro registro persistido sem requisito que
determine essas decisões.

Duplicatas não exigem identificador neste momento: duas ocorrências iguais são
linhas diferentes pela posição. Até a mesma instância de `ItemVenda` pode
aparecer mais de uma vez e a remoção por índice elimina somente a ocorrência
selecionada.

## Riscos reais e prevenção

| Risco | Consequência | Medida preventiva no MVP |
|---|---|---|
| Tabela visual ordenada de forma diferente da tupla | Remoção de uma linha diferente da exibida como selecionada | Não habilitar ordenação ou filtragem independente; renderizar na ordem de `venda.itens`. |
| Índice selecionado mantido após mudança da venda | Índice pode passar a apontar para outra linha ou sair da faixa | Resolver o índice no momento do comando, atualizar toda a tabela e limpar a seleção após qualquer mutação. |
| Comando sem seleção em venda vazia | Cálculo de `len(itens) - 1` produziria índice inválido | Desabilitar/ignorar a remoção quando a venda estiver vazia. |
| Comparar itens por igualdade para localizar a linha | Duplicatas iguais poderiam selecionar a ocorrência errada | Usar exclusivamente o índice visual sincronizado, nunca `list.index()`, igualdade ou identidade do item. |
| Alterar a venda entre remover e desfazer | A posição original poderia perder o contexto | Manter a regra existente: inclusão ou inserção consome a remoção pendente; nova remoção substitui a anterior. |

## Requisitos para a interface PySide6

- A tabela deve refletir exatamente a ordem de `EstadoVenda.venda.itens`.
- Com seleção válida, o comando deve enviar o índice da linha selecionada para
  `remover_com_desfazer()`.
- Sem seleção e com venda não vazia, deve enviar o índice do último item.
- Após remover, adicionar, inserir ou desfazer, deve reconstruir a apresentação
  a partir do novo estado e limpar a seleção antiga.
- Ordenação e filtragem independentes devem permanecer desabilitadas no MVP.
- A interface deve impedir remoção quando a venda estiver vazia e apresentar
  erros de domínio sem manter uma seleção obsoleta.
- Testes futuros com `pytest-qt` devem cobrir seleção, ausência de seleção,
  duplicatas, última linha, limpeza de seleção e sincronização após desfazer.

## Decisão

Manter índices é a solução mínima e coerente com o agregado imutável atual. Um
identificador estável não foi implementado porque não melhora o funcionamento
inicial e introduziria decisões sem requisito comprovado. A alternativa deverá
ser reavaliada apenas se a interface precisar dissociar a ordem visual da ordem
do modelo ou se outro requisito futuro exigir localizar linhas fora de sua
posição atual.
