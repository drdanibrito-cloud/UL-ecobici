import streamlit as st
import pandas as pd
import requests
import plotly.express as px

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

    return tabla_final

try:
    with st.spinner("Cargando datos en tiempo real..."):
        df_original = obtener_datos_ecobici()
        df = df_original.copy()

    # --- BARRA LATERAL / FILTROS ---
    st.sidebar.header("Filtros de Búsqueda")
    
    # Checkbox solicitado para filtrar si hay o no hay bicis
    solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles", value=False)
    if solo_con_bicis:
        df = df[df['Bicis_Disponibles'] > 0]

    # --- NUEVO: BUSCADOR POR NOMBRE O CÓDIGO QR ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Localizar Estación")
    
    metodo_busqueda = st.sidebar.radio(
        "Buscar por:",
        options=["Nombre", "Código Estación / QR"]
    )

    if metodo_busqueda == "Nombre":
        opciones = ["Seleccionar..."] + sorted(df['Nombre'].unique().tolist())
        seleccion = st.sidebar.selectbox("Elige o escribe el nombre:", opciones)
        estacion_encontrada = df[df['Nombre'] == seleccion] if seleccion != "Seleccionar..." else pd.DataFrame()
    else:
        opciones = ["Seleccionar..."] + sorted(df['ID'].unique().tolist(), key=int)
        seleccion = st.sidebar.selectbox("Elige o escribe el código numérico:", opciones)
        estacion_encontrada = df[df['ID'] == seleccion] if seleccion != "Seleccionar..." else pd.DataFrame()

    # Variables de control para el mapa dinámico
    zoom_actual = 11
    lat_centro = df['Latitud'].mean()
    lon_centro = df['Longitud'].mean()

    # Si se encontró una estación válida en el buscador, mostramos sus métricas numéricas dedicadas
    if not estacion_encontrada.empty:
        estacion_info = estacion_encontrada.iloc[0]
        
        # Ajustar vista del mapa a la estación
        lat_centro = estacion_info['Latitud']
        lon_centro = estacion_info['Longitud']
        zoom_actual = 15
        
        st.sidebar.markdown("### 📊 Estatus de Estación")
        st.sidebar.metric("🚲 Bicis Disponibles", f"{estacion_info['Bicis_Disponibles']} u.")
        st.sidebar.metric("🔌 Puertos Libres", f"{estacion_info['Puertos_Libres']} u.")
        st.sidebar.caption(f"Capacidad total: {estacion_info['Capacidad_Total']} | Porcentaje: {estacion_info['Disponibilidad_%']}%")
        st.sidebar.markdown("---")

    # --- METRICAS GENERALES ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Estaciones mostradas", len(df))
    col2.metric("Bicis disponibles", df['Bicis_Disponibles'].sum())
    col3.metric("Puertos libres", df['Puertos_Libres'].sum())

    # --- MAPA ---
    fig = px.scatter_mapbox(
        df,
        lat="Latitud",
        lon="Longitud",
        color="Disponibilidad_%",           
        color_continuous_scale="Viridis",  
        range_color=[0, 100],              
        hover_name="Nombre",
        hover_data={
            "Disponibilidad_%": ":.1f}%",  
            "Bicis_Disponibles": True,     
            "Capacidad_Total": True,
            "Latitud": False,
            "Longitud": False
        },
        zoom=zoom_actual,
        center={"lat": lat_centro, "lon": lon_centro},
        height=700
    )
    
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title="Disponibilidad",
            ticksuffix="%"                
        )
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- TABLA DE DATOS ---
    with st.expander("Ver datos en tabla"):
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar los datos: {e}")
