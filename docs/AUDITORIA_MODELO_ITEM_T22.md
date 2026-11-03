# T22 — Auditoria de cobertura do modelo de item

## Escopo e conclusão

Foram comparados `ProdutoSnapshot`, `ItemVenda`, as fábricas de item de
etiqueta, os serviços de venda em andamento e seus testes com `DECISOES.md`,
`REVISOES.md`, `ESCOPO.md` e `TICKETS_RENUMERADO.md`.

Não foi identificada lacuna funcional atual que exija alteração no código de
produção. O núcleo implementado atende ao contrato aprovado para itens de
etiqueta e está preparado, sem antecipação, para os fluxos futuros indicados
abaixo.

## Matriz de cobertura

| Requisito analisado | Evidência | Situação | Lacuna e consequência prática | Correção mínima / ticket |
|---|---|---|---|---|
| Snapshot comercial com ID opcional, código, nome, forma de venda e preço em centavos | `models/produto_snapshot.py`; `test_criar_snapshot_produto_copia_dados_comerciais`; `test_criar_snapshot_produto_preserva_id_ausente` | **Atendido** | Nenhuma. O preço inteiro é copiado sem recálculo. | Nenhuma. |
| Snapshot imutável e independente do cadastro | `ProdutoSnapshot` é `frozen=True`; `test_snapshot_permanece_independente_apos_mutacao_do_produto`; `test_item_criado_nao_mantem_referencia_mutavel_ao_produto` | **Atendido** | Nenhuma. Alterações posteriores no `Produto` não atingem o item. | Nenhuma. |
| Origem, subtotal e código bruto da etiqueta | `criar_item_de_etiqueta()` e `criar_item_de_etiqueta_com_estimativa()` copiam `valor_centavos` e `codigo_barras`; testes de valores exatos e preservação | **Atendido** | Nenhuma. O subtotal codificado permanece a referência, conforme DEC-009. | Nenhuma. |
| Quantidade ausente quando não informada ou não estimável | `ItemVenda` exige `NAO_INFORMADA` quando `quantidade is None`; testes de preço zero, subtotal zero e peso arredondado a zero | **Atendido** | Nenhuma. O item não afirma uma medida inexistente. | Nenhuma. |
| Quantidade estimada de PESO e UNIDADE com procedência | `criar_item_de_etiqueta_com_estimativa()` reutiliza `estimar_peso()` e `estimar_unidades()`; testes esperam `Decimal("0.896")` e `Decimal("2")` com origem `ESTIMADA` | **Atendido** | Nenhuma. Estimativa não altera subtotal nem é apresentada como medida real, conforme DEC-010 e DEC-011. | Nenhuma. |
| Quantidade informada | `ItemVenda` aceita `Decimal` positivo com origem `INFORMADA`; teste `test_item_venda_manual_aceita_quantidade_decimal_informada` | **Parcial** | O contrato de domínio existe, mas ainda não há fábrica para inclusão manual. Não afeta etiquetas. | Fluxos de UNIDADE no **T25** e PESO no **T26**; ligação à interface no **T29**. |
| Validações básicas do item | `ItemVenda.__post_init__()` valida subtotal inteiro não negativo e rejeita `bool`; origens; snapshot; quantidade `Decimal`, positiva e finita; coerência da procedência; código de barras por origem. Testes cobrem combinações válidas e inválidas. | **Atendido** | Nenhuma lacuna comprovada. Revalidar checksum no item duplicaria a responsabilidade do parser. | Nenhuma. |
| Imutabilidade do item e preservação das entradas | `ItemVenda` é `frozen=True`; testes de imutabilidade, ausência de mutação de `ProdutoEtiqueta` e snapshot independente | **Atendido** | Nenhuma. Os campos do snapshot também são valores imutáveis. | Nenhuma. |
| Produto opcional para Diversos | `produto: ProdutoSnapshot | None` e construção manual sem produto são aceitos | **Futuro** | O modelo comporta o caso, mas o fluxo comercial do código `9999` ainda não existe. | **T27**. |
| Uma linha por etiqueta e compatibilidade com venda em andamento | `VendaEmAndamento` armazena `tuple[ItemVenda, ...]`; `adicionar_item()` preserva ordem e identidade e permite a mesma instância repetida; testes cobrem duplicatas e versões independentes | **Atendido** | Nenhuma. Itens iguais não são agrupados, conforme DEC-012+1. | Identificação estável para seleção será tratada no **T24**, sem mudar este contrato antecipadamente. |
| Totalização, apresentação e persistência histórica | Não pertencem ao modelo atual; planejamento as separa do item em memória | **Futuro** | Ainda não há total da venda, lista gráfica nem gravação do snapshot. Isso não invalida o item em memória. | Totalização no **T23**, apresentação no **T30** e esquema persistente de itens no **T33**. |

## Fronteiras confirmadas

- Categoria, origem cadastral, situação ativa e timestamps não fazem parte do
  snapshot comercial aprovado no T09; sua ausência não é uma lacuna.
- O item de etiqueta recebe `ProdutoEtiqueta` já interpretado e associado. Não
  deve consultar SQLite nem repetir validação EAN-13.
- `criar_item_de_etiqueta()` permanece como fábrica sem estimativa, enquanto
  `criar_item_de_etiqueta_com_estimativa()` oferece a composição prevista no
  T15. Os dois contratos são úteis e estão cobertos.
- Identidade de linha, entrada manual, Diversos, totalização, interface e
  persistência são responsabilidades planejadas em tickets próprios. Antecipá-las
  neste ticket aumentaria o contrato sem resolver uma falha atual.

## Resultado da auditoria

O modelo de item já oferece o núcleo necessário: snapshot comercial estável,
subtotal e código originais, procedência explícita da quantidade, validações de
domínio e composição imutável com a venda em andamento. A única cobertura
parcial é intencional: `INFORMADA` já é representável, mas seus fluxos de criação
pertencem aos T25 e T26. As demais pendências listadas são funcionalidades
futuras, não defeitos atuais.
