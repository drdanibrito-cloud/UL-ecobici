import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Configuración inicial de la página
st.set_page_config(page_title="Ecobici CDMX", layout="wide", page_icon="🚲")
st.title("🚲 Mapa de Estaciones Ecobici")

@st.cache_data(ttl=60)
def obtener_datos_ecobici():
    url_info = "https://gbfs.mex.lyftbikes.com/gbfs/en/station_information.json"
    url_status = "https://gbfs.mex.lyftbikes.com/gbfs/en/station_status.json"

    # Peticiones a la API de Ecobici
    resp_info = requests.get(url_info).json()
    df_info = pd.DataFrame(resp_info['data']['stations'])

    resp_status = requests.get(url_status).json()
    df_status = pd.DataFrame(resp_status['data']['stations'])

    # Combinar información de estaciones con su estatus en tiempo real
    tabla_final = pd.merge(
        df_info[['station_id', 'name', 'lat', 'lon', 'capacity']],
        df_status[['station_id', 'num_bikes_available', 'num_docks_available', 'is_renting']],
        on='station_id'
    )

    # Renombrar columnas para el usuario
    tabla_final.columns = [
        'ID', 'Nombre', 'Latitud', 'Longitud',
        'Capacidad_Total', 'Bicis_Disponibles',
        'Puertos_Libres', '¿Operativa?'
    ]
    
    # Asegurar tipos de datos correctos
    tabla_final['Latitud'] = pd.to_numeric(tabla_final['Latitud'])
    tabla_final['Longitud'] = pd.to_numeric(tabla_final['Longitud'])
    tabla_final['Bicis_Disponibles'] = pd.to_numeric(tabla_final['Bicis_Disponibles']).fillna(0).astype(int)
    tabla_final['Puertos_Libres'] = pd.to_numeric(tabla_final['Puertos_Libres']).fillna(0).astype(int)
    tabla_final['Capacidad_Total'] = pd.to_numeric(tabla_final['Capacidad_Total']).fillna(0).astype(int)
    
    tabla_final['¿Operativa?'] = tabla_final['¿Operativa?'].map({1: 'SÍ', 0: 'NO'}).fillna('NO')

    # --- CÁLCULO PORCENTUAL ---
    tabla_final['Disponibilidad_%'] = (tabla_final['Bicis_Disponibles'] / tabla_final['Capacidad_Total'].replace(0, 1)) * 100
    tabla_final['Disponibilidad_%'] = tabla_final['Disponibilidad_%'].round(1)

    # Crear una columna combinada para facilitar la búsqueda por Texto o por ID (QR)
    tabla_final['Busqueda_Label'] = "ID: " + tabla_final['ID'].astype(str) + " - " + tabla_final['Nombre']

    return tabla_final

def obtener_ruta_osrm(lat1, lon1, lat2, lon2):
    """Obtiene el trazado de la ruta por calles conectando a la API libre de OSRM"""
    url = f"https://router.project-osrm.org/route/v1/foot/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url).json()
        if 'routes' in resp and len(resp['routes']) > 0:
            coords = resp['routes'][0]['geometry']['coordinates']
            return [[c[1], c[0]] for c in coords]  # Invierte a [lat, lon] para Plotly
    except:
        pass
    return None

def calcular_distancia_a_ruta(lat_est, lon_est, ruta_coords):
    """Mide la distancia mínima en metros entre una cicloestación y cualquier punto del trayecto"""
    if not ruta_coords:
        return 0.0
    ruta_lats = np.array([r[0] for r in ruta_coords])
    ruta_lons = np.array([r[1] for r in ruta_coords])
    # Conversión aproximada rápida: 1 grado en CDMX ~ 111,000 metros
    distancias = np.sqrt((ruta_lats - lat_est)**2 + (ruta_lons - lon_est)**2) * 111000
    return distancias.min()

try:
    with st.spinner("Cargando datos en tiempo real..."):
        df_original = obtener_datos_ecobici()
        df = df_original.copy()

    # --- BARRA LATERAL (Solo para filtros globales) ---
    st.sidebar.header("Filtros Globales")
    solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles", value=False)
    if solo_con_bicis:
        df = df[df['Bicis_Disponibles'] > 0]
        
    radio_cercania = st.sidebar.slider("Rango de cercanía a la ruta (metros):", min_value=100, max_value=700, value=300, step=50)

    # --- MÉTRICAS PRINCIPALES ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Estaciones most
