# generador_post_series_peliculas.py
# Programa para generar posts de series/películas en formato foro
# Fuente principal: TheTVDB v4
# + RATING IMDb vía OMDb
# + Tamaño solo número (se añade GB automáticamente)
# + MediaInfo multilínea (termina con FIN)
# + Imágenes postimages.org: pega manualmente los códigos BBCode completos

import requests
import os
import re
import time

IDIOMA_DEFAULT = "CASTELLANO"
RIPEADOR_DEFAULT = "MattDrayton"
SERVIDOR_DEFAULT = "MEGA"

# ── OMDb API ──
OMDB_API_KEY = "a35cf7f5"

# ── TheTVDB v4 ──
TVDB_API_KEY = "53589b30-0deb-477d-bf89-74061a6027ce"  # Project API key v4
TVDB_PIN = "VUR1LZTW"  # Subscriber PIN
TVDB_V4_BASE = "https://api4.thetvdb.com/v4"

headers_web = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ══════════════════════════════════════════════
#  OMDb — Rating IMDb
# ══════════════════════════════════════════════


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
            "y": año if año and str(año).isdigit() else None,
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
        return "No encontrado en OMDb"
    except Exception:
        return "Error"


# ══════════════════════════════════════════════
#  TheTVDB v4 — Auth
# ══════════════════════════════════════════════


def obtener_token_tvdb():
    url = f"{TVDB_V4_BASE}/login"
    payload = {"apikey": TVDB_API_KEY, "pin": TVDB_PIN}

    try:
        r = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}, timeout=10
        )
        r.raise_for_status()
        token = r.json().get("data", {}).get("token")
        if token:
            return token
        print(f"  ✗ TVDB no devolvió token: {r.text[:200]}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ Error de conexión con TVDB: {e}")
        return None
    except requests.exceptions.HTTPError:
        print(f"  ✗ Error HTTP de TVDB ({r.status_code}): {r.text[:200]}")
        return None
    except Exception as e:
        print(f"  ✗ Error inesperado al autenticar con TVDB: {e}")
        return None


# ══════════════════════════════════════════════
#  TheTVDB v4 — Búsqueda y ficha
# ══════════════════════════════════════════════


def buscar_tvdb(token, query):
    """
    Busca series por nombre en v4.
    Muestra hasta 8 resultados con año y permite filtrar por año
    o elegir manualmente por número.
    """
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{TVDB_V4_BASE}/search"
    params = {"query": query, "type": "series"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        resultados = r.json().get("data", [])
    except Exception as e:
        print(f"  ✗ Error buscando en TVDB: {e}")
        return None

    if not resultados:
        print("  No se encontraron resultados.")
        return None

    # Mostrar lista
    print("Resultados encontrados:")
    for i, s in enumerate(resultados[:8], 1):
        nombre = s.get("name", "Sin nombre")
        año = (s.get("first_air_time") or "")[:4] or "s/f"
        estado = s.get("status", "")
        print(f"  {i}. {nombre} ({año}) [{estado}]")

    # Opción: filtrar por año
    print("¿Filtrar por año de inicio? (ENTER para no filtrar): ", end="")
    filtro_año = input().strip()

    if filtro_año.isdigit():
        filtrados = [
            s
            for s in resultados
            if (s.get("first_air_time") or "").startswith(filtro_año)
        ]
        if filtrados:
            print(f"Resultados del año {filtro_año}:")
            for i, s in enumerate(filtrados[:8], 1):
                nombre = s.get("name", "Sin nombre")
                año = (s.get("first_air_time") or "")[:4] or "s/f"
                print(f"  {i}. {nombre} ({año})")
            resultados = filtrados
        else:
            print(f"  Sin resultados para el año {filtro_año}, mostrando todos.")

    # Elegir número
    print("Elige el número de la serie (ENTER = primera): ", end="")
    eleccion = input().strip()

    if eleccion.isdigit():
        idx = int(eleccion) - 1
        if 0 <= idx < len(resultados):
            return resultados[idx].get("tvdb_id") or resultados[idx].get("id")

    return resultados[0].get("tvdb_id") or resultados[0].get("id")


def extraer_ficha_tvdb(token, tvdb_id):
    """
    Obtiene todos los campos del post desde TVDB v4 endpoint extendido.
    """
    if not token or not tvdb_id:
        return {}

    headers = {"Authorization": f"Bearer {token}"}
    data = {}

    # — Info básica extendida —
    try:
        r = requests.get(
            f"{TVDB_V4_BASE}/series/{tvdb_id}/extended?meta=translations&short=false",
            headers=headers,
            timeout=12,
        )
        r.raise_for_status()
        d = r.json().get("data", {})
    except Exception as e:
        print(f"  ✗ Error obteniendo ficha de TVDB: {e}")
        return {}

    # — Título en español / título original —
    translations = d.get("translations", {}) or {}
    name_translations = translations.get("nameTranslations", []) or []
    overview_translations = translations.get("overviewTranslations", []) or []

    titulo_es = ""
    sinopsis_es = ""
    for t in name_translations:
        if t.get("language") == "spa":
            titulo_es = t.get("name", "")
            break
    for t in overview_translations:
        if t.get("language") == "spa":
            sinopsis_es = t.get("overview", "")
            break

    titulo_original = d.get("name", "")
    data["titulo"] = titulo_es if titulo_es else titulo_original
    data["titulo_original"] = titulo_original
    data["sinopsis"] = (sinopsis_es or d.get("overview") or "No disponible").strip()

    # — Año —
    first_aired = d.get("firstAired", "") or ""
    data["año"] = first_aired[:4] if first_aired else "—"

    # — País —
    PAISES = {
        "AUS": "Australia",
        "AUT": "Austria",
        "BEL": "Bélgica",
        "BRA": "Brasil",
        "CAN": "Canadá",
        "CHE": "Suiza",
        "CHL": "Chile",
        "CHN": "China",
        "COL": "Colombia",
        "CZE": "República Checa",
        "DEU": "Alemania",
        "DNK": "Dinamarca",
        "ESP": "España",
        "FIN": "Finlandia",
        "FRA": "Francia",
        "GBR": "Reino Unido",
        "GRC": "Grecia",
        "HUN": "Hungría",
        "IND": "India",
        "IRL": "Irlanda",
        "ISR": "Israel",
        "ITA": "Italia",
        "JPN": "Japón",
        "KOR": "Corea del Sur",
        "MEX": "México",
        "NLD": "Países Bajos",
        "NOR": "Noruega",
        "NZL": "Nueva Zelanda",
        "POL": "Polonia",
        "PRT": "Portugal",
        "RUS": "Rusia",
        "SWE": "Suecia",
        "TUR": "Turquía",
        "UK": "Reino Unido",
        "USA": "Estados Unidos",
        "ZAF": "Sudáfrica",
    }
    country = (d.get("originalCountry") or "").strip().upper()
    data["país"] = PAISES.get(country, country) if country else "—"

    # — Duración —
    runtime = d.get("averageRuntime") or d.get("runtime") or ""
    data["duración"] = f"{runtime} min" if runtime else "—"

    # — Géneros —
    genres = d.get("genres", []) or []
    data["género"] = (
        ", ".join(g.get("name", "") for g in genres if g.get("name")) or "—"
    )

    # — Rating TVDB —
    rating = d.get("score")
    data["rating"] = f"{rating}/10" if rating else "—"

    # — IMDb ID —
    imdb_id = None
    for remote in d.get("remoteIds", []) or []:
        if "imdb" in (remote.get("sourceName") or "").lower():
            imdb_id = remote.get("id", "")
            break
    data["imdb_id"] = imdb_id

    # — Actores (tipo 3) —
    characters = d.get("characters", []) or []
    actores_raw = [c for c in characters if c.get("type") == 3 and c.get("personName")]
    actores = [
        a.get("personName", "")
        for a in sorted(actores_raw, key=lambda x: x.get("sort", 99))
    ]
    actores = list(dict.fromkeys(actores))
    data["reparto"] = ", ".join(actores) if actores else "—"

    # — Director: se obtiene de los characters de los episodios (type=1) —
    try:
        r_eps = requests.get(
            f"{TVDB_V4_BASE}/series/{tvdb_id}/episodes/default",
            headers=headers,
            params={"page": 0},
            timeout=12,
        )
        r_eps.raise_for_status()
        eps_list = r_eps.json().get("data", {}).get("episodes", []) or []
        directores_count = {}
        eps_filtrados = [e for e in eps_list if e.get("seasonNumber", 0) >= 1]
        for ep in eps_filtrados[:10]:
            ep_id = ep.get("id")
            if not ep_id:
                continue
            try:
                r_ep = requests.get(
                    f"{TVDB_V4_BASE}/episodes/{ep_id}/extended",
                    headers=headers,
                    timeout=10,
                )
                r_ep.raise_for_status()
                ep_chars = r_ep.json().get("data", {}).get("characters", []) or []
                for c in ep_chars:
                    if c.get("type") == 1 and c.get("personName"):
                        nombre = c["personName"]
                        directores_count[nombre] = directores_count.get(nombre, 0) + 1
                time.sleep(0.3)
            except Exception:
                continue
        if directores_count:
            dirs_ordenados = sorted(
                directores_count, key=lambda x: directores_count[x], reverse=True
            )
            data["dirección"] = ", ".join(dirs_ordenados[:3])
        else:
            data["dirección"] = "—"
    except Exception:
        data["dirección"] = "—"

    return data


# ══════════════════════════════════════════════
#  TheTVDB v4 — Episodios por temporada
# ══════════════════════════════════════════════


def obtener_episodios_tvdb(token, serie_id):
    if not token or not serie_id:
        return {}

    episodios_por_temp = {}
    headers = {"Authorization": f"Bearer {token}"}
    page = 0

    todos = []
    while True:
        try:
            time.sleep(0.5)
            r = requests.get(
                f"{TVDB_V4_BASE}/series/{serie_id}/episodes/default",
                headers=headers,
                params={"page": page, "language": "spa"},
                timeout=12,
            )
            if r.status_code != 200:
                break
            d = r.json()
            eps = d.get("data", {}).get("episodes", []) or []
            todos.extend(eps)
            # v4 no pagina igual: si devuelve menos de 500 es la última página
            if len(eps) < 500:
                break
            page += 1
        except Exception:
            break

    for ep in todos:
        temp = ep.get("seasonNumber")
        num = ep.get("number", 0)
        titulo = ep.get("name") or "Sin título"
        if temp is None or temp == 0:
            continue
        key = f"T{temp}"
        if key not in episodios_por_temp:
            episodios_por_temp[key] = []
        if titulo != "Sin título":
            episodios_por_temp[key].append(f"{num:02d} - {titulo}")

    # Ordenar temporadas y episodios
    return {k: sorted(v) for k, v in sorted(episodios_por_temp.items())}


# ══════════════════════════════════════════════
#  Generador de post
# ══════════════════════════════════════════════


def generar_post():
    query = input("Título a buscar: ").strip()
    temporada = input("Temporada (ej: T1) [vacío = película]: ").strip()
    es_serie = bool(temporada)

    # — Auth TVDB v4 —
    token = obtener_token_tvdb()
    if not token:
        print("⚠️  No se pudo autenticar con TVDB. Consulta el error anterior.")

    # — Búsqueda en TVDB —
    tvdb_id = buscar_tvdb(token, query) if token else None

    if not tvdb_id:
        print("No se encontró en TVDB. Introduce el ID manualmente:")
        tvdb_id_raw = input("TVDB ID (número): ").strip()
        tvdb_id = int(tvdb_id_raw) if tvdb_id_raw.isdigit() else None

    # — Ficha completa —
    data = extraer_ficha_tvdb(token, tvdb_id) if tvdb_id else {}

    if not data:
        print("⚠️  No se pudieron obtener datos de TVDB.")
        data = {}

    # — Campos manuales si faltan —
    print(f"\nSerie: {data.get('titulo', query)} ({data.get('año', '—')})")
    if data.get("país", "—") == "—":
        pais_input = input("País de origen (ej: UK, USA, ESPAÑA): ").strip().upper()
        data["país"] = pais_input if pais_input else "—"
    if data.get("dirección", "—") == "—":
        dir_input = input("Director/Creador (ENTER para dejar vacío): ").strip()
        data["dirección"] = dir_input if dir_input else "—"

    # — Rating IMDb —
    rating_imdb = obtener_rating_imdb(
        imdb_id=data.get("imdb_id"),
        titulo=data.get("titulo"),
        año=data.get("año"),
        es_serie=es_serie,
    )

    # — Plataforma —
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
    plataforma = plataformas.get(input("\nNúmero: ").strip(), "WEB")

    # — Resolución fuente —
    resoluciones = {"1": "2160p", "2": "1080p"}
    print("\nSelecciona resolución fuente:")
    for k, v in resoluciones.items():
        print(f"{k} {v}")
    resolucion_fuente = resoluciones.get(input("\nNúmero: ").strip(), "1080p")

    fuente = f"{plataforma} WEB-DL {resolucion_fuente}"

    # — Tamaño —
    tamano_input = input("Tamaño total (solo número, ej: 3.5 o 12.8): ").strip()
    try:
        tamano = f"{float(tamano_input)}GB"
    except ValueError:
        tamano = "—"

    # — Episodios —
    epicom = input("Primer episodio (ej: 01): ").strip()
    epitotal = input("Total episodios (ej: 08): ").strip()

    # — Datos del ripeo —
    idioma = input(f"Idioma [{IDIOMA_DEFAULT}]: ").strip().upper() or IDIOMA_DEFAULT
    servidor = (
        input(f"Servidor [{SERVIDOR_DEFAULT}]: ").strip().upper() or SERVIDOR_DEFAULT
    )
    ripeador = input(f"Ripeado por [{RIPEADOR_DEFAULT}]: ").strip() or RIPEADOR_DEFAULT

    # — Resolución vídeo —
    resoluciones_vid = {
        "1": "3840×2160",
        "2": "3832×1920",
        "3": "2560×1440",
        "4": "1920×1080",
        "5": "1920x960",
    }
    print("\nSelecciona resolución de vídeo:")
    for k, v in resoluciones_vid.items():
        print(f"{k} {v}")
    resolucionx = resoluciones_vid.get(input("\nNúmero: ").strip(), "—")

    tasabits = input("Tasa bits: ").strip()

    # — Audio —
    audiotack = {"1": "AC3 256Kbps 2 canales", "2": "EAC3 640Kbps 6 canales"}
    print("\nSelecciona audio:")
    for k, v in audiotack.items():
        print(f"{k} {v}")
    audiostacks = audiotack.get(input("\nNúmero: ").strip(), "—")

    # — Subtítulos —
    letritas = {"1": "SI forzados SI", "2": "NO"}
    print("\nSubtítulos forzados:")
    for k, v in letritas.items():
        print(f"{k} {v}")
    subtitulos = letritas.get(input("\nNúmero: ").strip(), "—")

    # — MediaInfo multilínea —
    print("\nPega el MediaInfo completo aquí (Ctrl+V).")
    print("Cuando termines, escribe 'FIN' en una línea sola y pulsa Enter.\n")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "FIN":
            break
        lines.append(line)
    mediainfo = "\n".join(lines).strip() or "MediaInfo no incluido"

    # — Imágenes BBCode —
    imagenes_block = ""
    print("\nPega los códigos BBCode completos de postimages.org (uno por línea).")
    print(
        "Ejemplo: [url=https://postimg.cc/xxxx][img]https://i.postimg.cc/xxxx/imagen.jpg[/img][/url]"
    )
    print("Termina con Enter vacío (línea en blanco).\n")
    imagenes_lines = []
    while True:
        linea = input().strip()
        if not linea:
            break
        if linea.startswith("[url=") and "[img]" in linea and "[/img]" in linea:
            imagenes_lines.append(linea)
    if imagenes_lines:
        imagenes_block = "\n".join(imagenes_lines) + "\n"

    # — Episodios por temporada —
    episodios_por_temp = {}
    if es_serie and tvdb_id:
        episodios_por_temp = obtener_episodios_tvdb(token, tvdb_id)

    if episodios_por_temp:
        episodios_block = "\n[HIDE]\n[CODE]\n"
        for temp, eps in episodios_por_temp.items():
            episodios_block += f"\n{temp} ({len(eps)} episodios)\n"
            for ep in eps:
                episodios_block += f"  {ep}\n"
        episodios_block += "\n[/CODE]\n[/HIDE]\n"
    else:
        episodios_block = (
            "\n[HIDE]\n[CODE]\n"
            "No se pudieron obtener los títulos automáticamente.\n"
            "Puedes añadirlos manualmente aquí.\n"
            "[/CODE]\n[/HIDE]\n"
        )

    # ══════════════════════════════════════════
    #  Construcción del post
    # ══════════════════════════════════════════

    temp_str = f" {temporada}" if temporada else ""
    titulo_post = (
        f"{data.get('titulo', query)} T{temp_str} "
        f"[{fuente}] [{idioma}] [{tamano}] [{epicom}/{epitotal}] [{servidor}]"
    )

    ficha = f"""Ficha Técnica
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
RATING TVDB: {data.get('rating', '—')}
RATING IMDb: {rating_imdb}"""

    sinopsis = f"""Sinopsis
{data.get('sinopsis', 'No disponible')}"""

    ripeo = f"""Datos del ripeo
Ripeado por: {ripeador}
Fuente: {fuente}
Servidor: {servidor}"""

    datosvid = f"""Datos del Video
Formato: Matroska
Video: High@L4 | {resolucionx} @ {tasabits} kb/s
Framerate: 25,000
Resolución: {resolucionx}
Audio: Castellano {audiostacks}
Subtitulos: {subtitulos}"""

    post = (
        f"{titulo_post}\n\n"
        f"{imagenes_block}"
        f"{ficha}\n\n"
        f"{sinopsis}\n\n"
        f"{ripeo}\n\n"
        f"{datosvid}\n\n"
        f"[SPOILER]\n{mediainfo}\n[/SPOILER]\n\n"
        f"{episodios_block}"
    )

    safe_title = re.sub(r'[\\/*?:"<>|\r\n]', "", data.get("titulo", query)).replace(
        " ", "_"
    )
    filename = f"{safe_title}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(post)

    print("\n" + "=" * 60)
    print("POST GUARDADO EN:", os.path.abspath(filename))
    print("=" * 60 + "\n")
    print(post)


if __name__ == "__main__":
    print(
        "Generador de posts TheTVDB v4 + IMDb (OMDb) + imágenes postimages (manual BBCode)\n"
    )
    while True:
        generar_post()
        again = input("\n¿Crear otro post? (s/n): ").lower().strip()
        if again not in ("s", "si", "sí", "y", "yes"):
            print("Saliendo...\n")
            break
