# Escopo V1 — Sistema-PDV

## Objetivo
Um caixa Windows rápido, simples e operável offline, inicialmente para um único terminal, uma compra por vez. A V1 calcula e registra vendas comerciais **internas**, sem substituir as obrigações fiscais ou o emissor existente.

## Fluxo do operador
Leitura de código de barras EAN-13 interno ou digitação de código curto, lista de linhas (cada etiqueta é independente), subtotal por linha e total. Etiqueta traz produto e subtotal; normalmente **não** traz peso nem quantidade. Exibir estimativas sem afirmar medidas reais. Janela para PESO com peso/valor vinculados, UNIDADE com quantidade, `9999` com nome fixo Diversos e valor. Enter confirma; Esc cancela; retorno do foco ao leitor. Remover/desfazer última remoção. Catálogo PESO/UNIDADE, preço, origem, ativo e categorias personalizáveis. Atualização do catálogo não altera snapshots de itens.

## Finalização
Dinheiro/crédito/débito/Pix, registros independentes inclusive modalidade repetida, divisão igual em centavos, soma exata ao total e confirmação explícita. Sem troco operacional nem controle de gaveta. Histórico por venda, detalhes de itens/pagamentos e cancelamento interno integral justificado, sem estorno automático externo ou fiscal. Falha de SQLite: preservar compra, tentar novamente de modo idempotente, permitir liberação consciente com protocolo manual e modo de cálculo quando viável.

## Operação e manutenção
Login de Caixa/Administrador, autorização pontual de ações críticas, recuperação por códigos offline. Logs, diagnóstico exportável sem segredos, backup local/externo, instalação Windows, migrações, validação física de scanner e desempenho.

## Fora do escopo V1
NFC-e/SEFAZ, fila de contingência durável, estoque detalhado, produção/receitas, fornecedores, relatórios avançados, múltiplos caixas, atualização online automática, integração direta à balança, descrição personalizada em Diversos, controle de troco.
