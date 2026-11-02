# Catálogo de etiquetas reais

Este catálogo registra somente amostras apresentadas explicitamente como reais.
Ele não inclui códigos criados para testar limites ou mensagens de erro.

## Amostras disponíveis

| Código de barras | Campo de produto | Produto normalizado | Subtotal | Forma de venda |
|---|---:|---:|---:|---|
| `2023400053672` | `0234` | `234` | 5.367 centavos | Não documentada |
| `2001100137083` | `0011` | `11` | 13.708 centavos | Não documentada |
| `2014700015903` | `0147` | `147` | 1.590 centavos | Não documentada |

## Origem e verificação

As três amostras foram fornecidas como etiquetas reais nos requisitos do T07 e
incorporadas aos testes pelo commit `bcae309`. O teste parametrizado em
`tests/test_catalogo_etiquetas_reais.py` verifica o checksum EAN-13, preserva o
código completo e confere produto normalizado e subtotal em centavos.

Os casos de checksum incorreto, prefixo diferente de `2`, campo intermediário
diferente de `00`, valores-limite e outros dados inválidos são sintéticos e
permanecem separados em `tests/test_ean13.py` e
`tests/test_etiqueta_balanca.py`.

## Pendência de evidência

O repositório não contém foto, exportação da balança ou cadastro que associe
essas etiquetas a produtos classificados como `PESO` ou `UNIDADE`. O banco
legado também não contém os códigos de produto `234`, `11` ou `147`.

Por isso, não é possível cobrir honestamente as duas formas de venda com as
amostras atuais. Ficam pendentes ao menos uma etiqueta completa e autorizada de
produto por `PESO` e uma de produto por `UNIDADE`, acompanhadas da identificação
da forma de venda. Nenhuma classificação foi inferida do código de barras ou do
valor codificado.
