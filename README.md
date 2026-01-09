
Agendamento Ponto de Atendimento
Este projeto é uma aplicação web de gerenciamento de agendamentos para um ponto de atendimento, desenvolvida com Python e o framework Flask. Ele permite que administradores e coordenadores gerenciem agendamentos, visualizem estatísticas, e controlem usuários e configurações da plataforma.

Funcionalidades Principais
Login e Autenticação: O sistema possui um sistema de login com diferenciação entre usuários e administradores, protegendo as rotas sensíveis.

Gerenciamento de Agendamentos:

Dashboard: A tela principal exibe os agendamentos, com opções de filtragem por data, status e setor.

Criação, Edição e Exclusão: Administradores podem realizar operações completas (CRUD) nos agendamentos.

Controle de Conflitos: O sistema impede a criação ou edição de agendamentos que resultem em conflito de horário para o mesmo coordenador.

Controle de Acesso:

Administradores: Têm acesso a todas as funcionalidades, incluindo gerenciamento de usuários e configurações.

Coordenadores/Usuários Padrão: Têm acesso restrito, podendo visualizar apenas os agendamentos nos quais são o coordenador responsável.

Gerenciamento de Usuários (Admin): Apenas administradores podem criar, editar e excluir usuários, além de definir permissões de administrador.

Configurações do Sistema (Admin): Administradores podem gerenciar valores pré-definidos para o sistema, como:

Canais de atendimento (ex: Telefone, Email, Presencial).

Setores (ex: Comercial, Acadêmico).

Categorias de atendimento (ex: Matrícula, Bolsas).

Status dos agendamentos (ex: Aberto, Concluído).

Estrutura do Projeto
O projeto está organizado em dois arquivos principais:

app.py: Contém a lógica principal da aplicação Flask, incluindo as rotas, a lógica de negócio, e a manipulação dos formulários.

models.py: Define os modelos de dados (tabelas) do banco de dados usando o SQLAlchemy, mapeando as classes Python para as tabelas User, Agendamento, Canal, Setor, Categoria e Status.

Como Executar
Pré-requisitos: Certifique-se de ter o Python e o pip instalados.

Configuração do Ambiente:

Bash

# Clone o repositório ou baixe os arquivos
git clone <URL_DO_REPOSITÓRIO>
cd <pasta_do_projeto>

# Instale as dependências
pip install Flask Flask-SQLAlchemy Flask-Login Werkzeug
Inicialização do Banco de Dados:
Este comando cria o arquivo bancoAgendamentos.db e popula o banco de dados com um usuário administrador (admin), um usuário padrão (user) e valores padrão para as configurações.

Bash

flask init-db
Execução da Aplicação:

Bash

flask run
A aplicação estará disponível em http://127.0.0.1:5000.

Credenciais Padrão
Usuário Admin:

Username: admin

Senha: admin

Usuário Padrão:

Username: user

Senha: user
# SGA_panorama
