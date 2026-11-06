# Sistema-PDV — Auditoria técnica do Marco 2

**Referência:** `SistemaPDV-Marco2.zip` enviado em 06/11/2026.  
**Método:** inspeção estática dos módulos, documentos ativos e testes; extração isolada apenas de arquivos de código/documentação; execução de pytest sem PySide6; reprodução isolada de um cenário de revogação de autorização em banco SQLite temporário. Nenhum arquivo do projeto original foi modificado.

**Atualização de 06/11/2026:** COR-M2-01 e COR-M2-02 foram aplicadas no
repositório de desenvolvimento e validadas pela suíte completa. O P2 de
cancelamento incerto foi corrigido; os demais achados P2 e P3 abaixo permanecem
pendentes.

## Síntese

**Parecer atualizado:** Marco 2 aprovado na homologação funcional manual
informada pelo responsável (27/27 cenários), com a falha P1 de revogação
corrigida pela COR-M2-01, mas **ainda não recomendado para encerramento técnico
definitivo** antes da revisão dos riscos operacionais P2 e das demais entregas
da Consolidação do Marco 2. Não equivale à certificação de segurança para
produção.

- **730 testes aprovados** nesta auditoria em 30 arquivos de testes sem dependência gráfica (Python 3.13.5, pytest 9.0.2). Não foram executados os arquivos que importam PySide6, que não está disponível no ambiente. A tentativa inicial de suite ampla deu erros de *coleta* por falta da biblioteca, não por falhas lógicas verificadas.
- **961 testes aprovados** são o último resultado relatado pelo Codex no ambiente Windows do usuário; não foram independentemente repetidos por completo nesta auditoria.
- **966 testes aprovados** em 06/11/2026 no ambiente Windows do usuário após a
  COR-M2-01, incluindo T47, T48, INT-D2 e os novos cenários de revogação.
- **973 testes aprovados** em 06/11/2026 no ambiente Windows do usuário após a
  COR-M2-02, incluindo sucesso, falha confirmada, resultado incerto,
  concorrência e integração gráfica.
- O ZIP contém `data/sistema_acougue.db` e **dois backups pré-migração**. Esses arquivos não foram abertos ou usados nos testes. Como podem conter vendas, usuários e hashes, devem ser excluídos de futuros pacotes de revisão, salvo pedido específico de auditoria dos próprios dados.
- Requisitos encontrados no `requirements.txt`: PySide6, pytest, pytest-qt, tzdata.

## Achados por prioridade

### P1 — Revogação incompleta das autorizações emitidas pelo administrador (corrigido pela COR-M2-01)

**Código:** `services/autorizacao_pontual_service.py`, `_EstadoAutorizacao`, `GerenciadorAutorizacoesPontuais.emitir`, `consumir` e `invalidar_usuario`; `services/recuperacao_acesso_service.py`, `recuperar_acesso_administrativo`.

O estado de cada capacidade guarda a identidade do administrador que **autorizou**, mas `invalidar_usuario(usuario_id)` revoga somente capacidades cuja **sessão solicitante** pertence ao usuário indicado. Ao recuperar a senha administrativa, T48 chama a invalidação pelo ID do administrador; isso revoga suas sessões e capacidades solicitadas por ele, **mas não** as capacidades que ele emitiu para sessões Caixa.

**Reprodução independente:** com banco temporário, foram criados administrador e Caixa, emitida uma capacidade para o Caixa cancelar a venda fictícia `17`, gerado e consumido um código de recuperação para trocar a senha do administrador; a sessão do administrador passou a `autenticada=False`, **mas `GerenciadorAutorizacoesPontuais.consumir` ainda aceitou a capacidade antiga** e retornou a identidade administrativa. Nenhuma venda foi cancelada neste teste, e o banco real não foi acessado. A capacidade tem duração padrão de 60 segundos, limitando a janela, mas não eliminando a inconsistência de revogação.

**Correção proposta:** vincular explicitamente a capacidade também ao ID do administrador que a autorizou; revogar pelo ID tanto na qualidade de solicitante quanto de autorizador; testar recuperação de senha após autorização de um Caixa, bloqueando uso posterior. Avaliar revalidação do autorizador no consumo, com custo proporcional. Não substituir por perfil textual, token forjável ou senha no contexto.

**Correção validada:** `_EstadoAutorizacao` passou a conservar privadamente o
ID estável do Administrador autorizador, mantendo a identificação textual usada
pela auditoria comercial. `invalidar_usuario()` agora revoga capacidades em que
a identidade seja solicitante ou autorizadora. Emissão, consumo e revogação são
serializados pelo mesmo bloqueio; a recuperação administrativa já existente
aciona essa invalidação. Testes cobrem recuperação após concessão a Caixa,
solicitação pelo próprio Administrador, isolamento entre dois Administradores,
revogação concorrente e consumo único. A sessão Caixa permaneceu Caixa.

### P2 — Cancelamento pode ser confirmado no SQLite e comunicado como não concluído se o commit falhar de modo ambíguo (corrigido pela COR-M2-02)

**Código:** `services/cancelamento_venda_service.py` e `interface/pagina_historico.py`, `_finalizar_autorizacao`.

O serviço chama `conexao.commit()` e trata qualquer exceção com rollback e propagação. Em casos excepcionais de falha após o commit ser aceito pelo banco, o aplicativo pode desconhecer se o cancelamento aconteceu; a interface exibe erro e nova tentativa sem reconciliação explícita. Diferentemente da persistência de venda, o cancelamento não possui protocolo de *commit incerto*.

**Correção proposta:** em erro ambíguo de cancelamento, reler o status e os metadados por ID em uma conexão nova, apresentar estado comprovado ou marcar resultado incerto e orientar reconciliação, sem afirmar que a venda permanece ativa. Testar com injeção de falha pós-commit. Não alterar a garantia de consumo único da autorização.

**Correção validada:** somente exceções no commit iniciam reconciliação por nova
conexão. Venda ainda `ATIVA` confirma falha; venda `CANCELADA`, com metadados
iguais ou incompatíveis, permanece resultado incerto porque o esquema não
identifica a tentativa de cancelamento. Falha na própria consulta também
preserva a incerteza. A interface atualiza o Histórico quando possível, não
repete o cancelamento, não reutiliza a autorização e exige consulta expressa
antes de liberar nova solicitação para uma venda ainda ativa. Foram injetadas
falhas antes, durante e depois do commit, inclusive rollback falho e
cancelamento concorrente, sem alterar itens, pagamentos ou UUID do fechamento.

### P2 — Recuperação de fechamento incerto após reinicialização permanece em aberto (limitação conhecida)

**Código:** `interface/janela_principal.py`, estado `identificador_tentativa_fechamento` e `_fechamento_incerto` somente em memória; T40/INT-A.

A proteção idempotente durante o processo funciona, mas uma queda de energia/encerramento durante o resultado incerto perde o UUID da tentativa. O papel com etiquetas permite remontar itens, porém não permite identificar automaticamente a tentativa antiga.

**Ação:** definir procedimento operacional de reconciliação e critério de recuperação antes de liberar uso real. Vincular explicitamente à cobertura do T54 (protocolo de contingência) ou criar pendência com critério de aceite próprio. Não propor salvar todo o carrinho sem decisão do responsável.

### P2 — Dados operacionais no ZIP

O arquivo traz banco e backups na pasta `data/`. Embora o `.gitignore` cubra `data/*.db`, isso não protege backups em subpastas contra inclusão em ZIP, nem exclui material já rastreado no Git. **Não reutilizar esse pacote como anexo público.** Inspecionar a composição antes de compartilhar e atualizar orientações de envio.

### P3 — Lacunas de produto/planejamento ainda não convertidas em tickets executáveis

1. **Consulta gráfica do histórico de preços por 12 meses**: adiada pelo T44, sem ticket numerado exclusivo identificado em T49–T62.
2. **Gestão de categorias personalizáveis**: indicada na arquitetura futura, mas sem ticket executável próprio na sequência atual.
3. **Recuperação/alteração de senha de conta Caixa**: INT-E criou e ativa/desativa contas, mas não oferece redefinição; necessário procedimento administrativo, com autorização e revogação de sessões.
4. **Revisão da produtividade no diálogo de pagamentos** e **refinamento de layout**: documentados em seção de pendências do backlog, mas ainda sem data/ticket formal. Incluem persistência da divisão sugerida e atalho de conclusão independente.
5. **Homologação física do leitor**: explicitamente pendente, adequadamente situada na validação operacional T62.

### P3 — Backlog possui orientação de sequenciamento obsoleta

Ao final de `docs/TICKETS_RENUMERADO.md`, a seção «Regras de acompanhamento daqui em diante» ainda declara «O próximo ticket executável é T21». Essa orientação é incompatível com a conclusão relatada até T48/INT-E. Corrigir apenas o documento ativo, sem reescrever documentação legada.

## Áreas verificadas com resultado positivo

- Domínio e persistência separados da GUI; repositórios SQLite centralizados.
- Banco versionado até v9, backup pré-migração e verificação de integridade no serviço de inicialização; testes com `tmp_path`.
- T43: cancelamento transacional e histórico preservado, sem SQL de cancelamento na interface.
- T47: capacidades aleatórias, consumo único sob `Lock`, recurso/operação/sessão vinculados, sem elevação de sessão Caixa; **ressalva da revogação do autorizador acima**.
- T48: códigos de recuperação de alta entropia armazenados por verificador; consumo e troca de senha em transação; sem login automático.
- Interface com `QStackedWidget`, Frente de Caixa, Histórico, Produtos e Administração, com proteções de sessão de acordo com o código inspecionado.
- `tzdata` consta das dependências, resolvendo a falha de Windows anteriormente relatada.

## Ordem de ação sugerida

1. **Correção curta antes do encerramento do Marco 2:** revogação de capacidades emitidas por administrador após recuperação de sua senha; novo teste de regressão.
2. **Concluído pela COR-M2-02:** cancelamento incerto tratado sem comunicar
   certeza indevida e sem atribuir autoria por metadados coincidentes.
3. **Registrar formalmente** a estratégia para recuperação de UUID perdido pós-crash, possivelmente ligada ao T54; não necessariamente implementar já.
4. **Criar tickets/pendências explícitas** para senhas de Caixa, consulta gráfica de preços e categorias; manter ajustes de pagamentos/layout nas respectivas entregas de UX, antes de validação final.
5. **Corrigir instrução T21 obsoleta** no backlog e retirar bancos/backups de futuros ZIPs.
6. Rodar a suite completa no Windows (`python -m pytest -q`) após correções, complementar com testes manuais de autorização/cancelamento e repetir auditoria rápida antes do Marco 3.

**Nota metodológica:** os apontamentos P1 foram demonstrados por execução isolada; P2 relativos a commit incerto são análise de risco fundamentada no tratamento de exceções, não prova de ocorrência real; demais lacunas vêm do cotejo do código e backlog. Nenhuma alteração foi aplicada ao projeto fornecido.
