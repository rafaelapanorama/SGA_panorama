from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Agendamento, Status, Canal, Setor, Categoria
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
from sqlalchemy import or_, and_
from weasyprint import HTML
import re
import os
import pandas as pd
from io import BytesIO

# App initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-super-segura'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ponto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'bancoAgendamentos.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'


# Import models after app initialization to avoid circular import
from models import db, User, Agendamento, Canal, Setor, Categoria, Status

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


def formatar_cpf(cpf: str) -> str:
    cpf = re.sub(r'\D', '', cpf)
    return f'{cpf}'


# Função helper para obter a classe CSS do status
def get_status_class(status):
    """Retorna a classe CSS apropriada baseada no status"""
    if not status:
        return 'badge bg-secondary'
    
    status_lower = status.lower().replace(' ', '-')
    
    if 'não-apto-coordenação' in status_lower or 'nao-apto-coordenacao' in status_lower:
        return 'badge status-nao-apto-coordenacao'
    elif 'não-apto-financeiro' in status_lower or 'nao-apto-financeiro' in status_lower:
        return 'badge status-nao-apto-financeiro'
    elif 'apto-coordenação' in status_lower or 'apto-coordenacao' in status_lower:
        return 'badge status-apto-coordenacao'
    elif 'apto-financeiro' in status_lower:
        return 'badge status-apto-financeiro'
    elif 'Concluído-Secretaria' in status_lower or 'concluído-secretaria' in status_lower:
        return 'badge status-concluido-secretaria'
    else:
        return 'badge bg-secondary'

# Registrar a função como filtro do Jinja2
app.jinja_env.filters['status_class'] = get_status_class

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Main Routes ---

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login inválido.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    query = Agendamento.query

    # Filtros de GET
    filter_data = request.args.get('data')
    filter_status = request.args.get('status')
    filter_setor = request.args.get('setor')

    # Filtro de data
    if filter_data:
        try:
            date_obj = datetime.strptime(filter_data, '%Y-%m-%d').date()
            query = query.filter_by(data_agendamento=date_obj)
        except ValueError:
            flash('Formato de data inválido. Use YYYY-MM-DD.', 'warning')

    # Filtro de status
    if filter_status:
        query = query.filter_by(status=filter_status)

    # Filtro de setor
    if filter_setor:
        query = query.filter_by(setor=filter_setor)

    # Regras por perfil de usuário
    if current_user.is_admin or current_user.perfil == 'admin':
        # Administrador vê tudo
        pass

    elif current_user.perfil == 'financeiro':
        query = query.filter(Agendamento.status.in_([
            'Apto-Financeiro',
            'Não-Apto-Financeiro',
            'Apto-Coordenação'
        ]))

    else:  # Perfil coordenação ou user comum
        # Coordenação vê TODOS os seus agendamentos, incluindo os que foram para o Financeiro
        query = query.filter_by(coordenador=current_user.username)

    agendamentos = query.order_by(
        Agendamento.data_agendamento.desc(),
        Agendamento.horario.desc()
    ).all()

    context = {
        'agendamentos': agendamentos,
        'statuses': Status.query.all(),
        'setores': Setor.query.all()
    }

    # Contadores por tipo de perfil
    if current_user.is_admin or current_user.perfil == 'admin':
        context['admin_total_agendamentos_abertos'] = Agendamento.query.filter(
            Agendamento.status.in_([
                'Aberto-Coordenação',
                'Em andamento-Coordenação',
                'Remarcado-Coordenação',
                'Apto-Coordenação',
                'Não-Apto-Coordenação',
                'Não-Apto-Financeiro',
                'Apto-Financeiro'
            ])
        ).count()

        context['admin_total_agendamentos_concluidos'] = Agendamento.query.filter(
            Agendamento.status == 'Concluído-Secretaria'
        ).count()

        context['admin_status_counts_table'] = db.session.query(
            Agendamento.status, db.func.count(Agendamento.id)
        ).group_by(Agendamento.status).all()

        context['admin_coordenador_counts_table'] = db.session.query(
            Agendamento.coordenador, db.func.count(Agendamento.id)
        ).group_by(Agendamento.coordenador).all()

        context['admin_setor_counts_table'] = db.session.query(
            Agendamento.setor, db.func.count(Agendamento.id)
        ).group_by(Agendamento.setor).all()

    elif current_user.perfil == 'financeiro':
        context['total_agendamentos_abertos'] = query.filter(Agendamento.status.in_([
            'Apto-Coordenação',
        ])).count()
        context['total_agendamentos_concluidos'] = query.filter(Agendamento.status.in_([
            'Apto-Financeiro',
            'Não-Apto-Financeiro',
        ])).count()

    else:  # user comum (coordenação)
        # Agendamentos em andamento (ainda na coordenação)
        context['total_agendamentos_abertos'] = query.filter(Agendamento.status.in_([
            'Aberto-Coordenação',
            'Em andamento-Coordenação',
            'Remarcado-Coordenação'
        ])).count()

        # Agendamentos finalizados (inclui os que foram para o Financeiro)
        context['total_agendamentos_concluidos'] = query.filter(
            Agendamento.status.in_([
                'Apto-Coordenação',
                'Não-Apto-Coordenação',
                'Concluído-Secretaria',
                'Apto-Financeiro',
                'Não-Apto-Financeiro'
            ])
        ).count()

    return render_template('dashboard.html', **context)

# --- CRUD Routes (Admin only) ---

def get_time_options():
    """Generate time options in 30-minute intervals."""
    options = []
    for hour in range(24):
        options.append(time(hour, 0))
        options.append(time(hour, 30))
    return options

@app.route('/agendamento/novo', methods=['GET', 'POST'])
@login_required
def novo_agendamento():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        data_agendamento_str = request.form['data_agendamento']
        horario_str = request.form['horario']
        coordenador = request.form.get('coordenador')

        data_agendamento = datetime.strptime(data_agendamento_str, '%Y-%m-%d').date()
        horario = datetime.strptime(horario_str, '%H:%M').time()

        # Limpar e validar CPFs
        cpf_1 = re.sub(r'\D', '', request.form['cpf_responsavel_1'])
        cpf_2 = re.sub(r'\D', '', request.form['cpf_responsavel_2'])

        if len(cpf_1) != 11 or len(cpf_2) != 11:
            flash("CPF(s) inválido(s). Digite exatamente 11 números.", "danger")
            form_data = request.form.copy()
            form_data['cpf_responsavel_1'] = formatar_cpf(cpf_1) if len(cpf_1) == 11 else ''
            form_data['cpf_responsavel_2'] = formatar_cpf(cpf_2) if len(cpf_2) == 11 else ''
            form_data['data_agendamento'] = data_agendamento
            form_data['horario'] = horario
            return render_template('agendamento_form.html',
                                   title='Novo Agendamento',
                                   canais=Canal.query.all(),
                                   setores=Setor.query.all(),
                                   categorias=Categoria.query.all(),
                                   coordenadores=User.query.all(),
                                   time_options=get_time_options(),
                                   statuses=Status.query.all(),
                                   form_data=form_data)

        # CPF validado e formatado
        cpf_responsavel_1_tratado = formatar_cpf(cpf_1)
        cpf_responsavel_2_tratado = formatar_cpf(cpf_2)

        # Check for scheduling conflict
        conflito = Agendamento.query.filter_by(
            data_agendamento=data_agendamento,
            horario=horario,
            coordenador=coordenador
        ).first()

        if conflito:
            flash(f'O coordenador {coordenador} já possui um agendamento neste horário.', 'danger')
            form_data = request.form.copy()
            form_data['cpf_responsavel_1'] = cpf_responsavel_1_tratado
            form_data['cpf_responsavel_2'] = cpf_responsavel_2_tratado
            form_data['data_agendamento'] = data_agendamento
            form_data['horario'] = horario
        else:
            novo = Agendamento(
                canal=request.form['canal'],
                nome_responsavel_2=request.form['nome_responsavel_2'],
                nome_responsavel_1=request.form['nome_responsavel_1'],
                cpf_responsavel_1=cpf_responsavel_1_tratado,
                cpf_responsavel_2=cpf_responsavel_2_tratado,
                categoria=request.form['categoria'],
                status=request.form['status'],
                setor=request.form['setor'],
                aluno=request.form.get('aluno'),
                escolaAluno=request.form.get('escolaAluno'),
                motivo=request.form.get('motivo'),
                data_agendamento=data_agendamento,
                horario=horario,
                coordenador=coordenador,
                observacao=request.form.get('observacao')
            )
            db.session.add(novo)
            db.session.commit()
            flash('Agendamento criado com sucesso!', 'success')
            return redirect(url_for('dashboard'))

    # For GET request or if POST fails
    form_data = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        if 'data_agendamento' in form_data and form_data['data_agendamento']:
            form_data['data_agendamento'] = datetime.strptime(form_data['data_agendamento'], '%Y-%m-%d').date()
        if 'horario' in form_data and form_data['horario']:
            form_data['horario'] = datetime.strptime(form_data['horario'], '%H:%M').time()

    return render_template('agendamento_form.html',
                           title='Novo Agendamento',
                           canais=Canal.query.all(),
                           setores=Setor.query.all(),
                           categorias=Categoria.query.all(),
                           coordenadores=User.query.all(),
                           time_options=get_time_options(),
                           statuses=Status.query.all(),
                           form_data=form_data)


@app.route('/agendamento/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_agendamento(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
    
    agendamento = Agendamento.query.get_or_404(id)

    if request.method == 'POST':
        data_agendamento_str = request.form['data_agendamento']
        horario_str = request.form['horario']
        coordenador = request.form.get('coordenador')

        data_agendamento = datetime.strptime(data_agendamento_str, '%Y-%m-%d').date()
        horario = datetime.strptime(horario_str, '%H:%M').time()

        # Tratamento dos CPFs
        cpf_1 = re.sub(r'\D', '', request.form['cpf_responsavel_1'])
        cpf_2 = re.sub(r'\D', '', request.form['cpf_responsavel_2'])

        if len(cpf_1) != 11 or len(cpf_2) != 11:
            flash("CPF(s) inválido(s). Digite exatamente 11 números.", "danger")
            form_data = request.form.copy()
            form_data['cpf_responsavel_1'] = formatar_cpf(cpf_1) if len(cpf_1) == 11 else ''
            form_data['cpf_responsavel_2'] = formatar_cpf(cpf_2) if len(cpf_2) == 11 else ''
            return render_template('agendamento_form.html',
                                   title='Editar Agendamento',
                                   agendamento=agendamento,
                                   canais=Canal.query.all(),
                                   setores=Setor.query.all(),
                                   categorias=Categoria.query.all(),
                                   coordenadores=User.query.all(),
                                   time_options=get_time_options(),
                                   statuses=Status.query.all(),
                                   form_data=form_data)

        cpf_responsavel_1_tratado = formatar_cpf(cpf_1)
        cpf_responsavel_2_tratado = formatar_cpf(cpf_2)

        # Verificar conflito (excluindo o próprio agendamento)
        conflito = Agendamento.query.filter(
            Agendamento.id != id,
            Agendamento.data_agendamento == data_agendamento,
            Agendamento.horario == horario,
            Agendamento.coordenador == coordenador
        ).first()

        if conflito:
            flash(f'O coordenador {coordenador} já possui um agendamento neste horário.', 'danger')
            form_data = request.form.copy()
            form_data['cpf_responsavel_1'] = cpf_responsavel_1_tratado
            form_data['cpf_responsavel_2'] = cpf_responsavel_2_tratado
            return render_template('agendamento_form.html',
                                   title='Editar Agendamento',
                                   agendamento=agendamento,
                                   canais=Canal.query.all(),
                                   setores=Setor.query.all(),
                                   categorias=Categoria.query.all(),
                                   coordenadores=User.query.all(),
                                   time_options=get_time_options(),
                                   statuses=Status.query.all(),
                                   form_data=form_data)
        else:
            # Atualiza os dados no banco
            agendamento.canal = request.form['canal']
            agendamento.nome_responsavel_2 = request.form['nome_responsavel_2']
            agendamento.nome_responsavel_1 = request.form['nome_responsavel_1']
            agendamento.cpf_responsavel_1 = cpf_responsavel_1_tratado
            agendamento.cpf_responsavel_2 = cpf_responsavel_2_tratado
            agendamento.categoria = request.form['categoria']
            agendamento.status = request.form['status']
            agendamento.setor = request.form['setor']
            agendamento.aluno = request.form.get('aluno')
            agendamento.escolaAluno = request.form.get('escolaAluno')
            agendamento.motivo = request.form.get('motivo')
            agendamento.data_agendamento = data_agendamento
            agendamento.horario = horario
            agendamento.coordenador = coordenador
            agendamento.observacao = request.form.get('observacao')
            db.session.commit()
            flash('Agendamento atualizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))

    # GET request ou POST inválido
    form_data = {
        'canal': agendamento.canal,
        'nome_responsavel_1': agendamento.nome_responsavel_1,
        'nome_responsavel_2': agendamento.nome_responsavel_2,
        'cpf_responsavel_1': agendamento.cpf_responsavel_1,
        'cpf_responsavel_2': agendamento.cpf_responsavel_2,
        'categoria': agendamento.categoria,
        'status': agendamento.status,
        'setor': agendamento.setor,
        'aluno': agendamento.aluno,
        'escolaAluno': agendamento.escolaAluno,
        'motivo': agendamento.motivo,
        'data_agendamento': agendamento.data_agendamento,
        'horario': agendamento.horario,
        'coordenador': agendamento.coordenador,
        'observacao': agendamento.observacao
    } if request.method == 'GET' else request.form

    return render_template('agendamento_form.html',
                           title='Editar Agendamento',
                           agendamento=agendamento,
                           canais=Canal.query.all(),
                           setores=Setor.query.all(),
                           categorias=Categoria.query.all(),
                           coordenadores=User.query.all(),
                           time_options=get_time_options(),
                           statuses=Status.query.all(),
                           form_data=form_data)


@app.route('/agendamento/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_agendamento(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
    agendamento = Agendamento.query.get_or_404(id)
    db.session.delete(agendamento)
    db.session.commit()
    flash('Agendamento excluído com sucesso!', 'success')
    return redirect(url_for('dashboard'))

# --- User Routes ---


@app.route('/agendamento/checkout/<int:id>', methods=['POST'])
@login_required
def checkout_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    
    # ============ VALIDAÇÕES DE SEGURANÇA ============
    
    # Identificar tipo de usuário
    is_coordenacao_user = (current_user.perfil not in ['financeiro', 'admin'] and 
                           not current_user.is_admin)
    is_financeiro_user = current_user.perfil == 'financeiro'
    is_admin_user = current_user.is_admin or current_user.perfil == 'admin'
    
    # Verificar se agendamento está bloqueado para coordenação
    is_locked_for_coordenacao = (agendamento.status == 'Apto-Coordenação' and 
                                 agendamento.setor == 'Financeiro')
    
    # BLOQUEIO 1: Coordenação não pode editar agendamento já enviado ao financeiro
    if is_coordenacao_user and is_locked_for_coordenacao:
        flash('Este agendamento já foi enviado para o Financeiro e não pode mais ser editado pela Coordenação.', 'danger')
        return redirect(url_for('dashboard'))
    
    # BLOQUEIO 2: Coordenação não pode alterar agendamento que já está como "Apto-Coordenação"
    if is_coordenacao_user and agendamento.status == 'Apto-Coordenação':
        flash('Não é permitido alterar um agendamento que já está marcado como "Apto-Coordenação".', 'danger')
        return redirect(url_for('dashboard'))
    
    # ============ PROCESSAR ATUALIZAÇÃO ============
    
    new_status = request.form.get('status')
    new_setor = request.form.get('setor')
    new_observacao = request.form.get('observacao')

    # Validar status
    valid_statuses = [s.nome for s in Status.query.all()]
    
    if not new_status or new_status not in valid_statuses:
        flash('Status inválido ou não fornecido.', 'warning')
        return redirect(url_for('dashboard'))
    
    # Definir status permitidos por perfil
    status_permitidos_coordenacao = [
        'Aberto-Coordenação',
        'Em andamento-Coordenação',
        'Remarcado-Coordenação',
        'Apto-Coordenação',
        'Não-Apto-Coordenação'
    ]
    
    status_permitidos_financeiro = ['Apto-Financeiro', 'Não-Apto-Financeiro']
    
    # VALIDAÇÃO DE PERMISSÃO POR PERFIL
    if is_financeiro_user:
        if new_status not in status_permitidos_financeiro:
            flash('Você não tem permissão para usar este status.', 'danger')
            return redirect(url_for('dashboard'))
    elif is_coordenacao_user:
        if new_status not in status_permitidos_coordenacao:
            flash('Você não tem permissão para usar este status.', 'danger')
            return redirect(url_for('dashboard'))
    # Admin pode usar qualquer status
    
    # REGRA ESPECIAL: Se coordenação marca como "Apto-Coordenação", envia para Financeiro
    if new_status == 'Apto-Coordenação' and is_coordenacao_user:
        agendamento.status = new_status
        agendamento.setor = 'Financeiro'
        if new_observacao is not None:
            agendamento.observacao = new_observacao
        
        try:
            db.session.commit()
            flash(f'Agendamento #{id} marcado como "Apto-Coordenação" e enviado para o Financeiro! Você não poderá mais editá-lo.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar agendamento: {str(e)}', 'danger')
    else:
        # Atualização normal (mantendo sua lógica original)
        agendamento.status = new_status
        agendamento.setor = new_setor
        if new_observacao is not None:
            agendamento.observacao = new_observacao
        
        try:
            db.session.commit()
            flash(f'Status do agendamento alterado para {new_status}.\nObservação atualizada.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar agendamento: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

# --- Configuration Routes (Admin only) ---

@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Add new item
        if 'add_status' in request.form:
            nome = request.form.get('status_nome')
            if nome and not Status.query.filter_by(nome=nome).first():
                db.session.add(Status(nome=nome))
                flash('Status adicionado.', 'success')
        elif 'add_canal' in request.form:
            nome = request.form.get('canal_nome')
            if nome and not Canal.query.filter_by(nome=nome).first():
                db.session.add(Canal(nome=nome))
                flash('Canal adicionado.', 'success')
        elif 'add_setor' in request.form:
            nome = request.form.get('setor_nome')
            if nome and not Setor.query.filter_by(nome=nome).first():
                db.session.add(Setor(nome=nome))
                flash('Setor adicionado.', 'success')
        elif 'add_categoria' in request.form:
            nome = request.form.get('categoria_nome')
            if nome and not Categoria.query.filter_by(nome=nome).first():
                db.session.add(Categoria(nome=nome))
                flash('Categoria adicionada.', 'success')
        
        db.session.commit()
        return redirect(url_for('configuracoes'))

    canais = Canal.query.all()
    setores = Setor.query.all()
    categorias = Categoria.query.all()
    statuses = Status.query.all() # Fetch all statuses
    return render_template('configuracoes.html', canais=canais, setores=setores, categorias=categorias, statuses=statuses)

@app.route('/configuracoes/excluir/<string:model_name>/<int:id>', methods=['POST'])
@login_required
def excluir_config(model_name, id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))

    model_map = {
        'canal': Canal,
        'setor': Setor,
        'categoria': Categoria,
        'status': Status # Add Status to the map
    }
    model = model_map.get(model_name)
    
    if model:
        # Check if any Agendamento depends on this status before deleting
        if model_name == 'status':
            item = Status.query.get_or_404(id)
            if Agendamento.query.filter_by(status=item.nome).first():
                flash(f'Não é possível excluir o status {item.nome} porque existem agendamentos associados a ele.', 'danger')
                return redirect(url_for('configuracoes'))
        # Similar checks could be added for canal, setor, categoria if Agendamento uses their `nome`

        item = model.query.get_or_404(id)
        db.session.delete(item)
        db.session.commit()
        flash(f'{model_name.capitalize()} excluído com sucesso.', 'success')
    else:
        flash('Configuração inválida.', 'danger')
        
    return redirect(url_for('configuracoes'))


# --- User Management Routes (Admin only) ---

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))

    # garante que 'users' sempre exista
    users = User.query.all()
    form_data = {}

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        perfil = request.form.get('perfil', '').strip()
        email = request.form.get('email', '').strip()

        # manter dados no formulário em caso de erro
        form_data = request.form.to_dict()

        # Validações básicas
        if not username:
            flash('Nome de usuário é obrigatório.', 'warning')
        elif not email:
            flash('E-mail é obrigatório.', 'warning')
        elif not password:
            flash('Senha é obrigatória.', 'warning')
        elif User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe.', 'warning')
        elif User.query.filter_by(email=email).first():
            flash('E-mail já registrado.', 'warning')
        else:
            # Cria usuário e persiste
            novo = User(username=username, email=email, perfil=perfil)
            novo.set_password(password)
            # Se você usa is_admin via checkbox, trate aqui (ex: perfil == 'admin' ou checkbox)
            if perfil.lower() == 'admin':
                novo.is_admin = True
            db.session.add(novo)
            db.session.commit()
            flash('Usuário criado com sucesso.', 'success')
            return redirect(url_for('admin_users'))

        # se houve erro, recarrega lista de usuários para renderizar a página com dados atuais
        users = User.query.all()

    return render_template('admin_users.html', users=users, form_data=form_data)


@app.route('/admin/user/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.is_admin = 'is_admin' in request.form
        user.email = request.form.get('email')

        if not user.email:
            flash('E-mail é obrigatório.', 'warning')
            return render_template('user_form.html', user=user)
        
        # Check for unique email, excluding the current user
        existing_user_with_email = User.query.filter(User.email == user.email, User.id != user.id).first()
        if existing_user_with_email:
            flash('E-mail já registrado por outro usuário.', 'warning')
            return render_template('user_form.html', user=user)
            
        password = request.form.get('password')
        if password:
            user.set_password(password)
            
        db.session.commit()
        flash('Usuário atualizado com sucesso.', 'success')
        return redirect(url_for('admin_users'))

    return render_template('user_form.html', user=user)

@app.route('/admin/user/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))

    user_to_delete = User.query.get_or_404(id)
    
    if user_to_delete.id == current_user.id:
        flash('Você não pode excluir a si mesmo.', 'danger')
        return redirect(url_for('admin_users'))

    db.session.delete(user_to_delete)
    db.session.commit()
    flash('Usuário excluído com sucesso.', 'success')
    return redirect(url_for('admin_users'))


# --- EXPORTAR EXCEL E VISUALIZAR PDF ---

def build_booking_query(search_query_text=None, filters=None):
    query = Agendamento.query

    # 🔍 BUSCA LIVRE
    if search_query_text:
        search_query_text = search_query_text.strip()

        # múltiplos termos separados por vírgula
        if ',' in search_query_text:
            terms = [t.strip() for t in search_query_text.split(',') if t.strip()]
            and_filters = []

            for term in terms:
                or_filters = [
                    Agendamento.canal.ilike(f"%{term}%"),
                    Agendamento.setor.ilike(f"%{term}%"),
                    Agendamento.status.ilike(f"%{term}%"),
                    Agendamento.categoria.ilike(f"%{term}%"),
                    Agendamento.nome_responsavel_1.ilike(f"%{term}%"),
                    Agendamento.nome_responsavel_2.ilike(f"%{term}%"),
                    Agendamento.aluno.ilike(f"%{term}%"),
                ]

                # tentar interpretar como data
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        date_obj = datetime.strptime(term, fmt).date()
                        or_filters.append(Agendamento.data_agendamento == date_obj)
                        break
                    except ValueError:
                        pass

                and_filters.append(or_(*or_filters))

            query = query.filter(and_(*and_filters))

        # busca simples
        else:
            or_filters = [
                Agendamento.canal.ilike(f"%{search_query_text}%"),
                Agendamento.setor.ilike(f"%{search_query_text}%"),
                Agendamento.status.ilike(f"%{search_query_text}%"),
                Agendamento.categoria.ilike(f"%{search_query_text}%"),
                Agendamento.nome_responsavel_1.ilike(f"%{search_query_text}%"),
                Agendamento.nome_responsavel_2.ilike(f"%{search_query_text}%"),
                Agendamento.aluno.ilike(f"%{search_query_text}%"),
            ]

            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                try:
                    date_obj = datetime.strptime(search_query_text, fmt).date()
                    or_filters.append(Agendamento.data_agendamento == date_obj)
                    break
                except ValueError:
                    pass

            query = query.filter(or_(*or_filters))

    # FILTROS DO FORMULÁRIO
    if filters:
        if filters.get('data'):
            query = query.filter(
                Agendamento.data_agendamento == filters['data']
            )

        if filters.get('status'):
            query = query.filter(
                Agendamento.status == filters['status']
            )

        if filters.get('setor'):
            query = query.filter(
                Agendamento.setor.ilike(f"%{filters['setor']}%")
            )

    return query

def get_filtered_bookings():
    """Obtém agendamentos filtrados com base nos parâmetros do formulário ou query string"""
    query = Agendamento.query

    # Pega os filtros de POST ou GET
    filter_data = request.form.get('data') or request.args.get('data')
    filter_status = request.form.get('status') or request.args.get('status')
    filter_setor = request.form.get('setor') or request.args.get('setor')

    # Filtro de data
    if filter_data:
        try:
            date_obj = datetime.strptime(filter_data, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Agendamento.data_agendamento) == date_obj)
        except ValueError:
            pass

    # Filtro de status
    if filter_status:
        query = query.filter(Agendamento.status == filter_status)

    # Filtro de setor
    if filter_setor:
        query = query.filter(Agendamento.setor == filter_setor)

    # Regras por perfil
    if current_user.is_admin or current_user.perfil == 'admin':
        pass
    elif current_user.perfil == 'financeiro':
        query = query.filter(Agendamento.status.in_([
            'Apto-Financeiro',
            'Não-Apto-Financeiro',
            'Apto-Coordenação'
        ]))
    else:  # Coordenação
        query = query.filter(Agendamento.coordenador == current_user.username)

    return query.order_by(
        Agendamento.data_agendamento.desc(),
        Agendamento.horario.desc()
    ).all()

@app.route('/export_excel')
@login_required
def export_excel():
    """Exporta agendamentos filtrados para Excel"""
    try:
        bookings = get_filtered_bookings()  # pega os agendamentos filtrados

        # mostrar o que está sendo retornado
        print("QUANTIDADE DE BOOKINGS:", len(bookings))

        # Preparar dados para o DataFrame
        data = []
        for b in bookings:
            data.append({
                'ID': b.id,
                'Data Agendamento': b.data_agendamento.strftime('%d/%m/%Y') if b.data_agendamento else 'N/A',
                'Horário': b.horario.strftime('%H:%M') if b.horario else 'N/A',
                'Canal': b.canal or 'N/A',
                'Nome Responsável 1': b.nome_responsavel_1 or 'N/A',
                'CPF Responsável 1': b.cpf_responsavel_1 or 'N/A',
                'Nome Responsável 2': b.nome_responsavel_2 or 'N/A',
                'CPF Responsável 2': b.cpf_responsavel_2 or 'N/A',
                'Status': b.status or 'N/A',
                'Setor': b.setor or 'N/A',
                'Aluno': b.aluno or 'N/A',
                'Escola do Aluno': b.escolaAluno or 'N/A',
                'Categoria': b.categoria or 'N/A',
                'Motivo': b.motivo or 'N/A',
                'Coordenador': b.coordenador or 'N/A',
                'Observação': b.observacao or ''
            })

        if not data:
            flash('Nenhum agendamento encontrado para exportar.', 'warning')
            return redirect(url_for('dashboard'))

        # Criar DataFrame
        df = pd.DataFrame(data)
    
        # Criar arquivo Excel em memória
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
        output.seek(0)
        
        # Enviar arquivo para download
        return send_file(
            output,
            download_name="agendamentos.xlsx",
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print("ERRO EXPORT_EXCEL:", e)  # imprime o erro no terminal
        flash(f'Erro ao exportar Excel: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/preview_pdf', methods=['POST'])
@login_required
def preview_pdf():
    """Gera preview HTML do PDF (para visualização no navegador)"""
    try:
        bookings = get_filtered_bookings()

        # Preparar filtros aplicados para exibição
        filters_applied = []
        if request.form.get('data'):
            try:
                date_obj = datetime.strptime(request.form.get('data'), '%Y-%m-%d')
                filters_applied.append(f"Data: {date_obj.strftime('%d/%m/%Y')}")
            except:
                pass
        if request.form.get('status'):
            filters_applied.append(f"Status: {request.form.get('status')}")
        if request.form.get('setor'):
            filters_applied.append(f"Setor: {request.form.get('setor')}")

        return render_template(
            'report_pdf_template.html',
            bookings=bookings,
            filters_applied=filters_applied,
            current_date=datetime.now().strftime('%d/%m/%Y %H:%M')
        )

    except Exception as e:
        print(f"Erro ao gerar preview PDF: {str(e)}")
        return f"<h1>Erro ao gerar preview</h1><p>{str(e)}</p>"


@app.route('/download_pdf', methods=['POST'])
@login_required
def download_pdf():
    """Gera e faz download do PDF"""
    try:
        bookings = get_filtered_bookings()

        filters_applied = []
        if request.form.get('data'):
            try:
                date_obj = datetime.strptime(request.form.get('data'), '%Y-%m-%d')
                filters_applied.append(f"Data: {date_obj.strftime('%d/%m/%Y')}")
            except:
                pass
        if request.form.get('status'):
            filters_applied.append(f"Status: {request.form.get('status')}")
        if request.form.get('setor'):
            filters_applied.append(f"Setor: {request.form.get('setor')}")

        rendered_html = render_template(
            'report_pdf_template.html',
            bookings=bookings,
            filters_applied=filters_applied,
            current_date=datetime.now().strftime('%d/%m/%Y %H:%M')
        )

        pdf = HTML(string=rendered_html).write_pdf()

        filename = f"agendamentos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(
            io.BytesIO(pdf),
            download_name=filename,
            as_attachment=True,
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"Erro ao gerar PDF: {str(e)}")
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# --- CLI Commands ---

@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and initial data."""
    db.create_all()
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=True)
        admin.set_password('admin')
        admin.email = 'ti@colegiopanorama.com.br' # Adiciona um email padrão
        db.session.add(admin)
        print('Admin user created.')

    # Create regular user if not exists
    if not User.query.filter_by(username='user').first():
        user = User(username='user', is_admin=False)
        user.set_password('user')
        user.email = 'handerson@colegiopanorama.com.br' # Adiciona um email padrão
        db.session.add(user)
        print('Regular user created.')

    # Create regular financeiro if not exists
    if not User.query.filter_by(username='financeiro').first():
        financeiro = User(username='financeiro', is_admin=False, perfil='financeiro')
        financeiro.set_password('financeiro')
        financeiro.email = 'financeiro@colegiopanorama.com.br'
        db.session.add(financeiro)
        print('Usuário financeiro criado.')


    # Add default config values if they don't exist
    if not Canal.query.first():
        db.session.add_all([Canal(nome='Telefone'), Canal(nome='Email'), Canal(nome='Presencial'), Canal(nome='WhatsApp')])
        print('Default canais created.')
    if not Setor.query.first():
        db.session.add_all([Setor(nome='Comercial'), Setor(nome='Acadêmico'), Setor(nome='Financeiro'), Setor(nome='Fund. Anos Iniciais'), Setor(nome='Fund. Anos Finais'),Setor(nome='Ensino Médio')])
        print('Default setores created.')
    if not Categoria.query.first():
        db.session.add_all([Categoria(nome='Matrícula'), Categoria(nome='Bolsa'), Categoria(nome='Cancelamento'), Categoria(nome='Intervenção Psicologia'), Categoria(nome='Agendamento Coordenação')])
        print('Default categorias created.')

    # Add default statuses if they don't exist
    if not Status.query.first():
        db.session.add_all([
            Status(nome='Aberto-Coordenação'),
            Status(nome='Em andamento-Coordenação'),
            Status(nome='Remarcado-Coordenação'),
            Status(nome='Apto-Coordenação'),
            Status(nome='Não-Apto-Coordenação'),
            Status(nome='Apto-Financeiro'),
            Status(nome='Não-Apto-Financeiro'),
            Status(nome='Concluído-Secretaria'),

        ])
        print('Default statuses created.')

    db.session.commit()
    print("Database initialized.")
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)