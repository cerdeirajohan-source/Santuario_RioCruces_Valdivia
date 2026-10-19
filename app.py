import json
import math

import folium
import requests
import streamlit as st
from folium.features import DivIcon
from shapely.geometry import LineString
from streamlit_folium import st_folium

st.set_page_config(page_title="Santuario Río Cruces", page_icon="🦢", layout="wide")

HDR = {"User-Agent": "geovisualizador-rio-cruces/1.0 (proyecto academico)"}
CENTRO = [-39.68, -73.19]

# ------------------------------------------------------------------
# DATOS (edítalos: aquí se agregan o corrigen proyectos y especies)
# ------------------------------------------------------------------
# Eje APROXIMADO del río Cruces entre el norte de la isla Teja y el
# Castillo San Luis de Alba. Solo se usa si no se puede descargar el límite.
EJE = [(-39.790, -73.243), (-39.765, -73.232), (-39.742, -73.215),
       (-39.720, -73.200), (-39.695, -73.190), (-39.670, -73.182),
       (-39.645, -73.170), (-39.620, -73.160), (-39.595, -73.155),
       (-39.570, -73.150)]

# tipo: "EIA" -> azul   (aprobado con evaluación de impacto ambiental)
#       "DIA" -> rojo   (aprobado sin EIA, solo declaración)
#       "SIN" -> gris   (sin evaluación aprobada o denunciado ante la SMA)
# radio_m: radio del área de influencia en METROS (criterio ilustrativo).
# TODAS las coordenadas son aproximadas y están POR VERIFICAR en https://seia.sea.gob.cl
PROYECTOS = [
    {"nombre": "Planta Valdivia (Celulosa Arauco)", "tipo": "EIA",
     "lat": -39.640, "lon": -73.010, "radio_m": 5000, "wiki": "Celulosa Arauco y Constitución",
     "danos": "Genera efluentes líquidos industriales (riles). El caso del año 2004 en el río "
              "Cruces se vinculó con la muerte y migración de cisnes de cuello negro dentro "
              "del santuario. Ubicación por verificar."},
    {"nombre": "Condominio Parque Río Cruces (Etapa II)", "tipo": "DIA",
     "lat": -39.8044, "lon": -73.2600, "radio_m": 1500, "wiki": "Isla Teja",
     "danos": "Proyecto inmobiliario en Isla Teja, junto a vegas del humedal conectadas con el "
              "río Cruces. Se indica ingreso por DIA (la Etapa I habría ido por pertinencia). "
              "Tipo de ingreso y ubicación por verificar en el SEIA."},
    {"nombre": "Loteo Riberas de la Dehesa (Tres Bocas)", "tipo": "SIN",
     "lat": -39.7256, "lon": -73.2381, "radio_m": 1500, "wiki": "Río Cruces",
     "danos": "La SMA inspeccionó obras de loteo dentro del santuario por una posible elusión "
              "del SEIA. Riesgos: relleno de humedal, pérdida de hábitat y de zonas de "
              "inundación. Ubicación aproximada."},
    {"nombre": "Loteo Relleno Santa Rosa (Cabo Blanco)", "tipo": "SIN",
     "lat": -39.7753, "lon": -73.2311, "radio_m": 1000, "wiki": "Río Cruces",
     "danos": "Se señala relleno de suelo sin evaluación ambiental, junto a tributarios del "
              "santuario. Dato sin fuente verificada: por verificar."},
]

# tipo: animal | planta | insecto. "i" = posición aproximada sobre el eje.
ESPECIES = [
    {"tipo": "animal", "comun": "Cisne de cuello negro", "cient": "Cygnus melanocoryphus",
     "wiki": "Cygnus melanocoryphus", "i": 4,
     "info": "Ave acuática que anida en el humedal. Es la especie emblemática del santuario."},
    {"tipo": "animal", "comun": "Huillín", "cient": "Lontra provocax",
     "wiki": "Lontra provocax", "i": 6,
     "info": "Nutria de río en peligro, citada en la ficha Ramsar del sitio."},
    {"tipo": "animal", "comun": "Coipo", "cient": "Myocastor coypus",
     "wiki": "Myocastor coypus", "i": 2,
     "info": "Roedor semiacuático de orillas y pantanos."},
    {"tipo": "animal", "comun": "Garza cuca", "cient": "Ardea cocoi",
     "wiki": "Ardea cocoi", "i": 7,
     "info": "Ave pescadora de humedales y riberas."},
    {"tipo": "planta", "comun": "Luchecillo", "cient": "Egeria densa",
     "wiki": "Egeria densa", "i": 5,
     "info": "Planta acuática sumergida, base de la alimentación de los cisnes."},
    {"tipo": "planta", "comun": "Totora", "cient": "Schoenoplectus californicus",
     "wiki": "Schoenoplectus californicus", "i": 3,
     "info": "Planta de los totorales que forman parte de los bañados del humedal."},
    {"tipo": "insecto", "comun": "Ciervo volante", "cient": "Chiasognathus granti",
     "wiki": "Chiasognathus granti", "i": 1,
     "info": "Escarabajo de los bosques del sur de Chile. Especie de ejemplo de la zona: "
             "verificar su registro dentro del santuario."},
]

ICONOS = {"animal": ("🦢", "#4c9be8"), "planta": ("🌿", "#5cb85c"), "insecto": ("🪲", "#8d6e63")}


# ------------------------------------------------------------------
# FUNCIONES
# ------------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def wiki(titulo):
    """Imagen (miniatura) de Wikipedia para un artículo, o None."""
    try:
        url = "https://es.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(titulo.replace(" ", "_"))
        d = requests.get(url, headers=HDR, timeout=10).json()
        return d.get("thumbnail", {}).get("source")
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner="Buscando el límite del santuario...")
def limite_osm():
    """Intenta descargar el polígono del santuario desde OpenStreetMap."""
    for q in ["Santuario de la Naturaleza Río Cruces y Chorocamayo",
              "Santuario de la Naturaleza Carlos Anwandter"]:
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": q, "format": "jsonv2", "polygon_geojson": 1, "limit": 5},
                             headers=HDR, timeout=15)
            for it in r.json():
                g = it.get("geojson")
                if g and g["type"] in ("Polygon", "MultiPolygon"):
                    return {"type": "Feature", "properties": {}, "geometry": g}
        except Exception:
            continue
    return None


def limite_aproximado(metros=1000):
    """Franja de ~2 km de ancho alrededor del eje (esquemática)."""
    lat0, lon0 = EJE[0]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    xy = [((lo - lon0) * kx, (la - lat0) * ky) for la, lo in EJE]
    pol = LineString(xy).buffer(metros)
    coords = [[lon0 + x / kx, lat0 + y / ky] for x, y in pol.exterior.coords]
    return {"type": "Feature", "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [coords]}}


@st.cache_data(ttl=86400, show_spinner="Calculando isocronas...")
def isocronas(lat, lon, clave):
    r = requests.post("https://api.openrouteservice.org/v2/isochrones/driving-car",
                      headers={"Authorization": clave, "Content-Type": "application/json"},
                      json={"locations": [[lon, lat]], "range": [300, 600, 900]}, timeout=30)
    r.raise_for_status()
    return r.json()


def popup(titulo, img, texto):
    im = (f'<img src="{img}" style="width:100%;max-height:150px;object-fit:cover;border-radius:6px">'
          if img else '<i style="font-size:12px">(sin imagen disponible)</i>')
    html = (f'<div style="font-family:sans-serif;width:260px"><h4 style="margin:0 0 6px">{titulo}</h4>'
            f'{im}<p style="font-size:12px;margin-top:6px">{texto}</p></div>')
    return folium.Popup(html, max_width=300)


def marcador(grupo, lat, lon, emoji, fondo, tip, pop):
    html = (f'<div style="width:34px;height:34px;border-radius:50%;background:{fondo};'
            'border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.45);display:flex;'
            f'align-items:center;justify-content:center;font-size:18px">{emoji}</div>')
    folium.Marker([lat, lon], tooltip=tip, popup=pop,
                  icon=DivIcon(icon_size=(34, 34), icon_anchor=(17, 17), html=html)).add_to(grupo)


# ------------------------------------------------------------------
# BARRA LATERAL
# ------------------------------------------------------------------
st.sidebar.header("Tipo de mapa")
tipo_mapa = st.sidebar.radio("Mapa base", ["Satelital", "OpenStreetMap", "Isocronas"],
                             label_visibility="collapsed")

st.sidebar.header("Capas")
ver_santuario = st.sidebar.checkbox("Límite del santuario", True)
ver_influencia = st.sidebar.checkbox("Áreas de influencia", True)
ver_eia = st.sidebar.checkbox("Proyectos con EIA (azul)", True)
ver_dia = st.sidebar.checkbox("Proyectos sin EIA (rojo)", True)
ver_sin = st.sidebar.checkbox("Sin evaluación / denunciados (gris)", True)
ver_animales = st.sidebar.checkbox("Animales 🦢", True)
ver_plantas = st.sidebar.checkbox("Plantas 🌿", True)
ver_insectos = st.sidebar.checkbox("Insectos 🪲", True)

subido = st.sidebar.file_uploader("Límite oficial (GeoJSON, opcional)", type=["geojson", "json"])

# ------------------------------------------------------------------
# MAPA
# ------------------------------------------------------------------
st.title("Área de Influencia Santuario de la Naturaleza Río Cruces")

if tipo_mapa == "Satelital":
    m = folium.Map(CENTRO, zoom_start=11, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name="Satelital").add_to(m)
elif tipo_mapa == "OpenStreetMap":
    m = folium.Map(CENTRO, zoom_start=11, tiles="OpenStreetMap")
else:
    m = folium.Map(CENTRO, zoom_start=11, tiles="CartoDB positron")

# Límite del santuario (verde claro)
if ver_santuario:
    limite, fuente = None, ""
    if subido is not None:
        try:
            limite, fuente = json.load(subido), "archivo subido"
        except Exception as e:
            st.sidebar.error(f"No se pudo leer el archivo: {e}")
    if limite is None:
        limite = limite_osm()
        fuente = "OpenStreetMap"
    if limite is None:
        limite, fuente = limite_aproximado(), "APROXIMADO (esquemático, no oficial)"
    folium.GeoJson(limite, name="Santuario",
                   style_function=lambda f: {"color": "#4caf50", "weight": 2,
                                             "fillColor": "#a8e6a1", "fillOpacity": 0.5},
                   tooltip="Santuario de la Naturaleza Río Cruces y Chorocamayo").add_to(m)
    st.caption(f"Límite del santuario: {fuente}.")

# Proyectos y áreas de influencia
g_inf = folium.FeatureGroup("Áreas de influencia")
grupos = {"EIA": folium.FeatureGroup("Proyectos con EIA"),
          "DIA": folium.FeatureGroup("Proyectos sin EIA"),
          "SIN": folium.FeatureGroup("Sin evaluación / denunciados")}
visible_tipo = {"EIA": ver_eia, "DIA": ver_dia, "SIN": ver_sin}
colores_p = {"EIA": "#1f6fd6", "DIA": "#d62728", "SIN": "#7f7f7f"}
etiquetas = {"EIA": "Con Evaluación de Impacto Ambiental (EIA)",
             "DIA": "Sin EIA (aprobado por DIA)",
             "SIN": "Sin evaluación aprobada / denunciado ante la SMA"}
for p in PROYECTOS:
    t = p["tipo"]
    if not visible_tipo[t]:
        continue
    if ver_influencia:
        folium.Circle([p["lat"], p["lon"]], radius=p["radio_m"], color="#f5a25d", weight=2,
                      fill=True, fill_color="#ffc999", fill_opacity=0.35,
                      tooltip=f'Área de influencia: {p["radio_m"]/1000:.1f} km').add_to(g_inf)
    cuerpo = f'<b>{etiquetas[t]}</b><br>{p["danos"]}<br><i>Radio de influencia: {p["radio_m"]} m.</i>'
    marcador(grupos[t], p["lat"], p["lon"], "🏭", colores_p[t], p["nombre"],
             popup(p["nombre"], wiki(p["wiki"]), cuerpo))
for g in (g_inf, *grupos.values()):
    g.add_to(m)

# Biodiversidad
visibles = {"animal": ver_animales, "planta": ver_plantas, "insecto": ver_insectos}
for tipo, nombre in [("animal", "Animales"), ("planta", "Plantas"), ("insecto", "Insectos")]:
    if not visibles[tipo]:
        continue
    g = folium.FeatureGroup(nombre)
    for e in ESPECIES:
        if e["tipo"] != tipo:
            continue
        lat, lon = EJE[e["i"]]
        emoji, fondo = ICONOS[tipo]
        titulo = f'{e["comun"]} (<i>{e["cient"]}</i>)'
        marcador(g, lat + 0.004, lon - 0.006, emoji, fondo, e["comun"],
                 popup(titulo, wiki(e["wiki"]), e["info"]))
    g.add_to(m)

# Isocronas (requiere clave gratuita de OpenRouteService en los "Secrets")
if tipo_mapa == "Isocronas":
    clave = st.secrets.get("ORS_API_KEY", "")
    if not clave:
        st.info("Para ver isocronas reales agrega ORS_API_KEY (gratis en openrouteservice.org) "
                "en Settings → Secrets de Streamlit Cloud.")
    else:
        colores = {900: "#fde0c5", 600: "#f9b382", 300: "#e8743b"}
        for p in PROYECTOS:
            try:
                data = isocronas(p["lat"], p["lon"], clave)
                for f in sorted(data["features"], key=lambda f: -f["properties"]["value"]):
                    seg = f["properties"]["value"]
                    folium.GeoJson(f, style_function=lambda _f, c=colores.get(seg, "#f9b382"):
                                   {"color": c, "weight": 1, "fillColor": c, "fillOpacity": 0.35},
                                   tooltip=f'{seg // 60} min en auto desde {p["nombre"]}').add_to(m)
            except Exception as e:
                st.warning(f'No se pudo calcular la isocrona de {p["nombre"]}: {e}')

folium.LayerControl(collapsed=True).add_to(m)
st_folium(m, use_container_width=True, height=650, returned_objects=[])

st.caption("Datos ilustrativos: verifica proyectos (RCA, tipo de evaluación y coordenadas) en el SEIA "
           "y las especies en fuentes oficiales (CONAF, MMA) antes de usar el mapa en un informe.")
