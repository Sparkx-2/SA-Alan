
from flask import (
    Flask,
    request,
    session,
    redirect,
    render_template,
    url_for,
    flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from datetime import datetime

import sqlite3
import os
import requests
import uuid
import unicodedata


# ==========================================
# CONFIGURACAO DO BANCO DE DADOS
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

caminho_banco = os.path.join(
    BASE_DIR,
    "banco_de_dados",
    "streaming.db"
)


def conectar_banco():
    conexao = sqlite3.connect(caminho_banco)
    conexao.execute("PRAGMA foreign_keys = ON")

    return conexao


def criar_tabelas():
    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_usuario VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                conteudo TEXT NOT NULL,
                data TEXT NOT NULL,

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS avaliacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                conteudo TEXT NOT NULL,
                nota INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id),

                UNIQUE (usuario_id, conteudo)
            )
        """)

        conexao.commit()

    finally:
        conexao.close()


# ==========================================
# CONFIGURACAO DO FLASK
# ==========================================

app = Flask(
    __name__,
    template_folder="../interface",
    static_folder="../static"
)

app.secret_key = "chave_temporaria_123"


# ==========================================
# FUNCOES AUXILIARES
# ==========================================

def usuario_logado():
    return "username" in session


def normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto))

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return texto.casefold().strip()


# ==========================================
# INTEGRACAO COM O PLUTO TV
# ==========================================

def encontrar_conteudos(dados, resultados=None):
    # Identifica filmes e series dentro da resposta do catalogo

    if resultados is None:
        resultados = {}

    if isinstance(dados, dict):

        identificador = dados.get("_id")
        nome = dados.get("name")
        tipo = str(dados.get("type", "")).lower()

        if (
            identificador
            and nome
            and tipo in ("movie", "series")
        ):
            resultados[identificador] = {
                "id": identificador,
                "nome": nome,
                "tipo": tipo
            }

        for valor in dados.values():
            encontrar_conteudos(valor, resultados)

    elif isinstance(dados, list):

        for item in dados:
            encontrar_conteudos(item, resultados)

    return list(resultados.values())


def montar_url_pluto(conteudo):
    # Monta o endereco conforme o tipo de conteudo

    identificador = conteudo["id"]
    tipo = conteudo["tipo"]

    if tipo == "movie":
        return (
            "https://pluto.tv/br/on-demand/movies/"
            f"{identificador}/details"
        )

    if tipo == "series":
        return (
            "https://pluto.tv/br/on-demand/series/"
            f"{identificador}/season/1"
        )

    return None


def buscar_conteudos_pluto(pesquisa):
    # Inicia uma sessao no Pluto TV

    url_boot = "https://boot.pluto.tv/v4/start"

    parametros = {
        "appName": "web",
        "appVersion": "8.0.0",
        "deviceVersion": "1.0.0",
        "deviceModel": "web",
        "deviceMake": "chrome",
        "deviceType": "web",
        "clientID": str(uuid.uuid4()),
        "clientModelNumber": "1.0.0",
        "serverSideAds": "false",
        "drmCapabilities": "widevine:L3",
        "blockingMode": ""
    }

    headers = {
        "Origin": "https://pluto.tv",
        "Referer": "https://pluto.tv/",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        resposta = requests.get(
            url_boot,
            params=parametros,
            headers=headers,
            timeout=20
        )

        resposta.raise_for_status()

        dados_boot = resposta.json()
        token = dados_boot.get("sessionToken")

        if not token:
            return None, "Nao foi possivel iniciar uma sessao no Pluto TV."

        # Consulta o catalogo de filmes e series

        url_catalogo = "https://api.pluto.tv/v3/vod/categories"

        parametros_catalogo = {
            "includeItems": "true",
            "deviceType": "web"
        }

        headers_catalogo = {
            **headers,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        resposta_catalogo = requests.get(
            url_catalogo,
            params=parametros_catalogo,
            headers=headers_catalogo,
            timeout=60
        )

        resposta_catalogo.raise_for_status()

        catalogo = resposta_catalogo.json()

        # Extrai filmes e series

        conteudos = encontrar_conteudos(catalogo)

        termo = normalizar(pesquisa)

        # Procura titulos que contenham o termo pesquisado

        resultados = [
            conteudo
            for conteudo in conteudos
            if termo in normalizar(conteudo["nome"])
        ]

        if not resultados:
            return None, "Titulo nao encontrado no catalogo consultado do Pluto TV."

        # Organiza os resultados por relevancia

        resultados.sort(
            key=lambda conteudo: (
                normalizar(conteudo["nome"]) != termo,
                not normalizar(conteudo["nome"]).startswith(termo),
                len(conteudo["nome"])
            )
        )

        # Se houver apenas uma correspondencia exata,
        # abre diretamente esse conteudo

        exatos = [
            conteudo
            for conteudo in resultados
            if normalizar(conteudo["nome"]) == termo
        ]

        if len(exatos) == 1:
            resultados = exatos

        # Se houver somente um resultado, nao precisa
        # apresentar uma pagina de selecao

        if len(resultados) == 1:
            conteudo = resultados[0]

            return [{
                "id": conteudo["id"],
                "nome": conteudo["nome"],
                "tipo": conteudo["tipo"],
                "url": montar_url_pluto(conteudo)
            }], None

        # Prepara os resultados para a pagina de escolha

        opcoes = []

        for conteudo in resultados[:20]:
            opcoes.append({
                "id": conteudo["id"],
                "nome": conteudo["nome"],
                "tipo": conteudo["tipo"],
                "url": montar_url_pluto(conteudo)
            })

        return opcoes, None

    except requests.RequestException:
        return None, "Nao foi possivel conectar ao Pluto TV. Tente novamente mais tarde."

    except (ValueError, KeyError, TypeError):
        return None, "O Pluto TV retornou uma resposta inesperada."


# ==========================================
# PAGINA INICIAL
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# CADASTRO DE USUARIOS
# ==========================================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")
        email = request.form.get("email", "").strip()

        if not username or not senha or not email:
            flash("Preencha todos os campos.")
            return redirect(url_for("cadastro"))

        conexao = conectar_banco()
        cursor = conexao.cursor()

        try:
            cursor.execute("""
                SELECT id
                FROM usuarios
                WHERE nome_usuario = ? OR email = ?
            """, (username, email))

            usuario_existente = cursor.fetchone()

            if usuario_existente is not None:
                flash("Esse nome de usuario ou email ja esta cadastrado.")
                return redirect(url_for("cadastro"))

            hash_senha = generate_password_hash(senha)

            cursor.execute("""
                INSERT INTO usuarios (
                    nome_usuario,
                    email,
                    senha_hash
                )
                VALUES (?, ?, ?)
            """, (username, email, hash_senha))

            conexao.commit()

            flash("Cadastro realizado com sucesso!")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conexao.rollback()
            flash("Nao foi possivel realizar o cadastro. Verifique os dados.")
            return redirect(url_for("cadastro"))

        finally:
            conexao.close()

    return render_template("cadastro.html")


# ==========================================
# LOGIN DE USUARIOS
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if not username or not senha:
            flash("Preencha todos os campos.")
            return redirect(url_for("login"))

        conexao = conectar_banco()
        cursor = conexao.cursor()

        try:
            cursor.execute("""
                SELECT id, senha_hash
                FROM usuarios
                WHERE nome_usuario = ?
            """, (username,))

            usuario = cursor.fetchone()

            if usuario is None:
                flash("Usuario nao encontrado.")
                return redirect(url_for("login"))

            usuario_id = usuario[0]
            hash_senha = usuario[1]

            if not check_password_hash(hash_senha, senha):
                flash("Senha incorreta.")
                return redirect(url_for("login"))

            session["username"] = username
            session["usuario_id"] = usuario_id

            flash("Login realizado com sucesso!")
            return redirect(url_for("home"))

        finally:
            conexao.close()

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.pop("username", None)
    session.pop("usuario_id", None)
    session.pop("resultados_pluto", None)

    flash("Voce saiu da sua conta.")

    return redirect(url_for("home"))


# ==========================================
# PESQUISA DE FILMES E SERIES
# ==========================================

@app.route("/pesquisar", methods=["GET", "POST"])
def pesquisar():

    if not usuario_logado():
        flash("Voce precisa fazer login primeiro.")
        return redirect(url_for("login"))

    if request.method == "POST":

        conteudo = request.form.get("conteudo", "").strip()

        if not conteudo:
            flash("Digite o nome de um filme ou serie.")
            return redirect(url_for("home"))

        usuario_id = session["usuario_id"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        try:
            # Registra a pesquisa no historico

            cursor.execute("""
                INSERT INTO historico (
                    usuario_id,
                    conteudo,
                    data
                )
                VALUES (?, ?, ?)
            """, (
                usuario_id,
                conteudo,
                datetime.now().strftime("%d/%m/%Y %H:%M")
            ))

            conexao.commit()

        finally:
            conexao.close()

        # Pesquisa filmes e series no catalogo

        resultados, erro = buscar_conteudos_pluto(conteudo)

        if erro:
            flash(erro)
            return redirect(url_for("home"))

        # Se houver apenas um resultado, abre diretamente

        if len(resultados) == 1:
            return redirect(resultados[0]["url"])

        # Guarda as opcoes na sessao para a escolha do usuario

        session["resultados_pluto"] = resultados

        return render_template(
            "resultados_pluto.html",
            pesquisa=conteudo,
            resultados=resultados
        )

    return redirect(url_for("home"))


# ==========================================
# SELECAO DO CONTEUDO ENCONTRADO
# ==========================================

@app.route("/selecionar_conteudo", methods=["POST"])
def selecionar_conteudo():

    if not usuario_logado():
        flash("Voce precisa fazer login primeiro.")
        return redirect(url_for("login"))

    resultados = session.get("resultados_pluto", [])

    indice = request.form.get("indice", "")

    try:
        indice = int(indice)

    except ValueError:
        flash("Selecao invalida.")
        return redirect(url_for("home"))

    if indice < 0 or indice >= len(resultados):
        flash("O conteudo selecionado nao esta disponivel.")
        return redirect(url_for("home"))

    url_conteudo = resultados[indice].get("url")

    if not url_conteudo:
        flash("Nao foi possivel abrir esse conteudo.")
        return redirect(url_for("home"))

    # Limpa as opcoes armazenadas

    session.pop("resultados_pluto", None)

    return redirect(url_conteudo)


# ==========================================
# HISTORICO DE PESQUISAS
# ==========================================

@app.route("/historico")
def historico():

    if not usuario_logado():
        flash("Voce precisa fazer login.")
        return redirect(url_for("login"))

    username = session["username"]
    usuario_id = session["usuario_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT conteudo, data
            FROM historico
            WHERE usuario_id = ?
            ORDER BY id DESC
        """, (usuario_id,))

        resultados = cursor.fetchall()

        registros = [
            {
                "conteudo": linha[0],
                "data": linha[1]
            }
            for linha in resultados
        ]

        cursor.execute("""
            SELECT conteudo, nota
            FROM avaliacoes
            WHERE usuario_id = ?
        """, (usuario_id,))

        resultados_avaliacoes = cursor.fetchall()

        avaliacoes = {
            linha[0]: linha[1]
            for linha in resultados_avaliacoes
        }

    finally:
        conexao.close()

    return render_template(
        "historico.html",
        username=username,
        registros=registros,
        avaliacoes=avaliacoes
    )


# ==========================================
# AVALIACAO DE FILMES E SERIES
# ==========================================

@app.route("/avaliar", methods=["POST"])
def avaliar():

    if not usuario_logado():
        flash("Voce precisa fazer login.")
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]

    conteudo = request.form.get("conteudo", "").strip()
    nota = request.form.get("nota", "").strip()

    if not conteudo or not nota:
        flash("Informe o conteudo e a nota.")
        return redirect(url_for("historico"))

    try:
        nota = int(nota)

    except ValueError:
        flash("A nota precisa ser um numero.")
        return redirect(url_for("historico"))

    if nota < 1 or nota > 5:
        flash("A nota deve ser entre 1 e 5.")
        return redirect(url_for("historico"))

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT id
            FROM historico
            WHERE usuario_id = ? AND conteudo = ?
            LIMIT 1
        """, (usuario_id, conteudo))

        registro = cursor.fetchone()

        if registro is None:
            flash("Voce precisa pesquisar esse conteudo antes de avalia-lo.")
            return redirect(url_for("historico"))

        cursor.execute("""
            INSERT INTO avaliacoes (
                usuario_id,
                conteudo,
                nota
            )
            VALUES (?, ?, ?)

            ON CONFLICT(usuario_id, conteudo)
            DO UPDATE SET nota = excluded.nota
        """, (usuario_id, conteudo, nota))

        conexao.commit()

        flash("Avaliacao registrada com sucesso!")
        return redirect(url_for("historico"))

    finally:
        conexao.close()


# ==========================================
# PAGINA DE PESQUISA DE USUARIOS
# ==========================================

@app.route("/buscar_usuarios")
def pagina_buscar_usuarios():

    if not usuario_logado():
        flash("Voce precisa fazer login primeiro.")
        return redirect(url_for("login"))

    return render_template("buscar_usuarios.html")


# ==========================================
# PROCESSAMENTO DA PESQUISA DE USUARIOS
# ==========================================

@app.route("/buscar_usuario", methods=["POST"])
def buscar_usuario():

    if not usuario_logado():
        flash("Voce precisa fazer login primeiro.")
        return redirect(url_for("login"))

    username = request.form.get("username", "").strip()

    if not username:
        flash("Digite o nome do usuario.")
        return redirect(url_for("pagina_buscar_usuarios"))

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT id
            FROM usuarios
            WHERE nome_usuario = ?
        """, (username,))

        usuario = cursor.fetchone()

    finally:
        conexao.close()

    if usuario is None:
        flash("Usuario nao encontrado.")
        return redirect(url_for("pagina_buscar_usuarios"))

    return redirect(url_for("perfil", username=username))


# ==========================================
# PERFIL PUBLICO
# ==========================================

@app.route("/perfil/<username>")
def perfil(username):

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT id
            FROM usuarios
            WHERE nome_usuario = ?
        """, (username,))

        usuario = cursor.fetchone()

        if usuario is None:
            return "Usuario nao encontrado.", 404

        usuario_id = usuario[0]

        cursor.execute("""
            SELECT conteudo, data
            FROM historico
            WHERE usuario_id = ?
            ORDER BY id DESC
        """, (usuario_id,))

        resultados = cursor.fetchall()

        registros = [
            {
                "conteudo": linha[0],
                "data": linha[1]
            }
            for linha in resultados
        ]

        cursor.execute("""
            SELECT conteudo, nota
            FROM avaliacoes
            WHERE usuario_id = ?
        """, (usuario_id,))

        resultados_avaliacoes = cursor.fetchall()

        avaliacoes = {
            linha[0]: linha[1]
            for linha in resultados_avaliacoes
        }

    finally:
        conexao.close()

    return render_template(
        "perfil.html",
        username=username,
        registros=registros,
        avaliacoes=avaliacoes
    )


# ==========================================
# INICIALIZACAO DO SISTEMA
# ==========================================

if __name__ == "__main__":

    criar_tabelas()

    print("\nROTAS REGISTRADAS:")
    print(app.url_map)

    app.run(
        debug=True,
        use_reloader=False
    )
