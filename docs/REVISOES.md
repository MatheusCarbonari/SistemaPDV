# Revisões de arquitetura — aprovadas

## Revisão 01 — Entrada manual por peso
Código interno curto de produto PESO abre diálogo com campos peso kg e total R$. Editar peso recalcula total pelo preço cadastrado; editar total recalcula **peso estimado**. Último campo editado prevalece. Exemplo fictício: R$ 99,00/kg × 1,750 kg = R$ 173,25. Enter confirma e inclui; Esc fecha sem incluir e devolve foco. Pode servir de consulta sem modificar a venda. Etiqueta lida segue a DEC-009: seu subtotal prevalece.

## Revisão 02 — Falha na finalização
Falha ou resposta incerta: conservar itens e pagamentos na memória; oferecer nova tentativa com identificador único e prevenção de duplicações; nunca presumir não gravado quando verificação for impossível. Persistindo a falha, oferecer resumo e exigir aviso/confirmação explícita antes de liberar tela. Operador pode guardar papel com etiquetas e comprovante da maquininha ou anotar resumo completo. Continuar no modo de cálculo, se dados em memória forem suficientes. Recuperação/reconciliação manual posterior. **Sem fila durável nesta versão.** Evitar segunda cobrança por falha de software.

## Revisão 03 — Modelo de dados
Tabelas comerciais-alvo: produtos, historico_precos, vendas, itens_venda, pagamentos. Uma venda tem muitos itens e muitos pagamentos; um produto pode originar muitos itens e alterações de preço. Referência a produto é opcional no item de venda, para permitir **Diversos**, código reservado `9999`, nome fixo e valor informado, sem descrição extra nem produto cadastrado. Snapshot de nome, modalidade, preço de referência, subtotal, código original, tipo/precisão/proveniência da quantidade e demais campos históricos necessários. Produtos inativáveis, não excluídos fisicamente.

## Revisão 04 — Acesso e segurança
Primeiro uso cria administrador, sem senha padrão; duas contas básicas (Administrador e Caixa); login exigido para operar. Autorizações críticas: modificar preço, inativar produto, cancelar venda concluída, restaurar backup e configurações relevantes. Confirmação pontual, sem manter permissão elevada. Códigos de recuperação offline de uso único, exibidos para guarda segura e armazenados com hash. Preparação para expansão de usuários/autorizações.

## Revisão 05 — Backup, atualização, restauração
Programa/dados em locais diferentes. Instalador Windows e migrações versionadas; migrar somente após backup válido, com programa fechado. Falha: interrupção segura; não restaurar banco antigo automaticamente. Backup local **a cada 2 horas de funcionamento**, backup externo também **a cada 2 horas se disponível**; backup ao encerrar se houver mudanças; obrigatório antes de migrações. Retenção local **7 diários + 4 semanais** e externa **30 diários**; rotação respeita os pontos de restauração, sem destruir a última cópia boa. Validar integridade e testar restauração. Falha do destino externo avisa, sem impedir vendas. Restaurar exige administrador, confirmação e alerta de perda possível de dados mais recentes.

## Revisão 06 — Escopo, marcos, aceitação
Três marcos: (1) núcleo de leitura e cálculo; (2) fluxo comercial e autenticação; (3) confiabilidade e instalação. Metas iniciais: etiqueta até 200 ms; inclusão manual 200 ms; recálculo 100 ms; abertura pagamento 300 ms; finalização SQLite 1 s em operação normal. Medições repetidas e no equipamento real; metas ainda não validadas. Testes automatizados de regras, SQL e interface crítica; scanner e instalação testados fisicamente. Não liberar para produção só porque os testes unitários passam.
