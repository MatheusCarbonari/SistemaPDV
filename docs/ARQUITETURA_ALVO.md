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
SQL no widget. Caixa não acessa Produtos; a página somente é habilitada para
Administrador com sessão revalidada. Administração lista e gerencia somente
contas Caixa por serviços protegidos; visibilidade de botão nunca substitui a
autorização na camada de aplicação.
Resultado de commit incerto fixa a operação na Frente de Caixa até verificação
ou recuperação controlada.

“Trocar operador” invalida a sessão atual, fecha a janela e retorna ao diálogo
único de login. A operação é recusada enquanto itens, pagamentos, confirmação
ou fechamento estiverem pendentes. Fechar a janela pelo sistema invalida a
sessão sem iniciar outra automaticamente e respeita o mesmo bloqueio para não
descartar um atendimento em memória.

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
- `id` técnico não é `codigo` operacional. ID de venda persistente e único; usar identificador separado por tentativa para idempotência.
- Snapshot de cada item para não depender de mudanças no cadastro; `produto_id` opcional para Diversos.
- Preços monetários em centavos; multiplicação de kg usa Decimal e política explícita de arredondamento.
- Guardar forma de entrada e procedência da quantidade, especialmente se estimada por valor/preço.
- Durante venda com itens, novos produtos podem ser cadastrados, mas produtos
  existentes não podem ser editados, ativados ou desativados. O bloqueio é
  validado na execução da operação, e snapshots já lançados permanecem intactos.
- No futuro, categorias em tabela editável; não impor enumeração rígida.

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

## Riscos e validações ainda necessários
- Verificar padrão real de todas as etiquetas de balança, dígito verificador e semântica dos campos.
- Inspecionar scripts, dependências, base real e testes do ZIP antes de reaproveitar/refatorar.
- Definir limites precisos de precisão/arredondamento e política de cadastro código/forma de venda antes de implementar.
- Testar o leitor físico, lock SQLite, transações incertas, restauração e metas de latência no equipamento alvo.
