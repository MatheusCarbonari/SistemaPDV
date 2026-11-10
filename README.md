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
