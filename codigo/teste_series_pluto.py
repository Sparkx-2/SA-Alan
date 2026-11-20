
import requests
import uuid


# Configuracoes da API
URL_BOOT = "https://boot.pluto.tv/v4/start"
URL_CATALOGO = "https://api.pluto.tv/v3/vod/categories"
URL_TEMPORADAS = "https://api.pluto.tv/v3/vod/series/{}/seasons"

HEADERS = {
    "Origin": "https://pluto.tv",
    "Referer": "https://pluto.tv/",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


def iniciar_sessao():
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

    resposta = requests.get(
        URL_BOOT,
        params=parametros,
        headers=HEADERS,
        timeout=30
    )

    resposta.raise_for_status()

    dados = resposta.json()
    token = dados.get("sessionToken")

    if not token:
        raise ValueError("O Pluto TV nao retornou o token.")

    print("Sessao iniciada com sucesso!")

    return token


def encontrar_series(dados, resultados=None):
    if resultados is None:
        resultados = {}

    if isinstance(dados, dict):

        identificador = dados.get("_id")
        nome = dados.get("name")
        tipo = str(dados.get("type", "")).lower()

        if identificador and nome and tipo == "series":
            resultados[identificador] = {
                "id": identificador,
                "nome": nome
            }

        for valor in dados.values():
            encontrar_series(valor, resultados)

    elif isinstance(dados, list):
        for item in dados:
            encontrar_series(item, resultados)

    return list(resultados.values())


def main():
    try:
        # Inicia a sessao
        token = iniciar_sessao()

        headers_catalogo = {
            **HEADERS,
            "Authorization": f"Bearer {token}"
        }

        # Consulta o catalogo
        parametros = {
            "includeItems": "true",
            "deviceType": "web"
        }

        print("\nConsultando catalogo...")

        resposta = requests.get(
            URL_CATALOGO,
            params=parametros,
            headers=headers_catalogo,
            timeout=60
        )

        resposta.raise_for_status()

        catalogo = resposta.json()

        # Encontra as series
        series = encontrar_series(catalogo)

        print(f"\nTotal de series encontradas: {len(series)}")

        if not series:
            print("Nenhuma serie encontrada no catalogo.")
            return

        print("\n========== PRIMEIRAS SERIES ==========")

        for indice, serie in enumerate(series[:15], start=1):
            print(f"{indice}. {serie['nome']}")
            print(f"   ID: {serie['id']}")

        # Testa a consulta de temporadas
        serie = series[0]

        print("\n========== TESTE DE TEMPORADAS ==========")
        print(f"Serie escolhida: {serie['nome']}")

        url = URL_TEMPORADAS.format(serie["id"])

        resposta_temporadas = requests.get(
            url,
            params={
                "includeItems": "true",
                "deviceType": "web"
            },
            headers=headers_catalogo,
            timeout=60
        )

        print(f"Status HTTP: {resposta_temporadas.status_code}")

        resposta_temporadas.raise_for_status()

        temporadas = resposta_temporadas.json()

        print("\nTipo de resposta:", type(temporadas).__name__)

        if isinstance(temporadas, dict):
            print("Chaves recebidas:", list(temporadas.keys()))

        elif isinstance(temporadas, list):
            print("Quantidade de registros:", len(temporadas))

        print("\n========== RESPOSTA DA API ==========")
        print(str(temporadas)[:5000])

        # URL candidata para abrir a serie
        url_serie = (
            "https://pluto.tv/br/on-demand/series/"
            f"{serie['id']}/season/1"
        )

        print("\n========== URL CANDIDATA ==========")
        print(url_serie)

    except requests.RequestException as erro:
        print("\nErro na comunicacao com o Pluto TV:")
        print(erro)

    except (ValueError, TypeError, KeyError) as erro:
        print("\nErro ao interpretar a resposta:")
        print(erro)


if __name__ == "__main__":
    main()
