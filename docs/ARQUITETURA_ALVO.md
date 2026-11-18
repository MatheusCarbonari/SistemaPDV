# Arquitetura-alvo (planejada)

## Componentes
- `interface/`: PySide6 Qt Widgets; captura de eventos, foco, formulários e apresentação; nunca SQL.
- `services/` ou módulos de aplicação: casos de uso e coordenação de operações, autorização e transações.
- `models/` / domínio: regras de leitura, valores monetários, itens, quantidades, pagamentos; idealmente sem importação de Qt.
- `repositories/`: acesso parametrizado a dados.
- `database/`: conexão, esquema, migrações, transações.
- Serviços transversais: logging, backup, diagnósticos, instalação, recuperação.

## Navegação da interface
A aplicação mantém uma única janela principal com menu horizontal persistente
e páginas internas em `QStackedWidget`. A Frente de Caixa conserva venda e
pagamentos em memória durante a navegação. Histórico consome somente os serviços
de consulta e não contém SQL. Produtos administra o catálogo por serviços, sem
SQL no widget. Administrador e Caixa autenticados podem consultar Produtos; o
Administrador grava diretamente e o Caixa somente cadastra ou edita mediante
capacidade administrativa vinculada ao comando. Situação do produto, categorias
e histórico de preços permanecem exclusivos do Administrador. Administração
lista e gerencia somente contas Caixa por serviços protegidos; visibilidade de
botão nunca substitui a autorização na camada de aplicação.
Resultado de commit incerto fixa a operação na Frente de Caixa até verificação
ou recuperação controlada.

“Trocar operador” mantém a sessão atual válida enquanto autentica o próximo
operador no diálogo de login. Cancelar, usar `Esc` ou fechar o diálogo preserva
a sessão anterior; somente uma autenticação confirmada instala a nova sessão e
invalida a anterior e suas capacidades. A operação é recusada enquanto itens,
pagamentos, confirmação ou fechamento estiverem pendentes. Fechar a janela pelo
sistema invalida a sessão sem iniciar outra automaticamente e respeita o mesmo
bloqueio para não descartar um atendimento em memória.

O Histórico solicita o cancelamento de venda ativa exibindo os dados comerciais
originais e validando o motivo, sem criar estado intermediário persistente. A
execução abre a autorização administrativa do T47, vinculada à sessão
solicitante, operação e venda, e entrega sua capacidade opaca de uso único ao
serviço transacional do T43. A interface não sintetiza autorização, não acessa
SQL e só atualiza lista e detalhe depois do sucesso comprovado.

## Dados e integridade
- SQLite único local, foreign_keys habilitado, transação atômica ao gravar venda+itens+pagamentos.
- O esquema versão 7 introduziu `historico_precos_produtos`, com produto, preço
  anterior, novo preço e instante UTC na mesma transação da atualização.
- O esquema versão 8 introduz `usuarios` e o singleton `estado_identidade`. O
  marcador referencia o administrador inicial por FK `RESTRICT`, impedindo sua
  remoção normal e distinguindo configuração ausente de estado inconsistente.
- O esquema versão 9 introduz `codigos_recuperacao`, vinculando verificadores de
  alta entropia ao administrador e registrando consumo ou revogação sem guardar
  o código original. Consumo e atualização de senha compartilham a transação.
- O esquema versão 10 introduz `categorias` como cadastro estável e substitui o
  texto livre de `produtos` por `categoria_id`. A chave de unicidade usa
  normalização Unicode determinística; inativação preserva os produtos já
  vinculados, enquanto novas associações são validadas dentro da transação.
  Vendas e snapshots históricos permanecem independentes do nome atual.
- `id` técnico não é `codigo` operacional. O código comercial do produto pode
  mudar com autorização e unicidade revalidada; o ID e os snapshots históricos
  permanecem estáveis. ID de venda é persistente e único; usar identificador
  separado por tentativa para idempotência.
- Snapshot de cada item para não depender de mudanças no cadastro; `produto_id` opcional para Diversos.
- Preços monetários em centavos; multiplicação de kg usa Decimal e política explícita de arredondamento.
- Guardar forma de entrada e procedência da quantidade, especialmente se estimada por valor/preço.
- Durante venda com itens, novos produtos podem ser cadastrados, mas produtos
  existentes não podem ser editados, ativados ou desativados. O bloqueio é
  validado na execução da operação, e snapshots já lançados permanecem intactos.
- Categorias são entidades administráveis da versão 10, sem exclusão física;
  novas associações exigem categoria ativa.

## Falhas
Falha de gravação não prova ausência de commit. Nova tentativa deve reutilizar identificador estável e verificar resultado quando possível. Enquanto o resultado estiver incerto, itens e pagamentos permanecem em memória e a interface bloqueia um novo atendimento. Após sucesso comprovado, o ID definitivo é apresentado e a venda em memória é reiniciada. Se banco indisponível, modo de cálculo pode usar catálogo em memória; em reinício com banco indisponível não há garantia de recuperação. Sem persistência alternativa na V1.

O ponto de entrada prepara/migra o banco, conclui o primeiro acesso quando
necessário e sempre exige login antes de construir a janela principal. Cancelar
o login, apresentar credenciais inválidas ou detectar estado inconsistente
mantém a operação bloqueada.

## Identidade e senha

- `scrypt` com salt criptográfico individual; formato contém algoritmo, versão,
  parâmetros, salt e derivação, permitindo evolução futura.
- Política inicial: 12–128 caracteres, Unicode e frases-senha permitidos, sem
  senha universal ou credencial embutida.
- Hash inválido falha na verificação; senhas nunca são registradas em mensagens,
  logs ou documentação.
- T45 não cria sessão. O T46 cria `SessaoUsuario` somente após autenticação,
  nunca armazena senha na sessão e a encerra explicitamente no logout.
- Credenciais incorretas, contas inativas e hashes inválidos compartilham a
  mesma resposta. O limitador local aplica espera de 30 segundos depois de cinco
  falhas em 60 segundos; reiniciar não autentica nem bloqueia permanentemente.
- Autorização reconsulta ID, identificação, perfil e situação da conta. Caixa
  opera vendas, consulta Histórico e Produtos e pode cadastrar ou editar um
  produto somente com capacidade administrativa vinculada aos dados. Situação,
  categorias, histórico de preços e provisionamento permanecem administrativos.
- O T47 produz a capacidade de autorização pontual exigida pela INT-D2 sem
  elevar a sessão corrente. O T48 permite recuperação administrativa offline
  com código de uso único, invalida sessões e capacidades da identidade após a
  troca e exige novo login.
- O gerenciador de sessões registra nonces emitidos somente após login e exige
  correspondência com o mesmo objeto em memória. Construir `SessaoUsuario`
  manualmente não produz uma sessão reconhecida.
- O gerenciador de autorizações conserva privadamente solicitante, operação,
  recurso, ID estável e identificação textual do administrador, além da
  expiração. O chamador recebe somente um nonce; emissão, consumo e revogação
  usam o mesmo bloqueio. A invalidação de uma identidade remove capacidades
  solicitadas ou concedidas por ela. O consumo atômico em memória ocorre antes
  da transação comercial e nunca é revertido por falha posterior. Nenhuma
  capacidade ou senha é persistida.
- Para Produtos, o vínculo inclui SHA-256 de representação canônica versionada
  do comando normalizado. Cadastro usa o catálogo como recurso; edição usa o ID
  do produto e inclui seu estado-base. O serviço consome a capacidade antes de
  abrir a transação e o repositório compara produto e categoria sob
  `BEGIN IMMEDIATE`; divergência exige nova autorização. O hash nunca substitui
  a capacidade opaca.
- A INT-E reutiliza o login e os registros processuais existentes para criar,
  listar, ativar e desativar contas Caixa. Não cria Administradores adicionais,
  sessão elevada nem um segundo mecanismo de identidade.
- A redefinição administrativa de senha reutiliza a mesma política e o mesmo
  hash, atualiza somente uma identidade Caixa em transação e preserva sua
  situação. Login, emissão de capacidade e troca de credencial compartilham um
  bloqueio processual; depois do commit, sessões e capacidades do Caixa são
  revogadas antes de liberar novas autenticações. Não há coordenação entre
  instâncias distintas enquanto os gerenciadores permanecerem em memória.
- O cancelamento distingue falha anterior ao commit, falha de commit
  reconciliada com venda ainda ativa e resultado incerto. Após exceção no
  commit, uma nova conexão consulta somente status e metadados. `ATIVA`
  confirma ausência do cancelamento; `CANCELADA` não identifica a tentativa,
  mesmo com metadados iguais, pois o esquema não possui UUID de cancelamento.
  Consulta indisponível também mantém a incerteza. A interface pode atualizar o
  Histórico, mas não repete a operação nem reutiliza a autorização consumida.
- Códigos de recuperação são mostrados somente no retorno da emissão. Devem ser
  guardados em meio externo seguro; interrupção ou perda não permite consulta e
  requer rotação autenticada. O limitador de tentativas é local e em memória,
  portanto complementa — não substitui — os 160 bits de entropia de cada código.

## Distribuição
Binário Windows empacotado, arquivos de dados fora da instalação; instalador atualiza só programa e executa migrador quando necessário; backup válido e migração segura, sem retrocesso automático de banco em falha. A inicialização operacional recusa versões futuras e, para banco existente desatualizado, só migra depois de criar e verificar uma cópia única em `backups/pre_migracao` ao lado do arquivo SQLite. Compatibilidade/licença PySide6 deve ser avaliada em entrega comercial.

## Logs locais (T49)

- `services/logging_service.py` centraliza o `logging` da aplicação e grava
  JSON por linha em `sistema-pdv.log`.
- No Windows, o diretório padrão é
  `%LOCALAPPDATA%\Sistema-PDV\logs`. A variável `SISTEMA_PDV_LOG_DIR` permite
  definir outro destino, inclusive um diretório temporário nos testes.
- A rotação ocorre ao atingir 5 MiB e conserva cinco arquivos anteriores. O
  arquivo atual e os rotacionados podem ser consultados com editor de texto ou
  ferramenta que leia JSON Lines.
- São registrados inicialização e encerramento, preparação técnica do banco,
  falhas relevantes de persistência, resultados incertos de fechamento e
  cancelamento e erros não tratados que chegam ao runtime Python.
- O esquema não aceita senhas, hashes, salts, códigos de recuperação, tokens,
  capacidades, credenciais, SQL, objetos de sessão ou comandos comerciais.
  Exceções são identificadas somente pelo tipo, sem mensagem ou argumentos.
- Logging é auxiliar: falha de diretório ou escrita não altera transações,
  resultados comerciais ou os avisos apresentados ao operador.
- T49 não incluía metadados de versão nem gera pacote de suporte. O T50 adiciona
  a identificação técnica descrita abaixo; a exportação continua no T51.

## Versão e origem do build (T50)

- `services/version_service.py` é a fonte única do nome e da versão oficial do
  aplicativo e dos metadados opcionais de build e commit Git.
- A versão inicial do aplicativo é `0.1.0`; ela não deriva de
  `database.schema.VERSAO_ESQUEMA` e não identifica a versão do banco.
- A leitura é integralmente offline e não executa Git, não inspeciona `.git` e
  não depende de rede, SQLite ou diretório de trabalho.
- Metadados ausentes ou inválidos são normalizados para ausência e exibidos como
  `desconhecido`, sem fabricar identificadores.
- A janela principal oferece um Sobre discreto. A inicialização registra o
  evento catalogado `aplicacao_identificada`, limitado aos quatro campos
  técnicos validados; o mesmo objeto oferece esses dados para diagnóstico
  futuro, sem implementar a exportação do T51.
- No T59, o processo de build deverá preencher
  `IDENTIFICADOR_BUILD_EMBUTIDO` e `COMMIT_GIT_EMBUTIDO` em uma cópia temporária
  do módulo antes de empacotar. Como o módulo Python é importado normalmente,
  seus valores serão incorporados ao executável sem exigir Git na máquina do
  estabelecimento. O roteiro e a automação desse passo ainda não existem.

## Diagnóstico técnico exportável (T51)

- `services/diagnostico_service.py` revalida uma sessão Administrador e gera,
  sob solicitação explícita, um ZIP local com `manifesto.json` e
  `eventos.jsonl`. Não há envio automático nem dependência de internet.
- O manifesto contém versão do contrato, instante UTC, identificação do T50,
  estado conhecido do logging e contadores/limites da coleta. Ele não contém
  usuário, caminho local, banco ou dados comerciais.
- O coletor não recebe caminho de origem. Ele considera somente o arquivo
  `sistema-pdv.log` e as cinco rotações oficiais no diretório autorizado pelo
  T49, rejeita links simbólicos e ignora qualquer outro arquivo.
- Cada linha é tratada como não confiável. Somente eventos selecionados cujo
  componente, nível e mensagem coincidam com o catálogo são reconstruídos;
  campos desconhecidos, `operation_id` e `venda_id` são descartados.
- Limites atuais: seis arquivos, 1 MiB lido por arquivo, 16 KiB por linha, 1.000
  eventos e 1 MiB para o JSONL exportado. Truncamento e registros descartados
  são declarados no manifesto.
- O ZIP é escrito em arquivo temporário dentro do destino selecionado e
  publicado por renomeação atômica no Windows, sem substituir um pacote de
  mesmo nome. Falhas removem o temporário quando possível, são informadas sem
  mensagem de exceção e não alteram vendas.
- O T49 mantém em memória os estados `DESCONHECIDO`, `DISPONIVEL`,
  `FALHA_INICIALIZACAO` e `FALHA_ESCRITA`; o diagnóstico não inventa sucesso
  quando não há evidência.
- `sys.excepthook` permanece encadeado e `threading.excepthook` recebe cobertura
  equivalente, chamando o hook anterior. Não há interceptação global adicional
  do Qt: substituir `QApplication.notify()` ou instalar handler de mensagens Qt
  seria invasivo e poderia misturar avisos do framework com exceções comerciais
  já tratadas.
- A página Administração oferece a ação **Exportar diagnóstico**. Caixa não
  recebe essa permissão. Se o banco estiver indisponível e a sessão não puder
  ser revalidada, a exportação é recusada; essa é uma limitação deliberada de
  segurança.

## Catálogo essencial em memória (T52)

- `services/catalogo_memoria_service.py` mantém um snapshot local por janela,
  sem persistência adicional e sem credenciais ou dados de venda.
- Cada entrada é imutável e contém somente ID, código, nome, forma de venda,
  preço em centavos e situação. O mapa interno não é entregue à interface.
- A origem é uma única listagem consistente do SQLite, incluindo ativos e
  inativos. A construção ocorre fora do estado publicado e a troca do snapshot
  acontece integralmente sob bloqueio; carga vazia é válida, carga parcial não.
- A carga inicial ocorre depois da autenticação, durante a construção da janela.
  Cadastro, edição de código/preço e ativação/desativação recarregam o conjunto
  completo. A atualização invalida primeiro o snapshot; se a releitura falhar,
  o estado permanece `INDISPONIVEL` e nenhuma versão antiga é consultável.
- Consultas degradadas exigem chamada explícita ao serviço. O fluxo normal ainda
  consulta SQLite e não alterna silenciosamente para o snapshot. A entrada
  imutável é aceita pelos contratos existentes de etiqueta, estimativa e item,
  mantendo o valor total da etiqueta como subtotal oficial.
- Não há gravação no catálogo, fila de venda, fechamento ou cancelamento sem
  SQLite. Exibição do modo degradado pertence ao T53 e liberação/protocolo
  operacional pertencem ao T54.
- Cada instância fica vinculada internamente a um único arquivo SQLite. A
  comparação resolve e normaliza caminhos e, quando possível, confirma a
  identidade do arquivo, aceitando formas relativas/absolutas equivalentes.
  Uma origem diferente é recusada antes de ler, invalidar ou gravar; o caminho
  não é exposto no estado público, na interface ou em logs.
- Os fluxos integrados de cadastro, edição e situação validam a origem antes da
  autorização/transação e recarregam depois do sucesso. Chamadas externas que
  não recebem `catalogo_produtos` não sincronizam snapshots automaticamente;
  essa limitação evita um registro global ou ampliação arquitetural no T52.

## Modo de cálculo degradado (T53)

- `services/estado_operacional_service.py` mantém uma máquina de estados por
  janela: `NORMAL`, `CALCULO_DEGRADADO` ou `INDISPONIVEL`. Não existe transição
  automática de volta ao estado normal durante o processo.
- A degradação exige simultaneamente uma falha SQLite de acesso reconhecida e
  um snapshot T52 disponível da mesma origem. Erro de entrada, regra comercial,
  integridade ou programação permanece erro e não seleciona o catálogo.
- A sessão já emitida pode ser validada no registro processual confiável para
  manter apenas os cálculos autorizados. Nova autenticação, troca de operador,
  consulta administrativa e qualquer operação persistente continuam bloqueadas.
- Etiquetas preservam o total codificado como subtotal. Itens, quantidades e
  totais permanecem exclusivamente na memória e a interface os identifica como
  não registrados; não há fila, arquivo auxiliar ou segunda persistência.
- Cada banco usado pela janela fica vinculado, em memória e somente durante o
  processo, ao primeiro controlador operacional registrado. Persistência de
  vendas, cancelamentos e mutações de produto consultam esse vínculo pelo banco
  antes de validar ou gravar, mesmo se a integração omitir o controlador. Um
  controlador posterior não substitui a autoridade canônica; caminhos
  equivalentes do mesmo arquivo resolvem o mesmo vínculo. Na ausência de vínculo,
  chamadas legadas preservam o fluxo normal.
- O controlador mantém referência ao snapshot usado na degradação. Se esse
  catálogo for invalidado, a próxima consulta de estado muda de forma irreversível
  para `INDISPONIVEL` e cálculos adicionais são bloqueados. Não há recuperação
  automática; confirmação, liberação e retomada permanecem reservadas ao T54.
- Operações comerciais usam `operacao_comercial_em_modo_normal()` como seção
  crítica. A resolução do vínculo usa um bloqueio curto; em seguida, o `RLock` do
  controlador canônico permanece adquirido desde a validação do modo até o
  `commit`, `rollback` e reconciliação imediata. Assim, uma transição concorrente
  acontece integralmente antes ou depois da operação, nunca durante a gravação.
  Cadastro e edição podem entrar de forma aninhada porque o bloqueio é
  reentrante; bancos diferentes usam controladores independentes.
- O vínculo não possui remoção pública no T53. Reabrir uma janela no mesmo
  processo ou substituir fisicamente o arquivo mantendo o caminho conserva o
  estado anterior de forma fail-closed. Liberar ou reconstruir esse ciclo de
  vida com confirmação operacional pertence ao T54.

## Contingência e retomada operacional (T54)

- A interface conserva um aviso persistente nos modos `CALCULO_DEGRADADO` e
  `INDISPONIVEL` e oferece uma ação explícita para verificar recuperação. Itens e
  totais existentes permanecem em memória; a verificação ou retomada não os
  grava, descarta nem apresenta como venda persistida.
- A verificação técnica exige o arquivo SQLite existente, schema na versão
  esperada, tabelas essenciais legíveis, `PRAGMA quick_check` satisfatório e
  aquisição de `BEGIN IMMEDIATE` seguida de rollback. Ela nunca retorna o modo a
  `NORMAL` por si só e não cria um banco ausente.
- A confirmação repete a verificação dentro da seção crítica do controlador
  canônico vinculado ao banco. Em seguida revalida no SQLite credenciais do perfil
  Administrador e reconstrói integralmente o catálogo T52 antes da transição.
  Uma sessão local preservada, um perfil Caixa ou um controlador independente não
  concedem autoridade para liberar persistência.
- Fechamento com resultado incerto bloqueia tanto a liberação quanto qualquer
  falsa confirmação de normalidade. Falha de integridade, leitura, bloqueio,
  autenticação ou reconstrução do catálogo mantém o estado restritivo. Cada
  janela marca sua incerteza no controlador canônico compartilhado pelo banco;
  remover uma marca não elimina as demais. UUID e confirmação continuam privados
  da janela de origem. A ação de verificação fica desabilitada fora do modo
  `NORMAL` e uma tentativa recusada não altera esses dados.
- O protocolo é exclusivamente processual. Sem novo schema ou persistência
  auxiliar, não recupera UUID de fechamento, carrinho, pagamentos nem cálculos
  em memória após o encerramento do processo. Também não cria fila de vendas,
  recuperação automática, backup ou restauração.

## Backup SQLite local (T55)

- `services/backup_local_service.py` abre a origem em modo somente leitura e usa
  a Backup API do SQLite. Isso obtém uma imagem transacional consistente também
  em WAL, sem copiar diretamente o arquivo aberto e sem modificar registros ou
  schema.
- A cópia nasce como temporário no destino. Antes da publicação, uma conexão
  independente confirma `PRAGMA integrity_check = ok`, versão exata do schema,
  tabelas essenciais legíveis e ausência de violações de chave estrangeira. A
  publicação usa nome exclusivo e não substitui arquivos existentes.
- A identidade do banco é privada e deriva do caminho canônico e da identidade
  do arquivo. Cada origem usa subdiretório próprio em
  `backups/local/<identidade>`; substituir o banco no mesmo caminho cria nova
  identidade e não mistura sua rotação com as cópias anteriores.
- A retenção mantém o backup mais recente de cada um dos sete dias locais mais
  recentes e, antes desse intervalo, o mais recente de cada uma das quatro
  semanas ISO. A cópia recém-publicada é protegida mesmo se o relógio retroceder.
  Arquivos desconhecidos, temporários, links e outras identidades não participam
  da exclusão. Erro ao remover uma cópia antiga mantém o arquivo e aparece no
  resultado, sem invalidar o novo backup.
- A publicação exclusiva usa link atômico entre nomes no mesmo filesystem. Um
  destino local sem esse recurso é recusado de forma segura, sem fallback para
  sobrescrita ou cópia não atômica.
- O ciclo completo de uma operação — temporário, cópia, validação, publicação,
  retenção e confirmação do resultado — é serializado por origem e destino. Um
  `RLock` coordena threads e um arquivo oculto com lock exclusivo coordena
  processos que usam o mesmo serviço. O arquivo de lock é persistente e ignorado
  pela retenção; o sistema operacional libera o lock se o processo terminar.
  Cada operação adquire apenas esse lock e a espera expira em 60 segundos, sem
  ciclo de dependências. Origens distintas usam diretórios e locks distintos.
- O lock entre processos é cooperativo. A garantia não abrange exclusão por
  ferramentas externas nem filesystems de rede que não preservem corretamente
  locks e links atômicos; nesses ambientes o destino deve ser considerado
  incompatível até validação operacional.
- O serviço opera somente enquanto o controlador canônico permanece `NORMAL`.
  A cópia é recusada em `CALCULO_DEGRADADO` e `INDISPONIVEL`; ela não libera
  estado, não repara banco e não altera as barreiras comerciais.
- O T55 fornece mecanismo local sob chamada explícita. Periodicidade de duas
  horas, cópia ao encerrar, destino externo e alertas pertencem ao T56; seleção
  e aplicação de uma restauração pertencem ao T57.

## Backup externo configurável (T56)

- `services/backup_externo_service.py` não abre nem copia o SQLite operacional.
  Ele solicita ao T55 uma cópia local consistente, mantém um descritor estável
  dessa cópia e entrega seu conteúdo ao destino configurado.
- O contrato `DestinoBackupExterno` separa a origem validada do transporte. A
  implementação atual, `DestinoDiretorio`, atende unidade removível ou
  compartilhamento montado e permite testes isolados; novos transportes devem
  preservar validação, publicação exclusiva e contrato de falha.
- O destino é opt-in pela variável `SISTEMA_PDV_BACKUP_EXTERNO_DIR`. Sem valor,
  o estado é `NAO_CONFIGURADO` e nenhum backup é tentado. Com valor, o
  agendador faz uma tentativa em thread daemon após abrir a operação e aguarda
  duas horas a partir do fim de cada tentativa. Uma falha não provoca laço de
  retentativas; a próxima tentativa ocorre no intervalo regular.
- O transporte grava um temporário exclusivo no destino, calcula SHA-256 na
  origem e na cópia recebida, reabre o SQLite para as validações do T55 e só
  então publica sem sobrescrita. Falha limpa o temporário na medida permitida e
  preserva cópias válidas anteriores.
- Cada origem usa subdiretório e lock próprios. Operações cooperantes da mesma
  origem e destino serializam cópia, publicação e retenção; origens distintas
  permanecem isoladas. A retenção conserva um ponto por cada um dos 30 dias
  locais mais recentes e não toca arquivos desconhecidos.
- O estado público distingue `NAO_CONFIGURADO`, `PENDENTE`, `EM_EXECUCAO`,
  `SUCESSO` e `FALHA`, com última tentativa, último sucesso e tipo técnico do
  erro. Logs catalogados não contêm caminho, hash, credencial ou dado comercial.
  Esse estado é volátil e reinicia com o processo.
- Falha externa nunca libera estado operacional, nunca bloqueia operação
  comercial e não substitui restauração. O T57 continua responsável por
  seleção e recuperação assistida.
- Um diretório diferente pode estar no mesmo disco. O serviço rejeita a área
  local conhecida, mas não declara redundância física: mídia removível,
  compartilhamento, permissões e locks precisam ser homologados no ambiente.
- Limitações atuais: o agendador só existe enquanto o aplicativo está aberto;
  timestamps e resultado não sobrevivem ao reinício; parada de thread é
  cooperativa diante de I/O travado. O requisito histórico de backup ao encerrar
  quando houver mudanças não foi presumido: não existe marcador durável e
  confiável de mutação para implementá-lo sem ampliar a arquitetura.

## Restauração assistida em base de teste (T57)

- `services/restauracao_assistida_service.py` recebe explicitamente um backup
  T55 ou T56 e o caminho de uma nova base de teste. Não há descoberta
  automática, interface ou substituição do banco operacional.
- Antes de copiar, o serviço rejeita ausência, diretório, link simbólico, nome
  fora dos contratos oficiais, SQLite corrompido, schema incompatível,
  estrutura incompleta e violação de chave estrangeira.
- A autorização exige uma sessão emitida e ainda válida, confirmação
  explícita e credenciais de Administrador revalidadas no banco operacional
  pelo limitador de tentativas existente. Uma sessão Caixa pode solicitar a
  operação, mas credenciais Caixa nunca concedem a autoridade administrativa.
- A recuperação cria temporário exclusivo no diretório escolhido, copia o
  backup sem modificá-lo, valida novamente a cópia pelo contrato do T55 e por
  consultas funcionais a produtos, vendas e pagamentos, e publica por link
  exclusivo. Destino existente nunca é substituído. O filesystem do destino
  precisa oferecer hard link no mesmo diretório; sem essa garantia a publicação
  falha de forma conservadora.
- O resultado imutável informa caminho da base de teste, origem local ou
  externa, instante UTC, schema, validação e contagens de produtos, vendas e
  pagamentos. Logs registram somente resultado e tipo técnico de erro, sem
  caminhos, credenciais, hashes ou dados comerciais.
- O serviço não consulta nem modifica o controlador T54. Recuperação bem
  sucedida não muda o modo para `NORMAL`, não resolve fechamento incerto e não
  libera vendas. Substituição futura deverá preservar o banco anterior e exigir
  um protocolo próprio, fora deste ticket.

## Migrações versionadas e atualização coordenada (T58)

- `database/migracoes.py` é o registro único de rotas SQLite. Cada passo informa
  origem, destino, identificador, classificação legada e declaração explícita de
  compatibilidade com o aplicativo anterior. `PRAGMA user_version` continua
  sendo a versão do schema e não se confunde com a versão do aplicativo.
- O motor valida a estrutura progressiva declarada para cada versão: conjunto,
  tipo, nulabilidade e chave primária das colunas essenciais; unicidade, colunas,
  ordenação e colação dos índices; e definições exatas das chaves estrangeiras.
  A inspeção usa conexão SQLite somente leitura e nunca cria caminho ausente.
  O caminho completo é calculado antes da alteração, e todos os passos,
  inclusive cada avanço de `user_version`, usam uma única transação. Falha
  provoca rollback integral; versão futura, rota ausente, corrupção ou estrutura
  divergente bloqueiam a inicialização sem recriar tabelas.
- `preparar_banco_para_operacao()` serializa processos cooperantes por banco,
  inspeciona a origem, cria uma cópia consistente validada antes da primeira
  mudança e somente libera a operação após validação final. O backup reutiliza
  o núcleo SQLite do T55 com validador adequado à versão legada e confirma que
  `user_version` da cópia corresponde à versão original inspecionada, sem
  modificar retenção ou contratos públicos dos T55, T56 e T57.
- A coordenação usa lock de arquivo com espera limitada para processos que
  adotam o serviço e `BEGIN IMMEDIATE` como barreira SQLite. Ferramentas externas
  que ignoram o lock não fazem parte da garantia; a transação ainda impede duas
  gravações concorrentes no mesmo banco.
- As rotas v0→v10 são históricas e legadas. Elas permanecem disponíveis para a
  inicialização existente, mas não autorizam automaticamente a próxima etapa de
  um instalador. A rota v9→v10 reconstrói `produtos` e pode ser incompatível com
  aplicativos anteriores; atualizações operacionais por essa rota dependem de
  procedimento de manutenção e homologação fora deste ticket.
- Para qualquer migração posterior à v10, a DEC-056 é integral: cada passo
  deve primeiro declarar sua compatibilidade. A homologação é um estado
  separado e exige identificar a versão anterior do aplicativo e a evidência
  técnica; somente a rota integralmente declarada e homologada pode autorizar a
  etapa seguinte. DDL concluído, `integrity_check` satisfatório, declaração ou
  migração bem-sucedida não são, isoladamente, prova de compatibilidade.
- Os números SQLite v0→v10 são internos ao desenvolvimento. O primeiro
  lançamento comercial homologado poderá ser identificado como aplicativo
  `1.0.0`, independentemente do número interno de schema aprovado naquela data.
  Esse lançamento será o primeiro marco de compatibilidade comercial; as
  migrações existentes não serão renumeradas.
- O resultado estruturado separa três dimensões: aptidão estrutural para operar
  com o aplicativo atual; estado e passos da migração; e autorização para a
  próxima etapa de uma atualização coordenada. Banco novo ou já atualizado pode
  estar apto à operação com autorização de atualização falsa. Rota vazia nunca
  autoriza instalar outro aplicativo. A autorização somente pode ser positiva
  para uma rota não vazia, futura, integralmente declarada e homologada, e vale
  para aquela execução coordenada; ela não fica persistida no banco. O resultado
  também informa versões, backup, declaração e homologação, mas não instala
  executável, restaura automaticamente o banco nem substitui o futuro T60.
- O T60 deverá manter o PDV fechado, preservar executável, configurações e
  banco anteriores, validar as combinações aplicativo/schema antes e depois,
  acionar o T58, exigir backup válido e instalar o aplicativo novo somente se a
  etapa de banco autorizar. Falha de migração impede a instalação; falha do
  instalador deve conservar ou recuperar o executável anterior somente quando
  sua compatibilidade estiver comprovada. A combinação final precisa ser
  validada e o banco operacional jamais é substituído automaticamente por um
  backup como rollback comum. Se a coordenação for interrompida depois da
  migração, uma nova execução sem rota não herda a autorização anterior; o T60
  deverá revalidar explicitamente a combinação antes de prosseguir.

## Empacotamento Windows (T59)

- `main.py` é o ponto de entrada do PyInstaller. A especificação versionada gera
  `Sistema-PDV.exe` em modo `onedir`, sem console, e deixa as dependências sob a
  pasta da aplicação. QtCore, QtGui, QtWidgets e os plugins resolvidos pelos
  hooks oficiais do PyInstaller compõem o runtime; nenhum recurso externo é
  necessário atualmente.
- O roteiro copia por allowlist somente `main.py` e módulos Python de runtime.
  `data/`, testes, documentos, caches, logs, backups, credenciais e temporários
  não entram na análise. A árvore produzida é novamente auditada antes de ser
  considerada distribuição.
- Cada execução produz sua candidata em diretório isolado. A pasta publicada
  anterior não é removida durante preparação, PyInstaller, auditoria ou smoke;
  somente depois do sucesso ocorre uma troca protegida da saída local, com
  restauração da anterior se a própria publicação falhar. Isso não constitui
  atualização nem rollback de instalação do T60.
- O roteiro usa o caminho absoluto do interpretador resolvido no início,
  substitui temporariamente `PYTHONPATH` pela raiz conhecida e valida Windows
  x64, Python 3.14, versões fixadas em `requirements-build.txt` e `pip check`.
- Build e commit seguem exclusivamente o T50. Valores explícitos ou o commit do
  repositório de build são validados e escritos somente na cópia temporária de
  `services/version_service.py`; a fonte de desenvolvimento permanece com
  metadados desconhecidos. A máquina de execução não precisa de Git, Python ou
  rede.
- `database/conexao.py` centraliza a escolha de dados. Em desenvolvimento usa
  `repositorio/data/sistema_acougue.db`. O T59 usou provisoriamente
  `%LOCALAPPDATA%` para a distribuição ainda não instalada; o contrato
  comercial vigente é substituído pela fundação T60-B descrita abaixo.
- Não existe transferência automática entre o banco de desenvolvimento e o
  empacotado. O T59 não lê, copia, move, exclui ou migra esses arquivos. Backups
  locais e pré-migração continuam ao lado da origem escolhida. Em
  desenvolvimento, logs preservam o destino T49; em instalação comercial,
  seguem o ambiente T60-B sob `%PROGRAMDATA%`.
- O smoke test usa `%LOCALAPPDATA%` temporário, plataforma Qt `offscreen` e um
  argumento técnico do executável. Ele valida detecção congelada, metadados e
  criação de QApplication/widget, encerrando sem abrir nem criar SQLite. Não
  valida renderização da interface operacional, login ou fluxos comerciais;
  esses itens exigem homologação gráfica manual em VM isolada, com identidade
  T60-B e banco exclusivo de Homologação, nunca o banco operacional.
- O T59 não instala, cria atalhos, atualiza nem recupera executável. O T60-B
  substitui o caminho comercial provisório do T59 por `%PROGRAMDATA%`; não há
  transferência automática entre as localizações.

## Fundação da instalação Windows — T60-B, etapa 1

- A execução de desenvolvimento não exige instalação: usa o banco em
  `repositorio/data` e preserva o contrato de logs anterior. Uma execução
  reconhecida como PyInstaller, fora do smoke test restrito do T59, é sempre
  comercial e nunca recua silenciosamente para esse contexto.
- A identidade comercial é lida de
  `HKLM\SOFTWARE\Sistema-PDV\Installations\<InstallationId>`, visão de 64 bits.
  A subchave contém `ProductId`, `Environment`, `EnvironmentId`,
  `InstallationId`, `InstallRoot` e `ExecutablePath` como `REG_SZ`. O
  executável deve pertencer à raiz registrada sob a pasta conhecida
  `%ProgramFiles%`.
- O registro deve coincidir com o objeto JSON fechado
  `%PROGRAMDATA%\Sistema-PDV\<Producao|Homologacao>\administrative\installation.json`.
  O descritor contém `contract_version`, `product_id`, `environment`,
  `environment_id`, `installation_id`, `install_root` e `executable_path`.
  Produto e ambientes usam identificadores estáveis no código; cada instalação
  recebe um UUID normalizado próprio. Registro ausente, múltiplo, inacessível
  ou divergente bloqueia a inicialização.
- O runtime resolve `%ProgramFiles%` e `%PROGRAMDATA%` pelas Known Folder APIs
  do Windows. `PROGRAMDATA`, `LOCALAPPDATA`, `SISTEMA_PDV_LOG_DIR` e o diretório
  de trabalho não selecionam nem redirecionam uma instalação comercial.
- Produção usa `%PROGRAMDATA%\Sistema-PDV\Producao`; Homologação usa
  `%PROGRAMDATA%\Sistema-PDV\Homologacao`. Cada raiz possui `data`, `logs`,
  `config`, `administrative` e `maintenance` separados. Backups locais
  continuam sob a origem do banco e permanecem isolados pelo mesmo contexto.
- O contrato de ACL reserva aos Administradores e `SYSTEM` o controle de
  `config`, `administrative` e `maintenance`. O grupo local
  `Sistema-PDV-Operadores` deve receber escrita em `data` e `logs` e somente
  leitura/travessia nas áreas administrativas necessárias. O aplicativo apenas
  declara e verifica esse contrato; criação do grupo e aplicação das ACLs são
  responsabilidade futura do instalador e não ocorrem em desenvolvimento.
- O mutex nomeado comercial usa o namespace `Global` e combina produto,
  ambiente e instalação. Sua DACL concede controle a Administradores/`SYSTEM`
  e sincronização/modificação ao grupo de operadores. O kernel libera o recurso
  no encerramento normal ou abrupto; `WAIT_ABANDONED` também é aceito de forma
  segura. Produção e Homologação não compartilham mutex.
- A ordem de inicialização é: resolver e validar identidade; adquirir mutex;
  validar estado de manutenção; somente então importar a interface, configurar
  logging, preparar SQLite e criar sessões. Segunda instância exibe aviso
  nativo e encerra antes desses efeitos.
- Nesta etapa, `maintenance/state.json` é uma barreira mínima, não um diário de
  atualização. Para iniciar, o objeto deve identificar produto, ambiente e
  instalação, usar `contract_version` 1 e `status` `IDLE`. Arquivo ausente,
  inválido, desconhecido ou indicando operação incompleta mantém a instalação
  bloqueada. O coordenador, retomada e transições duráveis pertencem às etapas
  posteriores do T60.
- A política de preparação do SQLite é centralizada no serviço de inicialização
  e recebe o contexto da instalação. Em desenvolvimento, mantém criação e
  migrações automáticas legadas. Em contexto comercial, um banco ausente pode
  ser criado pelas validações existentes; um banco presente é aberto somente
  para inspeção. Se já estiver na versão esperada e estruturalmente íntegro,
  pode operar sem DDL. Se possuir versão anterior, a rota é identificada, mas a
  abertura é bloqueada antes de backup ou migração. Versão futura, estrutura
  divergente, banco fora do contexto e manutenção não livre permanecem
  fail-closed. Tanto a inicialização geral quanto a criação da janela principal
  atravessam essa mesma política.
- O argumento interno `--t59-smoke-test` permanece limitado à validação do
  runtime Qt em diretório temporário vazio: não resolve identidade comercial,
  não abre banco, não configura logs e não oferece operação do PDV.

## Instalador de instalação inicial — T60-B.2

- `installer/windows/Sistema-PDV.iss` é compilado duas vezes a partir da mesma
  fonte: Produção e Homologação. Ambos são instaladores por computador, x64,
  elevados e sem atualização. As raízes são
  `%ProgramFiles%\Sistema-PDV\Producao` e
  `%ProgramFiles%\Sistema-PDV\Homologacao`; os dados continuam nas raízes T60-B
  correspondentes sob `%PROGRAMDATA%`.
- Cada ambiente possui `AppId` e mutex estável próprios. O mutex de manutenção
  `Global\Sistema-PDV-<produto>-<ambiente>` é o primeiro objeto adquirido por
  qualquer participante. Instalador e futuro coordenador adquirem somente esse
  objeto, com acesso para `SYSTEM` e Administradores; o runtime permite também
  sincronização ao grupo de Operadores e, depois, adquire o mutex operacional
  `Global\Sistema-PDV-<produto>-<ambiente>-<instalação>`. A liberação ocorre em
  ordem inversa. Inno Setup usa o mutex de manutenção em `AppMutex` e o mantém
  adquirido durante todo o provisionamento ou desinstalação. A enumeração pelo
  caminho exato do processo é uma defesa adicional, não a exclusividade
  primária. Nenhum processo é encerrado automaticamente nem à força.
- A pré-validação ocorre antes de qualquer provisionamento. Ela recusa registro
  HKLM completo ou parcial, entrada de desinstalação, raiz de programa, raiz de
  dados, banco, manutenção ou evidência anterior do mesmo ambiente. Um registro
  parcial ou de ambiente desconhecido é tratado como estado de manutenção, não
  como espaço livre. Uma instalação completa do outro ambiente pode coexistir.
- O helper cria ou valida `Sistema-PDV-Operadores`, mas nunca adiciona usuários.
  ACLs protegidas concedem controle total somente a `SYSTEM` e Administradores;
  operadores recebem modificação em `data` e `logs` e leitura/execução em
  `config`, `administrative`, `administrative/manifests` e `maintenance`.
  Qualquer ACE de escrita para outro SID é recusada; Operadores também não podem
  alterar permissões nem assumir propriedade. A raiz é protegida antes de seus
  filhos, e cada diretório recebe ACL própria. Falha de aplicação ou
  comprovação de qualquer ACL impede `IDLE`.
- O provisionamento protege primeiro a raiz, cria `maintenance` e publica um
  GUID novo em `maintenance/state.json` como `INSTALLING` antes de criar as
  demais áreas. Após copiar a distribuição T59, Inno grava a identidade na visão
  HKLM de 64 bits. A finalização comprova executável, registro, grupo e ACLs,
  grava `installation.json` sem BOM e publica `IDLE` por substituição atômica.
  Falha deixa a raiz administrativa ocupada e estado restritivo, impedindo
  abertura comercial e nova instalação silenciosa.
- A desinstalação remove somente arquivos sob a raiz do programa, atalhos,
  entrada de Aplicativos Instalados e subchave HKLM daquela instalação. Como
  `%PROGRAMDATA%` não pertence ao manifesto de arquivos do Inno, banco, WAL,
  SHM, backups, logs, diagnósticos, configuração, identidade e evidências de
  manutenção são preservados. Esses resíduos bloqueiam uma reinstalação limpa e
  exigirão o procedimento administrativo de recuperação de etapa posterior.
- Para autorizar uma conta, um Administrador local deve adicioná-la
  explicitamente ao grupo, por exemplo em PowerShell elevado:
  `Add-LocalGroupMember -Group "Sistema-PDV-Operadores" -Member "DOMINIO\usuario"`.
  Remover a conta do grupo revoga o acesso operacional no próximo logon/token
  Windows aplicável.
- `scripts/build_installer_windows.ps1` audita novamente a distribuição T59,
  exige Inno Setup 7, compila ambos os ambientes em diretório isolado, valida os
  dois executáveis e publica somente ao final em `dist/installers`. A saída
  anterior permanece intacta se preparação, compilação ou validação falhar.
- A declaração nativa `TSecurityAttributes` e as assinaturas Win32 do mutex no
  Pascal Script dependem da arquitetura atual do processo `Setup` gerado. Uma
  futura mudança da arquitetura nativa desse processo exige revalidar tamanho e
  alinhamento de ponteiros, recompilar as duas variantes e repetir a homologação
  em VM antes de publicar um release.

## Migração administrativa de dados legados — T60-B.3

- O modo `--t60-migrar-dados-legados` é desviado em `main.py` antes do mutex
  operacional, logging, abertura de SQLite e sessões. Ele exige caminho de
  origem explícito, `--confirmar-ambiente` com a frase fechada de Produção ou
  Homologação e token Windows elevado. Não existe descoberta ou migração
  automática na abertura normal ou no instalador T60-B.2.
- A origem deve ser exatamente o banco T59 da conta que executa o procedimento,
  sob a Known Folder `%LOCALAPPDATA%\Sistema-PDV\data`. Links simbólicos,
  junctions, demais reparse points, hard links e caminhos arbitrários são
  recusados em todos os componentes. A identidade física é capturada na seleção
  e revalidada depois do mutex de manutenção, antes e depois da cópia. Como
  `%LOCALAPPDATA%` é por usuário, uma origem de
  outra conta exige executar o procedimento no contexto dessa conta com
  elevação; não há varredura de perfis nem confiança em variável de ambiente.
- O destino é derivado exclusivamente do contexto comercial validado em HKLM e
  `installation.json`. O serviço adquire o mutex de manutenção por ambiente,
  comprova `IDLE`, verifica que não existe outra instância `Sistema-PDV.exe` e
  exige que o diretório comercial `data` esteja integralmente vazio, inclusive
  sem arquivos desconhecidos, ocultos ou subdiretórios. Nada encontrado é
  removido, movido ou sobrescrito. Produção e
  Homologação nunca compartilham contexto ou histórico.
- `inspecionar_migracao()` abre a origem em modo somente leitura e exige schema
  atual, integridade e estrutura estrita. Versão anterior, futura ou divergente
  é encaminhada ao futuro coordenador; o T60-B.3 não chama o executor T58.
- A publicação usa `criar_copia_sqlite_consistente()` do T55 no diretório
  comercial vazio. A API SQLite incorpora dados confirmados em WAL ao snapshot,
  valida a candidata e publica sem sobrescrita. Origem, arquivos auxiliares e
  backups legados permanecem intactos; não há movimento ou restauração.
- Cada tentativa que alcança um contexto comercial confiável recebe UUID e
  diretório imutável em `administrative/manifests/data-migrations`. Eventos JSON
  registram início, validação, resultado e tipo seguro de falha, sem expor
  caminhos. Identidade divergente ou inacessível é recusada sem gravar no
  destino não confiável. Depois das pré-condições, `maintenance/state.json`
  passa a `MIGRATING_LEGACY_DATA`.
  Somente uma cópia publicada e validada permite substituir o estado por
  `IDLE`. Falha ou interrupção conserva estado restritivo; se o arquivo final já
  existir, nova tentativa é recusada e nunca o remove ou sobrescreve.
- Uma operação interrompida requer inspeção administrativa do estado, histórico
  e cópia publicada. Recuperação automática, migração de schema, restauração e
  atualização de executável permanecem fora desta etapa. O histórico é
  protegido pelas ACLs administrativas e publicado sem sobrescrita, mas ainda
  não possui assinatura criptográfica nem individualiza o Administrador além da
  comprovação do token elevado.

## Manifestos e integridade de pacotes — T60-B.4

- `package-manifest.json` usa contrato 1 e JSON UTF-8 canônico: chaves ordenadas,
  sem espaços supérfluos, duplicatas ou valores não JSON. Ele identifica produto,
  ambiente, pacote, versão T50, build, commit opcional, Windows x64, política de
  atualização, schema exigido, migrações declaradas e matriz explícita de
  origens por versão do aplicativo e schema. A geração é determinística quando
  conteúdo e metadados são iguais; não contém instante, caminho local ou segredo.
- O inventário cobre todos os arquivos do pacote, exceto o próprio manifesto e
  sua assinatura destacada, usando caminho POSIX relativo, tamanho e SHA-256.
  A inspeção rejeita ausências, extras, colisões sem distinção de caixa,
  caminhos absolutos ou com `..`, nomes reservados ou ambíguos no Windows,
  links, junctions, reparse points, hard links e entradas especiais. As mesmas
  verificações físicas protegem o manifesto, a assinatura e o relatório T59.
  Nenhum arquivo distribuído é executado durante a análise.
- A assinatura destacada usa Ed25519 sobre os bytes canônicos do manifesto. O
  `key_id` seleciona uma chave somente numa âncora pública confiável; uma chave
  entregue pelo próprio pacote não cria confiança. A chave privada é lida apenas
  pela ferramenta de assinatura e é recusada se estiver dentro do pacote.
- Não há chave pública comercial autorizada nesta etapa. A âncora embutida está
  vazia e, portanto, o verificador fail-closed rejeita qualquer assinatura no
  runtime normal. Testes criam chaves efêmeras somente em `tmp_path`. Incorporar
  ou rotacionar uma chave pública exigirá decisão de release, revisão do
  fingerprint e nova distribuição protegida em `%ProgramFiles%`; a chave privada
  nunca será incorporada.
- `scripts/build_windows.ps1` preserva o T59 sem manifesto quando nenhuma
  configuração é informada. Com `-ConfiguracaoManifesto`, gera e audita o
  manifesto somente depois do build, smoke test e `build-report.json`, mas antes
  da publicação protegida. `-ChavePrivadaManifesto` e `-ChaveIdManifesto` são
  opcionais e inseparáveis. Geração, auditoria, assinatura e futura verificação
  pelo coordenador continuam etapas distintas. O relatório T59 é gravado em
  UTF-8 sem BOM por API .NET explícita, compatível com Windows PowerShell 5.1 e
  PowerShell 7.
- `verificar_pacote_assinado()` comprova primeiro a assinatura, depois contrato,
  inventário, relatório T59, identidade comercial, plataforma e matriz de
  compatibilidade. O resultado mantém
  `atualizacao_coordenada_autorizada=False`: declaração e homologação registradas
  no manifesto não substituem a autorização do T58/T60 nem executam migração.
- O T60-B.4 não bloqueia concorrência externa que altere um diretório enquanto
  ele é inspecionado. O coordenador futuro deverá copiar ou abrir o pacote em
  staging administrativo exclusivo e revalidá-lo imediatamente antes de cada
  transição. Também permanecem pendentes assinatura comercial real, custódia e
  rotação de chaves, revogação, assinatura de código Authenticode e homologação
  do pacote numa VM Windows limpa e offline.

## Riscos e validações ainda necessários
- Homologar em VM Windows limpa a instalação e desinstalação reais, ACLs entre
  contas, mutex entre sessões, encerramento abrupto e coexistência entre
  Produção e Homologação; os testes automatizados não substituem essa etapa.
- Homologar também a migração T60-B.3 com conta operacional elevada, origem T59
  em WAL, junctions e reparse points reais, concorrência entre contas e sessões,
  interrupções em cada publicação, ACLs do histórico e reabertura do banco
  copiado. Nenhum desses ensaios deve usar dados operacionais reais.
- Verificar no T62 o padrão real das etiquetas de balança, dígito verificador,
  semântica dos campos e comportamento do leitor físico.
- Validar no T61/T62 lock SQLite, transações incertas, escala do Windows e metas
  de latência no equipamento alvo.
- Validar no ambiente instalado a mídia externa, permissões e semântica de
  locks do T56 e executar uma homologação manual da base de teste do T57. O
  Marco 2 cobre o backup pré-migração.
- Reavaliar em ticket futuro, mediante decisão de schema/persistência, a
  recuperação de UUID de fechamento e carrinho após encerramento do processo;
  o T54 documenta a impossibilidade atual e permanece fail-closed.
- Sessões, capacidades e bloqueios de credencial são locais ao processo; antes
  da produção, adotar instância única ou decidir coordenação entre processos.
- O cancelamento não possui identificador persistente por tentativa; resultado
  ambíguo permanece fail-closed até consulta e decisão operacional.
