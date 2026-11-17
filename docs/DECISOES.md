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
- **DEC-019** — Cadastro e edição foram inicialmente permitidos durante venda;
  o bloqueio posterior da edição de produtos existentes foi aprovado na
  **DEC-027**. Snapshot preserva itens; registrar histórico de alteração de
  preços com consulta aos 12 meses, sem exclusão automática.
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
  enquanto houver itens lançados. Snapshots já lançados não são alterados. As
  cláusulas originais de código somente leitura e categorias textuais foram
  substituídas, respectivamente, pelas **DEC-042** e **DEC-040**.
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
  por login válido. Caixa acessa Frente de Caixa, Histórico e consulta de
  Produtos; mutações do catálogo seguem a autorização definida no COMP-M2-06,
  e provisionamento de Caixa exige Administrador revalidado no banco. Logout
  invalida a sessão e fecha a janela. Cinco falhas por identificação em sessenta
  segundos geram espera de trinta segundos somente em memória, evitando bloqueio
  durável explorável. Conta desativada perde permissão na próxima operação
  protegida. T47 continua responsável por autorização pontual, sem elevação da
  sessão.
- **DEC-032** — Sessões e autorizações pontuais são capacidades opacas mantidas
  somente em memória. A sessão usa nonce criptográfico e identidade de objeto
  registrada; a autorização expira em 60 segundos e se vincula ao solicitante,
  operação, recurso e ID estável do Administrador autorizador, preservando sua
  identificação textual para auditoria. Emissão, consumo e revogação são
  serializados pelo mesmo bloqueio; invalidar uma identidade revoga capacidades
  que ela solicitou ou concedeu. O consumo é único e precede o efeito comercial,
  portanto falha posterior não restaura a capacidade. Reinício, logout,
  expiração e conta desativada falham fechados. O T43 não mantém caminho
  alternativo baseado em booleano, perfil textual ou contexto construível.
- **DEC-033** — Recuperação administrativa offline usa dez códigos independentes
  de 160 bits, apresentados uma vez e persistidos somente como SHA-256, adequado
  à entropia aleatória dos segredos. Emissão e rotação exigem sessão
  Administrador revalidada e confirmação da senha atual. Consumo e nova senha
  formam uma única transação; rotação revoga o conjunto anterior e recuperação
  bem-sucedida encerra todas as sessões e capacidades processuais da identidade,
  sem autenticação automática. Perda da apresentação exige nova rotação.
- **DEC-034** — A Administração básica é uma página interna restrita a sessão
  Administrador revalidada e gerencia somente contas Caixa. Criar conta exige
  senha inicial individual; ativação e desativação não alteram credenciais, e a
  desativação revoga sessões e capacidades processuais do operador. Troca de
  operador reutiliza o diálogo único de login e mantém a sessão atual válida até
  a autenticação do próximo operador; cancelar, usar `Esc` ou fechar o diálogo
  preserva a sessão anterior. Somente a troca confirmada encerra a sessão antiga
  e revoga suas capacidades. A troca continua recusada quando itens, pagamentos
  ou fechamento poderiam ser descartados. Fechar a janela também invalida a
  sessão e respeita o mesmo bloqueio comercial.
- **DEC-035** — Após INT-E e antes do T49 existe a fase Consolidação do Marco 2.
  A ordem aprovada é COR-M2-01 (revogação de autorizações), COR-M2-02
  (reconciliação de cancelamento incerto), detalhamento e execução de COMP-M2,
  homologação e auditoria final. A recuperação de UUID de fechamento incerto
  após encerramento será avaliada com o protocolo de contingência do T54. Essa
  sequência não autoriza antecipar o Marco 3 nem agrupar as correções em uma
  refatoração ampla.
- **DEC-036** — Falha anterior ao commit do cancelamento é falha confirmada;
  exceção durante o commit exige reconciliação em nova conexão. Venda ainda
  `ATIVA` confirma que a tentativa não persistiu. Venda `CANCELADA`, metadados
  coincidentes ou não, não prova a autoria da tentativa sem identificador
  persistente e permanece resultado incerto. Consulta indisponível também
  preserva a incerteza. A autorização já consumida nunca é reutilizada, a
  interface apenas atualiza o Histórico e uma nova tentativa depende de
  consulta expressa. Não será criada migração somente para converter incerteza
  em sucesso aparente.
- **DEC-037** — A divisão de pagamentos é uma referência visual explícita do
  saldo no instante em que o operador solicita “Sugerir divisão”. Parcelas
  usadas e pendentes permanecem visíveis; uma entrada manual ou alteração que
  torne a referência incompatível interrompe o preenchimento automático, mas
  não apaga a sugestão. Trocar modalidade nunca substitui o valor. `Enter`
  adiciona ou salva edição e `Ctrl+Enter` conclui somente quando o total estiver
  integralmente pago. A ordem de consolidação é COMP-M2-01, 02, 03, 04, 06 e
  por último 05, que realiza revisão visual, homologação e auditoria final.
- **DEC-038** — A redefinição administrativa de senha opera somente sobre uma
  conta Caixa selecionada e revalidada no momento da gravação. Reutiliza a
  política e o `scrypt` existentes, não exige a senha anterior e não altera a
  situação da conta. Após o commit confirmado, todas as sessões e capacidades
  processuais do operador são revogadas. Login, emissão de capacidade e troca
  de credencial compartilham coordenação reentrante em memória para que uma
  credencial antiga não seja publicada entre commit e revogação. Como os
  gerenciadores de T46/T47 são processuais, essa garantia não coordena duas
  instâncias simultâneas do programa; resolver isso exigiria infraestrutura de
  identidade compartilhada fora do escopo do COMP-M2-04.
- **DEC-039** — A consulta gráfica de preços é somente leitura e exige sessão
  Administrador revalidada pelo serviço. A janela inicial usa intervalo fechado
  a partir do mesmo dia e horário de 12 meses civis antes, comparado em UTC sem
  aplicar função sobre a coluna indexada; “Todo o histórico” remove somente esse
  limite. Instantes são apresentados em `America/Sao_Paulo`. Como o T44 não
  persistiu responsável, a interface declara a indisponibilidade e não infere a
  identidade a partir da sessão atual ou do cadastro do produto.
- **DEC-040** — O esquema versão 10 torna categorias entidades administráveis,
  com ID estável, nome exibido, chave `NFKC` com espaços normalizados e
  `casefold`, e estado ativo/inativo. `produtos.categoria_id` substitui o texto,
  enquanto `Produto.categoria` permanece uma projeção de leitura compatível.
  A migração reconstrói `produtos` em uma única transação, preserva IDs,
  referências e histórico, consolida nomes equivalentes e cria uma categoria
  inativa reservada para valores legados vazios; valores legados apenas
  numéricos são preservados, porém inativos. Categorias não são excluídas.
  Produto já vinculado pode permanecer em categoria inativa, mas nova associação
  exige categoria ativa revalidada sob a mesma transação da gravação.
- **DEC-041** — Cadastro e edição de Produtos pelo Caixa exigem capacidade
  pontual do T47 vinculada à sessão, operação distinta, recurso e SHA-256 de um
  comando canônico imutável. Edição inclui o estado-base completo; produto e
  categoria são comparados sob `BEGIN IMMEDIATE`, e qualquer divergência consome
  a capacidade sem gravar. Administrador opera diretamente após revalidação da
  sessão. Ativação, categorias e histórico de preços permanecem administrativos.
  O hash isolado não autoriza, não há elevação do Caixa nem persistência de
  capacidade. Falha após consumo exige nova autorização.
- **DEC-042** — O código comercial do produto é editável sem alterar seu ID
  interno. A edição usa o mesmo comando canônico e a mesma autorização pontual
  do catálogo, incluindo no hash o código novo e, no estado-base, o anterior.
  Sob `BEGIN IMMEDIATE`, produto, categoria e unicidade do código são
  revalidados; produtos inativos também ocupam seus códigos. Após uma troca
  confirmada, o código anterior pode ser reutilizado, sem reserva ou histórico
  próprio. Vendas anteriores conservam seus snapshots e alteração exclusiva do
  código não produz evento de preço. A interface alerta sobre a atualização da
  balança e o risco de etiquetas antigas somente quando o código muda.
- **DEC-043** — O T49 usa `logging` da biblioteca padrão e registros JSON por
  linha em arquivo local rotativo. O destino padrão é
  `%LOCALAPPDATA%\Sistema-PDV\logs` no Windows e pode ser substituído por
  `SISTEMA_PDV_LOG_DIR`; isso não altera o caminho do SQLite. Cada arquivo tem
  até 5 MiB e são conservados no máximo cinco arquivos anteriores. Eventos
  usam esquema fechado e campos explicitamente permitidos; senhas, hashes,
  salts, códigos de recuperação, credenciais, tokens, capacidades, SQL e
  objetos comerciais não são serializados. Mascaramento textual é apenas
  defesa adicional. Falha ao criar, rotacionar ou escrever o log não altera o
  resultado comercial nem substitui as mensagens existentes da interface.
- **DEC-044** — A versão inicial oficial do aplicativo é `0.1.0` e permanece
  independente da versão do schema SQLite. Nome, versão, identificador de build
  e commit Git são centralizados em `services/version_service.py`; build e
  commit ausentes são apresentados como `desconhecido`. A aplicação não consulta
  Git, `.git`, rede ou banco para obter esses valores. O T59 deverá preencher os
  metadados embutidos em uma cópia de build antes do empacotamento, sem alterar
  o banco nem usar o schema como versão. O Sobre e o evento seguro de
  inicialização consomem a mesma identificação; a exportação de pacote continua
  pertencendo ao T51.
- **DEC-045** — O T51 exporta diagnóstico local somente para Administrador com
  sessão revalidada. O ZIP contém exclusivamente `manifesto.json` e
  `eventos.jsonl`: identificação do T50, estado conhecido do logging, limites e
  contadores da coleta e até 1.000 eventos reconstruídos por contrato fechado.
  São lidos no máximo seis nomes oficiais de log e 1 MiB por arquivo; o JSONL
  exportado também é limitado a 1 MiB. Logs são entrada não confiável: mensagem,
  nível e componente devem coincidir com o catálogo, campos desconhecidos são
  descartados e IDs de venda e operação não são exportados. Banco, WAL, SHM,
  backups e arquivos arbitrários nunca são coletados. A geração usa temporário
  no destino escolhido e publicação atômica sem sobrescrita, sem rede. O estado
  do T49 passa a distinguir disponibilidade, falha de inicialização, falha de
  escrita e desconhecido. Exceções não tratadas em threads Python usam hook
  encadeado ao anterior; não será substituído `QApplication.notify()` nem
  instalado handler
  global de mensagens Qt, pois isso seria invasivo e não prova cobertura segura
  de exceções comerciais já tratadas.
- **DEC-046** — O T52 mantém, por processo, um snapshot imutável do catálogo
  essencial com ID, código, nome, forma de venda, preço em centavos e situação.
  A carga usa uma única listagem SQLite de produtos ativos e inativos e só é
  publicada após validação integral. A janela tenta a carga após autenticação;
  cadastro, edição e mudança de situação provocam recarga completa. Antes da
  recarga o snapshot é invalidado, e qualquer falha mantém estado explícito
  `INDISPONIVEL`, sem conservar silenciosamente uma versão antiga. O acesso
  degradado é uma API explícita, não um fallback automático. O T52 não autoriza
  fechamento, cancelamento ou persistência alternativa sem SQLite; estado
  operacional e protocolo de contingência continuam nos T53 e T54.
- **DEC-047** — Cada instância do catálogo do T52 é vinculada ao primeiro banco
  informado. A identidade é privada, baseada em caminho absoluto resolvido e
  normalizado, com confirmação por identidade do arquivo quando disponível;
  nenhum caminho entra no estado público, interface ou logs. Recarga,
  atualização ou mutação integrada com outro banco é rejeitada antes de leitura,
  autorização ou gravação, preservando snapshot e estado anteriores. Caminhos
  equivalentes para o mesmo arquivo são aceitos. Chamadas externas aos serviços
  de produto que omitam o catálogo continuam válidas, mas não oferecem
  sincronização automática; o PDV integrado sempre fornece a instância vinculada.
- **DEC-048** — A retomada do modo `NORMAL` no T54 exige, de forma cumulativa,
  verificação técnica satisfatória do SQLite recuperado, reconstrução integral
  do catálogo T52, inexistência de fechamento incerto pendente, confirmação
  explícita e credenciais de um Administrador revalidadas no próprio banco. A
  sessão local preservada pelo T53 e o perfil Caixa não concedem essa autoridade.
  A verificação isolada nunca libera o sistema automaticamente; qualquer falha
  mantém o controlador canônico em estado restritivo. Itens calculados continuam
  somente na memória e não são gravados pela retomada. Sem alterar o schema ou
  criar persistência auxiliar, o T54 não recupera UUID de fechamento, carrinho ou
  cálculos de contingência depois que o processo é encerrado. Enquanto o
  processo estiver ativo, cada janela registra sua incerteza no controlador
  canônico do banco; a retomada permanece bloqueada até todas as origens serem
  resolvidas, sem compartilhar UUID, confirmação ou dados comerciais.
- **DEC-049** — O T55 produz backup local por `sqlite3.Connection.backup` a partir
  de conexão somente leitura, primeiro em arquivo temporário no diretório de
  destino. A cópia só é publicada, sem sobrescrita, depois de validar
  `PRAGMA integrity_check`, versão do schema, tabelas essenciais e chaves
  estrangeiras. A identidade privada combina caminho canônico e identidade do
  arquivo de origem, isolando bancos diferentes sem alterar o schema. Backups
  locais ficam em `backups/local/<identidade>` ao lado do banco, salvo raiz
  explicitamente informada. A retenção conserva um ponto para cada um dos sete
  dias locais mais recentes e um ponto para cada uma das quatro semanas ISO
  anteriores ao intervalo diário; o novo backup e a última cópia reconhecida
  nunca são removidos. Rotação ocorre somente após publicação válida e ignora
  arquivos desconhecidos, temporários, links e outras origens. O T55 não agenda
  execuções, não envia cópias externamente e não restaura dados.
  Criação, publicação, retenção e formação do resultado usam uma única
  seção crítica por origem e destino: `RLock` no processo e lock exclusivo em
  arquivo para processos cooperantes. Origens diferentes não compartilham esse
  lock. A espera tem limite de 60 segundos e falha de coordenação não publica
  sucesso. A garantia entre processos depende de todos usarem o serviço e de um
  filesystem local com locks confiáveis; ferramentas externas e filesystems de
  rede que ignorem locks permanecem fora da garantia.
- **DEC-050** — O T56 reutiliza exclusivamente a cópia consistente e validada do
  T55 e separa dela o transporte por um contrato de destino. A implementação
  atual oferece destino de diretório explicitamente configurado por
  `SISTEMA_PDV_BACKUP_EXTERNO_DIR`; nuvem, FTP, credenciais e descoberta
  automática permanecem fora do escopo. O transporte calcula SHA-256 da cópia
  local aberta de forma estável, grava temporário no destino, compara o resumo,
  repete a validação SQLite e publica sem sobrescrever. A retenção externa
  conserva um ponto por cada um dos 30 dias locais mais recentes e ignora
  arquivos desconhecidos, links, temporários e outras origens. O agendador
  processual faz a primeira tentativa ao iniciar a operação configurada e as
  seguintes duas horas depois do fim de cada tentativa, sem sobreposição nem
  retentativa imediata. Falhas ficam em estado técnico e log seguro, mas não
  bloqueiam vendas nem alteram o protocolo T54. Estado e horários são somente
  processuais. Um caminho diferente não comprova mídia física distinta; essa
  validação continua sendo responsabilidade da instalação e homologação.
- **DEC-051** — O T57 entrega somente o serviço de recuperação isolada. A tela
  de restauração e qualquer integração automática permanecem posteriores.
- **DEC-052** — Uma futura substituição operacional deverá preservar
  obrigatoriamente o banco anterior. O T57 não substitui, renomeia, remove nem
  modifica o banco operacional.
- **DEC-053** — A recuperação assistida aceita os formatos reconhecidos de
  backup local do T55 e externo do T56. O tipo é identificado pelo contrato de
  nome e o conteúdo passa por validação SQLite integral; renomear um arquivo
  arbitrário não dispensa essa validação.
- **DEC-054** — O T57 publica exclusivamente uma nova base de teste em destino
  explícito e separado. A operação exige sessão válida, credenciais de
  Administrador revalidadas com o limitador existente e confirmação explícita.
  A cópia nasce como temporário, é validada antes da publicação exclusiva e
  não altera estado operacional, fechamento incerto, backup de origem ou banco
  comercial. Validar uma base de teste não autoriza retomada pelo T54.
- **DEC-055** — Migrações compatíveis são executadas automaticamente na etapa
  apropriada de inicialização ou atualização e devem terminar, ser validadas e
  manter as operações comerciais bloqueadas antes da liberação do PDV. O
  sucesso dessa etapa não presume nem autoriza, por si só, uma atualização
  completa do aplicativo. Banco apto ao aplicativo atual e autorização para
  instalar outro aplicativo são resultados independentes. Banco novo, banco já
  atualizado ou execução sem migrações pendentes podem operar normalmente, mas
  não concedem autorização de atualização por essa ausência de passos.
- **DEC-056** — A atualização coordenada migra o banco antes de instalar a nova
  versão do aplicativo. Deve preservar aplicativo, configurações e banco
  anteriores; verificar previamente as combinações compatíveis; exigir backup
  pré-migração validado; executar e validar a migração transacional; e somente
  então autorizar o futuro instalador a avançar. Falha reverte a transação e
  conserva o aplicativo anterior apenas quando sua compatibilidade com o banco
  preservado estiver comprovada. Rollback do banco não é rollback do executável
  e backup nunca substitui automaticamente o banco operacional como rollback
  comum. Declaração da migração, homologação com versão anterior e evidência
  técnica identificada, e autorização do instalador são estados distintos. O
  simples sucesso, a declaração isolada ou a ausência de migrações não
  comprovam compatibilidade. A autorização emitida pelo T58 pertence à rota
  não vazia avaliada naquela execução coordenada; não é uma propriedade
  persistente do banco final.
- **DEC-057** — Migrações são explícitas, determinísticas, sequenciais e
  identificadas pelas versões de origem e destino. O roteiro completo deve
  existir antes da primeira alteração; apenas passos pendentes são executados e
  passos concluídos não são reaplicados. As rotas históricas v1→v10 são
  preservadas como legado e não recebem autorização automática para o futuro
  instalador coordenado. Em particular, v9→v10 reconstrói `produtos` e pode
  quebrar aplicativos anteriores. Seu uso operacional exige procedimento
  específico de manutenção e homologação, fora do T58. Migrações posteriores
  à v10 devem declarar e validar explicitamente a compatibilidade com a versão
  anterior do aplicativo segundo a DEC-056. As versões SQLite v0→v10 são
  marcos internos de desenvolvimento e não definem a versão comercial. O
  primeiro lançamento homologado poderá ser o aplicativo `1.0.0` com qualquer
  versão interna de schema então aprovada, sem renumerar migrações. Esse
  lançamento, e não necessariamente o schema v10, estabelecerá a primeira base
  de compatibilidade para atualizações comerciais.
- **DEC-058** — O T59 usa PyInstaller em modo `onedir`, com aplicação gráfica
  sem console e fontes de build selecionadas por allowlist. O build incorpora
  metadados T50 somente numa cópia temporária e nunca inclui banco, WAL, SHM,
  backups, logs, credenciais, testes ou documentação interna. A execução em
  desenvolvimento conserva `repositorio/data`; a execução reconhecida como
  PyInstaller por `sys.frozen` e `sys._MEIPASS` usa
  `%LOCALAPPDATA%\Sistema-PDV\data` do usuário Windows. Não há cópia, migração,
  exclusão ou descoberta automática entre essas origens. Backups permanecem ao
  lado do banco e logs mantêm o contrato T49. O T60 deverá decidir se uma
  instalação multiusuário exigirá `%PROGRAMDATA%`, incluindo identidade do
  estabelecimento, permissões, coordenação e transição explícita dos dados.
  A saída de cada build é validada em diretório isolado antes de substituir a
  distribuição local anterior. O smoke `offscreen` cobre apenas o runtime Qt
  básico; interface, login e fluxos exigem homologação gráfica isolada.
- **DEC-059** — A instalação comercial do T60 é por computador. Executáveis e
  dependências pertencem a uma raiz registrada sob `%ProgramFiles%`; dados de
  Produção e Homologação ficam respectivamente em
  `%PROGRAMDATA%\Sistema-PDV\Producao` e
  `%PROGRAMDATA%\Sistema-PDV\Homologacao`. Cada ambiente possui identificador
  estável, GUID próprio de instalação, banco, logs, estado administrativo e
  mutex global independentes. A identidade deve coincidir entre HKLM e o
  descritor administrativo `installation.json`; ausência ou divergência
  bloqueia a execução empacotada, sem fallback para desenvolvimento ou
  `%LOCALAPPDATA%`. O grupo local `Sistema-PDV-Operadores` recebe somente os
  acessos operacionais que o futuro instalador provisionará; identidade,
  manifestos e estado de manutenção permanecem sob controle administrativo.
  O processo adquire o mutex antes de importar interface, banco, logging ou
  sessões e só prossegue quando o estado de manutenção é conhecido e livre.
  O desenvolvimento mantém `repositorio/data` e seus caminhos atuais. Esta
  decisão não autoriza migração automática de localização nem implementa o
  coordenador de atualização.
- **DEC-060** — A abertura operacional nunca executa migrações em banco de uma
  instalação comercial. Banco inexistente pode receber a criação inicial
  controlada; banco na versão esperada passa por inspeção somente leitura e
  validação estrutural estrita. Versão anterior exige manutenção/atualização
  coordenada e é recusada antes de backup ou DDL. Versão futura, estrutura
  divergente, caminho fora do contexto ou estado de manutenção não livre também
  bloqueiam a operação. Desenvolvimento preserva a preparação automática e as
  migrações históricas existentes. Essa separação não autoriza nenhuma rota do
  T58 nem antecipa o coordenador do T60.

## Decisões que exigem cuidado
- O código do produto pode ser alterado somente sem itens na venda em andamento;
  o mesmo bloqueio se aplica à forma de venda. A troca exige atenção ao cadastro
  da balança e às etiquetas antigas caso o código anterior seja reutilizado.
- Uma quantidade derivada do preço é **estimada**, nunca prova de pesagem. Quantidade informada manualmente não equivale a pesagem certificada.
- Recuperação de acesso: os códigos são gerados somente após login administrativo
  e confirmação da senha, devem ser guardados fora do computador e não podem ser
  consultados novamente. Fechar a apresentação exige rotacionar o conjunto.
- Código `9999` reservado; nenhum produto comum poderá usá-lo.
- O histórico diário converte o dia civil de São Paulo para intervalo UTC
  semiaberto e usa índice composto em `vendas(registrada_em, id)`; isso atende
  filtro e ordenação sem aplicar funções sobre a coluna persistida.
- O T43 registra a identidade devolvida pelo consumo da capacidade do T47. A
  INT-D1 coleta o motivo sem fabricar autorização; a INT-D2 abre o diálogo do
  T47 e entrega exclusivamente a capacidade emitida ao serviço transacional.
- A fila de contingência de persistência e eventual fila de documentos fiscais são responsabilidades diferentes e futuras. NFC-e tem regras específicas da SEFAZ, não é mero reenvio livre de totais.
