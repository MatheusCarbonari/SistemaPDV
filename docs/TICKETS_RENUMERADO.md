# Backlog de implementação — Sistema-PDV (sequência consolidada)

**Revisão:** 02/11/2026 — versão para substituir `docs/TICKETS.md` após revisão.

**Política de numeração:** T01–T20 são o histórico executado e permanecem como T01–T20; T13 é deliberadamente omitido. A execução retoma em **T21** e continua sempre em ordem crescente. O Marco 1.5 recupera pendências do backlog original; os Marcos 2 e 3 são renumerados sem mudar os objetivos originais.

**Evidência de execução:** T01–T20 foram reportados como concluídos pelo Codex; última suíte reportada: **331 testes aprovados** no T20. A verificação dos arquivos e testes no repositório local ainda é necessária para aprovação técnica definitiva.

**Importante:** identificação "Original Txx" abaixo refere-se somente ao documento do ZIP de 30/10/2026; não é numeração a ser executada. Os números oficiais são os novos cabeçalhos Txx deste documento. Nenhuma tarefa do Marco 1.5 deve duplicar o código já concluído.

## Mapa de correspondência — sem recriar tickets antigos

| Escopo no planejamento original | Execução aproveitável | Providência oficial |
|---|---|---|
| T01–T07 | T01–T07 realizados | Concluídos conforme relatórios |
| T08 — Catálogo de etiquetas reais | T06–T08 criaram parser e associação, mas não catálogo real | **T21** |
| T09 — Modelo de item em memória | T09–T11, T12, T14–T16 | **T22** apenas auditoria de lacunas |
| T10 — Inclusão de linha | T16 e T17 | Já atendido; sem novo ticket |
| T11 — Totalização | Nenhuma função de totalização reportada | **T23** |
| T12 — Remover e desfazer por identificador | T18–T20 cobrem índice e undo único; falta identificador estável | **T24** complementa, sem reimplementar |
| T14 — Entrada manual por unidade | T14 realizado foi estimativa de unidades, não entrada manual | **T25** |
| T15 — Entrada manual por peso | T12 realizou apenas estimativa de peso | **T26** |
| T16 — Diversos | Código 9999 reservado no T05; fluxo ainda não criado | **T27** |
| T17 — Janela PySide6 mínima | Não implementada | **T28** |
| T18 — Entrada e atalhos | Não implementados; decisões de foco e modais já aprovadas | **T29** |
| T19 — Lista de itens | Backend T16–T20 implementado; GUI pendente | **T30** |
| T20 — Medição de leitura | Ainda não implementada no hardware físico | **T31** |
| T21–T37 — Operação comercial | Não contemplados nos tickets executados | **T32–T48** |
| T38–T51 — Produção e confiabilidade | Não contemplados nos tickets executados | **T49–T62** |

**Regras da operação já aprovadas:** o leitor e a digitação usam um campo central; etiqueta mantém o subtotal original; quantidade/peso calculados são estimativas, exceto valores informados; `9999` abre Diversos; código manual de produto por unidade abre quantidade, por peso abre peso e valor editáveis; ao remover, prevalece o item selecionado e, sem seleção, a última linha. A atribuição de tecla (como F2) será feita no T29, sem conflitar com outros atalhos.

## Critério de conclusão padrão

- Escopo realizado sem mudanças laterais.
- Conceito técnico explicado antes do prompt de implementação.
- Testes específicos e regressão relevante executados em ambiente seguro.
- Código e documentação consistentes; arquivos modificados revisados.
- Relatório de mudanças, testes e riscos; aprovação do usuário para avançar.

## Marco 1 — Núcleo de leitura e cálculo (T01–T20 concluídos por relatório)

### T01 — Auditoria somente leitura
**Entrega verificável:** Inventariar código e testes existentes; recomendar reaproveitamento, sem editar código.
**Conceito a estudar:** Arquitetura, acoplamento, coesão.

### T02 — Testes de referência
**Entrega verificável:** Executar testes existentes em ambiente isolado; documentar falhas e dependências.
**Conceito a estudar:** pytest, fixture, isolamento.

### T03 — Mapa de dependências
**Entrega verificável:** Planejar transição de customtkinter para PySide6 sem implementá-la ainda.
**Conceito a estudar:** Camadas, dependência, refatoração.

### T04 — Contrato de Produto
**Entrega verificável:** Conferir entidade/validações atuais versus desenho aprovado; alterar apenas se necessário.
**Conceito a estudar:** Modelagem de entidade, invariantes.

### T05 — Reserva de códigos
**Entrega verificável:** Garantir código 9999 reservado e casos de teste isolados.
**Conceito a estudar:** Validação, restrições.

### T06 — Parser EAN-13
**Entrega verificável:** Validar formato e dígito verificador; rejeitar entradas inválidas.
**Conceito a estudar:** Parsing, checksums.

### T07 — Campos da etiqueta
**Entrega verificável:** Extrair código e subtotal em centavos; preservar código bruto.
**Conceito a estudar:** Domínio, precisão.

### T08 — Associação entre etiqueta e produto
**Entrega verificável:** Associar etiqueta válida ao produto ativo pelo código normalizado, sem criar item de venda.
**Conceito a estudar:** Composição de serviços e contratos de retorno.

O código de produto extraído remove zeros à esquerda e somente essa forma normalizada é consultada. Cadastros como `234` e `0234` são distintos; não há busca automática por variantes, portanto uma etiqueta com campo `0234` não encontra um produto cadastrado apenas como `0234`.

### T09 — Snapshot comercial do produto
**Entrega verificável:** Copiar os dados comerciais atuais do produto para um snapshot imutável e independente, sem criar item de venda.
**Conceito a estudar:** Objetos de valor, imutabilidade e snapshot.

### T10 — Modelo de item da venda
**Entrega verificável:** Definir um item imutável com snapshot comercial, origem, subtotal e metadados opcionais de quantidade, sem carrinho ou cálculos.
**Conceito a estudar:** Invariantes de domínio, dataclasses imutáveis e Decimal.

### T11 — Criar ItemVenda a partir de ProdutoEtiqueta
**Entrega verificável:** Transformar uma etiqueta já associada em item imutável, copiando snapshot, subtotal e código original sem recálculo.
**Conceito a estudar:** Função de fábrica, composição de modelos e isolamento de mutabilidade.

### T12 — Estimativa de peso
**Entrega verificável:** Estimar quilogramas a partir de subtotal e preço por kg em centavos, com três casas decimais e arredondamento explícito.
**Conceito a estudar:** Decimal, quantização e ROUND_HALF_UP.

### T14 — Estimativa de unidades
**Entrega verificável:** Estimar quantidade inteira sugerida a partir do subtotal e preço unitário com Decimal, ROUND_HALF_UP e mínimo de uma unidade para subtotal positivo.
**Conceito a estudar:** Regras comerciais de estimativa, arredondamento e Decimal.

### T15 — Integrar estimativas ao ItemVenda
**Entrega verificável:** Criar item de etiqueta com estimativa de peso ou unidades quando os dados permitirem, preservando fallback sem quantidade.
**Conceito a estudar:** Composição de funções puras, fallback e isolamento de mutabilidade.

### T16 — Modelo VendaEmAndamento
**Entrega verificável:** Representar em memória uma sequência imutável e ordenada de itens, sem operações de carrinho ou persistência.
**Conceito a estudar:** Coleções imutáveis, agregados em memória e invariantes.

### T17 — Adicionar itens à venda
**Entrega verificável:** Retornar nova versão da venda em andamento com o item acrescentado ao final, sem mutação ou agrupamento.
**Conceito a estudar:** Atualização imutável, identidade de objetos e versionamento em memória.

### T18 — Remover item da venda
**Entrega verificável:** Retornar nova versão da venda sem o item do índice indicado, preservando ordem e identidade dos demais.
**Conceito a estudar:** Fatiamento de tuples, índices e atualização imutável.

### T19 — Inserir item por posição
**Entrega verificável:** Retornar nova versão da venda com um item inserido no índice indicado, preparando o futuro desfazer sem implementá-lo.
**Conceito a estudar:** Inserção imutável por slicing, índices e identidade de objetos.

### T20 — Desfazer última remoção
**Entrega verificável:** Manter somente a última remoção em estado imutável, restaurá-la uma vez e invalidá-la após outras inclusões.
**Conceito a estudar:** Estado imutável, undo de uma etapa e composição de operações puras.

## Marco 1.5 — Recuperação das pendências do núcleo e interface (T21–T31)

As entregas deste marco são originalmente previstas no Marco 1; executá-las antes de iniciar operação comercial. Cada ticket começa consultando o código atual para evitar duplicações.

### T21 — Catálogo de etiquetas reais
**Origem:** backlog original T08.
**Entrega verificável:** Criar testes parametrizados com amostras reais autorizadas de etiquetas por peso e unidade, códigos de produto com zeros à esquerda, checksum e entradas inválidas; preservar os testes existentes.
**Conceito a estudar:** Testes de tabela, fixtures e casos de borda.

### T22 — Auditoria de cobertura do modelo de item
**Origem:** backlog original T09.
**Entrega verificável:** Conferir snapshot, origem, subtotal, estimativas e imutabilidade implementados; documentar cobertura e corrigir apenas lacunas reais com testes. Sem recriar ItemVenda.
**Conceito a estudar:** Contrato de domínio e análise de lacunas.

### T23 — Totalização da venda
**Origem:** backlog original T11.
**Entrega verificável:** Implementar soma exata em centavos a partir dos subtotais dos itens da venda/estado atual, inclusive venda vazia, sem recalcular a partir de preços e estimativas.
**Conceito a estudar:** Aritmética inteira, invariantes e funções puras.

### T24 — Identificação estável das linhas e remoção/desfazer
**Origem:** backlog original T12.
**Entrega verificável:** Complementar remoção por índice e desfazer existentes com identificação estável de linha para seleção na interface; preservar duplicatas, última remoção e estado imutável. Avaliar a menor mudança compatível antes de editar contratos.
**Conceito a estudar:** Identidade de linha versus índice e integridade do undo.
**Observação da revisão T24:** A identificação estável não foi implementada por não ser necessária ao funcionamento inicial do PDV.
A remoção por índice e o desfazer já atendem aos requisitos atuais. A decisão poderá ser reavaliada caso a interface futura exija identificação independente da posição.

### T25 — Entrada manual por unidade
**Origem:** backlog original T14.
**Entrega verificável:** Implementar fluxo lógico de entrada manual a partir de código curto e quantidade informada, com subtotal calculado segundo preço de referência e regras aprovadas; não confundir com quantidade estimada de etiqueta. Deixar diálogo visual para T29.
**Conceito a estudar:** Regras comerciais, Decimal e origem INFORMADA.

### T26 — Entrada manual por peso
**Origem:** backlog original T15.
**Entrega verificável:** Implementar fluxo lógico com peso e valor editáveis, último campo alterado determinando recálculo do outro, precisão e arredondamento explícitos, distinguindo peso informado de estimado. Diálogo visual somente no T29.
**Conceito a estudar:** Eventos, dependência entre campos e arredondamento.

### T27 — Diversos
**Origem:** backlog original T16.
**Entrega verificável:** Implementar inclusão manual de código 9999 com descrição fixa Diversos, valor digitado e produto ausente, preservando invariantes de ItemVenda e subtotal. Diálogo visual para T29.
**Conceito a estudar:** Representação opcional e validação comercial.

### T28 — Janela PySide6 mínima
**Origem:** backlog original T17.
**Entrega verificável:** Remover a interface CustomTkinter e criar o shell Qt Widgets do caixa, sem regra comercial na GUI.
**Conceito a estudar:** Qt Widgets, sinais e separação de camadas.
**Observação:** A remoção do CustomTkinter foi antecipada e incorporada ao T28 por decisão aprovada, evitando duas aplicações gráficas concorrentes.

### T29 — Entrada e atalhos
**Origem:** backlog original T18.
**Entrega verificável:** Ligar campo único a etiquetas e códigos manuais; diálogos contextuais para unidade, peso e Diversos; Enter/Esc, retorno do foco e atalhos, inclusive remoção selecionado/último e desfazer. Testar com pytest-qt.
**Conceito a estudar:** Eventos Qt, foco, sinais e testes de interface.

### T30 — Lista gráfica de itens
**Origem:** backlog original T19.
**Entrega verificável:** Exibir linhas distintas, valores, estimativas identificadas, subtotal totalizado, seleção e remoção; manter sincronização com EstadoVenda e evitar recálculos na GUI.
**Conceito a estudar:** Apresentação de estado, seleção e testes Qt.

### T31 — Medição de leitura
**Origem:** backlog original T20.
**Entrega verificável:** Instrumentar latência da leitura até atualização da lista; testar leitor físico, entradas repetidas e foco, registrando resultados e gargalos.
**Conceito a estudar:** Profiling e métricas operacionais.

**Validação simulada:** o fluxo foi exercitado com eventos reais de teclado Qt,
etiquetas documentadas, banco temporário, leituras consecutivas e integração até
a lista e o estado da venda. A medição com equipamento físico não foi realizada.

**Homologação física pendente:** não há leitor disponível neste momento. Quando
o equipamento estiver disponível, verificar: (1) leitura sem Enter manual e sem
duplicação quando o leitor enviar Enter; (2) leituras consecutivas e repetidas;
(3) foco, subtotal e quantidade de linhas após leituras válidas e inválidas.

## Marco 2 — Operação comercial (T32–T48)

### T32 — Esquema de vendas
**Origem:** backlog original T21.
**Entrega verificável:** Criar tabela vendas e migração testada.
**Conceito a estudar:** Modelagem relacional, migration.

### T33 — Esquema de itens
**Origem:** backlog original T22.
**Entrega verificável:** Criar itens_venda, snapshot e FK opcional de produto.
**Conceito a estudar:** Foreign keys, integridade.

### T34 — Esquema de pagamentos
**Origem:** backlog original T23.
**Entrega verificável:** Criar pagamentos 1:N e restrições.
**Conceito a estudar:** Cardinalidade relacional.

### T35 — Regras de pagamentos
**Origem:** backlog original T24.
**Entrega verificável:** Modalidades repetíveis, saldo restante e valores válidos.
**Conceito a estudar:** Invariantes, centavos.

### T36 — Divisão igual
**Origem:** backlog original T25.
**Entrega verificável:** Parcelas matematicamente exatas em centavos; testes.
**Conceito a estudar:** Divisão inteira, resto.

### T37 — Tela de pagamentos
**Origem:** backlog original T26.
**Entrega verificável:** Diálogo para registros de pagamento; sem SQL na GUI.
**Conceito a estudar:** Sinais, estado de formulário.
**Pendência de fluxo:** permitir editar e remover pagamentos já informados,
recalculando saldo e total pago, preservando os demais registros e permitindo
correção sem cancelar a venda inteira.

### T38 — Confirmação de venda
**Origem:** backlog original T27.
**Entrega verificável:** Resumo Enter/Esc e bloqueio de duplo comando.
**Conceito a estudar:** Fluxo, estado.

### T39 — Persistência atômica
**Origem:** backlog original T28.
**Entrega verificável:** Gravar venda, itens, pagamentos numa transação; rollback em falhas.
**Conceito a estudar:** ACID, transação.

### T40 — Idempotência do fechamento
**Origem:** backlog original T29.
**Entrega verificável:** Identificador por tentativa e verificação de commit incerto.
**Conceito a estudar:** Idempotência.

### T41 — Histórico de vendas
**Origem:** backlog original T30.
**Entrega verificável:** Consulta por ID/data e lista com uma linha por venda.
**Conceito a estudar:** Consultas, índices.

### T42 — Detalhes da venda
**Origem:** backlog original T31.
**Entrega verificável:** Exibir snapshots e pagamentos sem depender de preço atual.
**Conceito a estudar:** Read model.

### T43 — Cancelamento integral
**Origem:** backlog original T32.
**Entrega verificável:** Status, motivo, data, autorização e testes; sem apagar original.
**Conceito a estudar:** Máquina de estados.

## Integrações operacionais aprovadas — antes do T44

### INT-A — Integração do fechamento operacional
**Entrega verificável:** preparar ou migrar o banco antes de abrir a operação,
com backup automático verificado para banco existente desatualizado; conectar a
confirmação comercial à persistência idempotente; reutilizar o UUID em
recuperações; limpar a venda somente após sucesso comprovado e bloquear um novo
atendimento enquanto o resultado permanecer incerto.
**Limite:** backup pré-migração pontual, sem rotação, agendamento ou restauração
automática dos T55–T57.

### INT-B — Interface de histórico de vendas
**Decisão de interface:** uma única janela principal com menu horizontal e
páginas internas independentes para Frente de Caixa, Histórico e futuras áreas
de Produtos e Administração.
**Entrega verificável:** navegar sem recriar ou perder a venda em andamento;
consultar vendas por ID ou dia civil de São Paulo; listar número, data/hora
local, total e status; apresentar detalhes somente leitura com snapshots,
quantidades, subtotais, pagamentos e metadados de cancelamento. Navegação não
pode contornar fechamento com resultado incerto. Produtos é habilitada pela
INT-C; Administração permanece indisponível até sua integração própria.

### INT-C — Interface de administração de produtos
**Entrega verificável:** cadastrar, listar, editar, ativar e inativar produtos
em página interna da janela principal, preservando snapshots e mantendo o
histórico de preços como responsabilidade separada do T44.
**Estado:** aprovada após teste manual do fluxo gráfico.
**Proteção operacional:** com itens na venda em andamento, novos cadastros
continuam permitidos, mas edição e mudança de situação de produtos existentes
ficam bloqueadas até finalizar ou esvaziar a venda. O código identificador não
é editável no formulário. Resultado de commit incerto bloqueia toda a área.
Categorias permanecem textuais conforme o esquema atual, sem lista fixa nem
antecipação da gestão avançada futura.

### INT-D1 — Interface de solicitação de cancelamento
**Entrega verificável:** apresentar no Histórico o resumo da venda ativa,
coletar e validar o motivo e informar que a execução depende de autorização.
Esta etapa é somente visual: não cancela, não persiste solicitação, não cria
status intermediário e não fabrica identidade de autorizador.

### INT-D2 — Execução autorizada do cancelamento
**Entrega verificável:** após autenticação e autorização reais dos T45–T47,
conectar o formulário da INT-D1 ao contexto de autorização e ao serviço
transacional do T43, sem duplicar o formulário nem elevar permanentemente a
sessão. A posição deste registro não remove suas dependências de segurança.
**Contrato implementado:** o Histórico recebe a sessão autenticada da janela,
exige confirmação expressa e abre a autorização administrativa do T47 vinculada
à operação e ao ID exato da venda. Somente a capacidade aceita é entregue ao
T43; sucesso comprovado atualiza lista e detalhe, enquanto desistência,
credencial inválida, capacidade expirada/inválida, repetição e falha SQLite
preservam a venda. Cada nova tentativa exige nova autorização, a sessão Caixa
não é elevada e fechamento incerto mantém o fluxo bloqueado.

### T44 — Histórico de preços
**Origem:** backlog original T33.
**Entrega verificável:** Atualizar preço e registrar mudança em transação única; tela 12 meses depois.
**Conceito a estudar:** Auditoria de alterações.
**Contrato implementado:** registrar somente mudança efetiva, com produto,
preço anterior, preço novo e instante UTC, na mesma transação da atualização do
cadastro. O histórico é preservado após novas alterações ou inativação, sem
exclusão automática. Não há responsável registrado enquanto não existir
identidade autenticada; nenhuma identidade provisória deve ser criada.
**Pendência posterior:** consulta gráfica com janela inicial dos últimos 12
meses. A expressão “tela 12 meses depois” adia essa interface e não determina
expurgo de registros mais antigos.
**Dependência de segurança:** o ticket permanece no planejamento e pode evoluir
seus contratos de domínio/persistência, mas nenhuma exposição gráfica de ação
crítica pode contornar a autenticação e a autorização previstas nos T45–T47.

### T45 — Primeiro acesso
**Origem:** backlog original T34.
**Entrega verificável:** Criar administrador e hash seguro sem senha universal.
**Conceito a estudar:** Autenticação.
**Contrato implementado:** no primeiro acesso, criar exatamente um administrador
com identificação única e senha de 12 a 128 caracteres, protegida por `scrypt`
com salt individual e parâmetros versionados. A conclusão fica registrada por
um marcador singleton que referencia o administrador por FK restritiva. Estado
ausente, divergente ou adulterado falha de modo seguro e não reabre o cadastro.
**Decisão fail-closed:** após configurar o administrador — ou quando ele já
existe — a operação comercial somente fica disponível mediante o login do T46.
Não há senha padrão, sessão implícita, identidade fictícia nem bypass
operacional.

### T46 — Conta Caixa
**Origem:** backlog original T35.
**Entrega verificável:** Login e escopo operacional do Caixa.
**Conceito a estudar:** Sessão, perfis.
**Contrato implementado:** banco configurado sempre apresenta login e somente
uma credencial válida de conta ativa cria `SessaoUsuario` e permite construir a
janela comercial. Falhas de usuário, senha, conta inativa ou hash usam mensagem
indistinguível; cinco falhas em sessenta segundos impõem espera temporária de
trinta segundos em memória, sem bloqueio permanente. Logout invalida a sessão
e fecha a janela; reiniciar exige novo login. A conta é revalidada nas entradas
protegidas, de modo que desativação ou divergência posterior falha fechada.
**Perfis:** Caixa opera Frente de Caixa, pagamentos, confirmação e consulta do
Histórico, mas não acessa Produtos. Administrador também administra Produtos e
pode provisionar Caixa pelo serviço protegido. Não há cadastro público nem tela
antecipada de gestão de usuários. Cancelamento efetivo permanece bloqueado até
T47/INT-D2.

### T47 — Autorização pontual
**Origem:** backlog original T36.
**Entrega verificável:** Senha de admin só para ação crítica; não elevar sessão.
**Conceito a estudar:** Autorização.
**Dependência atual:** reutilizar a autenticação do T46 sem elevar nem trocar a
sessão operacional; somente então conectar a INT-D2.
**Contrato implementado:** sessões autenticadas recebem nonce criptográfico e
só são aceitas enquanto o mesmo objeto estiver no registro processual emissor.
Autorização administrativa emite uma capacidade opaca, válida por 60 segundos,
vinculada à sessão solicitante, operação e venda. O consumo remove a capacidade
sob bloqueio antes do efeito comercial; erro de vínculo, expiração, logout,
concorrência ou falha posterior não permitem reutilização. Credenciais e
capacidades não são persistidas, e a sessão Caixa nunca é elevada.
**Integração T43:** `cancelar_venda()` não aceita mais contexto construível;
exige capacidade emitida e consome-a no gerenciador confiável, preservando a
identidade administrativa na auditoria. A interface permanece desconectada até
INT-D2.

### T48 — Recuperação offline
**Origem:** backlog original T37.
**Entrega verificável:** Códigos únicos hash, consumo e rotação testados.
**Conceito a estudar:** Segredos, recuperação.
**Contrato implementado:** administrador autenticado e com senha atual confirmada
pode emitir ou rotacionar dez códigos offline de 160 bits. Somente verificadores
SHA-256 são persistidos no esquema versão 9; códigos anteriores ainda ativos são
revogados atomicamente e os originais aparecem apenas no diálogo da emissão.
Recuperar exige identificação, código ativo e nova senha conforme a política
vigente; consumo e atualização da senha ocorrem na mesma transação. Sucesso
revoga sessões e autorizações processuais da identidade e não abre nova sessão.
Cinco falhas em cinco minutos aplicam espera local de sessenta segundos.
**Guarda e interrupção:** os códigos devem ser copiados para meio externo seguro.
Não há consulta posterior. Se a apresentação for fechada ou perdida, confirmar
novamente a senha e rotacionar o conjunto; não existe senha mestra, código
universal, recuperação por internet ou reabertura do primeiro acesso.

### INT-E — Acesso gráfico de operadores e administração mínima
**Posição:** após T48 e antes do Marco 3.
**Entrega verificável:** revisar a tela e o fluxo inicial de login dos operadores
Caixa; oferecer acesso gráfico administrativo para provisionar contas Caixa;
avaliar gerenciamento mínimo de contas e troca segura de operador. Deve
reutilizar autenticação, sessões e permissões dos T46–T47, sem duplicar login,
criar bypass ou substituir a autorização pontual de operações críticas.
**Contrato implementado:** Administração é uma página interna disponível somente
para Administrador revalidado e permite listar, cadastrar, ativar e desativar
exclusivamente contas Caixa. Senha inicial individual segue a política vigente,
é ocultada na interface e persistida somente como hash. Desativação revoga
sessões e capacidades processuais do operador. “Trocar operador” invalida a
sessão atual e retorna ao mesmo diálogo de login, mas é bloqueado quando houver
itens, pagamentos, confirmação ou fechamento pendente; commit incerto também
bloqueia navegação e encerramento. Fechar a janela invalida a sessão e não pode
descartar atendimento aberto. INT-E encerra as integrações funcionais previstas
antes da homologação manual do Marco 2.

## Consolidação do Marco 2

Esta fase ocorre após a INT-E e antes do T49. Seu objetivo é encerrar os
achados da auditoria final e as lacunas funcionais ainda sem ticket próprio,
sem antecipar o Marco 3.

### COR-M2-01 — Revogação de autorizações
**Entrega verificável:** capacidades pontuais guardam o ID estável do
Administrador autorizador e são revogadas quando o usuário invalidado for o
solicitante ou o autorizador. Emissão, consumo e revogação devem permanecer
protegidos contra concorrência, sem persistir capacidades nem elevar a sessão
Caixa.
**Status:** concluída em 06/11/2026, com regressão de recuperação administrativa,
isolamento entre autorizadores, concorrência e consumo único; suíte completa com
966 testes aprovados.

### COR-M2-02 — Reconciliação de cancelamento com resultado incerto
**Entrega verificável:** distinguir falha confirmada de resultado ambíguo no
cancelamento e reconciliar o estado persistido antes de comunicar o resultado.
**Status:** concluída em 06/11/2026, sem alteração de schema. Falha anterior ao
commit e venda `ATIVA` após reconciliação são falhas confirmadas; venda
`CANCELADA` ou consulta indisponível permanecem resultado incerto por ausência
de identificador persistente da tentativa. A interface não repete o
cancelamento nem reutiliza a autorização. Suíte completa com 973 testes
aprovados.

### Pendência operacional — recuperação de UUID após encerramento
Definir procedimento para recuperar ou reconciliar o identificador de uma
tentativa de fechamento cujo resultado permaneceu incerto após o processo ser
encerrado. Avaliar a solução junto ao protocolo de contingência do T54, sem
antecipar persistência do carrinho.

### COMP-M2 — Complementos funcionais

Executar na ordem aprovada **COMP-M2-01 → 02 → 03 → 04 → 06 → 05**, sem
antecipar o Marco 3.

#### COMP-M2-01 — Melhorias no diálogo de pagamentos
**Entrega verificável:** persistir visualmente a divisão sugerida, preencher as
parcelas seguintes sem sobrescrever entrada manual, preservar valores ao trocar
modalidade e separar Adicionar de Concluir pagamentos por `Ctrl+Enter`.
**Status:** concluído em 06/11/2026. Seis novos testes cobrem persistência da
sugestão, parcelas seguintes, entrada manual, modalidade, edição/remoção e
atalhos; suíte completa com 979 testes aprovados.

#### COMP-M2-02 — Consulta gráfica do histórico de preços
**Entrega verificável:** apresentar a trilha já persistida pelo T44, com janela
inicial dos últimos 12 meses, sem alterar retenção nem preços históricos.

#### COMP-M2-03 — Categorias personalizáveis
**Entrega verificável:** substituir a categoria apenas textual pelo contrato
administrável aprovado, com migração e preservação dos produtos existentes.

#### COMP-M2-04 — Redefinição de senha de conta Caixa
**Entrega verificável:** permitir ao Administrador redefinir a senha individual
de Caixa, revogando sessões e capacidades da identidade sem criar senha padrão.

#### COMP-M2-06 — Revisão de layout e produtividade
**Entrega verificável:** revisar o layout integrado e os fluxos operacionais já
concluídos, sem introduzir novas regras comerciais.

#### COMP-M2-05 — Homologação e auditoria final do Marco 2
**Entrega verificável:** repetir a homologação manual, suíte completa e auditoria
final após todas as correções e complementos, antes de autorizar o T49.

## Marco 3 — Produção e confiabilidade (T49–T62)

### T49 — Log estruturado
**Origem:** backlog original T38.
**Entrega verificável:** Registros locais, rotação e mensagens de erro; sem segredos.
**Conceito a estudar:** Observabilidade.

### T50 — Informações de versão
**Origem:** backlog original T39.
**Entrega verificável:** Versão/commit no Sobre e diagnóstico.
**Conceito a estudar:** Build metadata.

### T51 — Exportação de diagnóstico
**Origem:** backlog original T40.
**Entrega verificável:** Pacote técnico limitado, com revisão de dados sensíveis.
**Conceito a estudar:** Suporte.

### T52 — Catálogo em memória
**Origem:** backlog original T41.
**Entrega verificável:** Cache essencial para leitura em banco degradado.
**Conceito a estudar:** Cache, consistência.

### T53 — Modo cálculo
**Origem:** backlog original T42.
**Entrega verificável:** Operar sem gravação quando for seguro; status explícito.
**Conceito a estudar:** Degradação graciosa.

### T54 — Protocolo de contingência
**Origem:** backlog original T43.
**Entrega verificável:** Resumo, alerta, confirmação e liberação sem falsa persistência.
**Conceito a estudar:** Recuperação operacional.

### T55 — Backup SQLite local
**Origem:** backlog original T44.
**Entrega verificável:** Cópia consistente, integridade e retenção local.
**Conceito a estudar:** Backup API.

### T56 — Backup externo
**Origem:** backlog original T45.
**Entrega verificável:** Destino externo, agendamento 2h, falhas e alertas.
**Conceito a estudar:** Tolerância a falhas.

### T57 — Restauração assistida
**Origem:** backlog original T46.
**Entrega verificável:** Autorização e validação de recuperação com base de teste.
**Conceito a estudar:** Recovery.

### T58 — Migrações versionadas
**Origem:** backlog original T47.
**Entrega verificável:** Roteiro de migração e recusa segura de esquema incompatível.
**Conceito a estudar:** Schema evolution.

### T59 — Empacotamento Windows
**Origem:** backlog original T48.
**Entrega verificável:** Criar distribuição com dependências, sem dados embarcados.
**Conceito a estudar:** Build/release.

### T60 — Instalador atualizável
**Origem:** backlog original T49.
**Entrega verificável:** Instalar/atualizar mantendo banco e configurações.
**Conceito a estudar:** Distribuição.

### T61 — Teste de performance
**Origem:** backlog original T50.
**Entrega verificável:** Medições repetidas, limites e gargalos no hardware real.
**Conceito a estudar:** Benchmark.

### T62 — Validação operacional
**Origem:** backlog original T51.
**Entrega verificável:** Scanner, pagamentos simulados, falhas, backups e checklist release.
**Conceito a estudar:** Aceitação e regressão.

## Pendências de planejamento posterior

### Revisão de layout e usabilidade operacional do PDV

Executar após a implementação e validação do fluxo completo de vendas, antes do
acabamento visual definitivo.

**Escopo:** revisar a distribuição da tela, reduzir espaçamentos excessivos,
avaliar o posicionamento e o destaque do total, melhorar a legibilidade da
tabela, a hierarquia das informações e a produtividade no uso por teclado e
mouse. Esta pendência não autoriza mudanças visuais antes dessa etapa.

### Revisão funcional e de usabilidade do diálogo de pagamentos

Comportamentos funcionais concluídos no COMP-M2-01. Refinamento visual amplo
permanece reservado ao COMP-M2-06.

**Separação entre Adicionar e Concluir:** Enter adiciona o pagamento ou
confirma a edição; zerar o saldo não fecha automaticamente o diálogo; concluir
exige botão ou atalho independente e explícito. Mesmo com saldo zero, permitir
revisar, editar e remover pagamentos.

O Enter usado para adicionar o último pagamento não conclui o diálogo. O
COMP-M2-01 adotou `Ctrl+Enter` como atalho explícito e independente para
Concluir pagamentos, mantendo separadas as ações Adicionar, Concluir pagamentos
e Confirmar venda.

**Preservação do valor informado:** alterar a modalidade entre Dinheiro,
Crédito, Débito e Pix não substitui o valor escolhido pelo operador. Sugerir o
saldo restante somente ao iniciar uma nova entrada, sem sobrescrever valores
já definidos.

**Persistência da divisão sugerida:** manter as parcelas sugeridas visíveis
durante os lançamentos, identificar as utilizadas e exibir as ainda disponíveis.
Não apagar a sugestão a cada pagamento nem exigir nova divisão pela quantidade
restante. Permitir refazer ou limpar a divisão por ação expressa e, após edições
manuais, manter consistência com o saldo real.

## Regras de acompanhamento daqui em diante

- O próximo ticket executável é **COMP-M2-02**. Seguir depois 03, 04, 06 e 05;
  T49 inicia somente após essas entregas, homologação e auditoria final da
  Consolidação do Marco 2.
- Antes de elaborar cada prompt Codex, conferir **este arquivo**, o relatório do último ticket e eventuais dependências já resolvidas. Não redefinir informalmente o objetivo numerado.
- Marcar como concluído somente após relatório, testes e revisão. Mantenha os títulos e origens dos tickets para rastreabilidade.
- Se um ticket estiver parcialmente pronto, implementar somente o restante e incluir testes de regressão; não duplicar código.
- Se for indispensável subdividir um ticket, atualizar este backlog **antes** de implementar, com a aprovação do usuário, realocando os tickets seguintes sem reaproveitar número já executado.
- Marcos 2/3 mantêm os objetivos do planejamento original e são apenas renumerados. Nenhuma funcionalidade fiscal está autorizada.
- Considerar antecipação de tarefas de segurança de migração e backup quando houver risco concreto, mediante aprovação antes da mudança na ordem.
