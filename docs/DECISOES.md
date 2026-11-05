# Registro de decisões arquiteturais (ADR resumido)

**Status de todas as decisões abaixo: aprovadas no planejamento; não necessariamente implementadas.** A numeração `DEC-012+1` é intencional.

- **DEC-001** — Venda ativa em memória; apenas venda confirmada persiste; desenho permite futura recuperação.
- **DEC-002** — Aplicativo desktop instalado.
- **DEC-003** — Windows primeiro, sem impedir portabilidade futura.
- **DEC-004** — Python como linguagem principal.
- **DEC-005** — PySide6 Qt Widgets; separar domínio do Qt e verificar obrigações de licença.
- **DEC-006** — SQLite local; transações, integridade, migrações e backups.
- **DEC-007** — Monólito modular sem interfaces/abstrações antecipadas.
- **DEC-008** — Dinheiro em centavos (int), Decimal onde necessário; evitar float monetário.
- **DEC-009** — Código EAN-13 da etiqueta: subtotal codificado é a referência; validar padrão e preservar código bruto.
- **DEC-010** — Mostrar referência do catálogo e peso estimado; aviso não bloqueante quando aplicável; sem integração com balança.
- **DEC-011** — Produtos PESO/UNIDADE; para unidade, estimativa inicial inteira corrigível, sem modificar subtotal codificado; guardar procedência.
- **DEC-012** — Campo único de entrada; código curto abre diálogo contextual; 9999 abre Diversos; Enter/Esc e foco.
- **DEC-012+1** — Uma linha por etiqueta lida, mesmo para produtos iguais; inclusão manual pode agrupar quantidade.
- **DEC-014** — Remover linha da venda aberta e desfazer apenas a última remoção.
- **DEC-015** — Confirmar fechamento e detalhamento dos pagamentos em diálogo antes de transação atômica.
- **DEC-016** — Cancelamento interno integral, com motivo/data, preservando histórico; sem estorno automático financeiro/fiscal.
- **DEC-017** — ID de venda inteiro crescente, não reaproveitado; exibição com zeros à esquerda; pesquisa ID/data.
- **DEC-018** — Pagamentos 1:N, modalidades repetíveis, sugestão de saldo restante, divisão igual em centavos; sem controle de troco/caixa.
- **DEC-019** — Cadastro e edição permitidos durante venda; snapshot preserva itens; registrar histórico de alteração de preços com consulta aos 12 meses, sem exclusão automática.
- **DEC-020** — Login inicial; contas básicas Administrador e Caixa; autorização por operação crítica, sem sessão administrativa permanente; preparado para usuários individuais.
- **DEC-021** — Logs, modo de cálculo degradado quando possível; sem fila durável na V1; nova tentativa idempotente e protocolo manual para persistência incerta.
- **DEC-022** — Backup automático local e externo, integridade e restauração testada; falha em backup externo não bloqueia caixa.
- **DEC-023** — Instalador Windows com atualização manual, programa e dados separados, migrações versionadas seguras.
- **DEC-024** — pytest unitário/integração, pytest-qt para fluxos críticos e teste no hardware real; metas objetivas.
- **DEC-025** — Antes de migrar banco existente desatualizado, criar backup
  único pela API SQLite em `backups/pre_migracao` ao lado do banco e exigir
  `PRAGMA integrity_check = ok`; falha bloqueia a aplicação sem migrar. Banco
  novo ou já atualizado não gera cópia, e versão futura é recusada.
- **DEC-026** — A interface operacional usa uma única janela principal com
  menu horizontal persistente e páginas internas independentes. Frente de
  Caixa mantém seu estado ao navegar; Histórico é somente leitura; páginas de
  Produtos e Administração só são habilitadas quando suas integrações forem
  implementadas. Commit incerto bloqueia a saída da Frente de Caixa.
- **DEC-027** — A página Produtos permite novos cadastros durante uma venda em
  andamento, mas bloqueia edição e ativação/inativação de produtos existentes
  enquanto houver itens lançados. O código fica somente leitura na edição;
  categorias continuam textuais e snapshots já lançados não são alterados.
- **DEC-028** — O cancelamento gráfico é dividido em INT-D1 e INT-D2. A INT-D1
  apenas apresenta a venda e valida o motivo, sem persistir, criar identidade ou
  chamar o serviço de cancelamento. A INT-D2 conecta esse pedido à autorização
  pontual dos T45–T47 e ao T43: a capacidade é vinculada à sessão, operação e
  venda, consumida uma vez, e a interface só anuncia sucesso após a transação.
- **DEC-029** — Alterações efetivas do preço de venda são auditadas na mesma
  transação da atualização do produto, guardando valor anterior, novo e instante
  UTC. Não há expurgo automático nem responsável fictício; identidade só será
  adicionada quando houver autenticação real. A consulta gráfica de 12 meses é
  uma etapa posterior e não limita a retenção dos registros.
- **DEC-030** — O primeiro administrador usa `scrypt` da biblioteca padrão com
  `N=2^14`, `r=8`, `p=5`, salt aleatório de 16 bytes e chave de 32 bytes; versão
  e parâmetros ficam no formato armazenado. A configuração é marcada por FK
  durável e a aplicação permanece fail-closed sem o login do T46. Estados
  ambíguos nunca liberam recriação nem operação comercial.
- **DEC-031** — A janela operacional exige `SessaoUsuario` criada exclusivamente
  por login válido. Caixa acessa Frente de Caixa e Histórico; Produtos e
  provisionamento de Caixa exigem Administrador revalidado no banco. Logout
  invalida a sessão e fecha a janela. Cinco falhas por identificação em sessenta
  segundos geram espera de trinta segundos somente em memória, evitando bloqueio
  durável explorável. Conta desativada perde permissão na próxima operação
  protegida. T47 continua responsável por autorização pontual, sem elevação da
  sessão.
- **DEC-032** — Sessões e autorizações pontuais são capacidades opacas mantidas
  somente em memória. A sessão usa nonce criptográfico e identidade de objeto
  registrada; a autorização expira em 60 segundos e se vincula ao solicitante,
  operação e recurso. O consumo é único sob bloqueio e precede o efeito
  comercial, portanto falha posterior não restaura a capacidade. Reinício,
  logout, expiração e conta desativada falham fechados. O T43 não mantém caminho
  alternativo baseado em booleano, perfil textual ou contexto construível.

## Decisões que exigem cuidado
- O código de produto existente é protegido contra edição pela interface; a
  forma de venda pode ser alterada somente sem itens na venda em andamento.
- Uma quantidade derivada do preço é **estimada**, nunca prova de pesagem. Quantidade informada manualmente não equivale a pesagem certificada.
- Recuperação de acesso: códigos únicos offline gerados na configuração, armazenados por hash e consumidos uma vez.
- Código `9999` reservado; nenhum produto comum poderá usá-lo.
- O histórico diário converte o dia civil de São Paulo para intervalo UTC
  semiaberto e usa índice composto em `vendas(registrada_em, id)`; isso atende
  filtro e ordenação sem aplicar funções sobre a coluna persistida.
- O T43 registra a identidade devolvida pelo consumo da capacidade do T47. A
  INT-D1 coleta o motivo sem fabricar autorização; a INT-D2 abre o diálogo do
  T47 e entrega exclusivamente a capacidade emitida ao serviço transacional.
- A fila de contingência de persistência e eventual fila de documentos fiscais são responsabilidades diferentes e futuras. NFC-e tem regras específicas da SEFAZ, não é mero reenvio livre de totais.
