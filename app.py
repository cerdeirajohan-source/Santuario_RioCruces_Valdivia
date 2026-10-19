import json

import folium
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="GeoVisualizador de Paillaco",
    page_icon="🌎",
    layout="wide",
)

# Coordenadas aproximadas del centro de Paillaco (lat, lon)
CENTRO = [-40.0708, -72.8697]

# Mapas base disponibles (nombre en pantalla -> nombre de teselas en folium)
MAPAS_BASE = {
    "OpenStreetMap": "OpenStreetMap",
    "Mapa claro": "CartoDB positron",
    "Mapa oscuro": "CartoDB dark_matter",
}

# Puntos de ejemplo (reemplázalos por los tuyos cuando tengas datos)
PUNTOS_EJEMPLO = [
    {"nombre": "Punto de ejemplo 1", "lat": -40.0708, "lon": -72.8697},
    {"nombre": "Punto de ejemplo 2", "lat": -40.0650, "lon": -72.8600},
    {"nombre": "Punto de ejemplo 3", "lat": -40.0780, "lon": -72.8800},
]

# ---------------- Barra lateral ----------------
st.sidebar.header("Capas disponibles")

mapa_base = st.sidebar.radio("Mapa base", list(MAPAS_BASE.keys()), index=1)

st.sidebar.subheader("Vectores")
ver_puntos = st.sidebar.checkbox("Puntos de ejemplo", value=True)
ver_area = st.sidebar.checkbox("Área de influencia (1,5 km)", value=True)

st.sidebar.subheader("Tu propia capa")
archivo = st.sidebar.file_uploader("Sube un archivo GeoJSON", type=["geojson", "json"])

# ---------------- Mapa ----------------
st.title("🌎 GeoVisualizador de Paillaco")
st.caption("Aplicación desarrollada con Streamlit. Seleccione las capas que desea visualizar.")

m = folium.Map(location=CENTRO, zoom_start=13, tiles=MAPAS_BASE[mapa_base])

if ver_area:
    folium.Circle(
        location=CENTRO,
        radius=1500,
        color="#1f4e79",
        fill=True,
        fill_opacity=0.15,
        tooltip="Área de influencia (ilustrativa)",
    ).add_to(m)

if ver_puntos:
    for p in PUNTOS_EJEMPLO:
        folium.Marker(
            location=[p["lat"], p["lon"]],
            popup=p["nombre"],
            tooltip=p["nombre"],
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(m)

capas_activas = int(ver_puntos) + int(ver_area)

if archivo is not None:
    try:
        datos = json.load(archivo)
        capa = folium.GeoJson(datos, name=archivo.name)
        capa.add_to(m)
        m.fit_bounds(capa.get_bounds())
        capas_activas += 1
    except Exception as e:
        st.sidebar.error(f"No se pudo leer el archivo: {e}")

folium.LayerControl().add_to(m)

st.sidebar.divider()
st.sidebar.write(f"Capas activas: **{capas_activas}**")

st_folium(m, use_container_width=True, height=600, returned_objects=[])
