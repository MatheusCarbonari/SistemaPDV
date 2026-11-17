# Sistema-PDV

Sistema de ponto de venda desenvolvido para operação local em açougues. A aplicação desktop organiza o atendimento do caixa, registra vendas comerciais internas e mantém catálogo, histórico e controles de acesso em SQLite.

> O projeto concluiu o Marco 2, mas ainda está em desenvolvimento. Ele não substitui sistemas fiscais e não está declarado pronto para produção ou homologado no equipamento do cliente.

## Funcionalidades implementadas

- Frente de Caixa com entrada central por etiqueta ou código manual.
- Produtos vendidos por peso ou unidade e lançamentos do tipo Diversos.
- Cálculos monetários em centavos e preservação de snapshots comerciais.
- Pagamentos múltiplos, inclusive modalidades repetidas e divisão exata em centavos.
- Confirmação e persistência idempotente de vendas.
- Histórico de vendas com itens, pagamentos e situação.
- Cancelamento integral com motivo e autorização administrativa pontual.
- Cadastro, edição, ativação e inativação de produtos.
- Categorias personalizáveis e histórico auditável de preços.
- Contas de Administrador e Caixa, login, troca de operador e permissões.
- Autorizações pontuais de uso único para operações críticas.
- Recuperação administrativa por códigos offline.
- Migração versionada do SQLite com backup verificado antes da atualização.
- Identificação offline da versão do aplicativo e da origem do build.
- Backup SQLite local validado e transporte externo configurável.

## Tecnologias

- Python
- PySide6 / Qt Widgets
- SQLite
- Pytest e pytest-qt

## Pré-requisitos

- Python 3.10 ou superior.
- Ambiente Windows para o uso operacional previsto pelo projeto.

As dependências Python estão declaradas em [`requirements.txt`](requirements.txt).

## Instalação

Execute os comandos a partir da raiz do repositório.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Execução

```powershell
python main.py
```

No primeiro uso de um banco novo, a aplicação conduz a criação do Administrador inicial. O banco e seus backups são dados locais e não devem ser adicionados ao Git.

## Logs locais

A aplicação registra eventos técnicos em formato JSON Lines. No desenvolvimento
Windows, o destino padrão é
`%LOCALAPPDATA%\Sistema-PDV\logs\sistema-pdv.log`; ele pode ser substituído por
`SISTEMA_PDV_LOG_DIR`. Na instalação comercial, Produção e Homologação usam o
diretório `logs` de seus contextos sob `%PROGRAMDATA%`, sem aceitar esse
redirecionamento por variável de ambiente. Os
arquivos possuem rotação e não devem conter senhas, hashes, códigos de
recuperação, credenciais ou capacidades de autorização. Consulte a
[arquitetura-alvo](docs/ARQUITETURA_ALVO.md#logs-locais-t49) para a política
completa.

## Versão e origem do build

A fonte oficial da identificação do aplicativo é
`services/version_service.py`. A versão atual é `0.1.0` e não corresponde à
versão do schema SQLite. A opção **Sobre** da janela principal apresenta versão,
identificador do build e commit Git; valores ainda não incorporados aparecem
como `desconhecido`.

A inicialização não executa Git e funciona sem pasta `.git` ou internet. O
empacotamento T59 preenche build e commit somente em uma cópia temporária do
módulo; o arquivo-fonte permanece sem metadados artificiais.

## Build Windows

O build validado usa Python 3.14, PyInstaller em modo `onedir` e as versões
fixadas em `requirements-build.txt`. Em um ambiente Windows limpo de build:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
.\scripts\build_windows.ps1
```

O resultado fica em `dist\windows\Sistema-PDV\`, com o executável
`Sistema-PDV.exe`; `dist\windows\build-report.json` registra build, commit e
SHA-256 do executável. Cada tentativa é preparada, auditada e testada sob um
diretório exclusivo de `build/`; `dist\windows` somente é substituído depois
dessas validações. Falhas anteriores à publicação preservam integralmente a
distribuição anterior. Essa troca protege apenas a saída local do build e não
é o mecanismo de atualização ou rollback do T60.

O roteiro resolve uma única vez o `python` ativo, exige Windows x64 e Python
3.14, confere as versões exatas de `requirements-build.txt` e executa
`pip check`. O `PYTHONPATH` herdado não participa da descoberta de módulos do
build. `SISTEMA_PDV_BUILD_ID` e `SISTEMA_PDV_COMMIT_GIT` podem
ser definidos antes do comando. Sem valores explícitos, o roteiro tenta usar o
commit do repositório de build e cria um identificador determinístico a partir
dele somente se a árvore estiver limpa. Em árvore modificada, commit e build
permanecem desconhecidos, salvo valores explícitos, para não atribuir o artefato
a um commit que não contém suas fontes. Git não é necessário na máquina que
executa o programa.

O roteiro audita arquivos proibidos e executa um smoke test Qt `offscreen`
isolado. Esse teste comprova somente o carregamento básico do runtime
empacotado, a criação de QApplication/widget, os metadados e a resolução segura
do caminho. Ele não comprova renderização visual da interface operacional,
login nem fluxos comerciais. Ele não inclui nem acessa o banco de `data/`.
Durante o desenvolvimento, o banco permanece em
`repositorio\data\sistema_acougue.db`. Uma instalação comercial validada usa
`%PROGRAMDATA%\Sistema-PDV\Producao\data\sistema_acougue.db` ou o equivalente
isolado de `Homologacao`. Nenhum banco é transferido automaticamente entre
esses locais; a migração administrativa explícita pertence a uma etapa futura.

### Homologação gráfica manual

Em uma VM Windows limpa, provisionar uma identidade temporária completa de
Homologação em HKLM e no `installation.json`, o estado de manutenção `IDLE`, o
grupo local e as ACLs descritas no contrato T60-B. Usar somente banco e
credenciais de teste sob a raiz isolada de Homologação em `%PROGRAMDATA%`.
Iniciar `Sistema-PDV.exe` sem o argumento de smoke e verificar abertura, escala,
fontes, foco, navegação e encerramento. Registrar ambiente e resultado; remover
somente os recursos temporários confirmados da VM. Nunca apontar esse
procedimento para o banco do estabelecimento.

O T59 não fornece instalador, atalhos, assinatura de código, atualização ou
rollback. O T60-B definiu identidade, `%PROGRAMDATA%`, ACLs e instância única,
mas ainda não provisiona esses recursos; a homologação comercial completa
continua dependente das próximas etapas do instalador.

## Exportação de diagnóstico

Na página **Administração**, um Administrador pode escolher um diretório e usar
**Exportar diagnóstico**. A aplicação cria um ZIP local com manifesto técnico e
eventos selecionados reconstruídos dos logs; não envia arquivos pela internet.

O pacote não inclui SQLite, WAL, SHM, backups, logs brutos, caminhos locais,
operadores, IDs de venda ou credenciais. A coleta possui limites de tamanho e
quantidade, e logs ausentes ou corrompidos são declarados sem bloquear vendas.
Por segurança, a sessão administrativa é revalidada no momento da exportação.

## Catálogo essencial em memória

Após autenticar a operação, a aplicação prepara um snapshot imutável dos dados
essenciais de produtos. O SQLite continua sendo a fonte oficial; alterações de
produto recarregam todo o snapshot e falhas o tornam indisponível, sem reutilizar
silenciosamente dados antigos.

Cada instância fica vinculada a um único arquivo SQLite. Representações
equivalentes do mesmo caminho são aceitas, mas outro banco é recusado sem expor
seu caminho nem substituir o snapshot já carregado.

O T52 fornece apenas a base de leitura controlada. O fluxo normal continua no
SQLite e ainda não existe liberação automática de operação degradada, fechamento
ou cancelamento sem banco; essas decisões pertencem aos T53 e T54.

## Backup externo configurável

O backup externo é desabilitado por padrão. Para habilitar o destino de
diretório, defina a variável antes de iniciar a aplicação:

```powershell
$env:SISTEMA_PDV_BACKUP_EXTERNO_DIR = "E:\Sistema-PDV\backups"
python main.py
```

Quando configurado, o sistema cria primeiro um backup local consistente pelo
mecanismo do T55 e transporta a cópia em segundo plano. A primeira tentativa
ocorre ao abrir a operação e as seguintes a cada duas horas após o fim da
tentativa anterior. Falhas ficam registradas sem bloquear vendas.

O diretório precisa estar em mídia ou compartilhamento administrado e com
permissões adequadas. Informar outro caminho no mesmo disco não cria redundância
física. A implementação atual não envia para nuvem, não restaura dados e não
executa enquanto o programa estiver fechado.

## Testes

```powershell
python -m pytest -q
```

Na auditoria final do Marco 2, a suíte completa aprovou 1.078 testes automatizados.

## Estado de desenvolvimento

- Marco 2 concluído e homologado no escopo definido.
- 1.078 testes automatizados aprovados na auditoria final.
- 13 cenários de homologação manual aprovados pelo responsável.
- Migração SQLite v9 → v10 validada em banco temporário isolado.
- Revisão Visual 01–05 e Correções Finais 01/02 aprovadas.

## Limitações e próximos passos

O Marco 3 concentra as entregas de confiabilidade e preparação operacional, incluindo:

- recuperação e contingência após resultados de fechamento incertos;
- coordenação entre instâncias da aplicação;
- backup periódico e externo, restauração e segurança operacional;
- empacotamento e atualização para Windows;
- testes de desempenho e homologação com scanner e equipamento reais;
- ambiente durável e isolado para futuras homologações manuais.

Até a conclusão dessas etapas, o software deve ser tratado como projeto em desenvolvimento, não como solução pronta para produção.

## Documentação

- [Índice da documentação](docs/README.md)
- [Backlog oficial](docs/TICKETS_RENUMERADO.md)
- [Decisões](docs/DECISOES.md)
- [Arquitetura-alvo](docs/ARQUITETURA_ALVO.md)
- [Auditoria final do Marco 2](docs/AUDITORIA_FINAL_MARCO_2_SISTEMA_PDV.md)
- [Escopo da V1](docs/ESCOPO.md)

## Dados e segurança

O `.gitignore` exclui bancos SQLite, arquivos WAL/journal, backups, ambientes locais, temporários e credenciais. Antes de publicar ou compartilhar o repositório, revise também o histórico Git: ignorar um arquivo impede novas inclusões, mas não remove conteúdo já registrado em commits anteriores.
