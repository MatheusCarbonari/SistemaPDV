# Backlog de implementação — tickets pequenos

**Status:** apenas planejamento. Nenhum ticket desta sequência está marcado como executado.

Cada ticket deve gerar uma alteração pequena, revisão fácil e testes apropriados. Se ultrapassar uma responsabilidade, subdividir antes de implementar. Os identificadores evitam T13 por convenção; isso não implica ticket ausente.

## Critério de conclusão padrão

- Escopo realizado sem mudanças laterais.
- Conceito técnico explicado antes do prompt de implementação.
- Testes específicos e regressão relevante executados em ambiente seguro.
- Código e documentação consistentes; arquivos modificados revisados.
- Relatório de mudanças, testes e riscos; aprovação do usuário para avançar.

## Marco 1 — Núcleo de leitura e cálculo

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

### T08 — Catálogo de etiquetas reais
**Entrega verificável:** Testes parametrizados com amostras autorizadas, incluindo unidades e códigos ruins.
**Conceito a estudar:** Testes de tabela.

### T09 — Modelo de item em memória
**Entrega verificável:** Definir dados históricos, origem e estimativas sem GUI.
**Conceito a estudar:** Objetos de domínio, snapshot.

### T10 — Inclusão de linha
**Entrega verificável:** Adicionar etiquetas separadamente; teste com mesmo produto repetido.
**Conceito a estudar:** Estado em memória.

### T11 — Totalização
**Entrega verificável:** Soma exata e políticas de arredondamento testadas.
**Conceito a estudar:** Centavos, Decimal.

### T12 — Remover e desfazer
**Entrega verificável:** Remoção por identificador de linha e undo único.
**Conceito a estudar:** Comandos reversíveis.

### T14 — Entrada manual por unidade
**Entrega verificável:** Quantidade em diálogo lógico; subtotal apropriado.
**Conceito a estudar:** Regras de negócio.

### T15 — Entrada manual por peso
**Entrega verificável:** Último campo editado define recálculo; registrar peso informado vs estimado.
**Conceito a estudar:** Eventos, arredondamento.

### T16 — Diversos
**Entrega verificável:** Atalho 9999, descrição fixa, valor sem produto associado.
**Conceito a estudar:** Representação opcional.

### T17 — Janela PySide6 mínima
**Entrega verificável:** Criar janela/shell e campo de leitura, sem lógica comercial na GUI.
**Conceito a estudar:** Qt Widgets, sinais/slots.

### T18 — Entrada e atalhos
**Entrega verificável:** Enter/Esc, diálogos contextuais e restauração do foco.
**Conceito a estudar:** Eventos Qt, pytest-qt.

### T19 — Lista de itens
**Entrega verificável:** Exibir linhas, subtotais, estimativas e remoção; conferir interface.
**Conceito a estudar:** MVC/MVP pragmaticamente.

### T20 — Medição de leitura
**Entrega verificável:** Instrumentar latência e testar leitor físico e repetição.
**Conceito a estudar:** Profiling, métricas.

## Marco 2 — Operação comercial

### T21 — Esquema de vendas
**Entrega verificável:** Criar tabela vendas e migração testada.
**Conceito a estudar:** Modelagem relacional, migration.

### T22 — Esquema de itens
**Entrega verificável:** Criar itens_venda, snapshot e FK opcional de produto.
**Conceito a estudar:** Foreign keys, integridade.

### T23 — Esquema de pagamentos
**Entrega verificável:** Criar pagamentos 1:N e restrições.
**Conceito a estudar:** Cardinalidade relacional.

### T24 — Regras de pagamentos
**Entrega verificável:** Modalidades repetíveis, saldo restante e valores válidos.
**Conceito a estudar:** Invariantes, centavos.

### T25 — Divisão igual
**Entrega verificável:** Parcelas matematicamente exatas em centavos; testes.
**Conceito a estudar:** Divisão inteira, resto.

### T26 — Tela de pagamentos
**Entrega verificável:** Diálogo para registros de pagamento; sem SQL na GUI.
**Conceito a estudar:** Sinais, estado de formulário.

### T27 — Confirmação de venda
**Entrega verificável:** Resumo Enter/Esc e bloqueio de duplo comando.
**Conceito a estudar:** Fluxo, estado.

### T28 — Persistência atômica
**Entrega verificável:** Gravar venda, itens, pagamentos numa transação; rollback em falhas.
**Conceito a estudar:** ACID, transação.

### T29 — Idempotência do fechamento
**Entrega verificável:** Identificador por tentativa e verificação de commit incerto.
**Conceito a estudar:** Idempotência.

### T30 — Histórico de vendas
**Entrega verificável:** Consulta por ID/data e lista com uma linha por venda.
**Conceito a estudar:** Consultas, índices.

### T31 — Detalhes da venda
**Entrega verificável:** Exibir snapshots e pagamentos sem depender de preço atual.
**Conceito a estudar:** Read model.

### T32 — Cancelamento integral
**Entrega verificável:** Status, motivo, data, autorização e testes; sem apagar original.
**Conceito a estudar:** Máquina de estados.

### T33 — Histórico de preços
**Entrega verificável:** Atualizar preço e registrar mudança em transação única; tela 12 meses depois.
**Conceito a estudar:** Auditoria de alterações.

### T34 — Primeiro acesso
**Entrega verificável:** Criar administrador e hash seguro sem senha universal.
**Conceito a estudar:** Autenticação.

### T35 — Conta Caixa
**Entrega verificável:** Login e escopo operacional do Caixa.
**Conceito a estudar:** Sessão, perfis.

### T36 — Autorização pontual
**Entrega verificável:** Senha de admin só para ação crítica; não elevar sessão.
**Conceito a estudar:** Autorização.

### T37 — Recuperação offline
**Entrega verificável:** Códigos únicos hash, consumo e rotação testados.
**Conceito a estudar:** Segredos, recuperação.

## Marco 3 — Produção e confiabilidade

### T38 — Log estruturado
**Entrega verificável:** Registros locais, rotação e mensagens de erro; sem segredos.
**Conceito a estudar:** Observabilidade.

### T39 — Informações de versão
**Entrega verificável:** Versão/commit no Sobre e diagnóstico.
**Conceito a estudar:** Build metadata.

### T40 — Exportação de diagnóstico
**Entrega verificável:** Pacote técnico limitado, com revisão de dados sensíveis.
**Conceito a estudar:** Suporte.

### T41 — Catálogo em memória
**Entrega verificável:** Cache essencial para leitura em banco degradado.
**Conceito a estudar:** Cache, consistência.

### T42 — Modo cálculo
**Entrega verificável:** Operar sem gravação quando for seguro; status explícito.
**Conceito a estudar:** Degradação graciosa.

### T43 — Protocolo de contingência
**Entrega verificável:** Resumo, alerta, confirmação e liberação sem falsa persistência.
**Conceito a estudar:** Recuperação operacional.

### T44 — Backup SQLite local
**Entrega verificável:** Cópia consistente, integridade e retenção local.
**Conceito a estudar:** Backup API.

### T45 — Backup externo
**Entrega verificável:** Destino externo, agendamento 2h, falhas e alertas.
**Conceito a estudar:** Tolerância a falhas.

### T46 — Restauração assistida
**Entrega verificável:** Autorização e validação de recuperação com base de teste.
**Conceito a estudar:** Recovery.

### T47 — Migrações versionadas
**Entrega verificável:** Roteiro de migração e recusa segura de esquema incompatível.
**Conceito a estudar:** Schema evolution.

### T48 — Empacotamento Windows
**Entrega verificável:** Criar distribuição com dependências, sem dados embarcados.
**Conceito a estudar:** Build/release.

### T49 — Instalador atualizável
**Entrega verificável:** Instalar/atualizar mantendo banco e configurações.
**Conceito a estudar:** Distribuição.

### T50 — Teste de performance
**Entrega verificável:** Medições repetidas, limites e gargalos no hardware real.
**Conceito a estudar:** Benchmark.

### T51 — Validação operacional
**Entrega verificável:** Scanner, pagamentos simulados, falhas, backups e checklist release.
**Conceito a estudar:** Aceitação e regressão.

## Observações de sequenciamento

- A execução começa pelo T01. Refazer a ordem dos demais tickets após a auditoria, se o código existente tornar alguma tarefa desnecessária.
- Alguns tickets ainda contêm interface ou persistência; se ficarem grandes na prática, subdividir antes de enviar ao Codex.
- Não executar tickets do Marco 3 só no fim se forem necessários para segurança de migração em marcos anteriores.
- Nenhuma funcionalidade fiscal está autorizada neste backlog.
