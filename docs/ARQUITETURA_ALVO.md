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
Administrador com sessão revalidada. Administração permanece desabilitada até
sua integração.
Resultado de commit incerto fixa a operação na Frente de Caixa até verificação
ou recuperação controlada.

## Dados e integridade
- SQLite único local, foreign_keys habilitado, transação atômica ao gravar venda+itens+pagamentos.
- O esquema versão 8 introduz `usuarios` e o singleton `estado_identidade`. O
  marcador referencia o administrador inicial por FK `RESTRICT`, impedindo sua
  remoção normal e distinguindo configuração ausente de estado inconsistente.
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
  opera vendas e consulta Histórico; Administrador também administra Produtos e
  provisiona Caixa pelo serviço protegido. A tela avançada de usuários não foi
  antecipada.
- T47 produzirá o contexto de autorização pontual exigido pela INT-D2 sem
  elevar a sessão corrente; T48 continua responsável pela recuperação offline.

## Distribuição
Binário Windows empacotado, arquivos de dados fora da instalação; instalador atualiza só programa e executa migrador quando necessário; backup válido e migração segura, sem retrocesso automático de banco em falha. A inicialização operacional recusa versões futuras e, para banco existente desatualizado, só migra depois de criar e verificar uma cópia única em `backups/pre_migracao` ao lado do arquivo SQLite. Compatibilidade/licença PySide6 deve ser avaliada em entrega comercial.

## Riscos e validações ainda necessários
- Verificar padrão real de todas as etiquetas de balança, dígito verificador e semântica dos campos.
- Inspecionar scripts, dependências, base real e testes do ZIP antes de reaproveitar/refatorar.
- Definir limites precisos de precisão/arredondamento e política de cadastro código/forma de venda antes de implementar.
- Testar o leitor físico, lock SQLite, transações incertas, restauração e metas de latência no equipamento alvo.
