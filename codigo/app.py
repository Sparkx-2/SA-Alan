
from flask import Flask, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from urllib.parse import quote

app = Flask(__name__)
"""
    No momento ele esta usando dicionarios pq queria testa as rotas no 
    terminal do python. Depois sera incrementado SQL.
"""
app.secret_key = "chave_temporaria_123"

usuarios = {}
historicos = {}
avaliacoes = {}

@app.route("/")
def home():
    return "Hello, World!"

def usuario_logado():
    return "username" in session

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if not username or not senha:
            return "Preencha todos os campos."

        if username in usuarios:
            return "Esse usuário já existe."

        usuarios[username] = generate_password_hash(senha)
        historicos[username] = []
        avaliacoes[username] = {}

        return "Cadastro realizado com sucesso!"

    return "Página de cadastro"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if not username or not senha:
            return "Preencha todos os campos."

        if username not in usuarios:
            return "Usuário não encontrado."

        hash_senha = usuarios[username]

        if not check_password_hash(hash_senha, senha):
            return "Senha incorreta."

        session["username"] = username

        return "Login realizado com sucesso!"

    return "Página de login"

@app.route("/logout")
def logout():
    session.pop("username", None)
    return "Você saiu da sua conta."

@app.route("/pesquisar", methods=["GET", "POST"])
def pesquisar():
    if not usuario_logado():
        return "Você precisa fazer login primeiro."

    if request.method == "POST":
        conteudo = request.form.get("conteudo", "").strip()

        if not conteudo:
            return "Digite o nome de um filme ou série."

        username = session["username"]

        historicos[username].append({
            "conteudo": conteudo,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M")
        })

        return redirect(
            "https://pluto.tv/search/details?query=" + quote(conteudo)
        )

    return "Página de pesquisa"

@app.route("/historico")
def historico():
    if not usuario_logado():
        return "Você precisa fazer login."

    username = session["username"]
    registros = historicos[username]

    if not registros:
        return "Seu histórico está vazio."

    resultado = f"Histórico de {username}:\n"

    for item in registros:
        resultado += f"- {item['conteudo']} | {item['data']}\n"

    return resultado

@app.route("/avaliar", methods=["POST"])
def avaliar():
    if not usuario_logado():
        return "Você precisa fazer login."

    username = session["username"]
    conteudo = request.form.get("conteudo", "").strip()
    nota = request.form.get("nota", "").strip()

    if not conteudo or not nota:
        return "Informe o conteúdo e a nota."

    if not any(
        item["conteudo"] == conteudo
        for item in historicos[username]
    ):
        return "Você precisa pesquisar esse conteúdo antes de avaliá-lo."

    try:
        nota = int(nota)
    except ValueError:
        return "A nota precisa ser um número."

    if nota < 1 or nota > 5:
        return "A nota deve ser entre 1 e 5."

    avaliacoes[username][conteudo] = nota

    return "Avaliação registrada com sucesso!"

@app.route("/perfil/<username>")
def perfil(username):
    if username not in usuarios:
        return "Usuário não encontrado."

    resultado = f"Perfil de {username}\n"
    resultado += "\nHistórico:\n"

    for item in historicos[username]:
        conteudo = item["conteudo"]
        nota = avaliacoes[username].get(
            conteudo,
            "Sem avaliação"
        )

        resultado += f"- {conteudo} | Nota: {nota}\n"

    return resultado

if __name__ == "__main__":
    app.run(debug=True)
