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

IDIOMA_DEFAULT = "CASTELLANO"
RIPEADOR_DEFAULT = "MattDrayton"
SERVIDOR_DEFAULT = "MEGA"

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def buscar_filmaffinity(query):
    search_url = f"https://www.filmaffinity.com/es/search.php?stext={query.replace(' ', '%20')}&stype=title"
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
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
        response = requests.get(url, headers=headers, timeout=12)
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
    print("\n=== GENERADOR DE POSTS FILMAFFINITY ===\n")

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
        print(f"{k} - {v}")

    opcion_plataforma = input("\nNúmero: ").strip()
    plataforma = plataformas.get(opcion_plataforma, "WEB")

    resoluciones = {"1": "2160p", "2": "1080p", "3": "720p"}

    print("\nSelecciona resolución:")
    for k, v in resoluciones.items():
        print(f"{k} - {v}")

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

    mediainfo = input("\nPega MediaInfo (ENTER para omitir): ").strip()
    if not mediainfo:
        mediainfo = "MediaInfo no incluido"

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
Video: High@L4 | 1920x960 @ 9432 kb/s
Framerate: 25,000
Resolución: 1920x960
Audio: Castellano EAC3 640Kbps 6 canales
Subtitulos: SI forzados SI
"""

    spoiler = f"""
[SPOILER="MediaInfo"]
{mediainfo}
[/SPOILER]
"""

    episodios_block = """
[HIDE="Episodios"]
[CODE]

[/CODE]
[/HIDE]
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
    print("Generador de posts Filmaffinity\n")
    while True:
        generar_post()
        again = input("\n¿Crear otro post? (s/n): ").lower().strip()
        if again not in ("s", "si", "sí", "y", "yes"):
            print("Saliendo...\n")
            break
