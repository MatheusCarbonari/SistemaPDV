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

### T44 — Histórico de preços
**Origem:** backlog original T33.
**Entrega verificável:** Atualizar preço e registrar mudança em transação única; tela 12 meses depois.
**Conceito a estudar:** Auditoria de alterações.

### T45 — Primeiro acesso
**Origem:** backlog original T34.
**Entrega verificável:** Criar administrador e hash seguro sem senha universal.
**Conceito a estudar:** Autenticação.

### T46 — Conta Caixa
**Origem:** backlog original T35.
**Entrega verificável:** Login e escopo operacional do Caixa.
**Conceito a estudar:** Sessão, perfis.

### T47 — Autorização pontual
**Origem:** backlog original T36.
**Entrega verificável:** Senha de admin só para ação crítica; não elevar sessão.
**Conceito a estudar:** Autorização.

### T48 — Recuperação offline
**Origem:** backlog original T37.
**Entrega verificável:** Códigos únicos hash, consumo e rotação testados.
**Conceito a estudar:** Segredos, recuperação.

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

## Regras de acompanhamento daqui em diante

- O próximo ticket executável é **T21**; depois T22, T23 etc. Sem retroceder à numeração original.
- Antes de elaborar cada prompt Codex, conferir **este arquivo**, o relatório do último ticket e eventuais dependências já resolvidas. Não redefinir informalmente o objetivo numerado.
- Marcar como concluído somente após relatório, testes e revisão. Mantenha os títulos e origens dos tickets para rastreabilidade.
- Se um ticket estiver parcialmente pronto, implementar somente o restante e incluir testes de regressão; não duplicar código.
- Se for indispensável subdividir um ticket, atualizar este backlog **antes** de implementar, com a aprovação do usuário, realocando os tickets seguintes sem reaproveitar número já executado.
- Marcos 2/3 mantêm os objetivos do planejamento original e são apenas renumerados. Nenhuma funcionalidade fiscal está autorizada.
- Considerar antecipação de tarefas de segurança de migração e backup quando houver risco concreto, mediante aprovação antes da mudança na ordem.
