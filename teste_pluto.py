
import requests
import uuid
import unicodedata


# Dados para iniciar uma sessao no Pluto TV
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


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return texto.casefold().strip()


def encontrar_filmes(dados, resultados=None):

    if resultados is None:
        resultados = {}

    if isinstance(dados, dict):

        if (
            "_id" in dados
            and "name" in dados
            and dados.get("type") == "movie"
        ):
            resultados[dados["_id"]] = dados

        for valor in dados.values():
            encontrar_filmes(valor, resultados)

    elif isinstance(dados, list):

        for item in dados:
            encontrar_filmes(item, resultados)

    return list(resultados.values())


try:

    # Inicia uma sessao
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
        raise Exception("O Pluto nao retornou um token de sessao.")

    print("Sessao iniciada com sucesso!")

    # Consulta o catalogo
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
        timeout=30
    )

    resposta_catalogo.raise_for_status()

    catalogo = resposta_catalogo.json()

    print("Catalogo recebido com sucesso!")

    filmes = encontrar_filmes(catalogo)

    print(f"\nQuantidade de filmes encontrados: {len(filmes)}")

    # Procura palavras relacionadas ao titulo
    termos = [
        "lord",
        "rings",
        "senhor",
        "aneis"
    ]

    encontrados = []

    for filme in filmes:

        nome = normalizar(filme["name"])

        if any(termo in nome for termo in termos):
            encontrados.append(filme)

    print("\n========== TITULOS RELACIONADOS ==========")

    if encontrados:

        for filme in encontrados:

            url_filme = (
                "https://pluto.tv/br/on-demand/movies/"
                + filme["_id"]
                + "/details"
            )

            print("\nNome:", filme["name"])
            print("ID:", filme["_id"])
            print("URL:", url_filme)

    else:
        print("Nenhum titulo relacionado encontrado.")

    # Mostra alguns titulos para conferir o catalogo
    print("\n========== PRIMEIROS 30 FILMES ==========")

    for indice, filme in enumerate(filmes[:30], start=1):
        print(f"{indice}. {filme['name']}")


except requests.RequestException as erro:

    print("\nErro na comunicacao com o Pluto:")
    print(erro)


except Exception as erro:

    print("\nErro durante o teste:")
    print(erro)
