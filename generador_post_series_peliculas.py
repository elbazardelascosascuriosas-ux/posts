# generador_post_series_peliculas.py
# Programa para generar posts de series/películas en formato foro
# Extrae datos de Filmaffinity.com (en español)
# + RATING IMDb vía OMDb (ID extraído + fallback Father Brown)
# + Subida automática de imágenes a postimages.org vía API + BBCode [url][img]
#   (con fallback manual si falla)

import requests
from bs4 import BeautifulSoup
import os
import re
import time
from pathlib import Path

IDIOMA_DEFAULT = "CASTELLANO"
RIPEADOR_DEFAULT = "MattDrayton"
SERVIDOR_DEFAULT = "MEGA"

# ── OMDb API ──
OMDB_API_KEY = "a35cf7f5"

# ── Postimages API ──
POSTIMAGES_API_KEY = "af7fe551c720dcc86aa2d902ba3d5773"

# ── TheTVDB v4 ── (opcional)
TVDB_API_KEY = "TU_API_KEY_DE_PROYECTO_AQUI"
TVDB_PIN = "TU_PIN_DE_SUSCRIPTOR_AQUI"

headers_web = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def subir_imagen_postimages(ruta_imagen):
    url = "https://api.postimages.org/1/upload"
    headers = headers_web.copy()
    headers["Referer"] = "https://postimages.org/"

    try:
        with open(ruta_imagen, "rb") as f:
            files = {"image": (Path(ruta_imagen).name, f, "image/png")}
            data = {"key": POSTIMAGES_API_KEY, "format": "json"}
            r = requests.post(url, files=files, data=data, headers=headers, timeout=30)
            r.raise_for_status()

            try:
                resp = r.json()
            except:
                print(f"Respuesta no JSON: {r.text[:200]}...")
                return None

            if resp.get("status") == "success":
                direct_url = resp["data"]["url"]
                viewer_url = resp["data"]["viewer"]
                bbcode = f"[url={viewer_url}][img]{direct_url}[/img][/url]"
                return bbcode
            else:
                print(f"Error en API: {resp.get('message', 'desconocido')}")
                return None
    except Exception as e:
        print(f"Error al subir {Path(ruta_imagen).name}: {e}")
        return None


def obtener_rating_imdb(imdb_id=None, titulo=None, año=None, es_serie=True):
    if imdb_id:
        params = {"apikey": OMDB_API_KEY, "i": imdb_id}
    else:
        search_title = (
            "Father Brown" if "padre brown" in (titulo or "").lower() else titulo
        )
        params = {
            "apikey": OMDB_API_KEY,
            "t": search_title,
            "y": año if año and año.isdigit() else None,
            "type": "series" if es_serie else "movie",
        }
        params = {k: v for k, v in params.items() if v is not None}

    try:
        r = requests.get(
            "http://www.omdbapi.com/", params=params, headers=headers_web, timeout=10
        )
        r.raise_for_status()
        data = r.json()

        if data.get("Response") == "True":
            rating = data.get("imdbRating", "N/A")
            votos = data.get("imdbVotes", "—")
            if rating != "N/A" and rating.strip():
                return f"{rating}/10 ({votos} votos)"
            return "N/A"
        else:
            return "No encontrado en OMDb"
    except:
        return "Error"


def extraer_imdb_id_de_filmaffinity(soup):
    possible_containers = [
        soup.find("div", id="external-links"),
        soup.find("dl", class_="external-links"),
        soup.find("div", class_="links"),
        soup.find("div", id="links"),
        soup.find("div", class_="movie-external-links"),
        soup.find("div", class_="external"),
        soup.find("div", class_="movie-info"),
        soup.find("div", class_="additional-info"),
        soup.find("footer"),
        soup,
    ]

    for container in possible_containers:
        if container:
            links = container.find_all("a", href=True)
            for a in links:
                href = a["href"]
                if "imdb.com/title/" in href or "imdb.com/es-es/title/" in href:
                    match = re.search(r"(tt\d+)", href)
                    if match:
                        return match.group(1)

    all_links = soup.find_all("a", href=re.compile(r"imdb\.com.*tt\d+", re.I))
    if all_links:
        href = all_links[0]["href"]
        match = re.search(r"(tt\d+)", href)
        if match:
            return match.group(1)

    return None


def obtener_token_tvdb():
    if not TVDB_API_KEY:
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
    except:
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
            return results[0]["id"]
    except:
        return None


def obtener_episodios_tvdb(token, serie_id):
    if not token or not serie_id:
        return {}

    episodios_por_temp = {}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        url_series = f"https://api4.thetvdb.com/v4/series/{serie_id}?language=spa"
        r = requests.get(url_series, headers=headers, timeout=10)
        r.raise_for_status()
        num_temps = r.json()["data"].get("numberOfSeasons", 1)
    except:
        num_temps = 5

    for temp in range(1, num_temps + 1):
        url = f"https://api4.thetvdb.com/v4/series/{serie_id}/episodes?season={temp}&language=spa"
        try:
            time.sleep(1.2)
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
            return (
                "https://www.filmaffinity.com" + href
                if not href.startswith("http")
                else href
            )
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

    data["año"] = data.get("año", "—")

    imdb_id = extraer_imdb_id_de_filmaffinity(soup)
    data["imdb_id"] = imdb_id

    return data


def generar_post():
    query = input("Título a buscar: ").strip()
    url = buscar_filmaffinity(query)

    if not url:
        url = input("URL Filmaffinity manual: ").strip()

    if not url:
        return

    data = extraer_ficha_filmaffinity(url)

    temporada = input("Temporada (ej: T1) [vacío = película]: ").strip()
    es_serie = bool(temporada)

    imdb_id = data.get("imdb_id")
    rating_imdb = obtener_rating_imdb(
        imdb_id=imdb_id,
        titulo=data.get("titulo"),
        año=data.get("año"),
        es_serie=es_serie,
    )

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

    print("\nSelecciona plataforma (ENTER = WEB):")
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

    tamano_input = input("Tamaño total (solo número, ej: 3.5 o 12.8): ").strip()
    try:
        tamano_num = float(tamano_input)
        tamano = f"{tamano_num}GB"
    except ValueError:
        tamano = "—"

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
    resolucionx = resolucion.get(opcion_res, "—")

    tasabits = input("Tasa bits: ").strip()

    audiotack = {"1": "AC3 256Kbps 2 canales", "2": "EAC3 640Kbps 6 canales"}

    print("\nSelecciona audio:")
    for k, v in audiotack.items():
        print(f"{k} {v}")

    opcion_res = input("\nNúmero: ").strip()
    audiostacks = audiotack.get(opcion_res, "—")

    letritas = {"1": "SI forzados SI", "2": "NO"}

    print("\nSubtítulos forzados:")
    for k, v in letritas.items():
        print(f"{k} {v}")

    opcion_res = input("\nNúmero: ").strip()
    subtitulos = letritas.get(opcion_res, "—")

    # MediaInfo multilínea
    print("\nPega el MediaInfo completo aquí (Ctrl+V).")
    print("Cuando termines, escribe 'FIN' en una línea sola y pulsa Enter.\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "FIN":
            break
        lines.append(line)

    mediainfo_text = "\n".join(lines).strip()
    mediainfo = mediainfo_text if mediainfo_text else "MediaInfo no incluido"

    # Imágenes postimages.org
    imagenes_block = ""
    print("\n¿Quieres añadir imágenes de postimages.org? (s/n)")
    respuesta = input().strip().lower()
    if respuesta in ("s", "si", "sí", "y", "yes"):
        print("Subida automática no funciona (API restringida).")
        print("Sube las imágenes manualmente en https://postimages.org/")
        print(
            "Copia los códigos BBCode completos (elige 'BBCode (foros)' en la página de resultado)."
        )
        print("Pega uno por línea aquí. Termina con Enter vacío.\n")

        bbcode_lines = []
        while True:
            bbcode = input().strip()
            if bbcode == "":
                break
            if bbcode.startswith("[url=") and "[img]" in bbcode:
                bbcode_lines.append(bbcode)

        if bbcode_lines:
            imagenes_block = "[center]\n"
            imagenes_block += "\n".join(bbcode_lines) + "\n"
            imagenes_block += "[/center]\n\n"
        else:
            print("No se añadieron imágenes.")

    episodios_por_temp = {}
    token = obtener_token_tvdb()
    if token:
        serie_id = buscar_serie_tvdb(token, data.get("titulo", query))
        if serie_id:
            episodios_por_temp = obtener_episodios_tvdb(token, serie_id)

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
RATING FILMAFFINITY: {data.get('rating', '—')}
RATING IMDb: {rating_imdb}
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

{imagenes_block}{ficha.strip()}

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
    print(
        "Generador de posts Filmaffinity + TheTVDB + IMDb + imágenes postimages (manual BBCode)\n"
    )
    while True:
        generar_post()
        again = input("\n¿Crear otro post? (s/n): ").lower().strip()
        if again not in ("s", "si", "sí", "y", "yes"):
            print("Saliendo...\n")
            break
