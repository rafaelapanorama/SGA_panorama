from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Canal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

class Setor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

# class User(UserMixin, db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(150), unique=True, nullable=False)
#     email = db.Column(db.String(150), unique=True, nullable=False)
#     password_hash = db.Column(db.String(128), nullable=False)
#     is_admin = db.Column(db.Boolean, default=False)

#     def set_password(self, password):
#         self.password_hash = generate_password_hash(password)

#     def check_password(self, password):
#         return check_password_hash(self.password_hash, password)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    email = db.Column(db.String(150), unique=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    perfil = db.Column(db.String(50), default='user')  # <-- Novo campo
    setor = db.Column(db.String(100))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f'<Status {self.nome}>'

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    canal = db.Column(db.String(100), nullable=False)
    nome_responsavel_2 = db.Column(db.String(150), nullable=False)
    nome_responsavel_1 = db.Column(db.String(150), nullable=False)
    cpf_responsavel_1 = db.Column(db.String(11), nullable=False)
    cpf_responsavel_2 = db.Column(db.String(11), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Agendado')
    setor = db.Column(db.String(100), nullable=False)
    aluno = db.Column(db.String(150))
    escolaAluno = db.Column(db.String(255)) 
    motivo = db.Column(db.Text)
    data_agendamento = db.Column(db.Date, nullable=False)
    horario = db.Column(db.Time, nullable=False)
    coordenador = db.Column(db.String(150))
    observacao = db.Column(db.Text)


