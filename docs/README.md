# Documentação do Sistema-PDV

Este diretório reúne a documentação ativa e os registros históricos do projeto. A fonte oficial do planejamento executável é o backlog renumerado; arquivos históricos não devem ser usados para redefinir tickets ou decisões vigentes.

## Documentos ativos

| Documento | Finalidade |
| --- | --- |
| [`TICKETS_RENUMERADO.md`](TICKETS_RENUMERADO.md) | Backlog oficial, estado dos Marcos 1 e 2 e planejamento do Marco 3. |
| [`DECISOES.md`](DECISOES.md) | Registro resumido das decisões aprovadas. |
| [`ARQUITETURA_ALVO.md`](ARQUITETURA_ALVO.md) | Arquitetura vigente e riscos ainda destinados ao Marco 3. |
| [`AUDITORIA_FINAL_MARCO_2_SISTEMA_PDV.md`](AUDITORIA_FINAL_MARCO_2_SISTEMA_PDV.md) | Evidências, homologação e parecer de encerramento do Marco 2. |
| [`ESCOPO.md`](ESCOPO.md) | Objetivos, limites e exclusões da V1. |
| [`REVISOES.md`](REVISOES.md) | Revisões de arquitetura e regras operacionais aprovadas. |
| [`CATALOGO_ETIQUETAS_REAIS.md`](CATALOGO_ETIQUETAS_REAIS.md) | Evidências disponíveis e pendências para etiquetas e scanner. |

Para uma visão pública e instruções de instalação, consulte o [`README.md` da raiz](../README.md).

## Documentos históricos

`historico/` preserva auditorias intermediárias, o inventário inicial, revisões de tickets concluídos e o backlog de numeração anterior. Esses arquivos mantêm rastreabilidade, mas podem descrever estados já superados.

| Documento | Contexto histórico |
| --- | --- |
| [`historico/ALTERACOES_DOCUMENTACAO.md`](historico/ALTERACOES_DOCUMENTACAO.md) | Organização inicial do pacote recebido. |
| [`historico/ESTADO_ATUAL.md`](historico/ESTADO_ATUAL.md) | Inventário preliminar anterior à implementação dos marcos. |
| [`historico/TICKETS.md`](historico/TICKETS.md) | Backlog com numeração anterior, substituído pelo backlog oficial. |
| [`historico/RELATORIO_AUDITORIA_SISTEMA_PDV_MARCO_1_5.md`](historico/RELATORIO_AUDITORIA_SISTEMA_PDV_MARCO_1_5.md) | Auditoria de encerramento do Marco 1.5. |
| [`historico/AUDITORIA_MODELO_ITEM_T22.md`](historico/AUDITORIA_MODELO_ITEM_T22.md) | Auditoria intermediária do modelo de item. |
| [`historico/REVISAO_IDENTIFICACAO_LINHAS_T24.md`](historico/REVISAO_IDENTIFICACAO_LINHAS_T24.md) | Decisão técnica aplicada no T24. |
| [`historico/AUDITORIA_LACUNAS_GRAFICAS_SISTEMA_PDV_T43.md`](historico/AUDITORIA_LACUNAS_GRAFICAS_SISTEMA_PDV_T43.md) | Lacunas gráficas observadas após o T43 e resoluções posteriores. |

`legado/` preserva documentação técnica recebida do projeto anterior. Ela serve apenas como referência histórica e não substitui os contratos ativos.

- [`legado/ARQUITETURA.md`](legado/ARQUITETURA.md)
- [`legado/REGRAS_BANCO_DADOS.md`](legado/REGRAS_BANCO_DADOS.md)
- [`legado/REGRAS_NEGOCIO.md`](legado/REGRAS_NEGOCIO.md)

## Regra de leitura

Em caso de divergência, prevalecem as decisões mais recentes registradas em `DECISOES.md`, o backlog `TICKETS_RENUMERADO.md`, a arquitetura-alvo e a auditoria final. Planejamento do Marco 3 não deve ser tratado como funcionalidade já implementada.
