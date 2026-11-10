# Sistema-PDV — Auditoria Final do Marco 2

**Data:** 10/11/2026

**Commit auditado:** `17c0899 fix: permite alterar codigo do produto`

**Escopo:** implementação, testes e documentação do Marco 2, integrações,
consolidação e correções finais.

**Restrições respeitadas:** nenhuma regra ou migração foi alterada; nenhum banco
em `data/` foi aberto ou modificado; nenhum commit foi criado.

## 1. Parecer executivo

**Parecer: APTO E CONCLUÍDO para o encerramento formal do Marco 2.**

Não foi encontrada falha funcional nos testes automatizados: a suíte completa
passou em uma única execução, sem repetição e sem aviso Qt/COM. O código apresenta
cobertura consistente de schema, vendas, pagamentos, identidade, autorização,
cancelamento, produtos, categorias e interface.

O bloqueio de aceite foi removido pela confirmação do responsável de que a
homologação manual final aprovou **13 de 13 cenários**, já após a Revisão Visual
01–05 e as Correções Finais 01 e 02. As contradições documentais e a proteção de
artefatos apontadas originalmente também foram corrigidas. Não permanece achado
P1 aberto no escopo do Marco 2.

Este parecer não significa que o sistema esteja pronto para produção. Scanner,
desempenho, backup periódico, restauração, empacotamento e contingência durável
continuam pertencendo ao Marco 3.

## 2. Método e resultados

### Comandos executados

- `python -m pytest -q`: **1078 testes aprovados em 286,51 s** (`4m46s`).
- `python -m compileall -q .`: aprovado, sem saída de erro.
- `git diff --check`: aprovado.
- `git status --short`: somente `?? data/` antes da atualização deste relatório.

A suíte foi executada uma vez, integralmente, sem repetição de casos falhos. Não
houve indício de teste instável nesta rodada. Os testes que criam SQLite usam
`tmp_path` ou caminhos temporários explícitos; não foram encontradas chamadas de
teste aos caminhos padrão do banco operacional.

### Evidências consolidadas e origem

**Verificadas diretamente pelo Codex:** suíte integral com **1.078 testes
aprovados**; compilação; verificações do Git; inspeção de código e documentos; e
migração real v9→v10 em pasta temporária isolada. A migração preservou 4
produtos, 2 vendas, 4 itens, 3 pagamentos, 3 registros de histórico de preços,
2 usuários, estado de identidade e recuperação. IDs e relacionamentos foram
preservados; `PRAGMA integrity_check` retornou `ok`, `foreign_key_check` não
retornou linhas, o backup v9 foi criado e validado, e a aplicação offscreen leu
os registros migrados. Os arquivos temporários foram removidos ao final.

**Informadas e aprovadas pelo responsável:** homologação manual final com
**13/13 cenários aprovados**, aprovação da Revisão Visual 01–05 e aprovação das
Correções Finais 01 e 02. O Codex registra essa confirmação como evidência de
aceite, sem apresentá-la como execução manual independente própria.

### Qt e `0x8001010d`

O aviso `0x8001010d` não ocorreu nesta auditoria. O código corresponde a
`RPC_E_CANTCALLOUT_ININPUTSYNCCALL`: o Windows recusou uma chamada COM de saída
enquanto processava uma chamada síncrona de entrada. A classificação atual é
**P3, ambiental/intermitente sob observação**, porque não foi reproduzido, não
afetou os 1.078 testes e não há evidência de falha comercial associada. Se surgir
na aplicação real com perda de foco, travamento ou operação incompleta, deve ser
reclassificado e reproduzido com o contexto do evento Qt. Referência:
[Microsoft — HRESULT Values](https://learn.microsoft.com/openspecs/windows_protocols/ms-erref/705fb797-2175-4a90-b5a3-3918024b10b8).

## 3. Evidências por área

### Banco de dados

- `VERSAO_ESQUEMA = 10`; migrações sequenciais v0→v10 e recusa de versão futura.
- A migração representativa v9→v10 preserva IDs e atributos de produtos,
  referências de itens, histórico de preços e integridade referencial.
- A falha injetada na migração v10 restaura produtos, categorias e
  `user_version = 9`.
- `PRAGMA foreign_keys = ON` é aplicado a cada conexão; a migração executa
  `foreign_key_check` antes do commit.
- Índices de tentativa idempotente, histórico de vendas, histórico de preços,
  recuperação e categoria foram conferidos no schema e nos testes.
- Banco legado em WAL é copiado pela API de backup do SQLite, validado por
  `PRAGMA integrity_check = ok` e somente então migrado. Falhas de backup e de
  integridade interrompem antes da migração; falha de migração preserva a cópia.
- Banco novo e banco atualizado não criam backup desnecessário.
- Não houve acesso ao banco operacional durante esta auditoria.

### Vendas e pagamentos

- Leitura simulada de etiquetas documentadas, códigos manuais, produtos por
  peso/unidade e Diversos está coberta até a lista gráfica.
- Dinheiro permanece inteiro em centavos; quantidades usam `Decimal` e os testes
  cobrem arredondamento, diferenças de um centavo e divisão exata.
- Inclusão, edição, remoção, modalidades repetidas, sugestão de divisão e
  atalhos de pagamento foram exercitados.
- Confirmação separada, transação venda+itens+pagamentos, rollback e FKs foram
  validados.
- UUID idempotente, repetição compatível, colisão incompatível e commit incerto
  possuem testes de falha antes, durante e depois do commit.
- Snapshots históricos permanecem independentes do cadastro atual.

### Segurança e usuários

- Primeiro acesso fail-closed, login, logout, troca cancelada e troca confirmada
  estão cobertos.
- Sessões fabricadas, expiradas, encerradas ou de conta inativa são recusadas.
- Redefinição e recuperação de senha revogam sessões e capacidades conforme o
  contrato processual.
- Autorizações T47 são opacas, vinculadas a sessão/operação/recurso/dados,
  expiram e têm consumo único protegido por bloqueio.
- Cadastro e edição de Produtos pelo Caixa exigem capacidade vinculada ao hash
  do comando; serviços públicos de gravação revalidam a sessão.
- Cancelamento exige capacidade real, usa `BEGIN IMMEDIATE`, preserva itens e
  pagamentos e distingue falha comprovada de resultado incerto.
- Testes de concorrência cobrem consumo, revogação, alteração de credencial,
  categorias, produtos e cancelamento dentro de uma instância do processo.

### Produtos e categorias

- Cadastro, edição, ativação/inativação, categorias ativas/inativas e histórico
  de preços estão cobertos.
- Alteração de código preserva ID, rejeita duplicidade inclusive de inativo,
  libera código anterior, atualiza a leitura atual e mantém snapshots antigos.
- Alteração exclusiva de código não cria histórico de preço.
- Estado-base e unicidade são revalidados dentro da transação.

### Interface

- pytest-qt cobre Frente de Caixa, Pagamentos, Histórico, Produtos,
  Administração, primeiro acesso, login, autorizações e confirmações.
- Há verificações de foco, Enter/Esc/Tab/Ctrl+Enter, seleção, bloqueios e
  preservação de estado.
- Layouts possuem testes em 1024×720 e 1280×800; Pagamentos também em 900×700 e
  640×480; formulários possuem simulação de fonte a 125%.
- Esses testes não substituem a homologação renderizada no Windows real com
  escala do sistema, tema, fontes e hardware do estabelecimento.

## 4. Achados classificados

### P1 — bloqueia encerramento

Nenhum achado P1 permanece aberto.

#### P1-01 — Homologação manual final após as últimas mudanças — resolvido

O responsável confirmou **13/13 cenários aprovados** após a Revisão Visual 01–05
e as Correções Finais 01/02. Essa confirmação satisfaz o aceite do Marco 2. Ela
não equivale à homologação física no equipamento do cliente, que permanece no
Marco 3.

### P2 — decisões explícitas e achados resolvidos

#### P2-01 — Documentos ativos possuíam contratos contraditórios — resolvido

- A arquitetura dizia que Caixa não acessava Produtos e que trocar operador
  invalidava imediatamente a sessão e fechava a janela.
- A DEC-027 dizia que o código era somente leitura e que categorias permaneciam
  textuais; decisões posteriores alteraram ambos os contratos.
- O backlog indicava COMP-M2-05 como próximo ticket apesar de sua implementação.
- Riscos já implementados, como categorias, ainda apareciam como futuros.

**Resolução:** `ARQUITETURA_ALVO.md` foi alinhado ao comportamento implementado;
as DEC-019/027 registram quais cláusulas foram substituídas pelas decisões mais
recentes; o backlog registra COMP-M2-05 e as correções finais como implementados,
sem marcar o Marco 2 como encerrado. O histórico e a numeração foram preservados.

#### P2-02 — UUID de fechamento incerto não sobrevive ao processo

A idempotência funciona enquanto o UUID permanece em memória. Encerramento ou
queda após resultado incerto perde a correlação automática. A pendência já está
ligada ao T54. O adiamento está documentado e não autoriza liberação operacional
antes do protocolo de contingência.

#### P2-03 — Cancelamento incerto não identifica persistentemente a tentativa

Após erro de commit, venda `CANCELADA` comprova o estado, mas não a autoria da
tentativa atual. O comportamento fail-closed está correto; a limitação permanece
por ausência deliberada de UUID de cancelamento. A pendência foi vinculada ao
T54, sem criar migração apenas para encerrar o Marco 2.

#### P2-04 — Sessões, capacidades e coordenação são locais ao processo

As garantias concorrentes valem em uma instância. Duas instâncias podem ter
registros independentes de sessão/capacidade e bloqueios de credencial distintos.
Antes do uso real, deve existir instância única ou coordenação entre processos;
essa decisão foi vinculada ao T60. Não ampliar automaticamente o Marco 2.

#### P2-05 — Scanner físico e medição real não foram homologados

O T31 registra validação simulada, mas não foi encontrada instrumentação de
latência no código nem medição com leitor físico. O T61/T62 prevê desempenho e
validação operacional. Essa validação permanece explicitamente destinada aos
T61/T62 do Marco 3 e não é apresentada como concluída.

#### P2-06 — Artefatos locais e regra insuficiente de ignore — resolvido

Foram identificados, apenas por caminho, três backups pré-migração não rastreados
em `data/backups/pre_migracao/`; nenhum conteúdo foi aberto. O `.gitignore` agora
protege todo `data/**`, bancos `.db`/`.sqlite`/`.sqlite3` em subdiretórios,
journals/WAL, backups, temporários, logs e credenciais locais. Os arquivos
existentes não foram removidos ou modificados.

#### P2-07 — Segurança e ciclo completo dos backups pertencem ao Marco 3

O backup pré-migração está implementado e verificado. Rotação, destino externo,
permissões do diretório, restauração assistida e teste periódico permanecem nos
T55–T57. O adiamento é coerente, mas impede considerar o sistema pronto para
produção.

### P3 — não bloqueante

- `0x8001010d`: não reproduzido; monitorar em homologação real.
- Dependências de `requirements.txt` não estão fixadas por versão; tratar na
  preparação de build/release do Marco 3.
- Escala a 125% foi simulada em testes, mas deve ser confirmada no Windows real.
- Metas de latência e desempenho permanecem para T61.
- O aviso apresentado ao alterar o código comercial do produto possui pequeno
  ajuste visual pendente. A mensagem e a proteção operacional estão funcionais;
  o refinamento é melhoria de apresentação não bloqueante.

## 5. Pendências por destino

### Critérios de encerramento atendidos

1. Homologação manual final: 13/13 cenários aprovados pelo responsável.
2. Suíte automatizada final: 1.078 testes aprovados pelo Codex.
3. Migração v9→v10: aprovada pelo Codex em banco temporário isolado.
4. Revisão Visual 01–05 e Correções Finais 01/02: aprovadas pelo responsável.
5. Documentos ativos e proteção de artefatos: revisados, sem P1 aberto.

### Preservadas para o Marco 3

- Recuperação durável de UUID e protocolo de contingência: T54.
- Scanner físico, escala real, desempenho e lock no equipamento: T61/T62.
- Backup periódico/externo e restauração: T55–T57.
- Migrações de distribuição, empacotamento e instalador: T58–T60.
- Coordenação entre processos ou política de instância única.
- Identificador persistente de tentativa de cancelamento, se priorizado.
- Ambiente durável e isolado para futuras homologações manuais.
- Pequeno refinamento visual do aviso de alteração do código do produto.

## 6. Registro da homologação manual final

O responsável confirmou **13/13 cenários aprovados**, a Revisão Visual 01–05 e
as Correções Finais 01/02. A confirmação foi informada pelo responsável e não
reproduzida como auditoria manual independente pelo Codex. A migração v9→v10 foi
verificada separadamente pelo Codex em banco temporário.

Esse aceite não inclui leitor físico, desempenho no equipamento do cliente,
backup operacional completo nem restauração. Futuras homologações devem usar
ambiente durável e isolado, nunca apagar ou reutilizar `data/`, e executar o
checklist operacional previsto no T62.

## 7. Git e organização proposta

- HEAD auditado: `17c0899`.
- Nenhum arquivo SQLite está rastreado.
- Os caminhos dos backups locais foram identificados para validar o ignore;
  nenhum banco operacional foi aberto ou alterado.
- O estado atual contém somente `.gitignore` e os quatro documentos ativos
  modificados por esta organização; `data/` não aparece mais como pendência.
- Não há arquivo preparado na área de stage nem credencial, chave ou banco
  rastreado entre as alterações propostas.

Proposta, sem executar commits:

1. Após revisão do responsável, um commit documental pode reunir o relatório,
   o alinhamento dos documentos ativos e o `.gitignore`:
   `docs: encerra formalmente o marco 2`.
2. Eventuais falhas da homologação devem gerar commits próprios por correção;
   não misturar com o relatório nem com o Marco 3.

## 8. Parecer final

O **Marco 2 está formalmente concluído**. A homologação final foi aprovada pelo
responsável, as verificações automatizadas e a migração isolada foram aprovadas
pelo Codex, e não há achado P1 aberto. Este parecer encerra o marco de
desenvolvimento; **não declara o sistema pronto para produção nem homologado no
equipamento do cliente**. A liberação operacional depende das entregas de
confiabilidade e validação física preservadas no Marco 3.
