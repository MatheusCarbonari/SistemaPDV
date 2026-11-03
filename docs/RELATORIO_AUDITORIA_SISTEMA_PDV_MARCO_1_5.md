# Auditoria técnica do Sistema-PDV — Marco 1.5

**Origem:** ZIP `SistemaPDV-Marco 1 finalizado.zip`, recebido nesta conversa.  
**Escopo:** inspeção do código de produção, planejamento, execução de testes viáveis neste ambiente e simulações independentes.  
**Alterações no projeto:** nenhuma.

## Resultados reproduzidos

- **434 testes Python de domínio/serviços/repositório/banco passaram** (`python -m pytest -q --ignore=tests/test_entrada_interface.py --ignore=tests/test_fluxo_leitura_etiquetas.py --ignore=tests/test_interface_pyside6.py --ignore=tests/test_lista_venda_interface.py`).
- **43 testes Qt não foram reexecutados** por indisponibilidade de PySide6/pytest-qt no Linux da auditoria e impossibilidade de instalar pacotes por restrição de rede. O relato anterior de 477 aprovados pertence ao ambiente do Codex/usuário, e não foi reproduzido integralmente aqui.
- **15.000 operações aleatórias de venda**, com inclusão, remoção, desfazer, diversos, etiquetas, itens por peso e por unidade; a cada operação, o estado e o total em centavos foram comparados contra uma implementação de referência. Nenhuma divergência.
- Etiquetas documentadas: `2023400053672` => 5367 centavos e `2001100137083` => 13708 centavos, sem recálculo do valor da etiqueta.
- `compileall` de código de produção e testes: sem erro de sintaxe.

## Achados e recomendações

### A1 — Inicialização em banco ausente (risco funcional, comprovado)

O bootstrap `interface/aplicacao.py` instancia `JanelaPrincipal`, mas não chama `criar_tabelas`. A função `database/conexao.py:conectar` cria um arquivo SQLite se ele não existir. Reproduzi a busca de um produto apontando para banco inexistente; ela gerou um arquivo vazio e terminou em `sqlite3.OperationalError: no such table: produtos`. A consulta é disparada pela entrada da interface sem tratamento para essa exceção.

**Tratamento recomendado:** estabelecer inicialização/versionamento de schema antes do primeiro consumo de dados, com diagnóstico amigável, sem antecipar uma migração geral. É particularmente relevante para a instalação em máquina nova e deve ser planejado no Marco 2 e harmonizado com T45/T58.

### A2 — Catálogo local enviado está quase vazio (limitação de teste, comprovada)

O arquivo `data/sistema_acougue.db` contém somente a tabela `produtos` e **um produto com código `1`**. As etiquetas reais de códigos 234, 11 e 147 não podem ser validadas contra o catálogo contido no ZIP sem dados de teste isolados. Os testes existentes corretamente usam bancos temporários e produtos de teste.

**Tratamento recomendado:** usar bases de demonstração temporárias ou ampliar o cadastro real somente quando autorizado; não editar o banco enviado durante uma auditoria.

### A3 — Homologação com leitor físico não realizada (pendência conhecida)

Os testes simulam sinais e eventos de teclado, mas não a velocidade de hardware, seu prefixo/sufixo nem sua compatibilidade. Manter a pendência explícita até o equipamento estar disponível.

### A4 — Metas de latência do T31 (lacuna documental/escopo)

O título e a entrega original do T31 em `docs/TICKETS_RENUMERADO.md` incluem **instrumentar latência da leitura até a lista**. A seção de conclusão descreve testes de integração simulados, mas não apresenta métricas de latência. Isso não invalida o escopo adaptado sem leitor, porém evita considerar a medição original demonstrada. Recomenda-se medição futura com ambiente e equipamento apropriados.

### A5 — Artefato ZIP contém ambiente virtual Windows e `.git` (higiene de entrega)

O ZIP possui mais de 7.000 entradas, incluindo `.venv`, bibliotecas Windows, cache e histórico `.git`; grande parte do tamanho não é código de projeto. Isso não é bug da aplicação. Para futuras revisões, preferir exportar apenas código, testes, documentação e dependências, excluindo `.venv`, `.git`, caches e bancos reais quando não forem necessários.

## Arquitetura observada

- Domínio e serviços comerciais separados da interface PySide6.
- Venda em andamento em memória, com modelos imutáveis e funções puras para adicionar, remover, inserir e desfazer.
- Conversão monetária baseada em inteiros/Decimal; valor de etiqueta preservado na criação dos itens.
- Estado legado `tipo_item=None` preservado; Diversos identificado explicitamente por `tipo_item='DIVERSOS'`.
- Catálogo SQLite e testes isolados via `tmp_path`.
- Backlog oficial `docs/TICKETS_RENUMERADO.md`: T32 = esquema de vendas; revisão de layout/usabilidade está registrada para depois do fluxo comercial completo.

## Conclusão

O núcleo testável encontra-se estável nas verificações executadas. Recomendo avançar ao planejamento do T32, com atenção ao bootstrap do schema/primeiro acesso antes da implantação. Continuam pendentes os testes PySide6 neste ambiente, a homologação com leitor físico e a medição de latência real. Nenhum arquivo de produção foi modificado nesta auditoria.
