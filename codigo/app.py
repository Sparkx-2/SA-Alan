
from flask import Flask, request, session, redirect, render_template, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from urllib.parse import quote

app = Flask(__name__, template_folder="../interface", static_folder="../static")

app.secret_key = "chave_temporaria_123"

usuarios = {}
historicos = {}
avaliacoes = {}


# Página inicial
@app.route("/")
def home():
    return render_template("index.html")


# Verifica se existe usuário logado
def usuario_logado():
    return "username" in session


# Cadastro
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if not username or not senha:
            flash("Preencha todos os campos.")
            return redirect(url_for("cadastro"))

        if username in usuarios:
            flash("Esse usuário já existe.")
            return redirect(url_for("cadastro"))

        usuarios[username] = generate_password_hash(senha)
        historicos[username] = []
        avaliacoes[username] = {}

        flash("Cadastro realizado com sucesso!")
        return redirect(url_for("login"))

    return render_template("cadastro.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if not username or not senha:
            flash("Preencha todos os campos.")
            return redirect(url_for("login"))

        if username not in usuarios:
            flash("Usuário não encontrado.")
            return redirect(url_for("login"))

        hash_senha = usuarios[username]

        if not check_password_hash(hash_senha, senha):
            flash("Senha incorreta.")
            return redirect(url_for("login"))

        session["username"] = username

        flash("Login realizado com sucesso!")
        return redirect(url_for("home"))

    return render_template("login.html")


# Logout
@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Você saiu da sua conta.")
    return redirect(url_for("home"))


# Pesquisa de filmes e séries
@app.route("/pesquisar", methods=["GET", "POST"])
def pesquisar():
    if not usuario_logado():
        flash("Você precisa fazer login primeiro.")
        return redirect(url_for("login"))

    if request.method == "POST":
        conteudo = request.form.get("conteudo", "").strip()

        if not conteudo:
            flash("Digite o nome de um filme ou série.")
            return redirect(url_for("home"))

        username = session["username"]

        historicos[username].append({
            "conteudo": conteudo,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M")
        })

        return redirect(
            "https://pluto.tv/search/details?query=" + quote(conteudo)
        )

    return redirect(url_for("home"))


# Histórico
@app.route("/historico")
def historico():
    if not usuario_logado():
        flash("Você precisa fazer login.")
        return redirect(url_for("login"))

    username = session["username"]

    return render_template(
        "historico.html",
        username=username,
        registros=historicos[username],
        avaliacoes=avaliacoes[username]
    )


# Avaliação de filmes e séries
@app.route("/avaliar", methods=["POST"])
def avaliar():
    if not usuario_logado():
        flash("Você precisa fazer login.")
        return redirect(url_for("login"))

    username = session["username"]
    conteudo = request.form.get("conteudo", "").strip()
    nota = request.form.get("nota", "").strip()

    if not conteudo or not nota:
        flash("Informe o conteúdo e a nota.")
        return redirect(url_for("historico"))

    if not any(
        item["conteudo"] == conteudo
        for item in historicos[username]
    ):
        flash("Você precisa pesquisar esse conteúdo antes de avaliá-lo.")
        return redirect(url_for("historico"))

    try:
        nota = int(nota)
    except ValueError:
        flash("A nota precisa ser um número.")
        return redirect(url_for("historico"))

    if nota < 1 or nota > 5:
        flash("A nota deve ser entre 1 e 5.")
        return redirect(url_for("historico"))

    avaliacoes[username][conteudo] = nota

    flash("Avaliação registrada com sucesso!")
    return redirect(url_for("historico"))


# Página de pesquisa de usuários
@app.route("/buscar_usuarios")
def pagina_buscar_usuarios():
    if not usuario_logado():
        flash("Você precisa fazer login primeiro.")
        return redirect(url_for("login"))

    return render_template("buscar_usuarios.html")


# Processamento da pesquisa de usuários
@app.route("/buscar_usuario", methods=["POST"])
def buscar_usuario():
    if not usuario_logado():
        flash("Você precisa fazer login primeiro.")
        return redirect(url_for("login"))

    username = request.form.get("username", "").strip()

    if not username:
        flash("Digite o nome do usuário.")
        return redirect(url_for("pagina_buscar_usuarios"))

    if username not in usuarios:
        flash("Usuário não encontrado.")
        return redirect(url_for("pagina_buscar_usuarios"))

    return redirect(url_for("perfil", username=username))


# Perfil público
@app.route("/perfil/<username>")
def perfil(username):
    if username not in usuarios:
        return "Usuário não encontrado.", 404

    return render_template(
        "perfil.html",
        username=username,
        registros=historicos[username],
        avaliacoes=avaliacoes[username]
    )


if __name__ == "__main__":
    print("\nROTAS REGISTRADAS:")
    print(app.url_map)

    app.run(debug=True, use_reloader=False)
