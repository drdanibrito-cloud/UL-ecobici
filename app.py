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
    # Conversión aproximada rápida: 1 grado de latitud/longitud en CDMX ~ 111,000 metros
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
    col1.metric("Estaciones mostradas", len(df))
    col2.metric("Bicis disponibles", df['Bicis_Disponibles'].sum())
    col3.metric("Puertos libres", df['Puertos_Libres'].sum())

    st.markdown("---")

    # --- SECCIÓN SUPERIOR DEL MAPA: TRAZADOR DE RUTAS POR QR / NOMBRE ---
    st.subheader("🗺️ Trazar Ruta y Ver Disponibilidad Cercana")
    
    opciones_busqueda = ["Selecciona una cicloestación..."] + sorted(df['Busqueda_Label'].tolist())
    
    c_orig, c_dest = st.columns(2)
    with c_orig:
        origen_sel = st.selectbox("🚲 Punto de Origen (QR o Nombre):", options=opciones_busqueda, key="origen_ruta")
    with c_dest:
        destino_sel = st.selectbox("🏁 Punto de Destino (QR o Nombre):", options=opciones_busqueda, key="destino_ruta")

    # Inicializar parámetros por defecto del mapa
    zoom_actual = 11
    lat_centro = df['Latitud'].mean()
    lon_centro = df['Longitud'].mean()
    ruta_linea = None

    # Lógica de cálculo si se seleccionan ambos puntos
    if origen_sel != "Selecciona una cicloestación..." and destino_sel != "Selecciona una cicloestación...":
        est_origen = df[df['Busqueda_Label'] == origen_sel].iloc[0]
        est_destino = df[df['Busqueda_Label'] == destino_sel].iloc[0]
        
        # --- NUEVO WIDGET: DETALLE NUMÉRICO DE LAS ESTACIONES ELEGIDAS ---
        st.markdown("### 📊 Disponibilidad en Estaciones Seleccionadas")
        det_col1, det_col2 = st.columns(2)
        
        with det_col1:
            st.metric(
                label=f"🚲 Bicis Libres en Origen ({est_origen['Nombre']})", 
                value=f"{est_origen['Bicis_Disponibles']} u.",
                delta=f"Capacidad: {est_origen['Capacidad_Total']}",
                delta_color="off"
            )
        with det_col2:
            st.metric(
                label=f"🔌 Puertos Libres en Destino ({est_destino['Nombre']})", 
                value=f"{est_destino['Puertos_Libres']} u.",
                delta=f"Capacidad: {est_destino['Capacidad_Total']}",
                delta_color="off"
            )
        # -----------------------------------------------------------------

        with st.spinner("Calculando trayecto óptimo entre estaciones..."):
            ruta_linea = obtener_ruta_osrm(est_origen['Latitud'], est_origen['Longitud'], est_destino['Latitud'], est_destino['Longitud'])
        
        if r_linea := ruta_linea:
            # Calcular distancias y filtrar el DataFrame de estaciones
            df['Metros_a_Ruta'] = df.apply(lambda r: calcular_distancia_a_ruta(r['Latitud'], r['Longitud'], r_linea), axis=1)
            df = df[df['Metros_a_Ruta'] <= radio_cercania]
            
            # Ajustar encuadre del mapa al punto de partida
            lat_centro = est_origen['Latitud']
            lon_centro = est_origen['Longitud']
            zoom_actual = 14
        else:
            st.error("No se pudo conectar al servidor de mapas para trazar la línea física del camino.")

    # --- RECONSTRUCCIÓN DEL MAPA INTERACTIVO CON FILTRADO DE RUTA ---
    fig = go.Figure()

    # 1. Añadir los marcadores secuenciales de Ecobici
    if not df.empty:
        fig.add_trace(go.Scattermapbox(
            lat=df['Latitud'],
            lon=df['Longitud'],
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=11,
                color=df['Disponibilidad_%'],
                colorscale='Viridis',
                cmin=0,
                cmax=100,
                showscale=True,
                colorbar=dict(title="Disponibilidad", ticksuffix="%")
            ),
            text=df['Nombre'],
            hovertemplate="<b>%{text}</b><br>" +
                          "Bicis Disponibles: " + df['Bicis_Disponibles'].astype(str) + "<br>" +
                          "Puertos Libres: " + df['Puertos_Libres'].astype(str) + "<br>" +
                          "Ocupación: %{marker.color:.1f}%<extra></extra>"
        ))

    # 2. Añadir la línea del trayecto si ya fue calculada por OSRM
    if ruta_linea:
        fig.add_trace(go.Scattermapbox(
            lat=[p[0] for p in ruta_linea],
            lon=[p[1] for p in ruta_linea],
            mode='lines',
            line=dict(width=4, color='#FF4500'),  # Línea naranja/roja vibrante para distinguir el camino
            name='Trayecto vial'
        ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center={"lat": lat_centro, "lon": lon_centro},
            zoom=zoom_actual
        ),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=650,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # --- TABLA DE DATOS ---
    with st.expander("Ver datos en tabla"):
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar los datos: {e}")
