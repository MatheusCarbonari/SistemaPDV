# Backlog de implementação — Sistema-PDV (sequência consolidada)

**Revisão:** 02/11/2026 — versão oficial que substituiu o backlog histórico preservado em `docs/historico/TICKETS.md`.

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

**Status do marco:** **CONCLUÍDO em 10/11/2026.** O responsável confirmou a
homologação manual final com 13/13 cenários aprovados, incluindo a Revisão Visual
01–05 e as Correções Finais 01/02. O Codex verificou diretamente a suíte com
1.078 testes e a migração v9→v10 em banco temporário isolado. O encerramento do
marco não representa prontidão para produção nem homologação no equipamento do
cliente; essas dependências permanecem no Marco 3.

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
**Consulta gráfica concluída no COMP-M2-02:** janela inicial dos últimos 12
meses, com acesso expresso ao histórico integral, sem expurgo de registros mais
antigos. O T44 não possui coluna de responsável e a interface informa essa
ausência sem fabricar identidade histórica.
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
**Perfis:** Caixa opera Frente de Caixa, pagamentos, confirmação, Histórico e
consulta de Produtos. Cadastro e edição de Produtos pelo Caixa exigem capacidade
pontual vinculada aos dados aprovados; situação, categorias e histórico de
preços permanecem administrativos. Administrador executa essas operações
diretamente e pode provisionar Caixa pelo serviço protegido.

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
sessões e capacidades processuais do operador. “Trocar operador” reutiliza o
diálogo de login e preserva a sessão atual durante a tentativa; somente uma nova
autenticação confirmada invalida a sessão anterior e suas capacidades. A troca
é bloqueada quando houver itens, pagamentos, confirmação ou fechamento pendente;
commit incerto também bloqueia navegação e encerramento. Fechar a janela invalida
a sessão e não pode descartar atendimento aberto. INT-E encerra as integrações
funcionais previstas antes da homologação manual do Marco 2.

## Consolidação do Marco 2

Esta fase ocorre após a INT-E e antes do T49. Seu objetivo é encerrar os
achados da auditoria final e as lacunas funcionais ainda sem ticket próprio,
sem antecipar o Marco 3.

### Correção Final 01 — Troca de Operador
**Entrega verificável:** cancelar a autenticação do próximo operador retorna ao
PDV sem encerrar a aplicação nem invalidar a sessão anterior. Botão Cancelar,
`Esc` e fechamento pelo `X` possuem o mesmo comportamento. Em troca confirmada,
a nova sessão é revalidada antes de substituir a atual; em seguida, a sessão
anterior e suas capacidades são invalidadas e as permissões das páginas são
atualizadas conforme o novo perfil. Atendimento em andamento e fechamento
incerto continuam bloqueando a abertura do fluxo. O primeiro login permanece
distinto: cancelá-lo encerra normalmente quando não existe sessão a restaurar.
**Status:** concluída e validada por regressão automatizada. Cancelar por botão,
`Esc` ou `X` preserva a sessão anterior; troca confirmada instala a nova sessão
antes de invalidar a antiga e suas capacidades.

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
**Status:** concluído em 06/11/2026. A página Produtos abre consulta somente
leitura para o produto selecionado, protegida por sessão Administrador. O
diálogo exibe instante local de São Paulo e preços anterior/novo, ordenados do
mais recente, com alternância expressa entre 12 meses e todo o histórico. A
consulta admite inativos, preserva filtros e seleção e não grava no banco.

#### COMP-M2-03 — Categorias personalizáveis
**Entrega verificável:** substituir a categoria apenas textual pelo contrato
administrável aprovado, com migração e preservação dos produtos existentes.
**Status:** concluído em 06/11/2026. O esquema versão 10 introduz `categorias`
com ID estável, nome, chave Unicode normalizada e situação, e substitui a coluna
textual de `produtos` por `categoria_id`. A migração preserva IDs e atributos dos
produtos, referências comerciais e histórico de preços; categorias legadas
equivalentes são consolidadas e valores vazios ou apenas numéricos ficam
inativos para tratamento administrativo. Administradores podem cadastrar,
renomear, ativar e desativar categorias; não há exclusão física. Os formulários
de Produtos usam seleção fechada e revalidam a categoria ativa na gravação.
Suíte completa aprovada com 1004 testes.

#### COMP-M2-04 — Redefinição de senha de conta Caixa
**Entrega verificável:** permitir ao Administrador redefinir a senha individual
de Caixa, revogando sessões e capacidades da identidade sem criar senha padrão.
**Status:** concluído em 06/11/2026. A página Administração abre diálogo
dedicado para nova senha e confirmação, reutiliza a política e o hash vigentes
e preserva contas inativas. O serviço revalida Administrador e alvo Caixa,
confirma a atualização transacional e revoga sessões e capacidades do operador.
Login, emissão de capacidade e troca de credencial são serializados no processo;
a coordenação não se estende a outro processo da aplicação.

#### COMP-M2-06 — Produtos com autorização administrativa
**Entrega verificável:** permitir consulta de Produtos pelo Caixa e exigir
capacidade administrativa de uso único, vinculada ao comando e ao estado-base,
para cada cadastro ou edição.
**Status:** concluído em 06/11/2026, sem alteração de schema. Comandos imutáveis
e normalizados geram SHA-256 canônico; o T47 vincula sessão, operação, recurso e
hash, preservando integralmente o cancelamento de vendas. Serviços públicos de
gravação exigem Administrador válido ou Caixa com capacidade correspondente.
Edições comparam produto e categoria sob `BEGIN IMMEDIATE`, e o histórico de
preços permanece na mesma transação. Situação, categorias e histórico de preços
continuam exclusivos do Administrador. A suíte completa foi aprovada com 1018
testes.

#### COMP-M2-05 — Revisão visual e produtividade
**Entrega verificável:** revisar layout, dimensões, espaçamentos, legibilidade,
fluxos por teclado e produtividade das páginas e diálogos integrados, incluindo
o diálogo de pagamentos, sem alterar regras comerciais. Ao final, repetir a
homologação manual, suíte completa e auditoria do Marco 2 antes do T49.
**Status funcional e visual:** implementação concluída pelos Visuais 01 a 05 e
respectivos ajustes. A suíte final possui 1.078 testes aprovados pelo Codex. O
responsável confirmou a homologação manual final com 13/13 cenários e aprovou a
Revisão Visual 01–05. O COMP-M2-05 está concluído; isso não antecipa o Marco 3.
**Andamento — Visual 01, Frente de Caixa:** reorganização visual iniciada sem
novo identificador de ticket. O leitor de códigos foi compactado, retorno da
última operação recebeu distinção entre sucesso, alerta e erro, a tabela passou
a priorizar a descrição do produto e o rodapé separa ações secundárias, total e
ações comerciais. Permanecem pendentes as demais telas, os diálogos — inclusive
Pagamentos —, a homologação manual final e a auditoria de encerramento do
COMP-M2-05. O Visual 01 foi validado com 1022 testes automatizados.
**Ajuste — Visual 01.1:** a Frente de Caixa adotou paleta escura explícita e
localizada para harmonizar com o shell no tema escuro do Windows. Leitor,
mensagens, tabela, seleção, botões e total possuem cores independentes da
paleta automática; o título interno duplicado foi removido. As proporções e a
hierarquia aprovadas no Visual 01 foram preservadas. Este ajuste não inicia o
Visual 02 nem conclui o COMP-M2-05. O Visual 01.1 foi validado com 1025 testes
automatizados.
**Refino — Visual 01.2:** barra superior e Frente de Caixa compartilham a mesma
cor de fundo escura; navegação, identificação e ações de sessão usam a mesma
linguagem dos botões inferiores, com estados normal, ativo, hover e desabilitado
explícitos. Leitor e retorno operacional passam a ocupar a mesma faixa
horizontal, preservando foco, scanner, mensagens e o restante do layout. Este
refino encerra apenas o Visual 01 e não inicia o Visual 02. O Visual 01.2 foi
validado com 1026 testes automatizados.
**Correção — Visual 01.3:** os quatro botões de navegação reservam largura pela
métrica da fonte selecionada em negrito, com altura e folga lateral constantes
entre os estados normal, selecionado, hover e desabilitado. Cores, bordas e
arredondamento aprovados no Visual 01.2 permanecem inalterados. O ajuste foi
validado com 69 testes pertinentes e renderizações nas escalas 100% e 125%.
**Andamento — Visual 02, Pagamentos:** o diálogo foi ampliado, tornou-se
redimensionável e adotou a paleta escura da Frente de Caixa, com conteúdo
vertical rolável e ações finais sempre acessíveis. Resumo financeiro, lançamento,
pagamentos registrados, sugestão de divisão e conclusão possuem áreas distintas.
A última divisão apresenta separadamente a base calculada — que pode diferir do
total original —, quantidade, valores e situação de cada parcela; alterações
manuais preservam essa referência como desatualizada e interrompem o
preenchimento automático até nova solicitação expressa. `Enter`, `Ctrl+Enter`,
edição, remoção, foco e regras comerciais do COMP-M2-01 foram preservados. O
Visual 02 foi validado com 1033 testes automatizados, renderizações em 900×700 e
640×480 e simulação automatizada de fonte a 125%. Esta etapa não inicia o Visual
03 nem conclui isoladamente o COMP-M2-05.
**Refino — Visual 02.1, Reorganização de Pagamentos:** abaixo dos cartões do
resumo, lançamento e divisão passam a ocupar a coluna esquerda, enquanto os
pagamentos registrados e suas ações ocupam a direita. As modalidades são quatro
botões sempre visíveis e de seleção exclusiva; o título do bloco informa quando
um lançamento está em edição. A tabela de pagamentos reserva proporções iguais
para modalidade e valor, com dinheiro alinhado à direita, e a divisão organiza
base, quantidade e situação em linhas curtas, mantendo parcelas e estados em
tabela própria. Em 900×700 e 1024×720 não há rolagem; abaixo de 760 px as colunas
são empilhadas e o conteúdo usa somente rolagem vertical. O refino preserva os
atalhos e contratos do COMP-M2-01, não implementa F1–F4 e não inicia o Visual 03.
O Visual 02.1 foi validado com 1036 testes automatizados, incluindo 46 testes
focados de pagamentos e confirmação, e simulação de fonte a 125%.
**Andamento — Visual 03, Histórico de Vendas:** a página adotou a paleta escura
da Frente de Caixa e separa consulta, lista e detalhe em blocos proporcionais.
A lista apresenta `Venda nº N`, preservando o ID interno em dados da linha, com
data/hora completa, total alinhado à direita e situação compacta e diferenciada.
Os itens exibem como colunas principais descrição, quantidade ou peso, preço de
referência e subtotal; posição, tipo, código, forma de venda, origem, origem da
quantidade e código de barras permanecem disponíveis no painel técnico do item
selecionado. Pagamentos usam colunas equilibradas e valores à direita, enquanto
situação, motivo, data e autorizador do cancelamento ocupam uma área contextual
com ação proporcional. Em 1024×720 e 1280×800 a página usa duas colunas sem
rolagem; em larguras menores, filtros e detalhes são empilhados com rolagem
vertical e sem rolagem horizontal. Consultas, snapshots, ordem, autorizações e
tratamento de resultado incerto foram preservados. O Visual 03 foi validado com
1040 testes automatizados e não inicia os Visuais 04 ou 05.
**Refino — Visual 03.1, Histórico e Cancelamento:** a consulta reserva espaço
próprio para o seletor do campo de data e mantém os quatro campos da lista de
vendas compactos, inclusive a data/hora completa sem ocupar a largura restante.
O Histórico remove da apresentação o painel técnico do item, sem alterar os
dados persistidos, modelos ou serviços. Pagamentos repetidos continuam em linhas
independentes, agora numeradas para apresentação, com mais linhas visíveis e
rolagem vertical destacada quando necessária. O diálogo de solicitação foi
reduzido ao resumo da venda, quantidades de itens e pagamentos, motivo obrigatório
e aviso de dependência da autorização administrativa; as tabelas redundantes
foram retiradas somente desse diálogo. O bloco de situação e cancelamento, o
fluxo de capacidade administrativa e o tratamento de resultado incerto foram
preservados. Esta etapa não inicia o Visual 04 nem altera regras comerciais.
O Visual 03.1 foi validado com 1043 testes automatizados.
**Refino — Visual 03.2, Reorganização do Histórico:** consulta e resumo compacto
permanecem no topo; abaixo, Vendas encontradas ocupa a coluna esquerda e
Pagamentos originais, seguido de Situação e cancelamento, ocupa a coluna direita,
com larguras equivalentes. Produtos e itens vendidos passa a ocupar toda a faixa
inferior. As colunas de vendas e itens são recalculadas proporcionalmente ao
espaço disponível, priorizando a data/hora completa na lista e a descrição nos
itens. Quantidades maiores usam rolagem dentro das tabelas, sem ampliar a página.
Em 1024×720 e 1280×800, conteúdo moderado permanece visível sem rolagem geral;
abaixo de 850 px, vendas, informações operacionais e produtos são empilhados com
rolagem vertical. O campo de data abre o calendário ao ser clicado e mantém área
reservada para o seletor. Tema, diálogo de cancelamento, autorizações, snapshots e
regras comerciais foram preservados. Esta etapa não inicia o Visual 04.
O Visual 03.2 foi validado com 1045 testes automatizados.
**Andamento — Visual 04, Produtos e Administração:** Produtos adota filtros e
ações responsivos, tabela com proporções explícitas que priorizam nome e
categoria e valores monetários alinhados à direita. O cadastro e a edição foram
separados em Identificação e Classificação e venda, com campos limitados pelo
conteúdo e indicação clara de novo produto ou edição. Categorias e Histórico de
preços receberam janelas proporcionais, tabelas equilibradas, controles compactos
e tema escuro explícito. Administração foi organizada nos blocos Operadores
cadastrados e Cadastrar operador, mantendo ações junto à lista e credenciais em
campos compactos; Redefinir senha destaca o operador e mantém botões próximos.
Em 1024×720 e 1280×800, tabelas aproveitam a largura sem rolagem horizontal; em
larguras reduzidas, filtros e ações de Produtos são redistribuídos em duas linhas.
Seleção, foco, permissões, autorizações pontuais, limpeza de senhas, categorias,
histórico de preços e bloqueios comerciais permanecem inalterados. Esta etapa não
inicia o Visual 05 nem altera schema, modelos ou serviços comerciais.
O Visual 04 foi validado com 1055 testes automatizados, incluindo páginas em
1024×720, 1280×800 e dimensões reduzidas.
**Ajuste — Visual 04.1, Diálogos de Produtos:** cadastro e edição preservam o
tamanho geral, mas passam a usar campos menores e uma grade de duas linhas em
Classificação e venda, com espaçamentos explícitos entre categoria, forma de
venda, preço e origem. Código e nome também foram compactados. A confirmação de
ativação ou desativação mantém a mesma decisão comercial em um diálogo simples,
agora com botões `Sim` e `Não` mais largos e baixos. Página Produtos, Categorias,
Histórico de preços, permissões, autorizações e persistência permanecem
inalterados. Esta etapa não inicia o Visual 05.
O Visual 04.1 foi validado com 1058 testes automatizados.
**Refino — Visual 04.2, Formulários de Produtos e Administração:** cadastro e
edição de produtos passam a compor cada rótulo acima do respectivo controle, em
blocos independentes organizados em duas colunas. Essa composição preserva as
duas linhas comerciais — Categoria e Forma de venda; Preço e Origem — sem disputa
horizontal entre rótulos, inclusive com fonte ampliada a 125%. A confirmação de
situação deixa o `QMessageBox` padrão e utiliza diálogo compacto, sem ícone ou
áreas reservadas, com pergunta direta e botões `Sim` e `Não` lado a lado.
Administração organiza Operadores cadastrados e Cadastrar operador em colunas
equivalentes e alinhadas ao topo, com campos verticais compactos; abaixo de 850 px
os blocos são empilhados com rolagem vertical. Capturas renderizadas foram
inspecionadas em 1024×720, 1280×800 e fonte a 125%. Regras, permissões, serviços e
persistência permanecem inalterados. Esta etapa não inicia o Visual 05.
O Visual 04.2 foi validado com 1060 testes automatizados e capturas renderizadas
dos estados vazio, preenchido, confirmação, resoluções-alvo e fonte a 125%.
**Andamento — Visual 05, Diálogos e mensagens:** primeiro acesso, login,
recuperação administrativa, emissão de códigos, autorização pontual e
confirmação da venda compartilham a paleta escura, campos compactos, grupos
semânticos, ações proporcionais e mensagens corrigíveis junto ao contexto. A
autorização preserva a descrição e o hash do comando, mas organiza os dados em
linhas legíveis e destaca alterações de categoria e preço. A confirmação da
venda separa resumo financeiro e pagamentos, mantendo `Enter`, `Esc` e a
proteção contra acionamento duplicado. Mensagens operacionais simples continuam
no contexto da página; falha, sucesso e resultado incerto mantêm textos distintos,
sem afirmar um desfecho quando ele não foi comprovado. Pagamentos e Solicitar
cancelamento permanecem visualmente inalterados. Schema, serviços, contratos de
segurança e banco operacional não foram modificados. Permanece pendente criar,
em etapa futura, um ambiente isolado de homologação manual; ele não faz parte
deste Visual 05. A etapa foi validada com 1066 testes automatizados e inspeção
renderizada dos diálogos principais, inclusive com fonte simulada a 125%.

**Correção Final 02 — Alteração do código do produto:** concluída. O código
comercial pode ser alterado na edição por Administrador ou Caixa com autorização
pontual. O ID interno permanece estável; o comando autorizado vincula os códigos
anterior e novo, e a transação revalida tanto o estado-base quanto a unicidade
global, incluindo produtos inativos. O código anterior fica disponível para
reutilização e os snapshots de vendas permanecem inalterados. O formulário
apresenta o aviso operacional sobre balança e etiquetas somente quando há troca
efetiva do código. Alteração exclusiva de código não cria histórico de preço.
Não houve alteração de schema nem criação de reserva ou histórico de códigos.
A correção foi validada com 1078 testes automatizados.

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
**Pendências vinculadas do Marco 2:** recuperar ou reconciliar o UUID de
fechamento após encerramento do processo; definir o procedimento para
cancelamento com commit incerto, reconhecendo que o schema atual não identifica
de forma persistente a tentativa que produziu uma venda `CANCELADA`.

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
**Pendência vinculada do Marco 2:** definir e impor instância única da aplicação
ou introduzir coordenação entre processos para sessões, capacidades e bloqueios
de credencial antes da liberação operacional.

### T61 — Teste de performance
**Origem:** backlog original T50.
**Entrega verificável:** Medições repetidas, limites e gargalos no hardware real.
**Conceito a estudar:** Benchmark.

### T62 — Validação operacional
**Origem:** backlog original T51.
**Entrega verificável:** Scanner, pagamentos simulados, falhas, backups e checklist release.
**Conceito a estudar:** Aceitação e regressão.
**Pendências vinculadas do Marco 2:** homologar leitor físico, foco e Enter do
scanner, escala real do Windows e comportamento completo no equipamento alvo.
Preparar um ambiente durável e isolado para futuras homologações manuais, sem
usar nem apagar o banco operacional.

## Registros de usabilidade consolidados

### Melhoria não bloqueante — aviso de alteração do código do produto

O aviso operacional da Correção Final 02 está funcional e informa a necessidade
de atualizar a balança e o risco de etiquetas antigas. Permanece um pequeno
ajuste de apresentação visual para etapa futura. A melhoria não altera o comando
autorizado, a validação, a persistência ou o encerramento do Marco 2.

### Revisão de layout e usabilidade operacional do PDV

**Situação:** absorvida pelos Visuais 01 a 05 do COMP-M2-05. O texto abaixo é
preservado como origem dos critérios de revisão, não como ticket pendente.

**Escopo:** revisar a distribuição da tela, reduzir espaçamentos excessivos,
avaliar o posicionamento e o destaque do total, melhorar a legibilidade da
tabela, a hierarquia das informações e a produtividade no uso por teclado e
mouse. Esta pendência não autoriza mudanças visuais antes dessa etapa.

### Revisão funcional e de usabilidade do diálogo de pagamentos

**Situação:** comportamentos concluídos no COMP-M2-01 e refinamento executado nos
Visuais 02 e 02.1 do COMP-M2-05. O texto abaixo permanece como registro dos
critérios aprovados.

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

- O Marco 2 está formalmente concluído. COMP-M2-01 a 06, Visuais 01 a 05 e
  Correções Finais 01/02 estão implementados e aprovados no escopo do marco.
- **T49** é o próximo ticket numerado. As limitações de contingência, backups,
  restauração, empacotamento, desempenho e validação física permanecem nos
  T54–T62 e não devem ser
  antecipadas apenas para encerrar o marco.
- Antes de elaborar cada prompt Codex, conferir **este arquivo**, o relatório do último ticket e eventuais dependências já resolvidas. Não redefinir informalmente o objetivo numerado.
- Marcar como concluído somente após relatório, testes e revisão. Mantenha os títulos e origens dos tickets para rastreabilidade.
- Se um ticket estiver parcialmente pronto, implementar somente o restante e incluir testes de regressão; não duplicar código.
- Se for indispensável subdividir um ticket, atualizar este backlog **antes** de implementar, com a aprovação do usuário, realocando os tickets seguintes sem reaproveitar número já executado.
- Marcos 2/3 mantêm os objetivos do planejamento original e são apenas renumerados. Nenhuma funcionalidade fiscal está autorizada.
- Considerar antecipação de tarefas de segurança de migração e backup quando houver risco concreto, mediante aprovação antes da mudança na ordem.
