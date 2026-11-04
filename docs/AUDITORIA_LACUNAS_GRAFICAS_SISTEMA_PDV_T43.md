# Auditoria de integração gráfica e cobertura do backlog — Sistema-PDV após T43

**Base examinada:** ZIP `Sistema-PDV - Copia.zip`, fornecido pelo usuário. Análise realizada somente sobre uma cópia isolada; nenhum arquivo original foi alterado.

## Verificações realizadas

- Inspeção de `interface/`, `services/`, `repositories/`, `database/`, `models/` e `docs/TICKETS_RENUMERADO.md` (T01–T62).
- `pytest` excluindo sete arquivos que importam Qt: **722 testes aprovados**. Os testes gráficos não puderam ser executados neste ambiente por ausência de PySide6. O relatório prévio do Codex mencionou **795 testes aprovados** no Windows; esse resultado não foi reproduzido integralmente aqui.
- **Atualização INT-A/INT-B em 04/11/2026:** suíte completa executada no ambiente de
  desenvolvimento com PySide6, totalizando **822 testes aprovados**. Todos os
  bancos criados pelos novos testes permaneceram sob `tmp_path`.
- Inspeção somente leitura do banco SQLite incluído no ZIP: **`PRAGMA user_version = 0`**, com tabela `produtos`; o código atual espera **versão 6** para persistência, histórico e cancelamento. O banco original não foi migrado.

## Lacunas prioritárias identificadas no código

### Resolvido pela INT-A — Fechamento gráfico e persistência

`interface/janela_principal.py` conecta a confirmação comercial a
`persistir_venda_confirmada_idempotente()`. Um UUID é mantido durante toda a
tentativa lógica; falha definitiva preserva a venda para nova tentativa e
resultado incerto bloqueia a operação até verificação explícita com o mesmo
UUID. Somente o sucesso comprovado apresenta o ID e limpa itens e pagamentos.

**Cobertura:** registrada como **INT-A** no backlog oficial.

### Resolvido pela INT-A — Inicialização e migração segura

`interface/aplicacao.py` prepara o banco antes de criar a janela principal.
Bancos novos recebem o esquema atual; bancos atualizados não geram backup
desnecessário; bancos desatualizados só migram após backup SQLite verificado em
`backups/pre_migracao`; versões futuras e falhas interrompem a abertura da
operação comercial.

**Cobertura:** registrada como **INT-A**; rotação, agendamento e restauração
continuam pertencendo aos T55–T57.

### Resolvido pela INT-B — Histórico acessível por página interna

Uma única janela principal mantém menu horizontal e páginas internas. A página
Histórico reutiliza `buscar_venda_resumida_por_id`,
`listar_vendas_resumidas_por_data` e `buscar_venda_detalhada_por_id`, com busca
por ID/data, apresentação local em São Paulo e detalhamento somente leitura de
itens, snapshots, quantidades, pagamentos e cancelamento. A navegação preserva
a venda aberta e é bloqueada durante commit incerto.

**Cobertura:** registrada como **INT-B** no backlog oficial.

### P1 — Cancelamento sem interface, e autorização ainda não implementada

`services/cancelamento_venda_service.py` existe, mas não está acessível pela janela. A autorização aceita identidade no contexto, não autentica credenciais. T45–T47 cobrem segurança, mas **não há ticket explícito de UI de cancelamento após conectar a autorização**.

**Cobertura futura:** registrada como **INT-D**, condicionada à autenticação e
autorização dos T45–T47. Não expor a operação antes dessa dependência.

### P1 — Administração/cadastro de produtos sem UI

`services/produto_service.py` e `repositories/produto_repository.py` expõem criar/listar/atualizar/ativar/desativar; `interface/` só consulta produto por código para vender. Não existe tela para cadastrar ou corrigir produtos. Isso inviabiliza administrar o catálogo pelo PDV novo.

**Cobertura futura:** registrada como **INT-C** para cadastro, listagem,
edição, ativação e inativação. O T44 permanece responsável pelo histórico de
preços. Categorias customizáveis continuam futuras e sem entrega própria nesta
sequência.

### P1 — Histórico de preços: parte da entrega adiada sem ticket claro

T44 prevê alteração de preço auditada e "tela 12 meses depois", mas a visualização futura não aparece com ticket inequívoco. Registrar essa segunda etapa antes de considerar o fluxo administrativo concluído.

## Itens já cobertos por tickets futuros (não antecipar)

- T44: atualização/histórico de preços (persistência e auditoria), não necessariamente a tela posterior.
- T45–T48: primeiro acesso, conta Caixa, autorização pontual e recuperação offline.
- T49–T51: logs, versão e diagnóstico.
- T52–T54: catálogo em memória e contingência/degradação.
- T55–T57: backup e restauração.
- T58–T60: roteiro de migração, empacotamento e instalador.
- T61–T62: desempenho e validação operacional/hardware físico.
- Pendências já documentadas: layout, espaçamentos, legibilidade, divisão sugerida no diálogo de pagamentos e atalho separado de conclusão.

## Recomendações de sequência (sem renumerar tickets existentes)

1. **INT-A — resolvida:** bootstrap seguro e fechamento idempotente integrado.
2. **INT-B — resolvida:** navegação por páginas e histórico completo somente leitura.
3. **INT-C — pendente:** tela de cadastro, edição, listagem e ativação/desativação de produtos; histórico de preços permanece separado.
4. **INT-D — pendente:** depois de T45–T47, GUI de cancelamento protegida por autorização pontual.
5. Registrar ticket/entrega futura para visualização dos últimos 12 meses de preços e, se permanecer no escopo, categorias personalizáveis.
6. Corrigir documentação operacional desatualizada, quando houver ticket de higiene: `docs/ESTADO_ATUAL.md` descreve um estágio antigo; não confundir com fonte de estado atual. O arquivo `.gitignore` já cobre `.venv`, `.pytest_cache`, `__pycache__`, `.vscode` e `data/*.db` — ignorar não remove arquivos já rastreados.

## Critério de conclusão

O fluxo gráfico entre confirmação e registro definitivo foi conectado pela
INT-A, e o histórico passou a ser acessível por página interna na INT-B.
Permanecem ausentes as funcionalidades de administração de produtos e
cancelamento. Os testes automatizados não substituem a validação operacional no
Windows, e a homologação de leitor físico permanece pendente.
