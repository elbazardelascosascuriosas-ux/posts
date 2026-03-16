# generador_post_series_peliculas.py
# Programa para generar posts de series/películas en formato foro
# Extrae datos de Filmaffinity.com (en español)
# Limpieza estricta: sin "Serie", "Miniserie", "TV", etc. en título ni título original
# Ficha sin puntos ni alineaciones con ....
# Incluye sección fija "Datos del Video"

import requests
from bs4 import BeautifulSoup
import os
import re
import time
import json

IDIOMA_DEFAULT = "CASTELLANO"
RIPEADOR_DEFAULT = "MattDrayton"
SERVIDOR_DEFAULT = "MEGA"

# ── TheTVDB v4 ── (cámbialos por tus valores reales)
TVDB_API_KEY = "TU_API_KEY_DE_PROYECTO_AQUI"  # ← obligatoria
TVDB_PIN = "TU_PIN_DE_SUSCRIPTOR_AQUI"  # ← si no estás suscrito, pon "" y fallará

headers_web = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def obtener_token_tvdb():
    if not TVDB_API_KEY:
        print("No hay API_KEY configurada para TheTVDB.")
        return None

    url = "https://api4.thetvdb.com/v4/login"
    payload = {"apikey": TVDB_API_KEY}
    if TVDB_PIN:
        payload["pin"] = TVDB_PIN

    try:
        r = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}, timeout=10
        )
        r.raise_for_status()
        return r.json()["data"]["token"]
    except Exception as e:
        print(f"Error al obtener token TheTVDB: {e}")
        return None


def buscar_serie_tvdb(token, query):
    if not token:
        return None

    url = f"https://api4.thetvdb.com/v4/search?query={query}&type=series&language=spa"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        results = r.json().get("data", [])
        if results:
            return results[0]["id"]  # primera coincidencia
    except:
        pass
    return None


def obtener_episodios_tvdb(token, serie_id):
    if not token or not serie_id:
        return {}

    episodios_por_temp = {}
    headers = {"Authorization": f"Bearer {token}"}

    # Primero obtenemos el número de temporadas (de /series/{id})
    try:
        url_series = f"https://api4.thetvdb.com/v4/series/{serie_id}?language=spa"
        r = requests.get(url_series, headers=headers, timeout=10)
        r.raise_for_status()
        num_temps = r.json()["data"].get("numberOfSeasons", 1)
    except:
        num_temps = 5  # fallback razonable

    for temp in range(1, num_temps + 1):
        url = f"https://api4.thetvdb.com/v4/series/{serie_id}/episodes?season={temp}&language=spa"
        try:
            time.sleep(1.2)  # anti-rate-limit
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                break
            data = r.json()
            episodios = data.get("data", {}).get("episodes", [])
            lista = []
            for ep in episodios:
                num = ep.get("number", 0)
                titulo = ep.get("name", "Sin título")
                if titulo != "Sin título":
                    lista.append(f"{num:02d} - {titulo}")
            if lista:
                episodios_por_temp[f"T{temp}"] = lista
        except:
            break

    return episodios_por_temp


def buscar_filmaffinity(query):
    search_url = f"https://www.filmaffinity.com/es/search.php?stext={query.replace(' ', '%20')}&stype=title"
    try:
        response = requests.get(search_url, headers=headers_web, timeout=10)
        response.raise_for_status()
    except:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    results = soup.find_all("div", class_="mc-info-container")

    for r in results:
        link = r.find("a")
        if link and link.get("href"):
            href = link["href"]
            if href.startswith("http"):
                return href
            else:
                return "https://www.filmaffinity.com" + href
    return None


def extraer_ficha_filmaffinity(url):
    try:
        response = requests.get(url, headers=headers_web, timeout=12)
        response.raise_for_status()
    except:
        return {"titulo": "No disponible", "titulo_original": "No disponible"}

    soup = BeautifulSoup(response.text, "html.parser")
    data = {}

    basura = [
        "Serie de TV",
        "TV Series",
        "Miniserie de TV",
        "TV Miniseries",
        "Miniseries",
        "Serie",
        "Miniserie",
        "Series",
        "Serie-TV",
        "TV",
        "Animation",
        "Anime",
        "(Miniserie)",
        "(Serie)",
        "(TV)",
        "–",
        ":",
        "  ",
        "(2024)",
        "(2025)",
        "(2026)",
    ]

    titulo_tag = soup.find("h1")
    if titulo_tag:
        t = titulo_tag.get_text(" ", strip=True)
        for b in basura:
            t = t.replace(b, "")
        t = re.sub(r"\([^)]*\)", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        t = t.strip("-:").strip()
        data["titulo"] = t if t else "Sin título"
    else:
        data["titulo"] = "Sin título"

    sinopsis_tag = soup.select_one('[itemprop="description"]')
    data["sinopsis"] = sinopsis_tag.text.strip() if sinopsis_tag else "No disponible"

    rating = soup.select_one("#movie-rat-avg")
    data["rating"] = rating.text.strip() if rating else "No disponible"

    ficha = soup.find("dl", class_="movie-info")
    if ficha:
        dts = ficha.find_all("dt")
        dds = ficha.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.text.strip().lower().replace(":", "").strip()
            val = dd.get_text(" ", strip=True).replace("\n", " ").strip()
            data[key] = val

    titulo_orig = data.get("titulo original", "")
    if titulo_orig:
        to = titulo_orig.strip()
        for b in basura:
            to = to.replace(b, "")
        to = re.sub(r"\([^)]*\)", "", to)
        to = re.sub(r"\s+", " ", to).strip()
        to = to.strip("-:").strip()
        data["titulo_original"] = to if to else data["titulo"]
    else:
        data["titulo_original"] = data["titulo"]

    return data


def generar_post():
    print("\n=== GENERADOR DE POSTS FILMAFFINITY + TheTVDB ===\n")

    query = input("Título a buscar: ").strip()
    url = buscar_filmaffinity(query)

    if not url:
        print("No encontrado en búsqueda automática.")
        url = input("Introduce la URL de Filmaffinity manualmente: ").strip()

    if not url:
        print("No se proporcionó URL. Saliendo...")
        return

    print("URL utilizada:", url)
    print("Extrayendo datos...\n")

    data = extraer_ficha_filmaffinity(url)

    temporada = input("Temporada (ej: T1) [dejar vacío si es película]: ").strip()

    plataformas = {
        "1": "AMZN",
        "2": "NF",
        "3": "DSNP",
        "4": "ATVP",
        "5": "HMAX",
        "6": "PMTP",
        "7": "SKY",
        "8": "ITV",
        "9": "BBC",
        "10": "WEBRip",
    }

    print("\nSelecciona plataforma (o presiona ENTER para WEB):")
    for k, v in plataformas.items():
        print(f"{k} {v}")

    opcion_plataforma = input("\nNúmero: ").strip()
    plataforma = plataformas.get(opcion_plataforma, "WEB")

    resoluciones = {"1": "2160p", "2": "1080p"}

    print("\nSelecciona resolución:")
    for k, v in resoluciones.items():
        print(f"{k} {v}")

    opcion_res = input("\nNúmero: ").strip()
    resolucion_fuente = resoluciones.get(opcion_res, "1080p")

    fuente = f"{plataforma} WEB-DL {resolucion_fuente}"

    tamano = input("Tamaño total (ej: 3.5GB o 12.8GB): ").strip()
    epicom = input("Primer episodio (ej: 01): ").strip()
    epitotal = input("Total episodios (ej: 08): ").strip()

    idioma = input(f"Idioma [{IDIOMA_DEFAULT}]: ").strip().upper() or IDIOMA_DEFAULT
    servidor = (
        input(f"Servidor [{SERVIDOR_DEFAULT}]: ").strip().upper() or SERVIDOR_DEFAULT
    )
    ripeador = input(f"Ripeado por [{RIPEADOR_DEFAULT}]: ").strip() or RIPEADOR_DEFAULT

    resolucion = {
        "1": "3840×2160",
        "2": "3832×1920",
        "3": "2560×1440",
        "4": "1920×1080",
        "5": "1920x960",
    }

    print("\nSelecciona resolución:")
    for k, v in resolucion.items():
        print(f"{k} {v}")

    opcion_res = input("\nNúmero: ").strip()
    resolucionx = resolucion.get(opcion_res)

    tasabits = input(f"Tasa bits: ").strip()

    audiotack = {"1": "AC3 256Kbps 2 canales", "2": "EAC3 640Kbps 6 canales"}

    print("\nSelecciona resolución:")
    for k, v in audiotack.items():
        print(f"{k} {v}")

    opcion_res = input("\nNúmero: ").strip()
    audiostacks = audiotack.get(opcion_res)

    letritas = {"1": "SI forzados SI", "2": "NO"}

    print("\nSelecciona resolución:")
    for k, v in letritas.items():
        print(f"{k} {v}")

    opcion_res = input("\nNúmero: ").strip()
    subtitulos = letritas.get(opcion_res)

    mediainfo = input("\nPega MediaInfo (ENTER para omitir): ").strip()
    if not mediainfo:
        mediainfo = "MediaInfo no incluido"

    # ── TheTVDB: Intentar episodios automáticos ──
    episodios_por_temp = {}
    print("\nIntentando obtener episodios de TheTVDB...")
    token = obtener_token_tvdb()
    if token:
        serie_id = buscar_serie_tvdb(token, data.get("titulo", query))
        if serie_id:
            print(f"Serie encontrada en TheTVDB (ID: {serie_id})")
            episodios_por_temp = obtener_episodios_tvdb(token, serie_id)
        else:
            print("No se encontró la serie en TheTVDB.")
    else:
        print("No se pudo autenticar en TheTVDB (revisa API_KEY y PIN).")

    # Construir bloque de episodios
    if episodios_por_temp:
        episodios_block = '[HIDE="Lista de episodios por temporada"]\n'
        for temp, eps in episodios_por_temp.items():
            episodios_block += f"\n{temp} ({len(eps)} episodios)\n"
            for ep in eps:
                episodios_block += f"  {ep}\n"
        episodios_block += "[/HIDE]\n"
    else:
        episodios_block = """
[HIDE]
[CODE]
No se pudieron obtener los títulos automáticamente.
Puedes añadirlos manualmente aquí.
[/CODE]
[/HIDE]
"""

    temp_str = f" T{temporada}" if temporada else ""
    titulo_post = f"{data['titulo']}{temp_str} [{fuente}] [{idioma}] [{tamano}] [{epicom}/{epitotal}] [{servidor}]"

    ficha = f"""
Ficha Técnica
TÍTULO: {data.get('titulo', '—')}
TÍTULO ORIGINAL: {data.get('titulo_original', '—')}
TEMPORADA: {temporada or '—'}
CAPÍTULOS: {epitotal or '—'}
AÑO: {data.get('año', '—')}
PAÍS: {data.get('país', '—')}
DURACIÓN: {data.get('duración', '—')}
DIRECTOR: {data.get('dirección', '—')}
REPARTO: {data.get('reparto', '—')}
GÉNERO: {data.get('género', '—')}
RATING: {data.get('rating', '—')}
"""

    sinopsis = f"""
Sinopsis
{data.get('sinopsis', 'No disponible')}
"""

    ripeo = f"""
Datos del ripeo
Ripeado por: {ripeador}
Fuente: {fuente}
Servidor: {servidor}
"""

    datosvid = f"""
Datos del Video
Formato: Matroska
Video: High@L4 | {resolucionx} @ {tasabits} kb/s
Framerate: 25,000
Resolución: {resolucionx}
Audio: Castellano {audiostacks}
Subtitulos: {subtitulos}
"""

    spoiler = f"""
[SPOILER]
{mediainfo}
[/SPOILER]
"""

    post = f"""{titulo_post}

{ficha.strip()}

{sinopsis.strip()}

{ripeo.strip()}

{datosvid.strip()}

{spoiler}

{episodios_block}
"""

    safe_title = re.sub(r'[\\/*?:"<>|\r\n]', "", data["titulo"]).replace(" ", "_")
    filename = f"{safe_title}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(post)

    print("\n" + "=" * 60)
    print("POST GUARDADO EN:", os.path.abspath(filename))
    print("=" * 60 + "\n")
    print(post)


if __name__ == "__main__":
    print("Generador de posts Filmaffinity + TheTVDB\n")
    while True:
        generar_post()
        again = input("\n¿Crear otro post? (s/n): ").lower().strip()
        if again not in ("s", "si", "sí", "y", "yes"):
            print("Saliendo...\n")
            break
