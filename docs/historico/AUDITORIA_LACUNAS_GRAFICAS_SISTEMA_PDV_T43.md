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
- **Atualização T47 em 05/11/2026:** suíte completa com **909 testes
  aprovados**; capacidades fabricadas, vínculo, expiração, logout, desativação,
  concorrência e falha comercial após consumo foram verificados somente em
  bancos temporários.
- **Atualização INT-D2 em 05/11/2026:** suíte completa com **926 testes
  aprovados**; o Histórico passou a executar o T43 exclusivamente com a
  capacidade pontual do T47, preservando a sessão Caixa e atualizando lista e
  detalhe somente após sucesso comprovado. Os testes de integração utilizaram
  exclusivamente bancos temporários.
- **Atualização T48 em 05/11/2026:** suíte completa com **946 testes aprovados**;
  emissão, apresentação única, rotação, consumo concorrente, rollback, política
  de senha, revogação processual e recuperação pelo login foram verificados
  exclusivamente em bancos temporários.
- **Atualização INT-E em 05/11/2026:** suíte completa com **961 testes
  aprovados**; gestão gráfica de contas Caixa, permissões administrativas,
  ativação/desativação, revogação processual, troca de operador e bloqueios por
  atendimento ou commit incerto foram verificados exclusivamente em bancos
  temporários.
- Inspeção somente leitura do banco SQLite incluído no ZIP: **`PRAGMA user_version = 0`**, com tabela `produtos`; após o T48, o código espera **versão 9** para persistência, histórico, cancelamento, auditoria, identidade e recuperação offline. O banco original não foi migrado.

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

### Resolvido pela INT-D2 — Cancelamento gráfico autorizado

O Histórico oferece “Solicitar cancelamento” somente para vendas ativas e
sessões autenticadas. O diálogo apresenta ID, data, valor, itens e pagamentos,
exige motivo e confirmação expressa, então abre a autorização administrativa do
T47 para a venda exata. A capacidade é consumida pelo T43 e a consulta só muda
para CANCELADA após sucesso transacional comprovado.

Desistência, credencial inválida, administrador inativo, capacidade expirada,
fabricada, reutilizada ou vinculada a outro ID, repetição e falha SQLite não
produzem sucesso falso. Nova tentativa exige nova autorização; a sessão Caixa
permanece Caixa e o bloqueio por fechamento incerto impede a execução.

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

### Resolvido pelo T47 — Autorização pontual não forjável

Sessões autenticadas e autorizações pontuais agora dependem de registros
processuais emissores e nonces criptográficos. Objetos construídos manualmente
não são reconhecidos. A capacidade se vincula à sessão Caixa, operação e venda,
expira em 60 segundos e é removida sob bloqueio antes de qualquer efeito no
SQLite. O T43 consome exclusivamente esse contrato e conserva a identidade do
administrador na auditoria.

A INT-D2 conecta o diálogo auxiliar ao formulário da INT-D1 sem criar um segundo
mecanismo de autorização. O T48 acrescenta recuperação offline de Administrador
por códigos de uso único, sem autenticação automática. A INT-E conclui o
provisionamento gráfico e a situação das contas Caixa, além da troca segura de
operador pelo mesmo login.

### Resolvido pela INT-E — Administração mínima e troca de operador

A página Administração lista, cadastra, ativa e desativa somente contas Caixa.
Os serviços revalidam sessão e perfil Administrador independentemente da
visibilidade dos controles. Senhas iniciais seguem a política existente e nunca
entram na sessão; desativação revoga sessões e capacidades do operador.

Trocar operador invalida a sessão atual e reabre o diálogo único de login.
Itens, pagamentos, confirmação pendente ou commit incerto bloqueiam troca e
fechamento da janela para impedir perda silenciosa do atendimento.

## Itens já cobertos por tickets futuros (não antecipar)

- T44: persistência e auditoria de preços resolvidas; consulta gráfica de 12
  meses permanece posterior.
- T45–T48 e INT-E resolvidos; a homologação manual do Marco 2 precede o avanço
  para as entregas de produção e confiabilidade do Marco 3.
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
5. **INT-D2 — resolvida:** execução do cancelamento protegida por autorização pontual dos T45–T47.
6. **INT-E — resolvida:** gestão básica de Caixa e troca segura pelo login único.
7. Registrar ticket/entrega futura para visualização dos últimos 12 meses de preços e, se permanecer no escopo, categorias personalizáveis.
8. Corrigir documentação operacional desatualizada, quando houver ticket de higiene: `docs/historico/ESTADO_ATUAL.md` descreve um estágio antigo; não confundir com fonte de estado atual. O arquivo `.gitignore` já cobre `.venv`, `.pytest_cache`, `__pycache__`, `.vscode` e `data/*.db` — ignorar não remove arquivos já rastreados.

## Critério de conclusão

O fluxo gráfico entre confirmação e registro definitivo foi conectado pela
INT-A, o histórico passou a ser acessível por página interna na INT-B e a
administração de produtos foi integrada pela INT-C. O cancelamento gráfico foi
conectado pela INT-D2 à autorização pontual do T47 e à transação do T43, sem
elevar a sessão operacional. A recuperação offline foi concluída no T48 e a
gestão básica de operadores na INT-E. Os testes automatizados não substituem a
validação operacional no Windows, e a homologação de leitor físico permanece
pendente.
