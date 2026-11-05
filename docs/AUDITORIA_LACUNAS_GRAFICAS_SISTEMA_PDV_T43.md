# Auditoria de integração gráfica e cobertura do backlog — Sistema-PDV após T43

**Base examinada:** ZIP `Sistema-PDV - Copia.zip`, fornecido pelo usuário. Análise realizada somente sobre uma cópia isolada; nenhum arquivo original foi alterado.

## Verificações realizadas

- Inspeção de `interface/`, `services/`, `repositories/`, `database/`, `models/` e `docs/TICKETS_RENUMERADO.md` (T01–T62).
- `pytest` excluindo sete arquivos que importam Qt: **722 testes aprovados**. Os testes gráficos não puderam ser executados neste ambiente por ausência de PySide6. O relatório prévio do Codex mencionou **795 testes aprovados** no Windows; esse resultado não foi reproduzido integralmente aqui.
- **Atualização INT-A/INT-B em 04/11/2026:** suíte completa executada no ambiente de
  desenvolvimento com PySide6, totalizando **822 testes aprovados**. Todos os
  bancos criados pelos novos testes permaneceram sob `tmp_path`.
- **Atualização INT-C em 05/11/2026:** suíte completa com **836 testes
  aprovados**; os testes de produtos utilizaram exclusivamente bancos sob
  `tmp_path`. A interface da INT-C foi posteriormente aprovada em teste manual.
- **Atualização INT-D1 em 05/11/2026:** suíte completa com **845 testes
  aprovados**; os cenários de solicitação visual utilizaram exclusivamente
  bancos temporários e confirmaram ausência de alteração comercial.
- **Atualização T44 em 05/11/2026:** suíte completa com **854 testes
  aprovados**; migração e auditoria transacional de preços foram verificadas
  somente em bancos temporários.
- **Atualização T45 em 05/11/2026:** suíte completa com **879 testes
  aprovados**; criação concorrente, hash, migração, estados inconsistentes e
  bloqueio operacional foram verificados somente em bancos temporários.
- **Atualização T46 em 05/11/2026:** suíte completa com **893 testes
  aprovados**; autenticação, perfis, limitação temporária, logout e revalidação
  de sessão foram verificados exclusivamente em bancos temporários.
- Inspeção somente leitura do banco SQLite incluído no ZIP: **`PRAGMA user_version = 0`**, com tabela `produtos`; após o T45, o código espera **versão 8** para persistência, histórico, cancelamento, auditoria de preços e identidade inicial. O banco original não foi migrado.

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

### Parcialmente resolvido pela INT-D1 — Solicitação visual de cancelamento

O Histórico oferece “Solicitar cancelamento” somente para vendas ativas. O
diálogo apresenta ID, data, valor, status e contagens comerciais, exige motivo
e informa que nenhum cancelamento é executado. Vendas canceladas continuam
consultáveis e não reabrem o fluxo.

O código não chama `cancelar_venda()`, não cria autorizador fictício e não grava
solicitação ou status intermediário. A execução permanece na **INT-D2**,
condicionada à autenticação e autorização reais dos T45–T47.

### Resolvido pela INT-C — Administração de produtos em página interna

`interface/pagina_produtos.py` lista e pesquisa por código ou nome, cadastra,
edita e ativa/inativa produtos reutilizando serviço e repositório. Categorias
continuam textuais e preços são convertidos exatamente para centavos. A página
preserva a venda e os pagamentos ao navegar, reflete novos cadastros nas
consultas seguintes do caixa e trata falhas de banco sem encerrar a aplicação.

Com itens lançados, cadastro novo é permitido, mas edição e mudança de situação
de produto existente são recusadas no momento da operação. Commit incerto
mantém o bloqueio integral da INT-A. O T44 permanece responsável pelo histórico
de preços, e categorias customizáveis continuam futuras.

### Parcialmente resolvido pelo T44 — Histórico de preços persistente

O esquema versão 7 registra alterações efetivas de preço na mesma transação da
edição do produto, com valores anterior/novo e instante UTC. O histórico é
preservado após novas alterações e inativação; snapshots comerciais continuam
independentes. Não há responsável fictício nem expurgo automático.

A consulta gráfica dos últimos 12 meses permanece explicitamente adiada no
backlog oficial. Ela não foi antecipada e ainda precisa de entrega própria antes
de o fluxo administrativo ser considerado completo.

### Resolvido pelo T45 — Primeiro administrador em modo fail-closed

O esquema versão 8 armazena usuários e um marcador durável da configuração
inicial. O administrador é criado uma única vez sob transação concorrente, com
senha derivada por `scrypt` e salt individual. Ausência inesperada, marcador
divergente ou usuário órfão bloqueiam o fluxo sem oferecer recriação.

### Resolvido pelo T46 — Login, sessão e escopo Caixa

O ponto de entrada agora apresenta login após o primeiro acesso e somente cria a
janela principal com uma sessão autenticada. Caixa pode operar vendas e consultar
o Histórico, mas não acessa Produtos; Administrador conserva esse acesso e pode
provisionar Caixa pelo serviço protegido. Logout encerra a sessão e fecha a
interface, e conta desativada perde acesso na próxima operação revalidada.

A indisponibilidade temporária entre T45 e T46 foi eliminada sem criar bypass.
INT-D2 ainda depende da autorização pontual real do T47; o formulário da INT-D1
continua sem qualquer efeito comercial.

## Itens já cobertos por tickets futuros (não antecipar)

- T44: persistência e auditoria de preços resolvidas; consulta gráfica de 12
  meses permanece posterior.
- T45–T46 resolvidos; T47–T48: autorização pontual e recuperação offline
  permanecem futuros.
- T49–T51: logs, versão e diagnóstico.
- T52–T54: catálogo em memória e contingência/degradação.
- T55–T57: backup e restauração.
- T58–T60: roteiro de migração, empacotamento e instalador.
- T61–T62: desempenho e validação operacional/hardware físico.
- Pendências já documentadas: layout, espaçamentos, legibilidade, divisão sugerida no diálogo de pagamentos e atalho separado de conclusão.

## Recomendações de sequência (sem renumerar tickets existentes)

1. **INT-A — resolvida:** bootstrap seguro e fechamento idempotente integrado.
2. **INT-B — resolvida:** navegação por páginas e histórico completo somente leitura.
3. **INT-C — resolvida:** cadastro, edição, listagem e ativação/desativação em página interna; histórico de preços permanece separado.
4. **INT-D1 — resolvida:** formulário e confirmação visual sem efeito comercial.
5. **INT-D2 — pendente:** depois de T45–T47, execução do cancelamento protegida por autorização pontual.
6. Registrar ticket/entrega futura para visualização dos últimos 12 meses de preços e, se permanecer no escopo, categorias personalizáveis.
7. Corrigir documentação operacional desatualizada, quando houver ticket de higiene: `docs/ESTADO_ATUAL.md` descreve um estágio antigo; não confundir com fonte de estado atual. O arquivo `.gitignore` já cobre `.venv`, `.pytest_cache`, `__pycache__`, `.vscode` e `data/*.db` — ignorar não remove arquivos já rastreados.

## Critério de conclusão

O fluxo gráfico entre confirmação e registro definitivo foi conectado pela
INT-A, o histórico passou a ser acessível por página interna na INT-B e a
administração de produtos foi integrada pela INT-C. Permanece ausente a
execução autorizada do cancelamento: a INT-D1 cobre somente a preparação visual
e a INT-D2 depende do T47 sobre a base autenticada dos T45–T46. Os testes
automatizados não substituem a
validação operacional no Windows, e a homologação de leitor físico permanece
pendente.
