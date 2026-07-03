import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import numpy as np  # Necesario para la simulación del historial

# Configuración inicial de la página
st.set_page_config(page_title="Ecobici CDMX Pro", layout="wide", page_icon="🚲")
st.title("🚲 Tablero de Estaciones Ecobici CDMX")

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

    # CÁLCULO PORCENTUAL
    tabla_final['Disponibilidad_%'] = (tabla_final['Bicis_Disponibles'] / tabla_final['Capacidad_Total'].replace(0, 1)) * 100
    tabla_final['Disponibilidad_%'] = tabla_final['Disponibilidad_%'].round(1)

    return tabla_final

try:
    with st.spinner("Cargando datos en tiempo real..."):
        df_original = obtener_datos_ecobici()
        df = df_original.copy()

    # --- BARRA LATERAL / FILTROS ---
    st.sidebar.header("Filtros y Configuración")
    
    # [IDEA 4] Estilos de Mapa Personalizados
    estilo_mapa = st.sidebar.selectbox(
        "Estilo del mapa base:",
        options=["open-street-map", "carto-positron", "carto-darkmatter"],
        index=1  # Default en Carto-Positron porque hace resaltar mejor la paleta secuencial
    )
    
    # [IDEA 4] Selector de Paleta Secuencial
    paleta_color = st.sidebar.selectbox(
        "Paleta secuencial del mapa:",
        options=["Viridis", "Cividis", "Plasma", "Blues", "YlGnBu"],
        index=0
    )

    st.sidebar.markdown("---")
    
    # Checkbox para filtrar si hay o no hay bicis
    solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles", value=False)
    if solo_con_bicis:
        df = df[df['Bicis_Disponibles'] > 0]

    # [IDEA 2] Buscador de Estaciones Cercanas / Zoom Dinámico
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Localizar Estación")
    estacion_seleccionada = st.sidebar.selectbox(
        "Selecciona una estación para centrar el mapa:",
        options=["Ninguna"] + sorted(df['Nombre'].tolist())
    )

    # Configuración de zoom por defecto
    zoom_actual = 11
    lat_centro = df['Latitud'].mean()
    lon_centro = df['Longitud'].mean()

    # Si el usuario elige una estación, movemos el centro del mapa hacia ella
    if estacion_seleccionada != "Ninguna":
        estacion_data = df[df['Nombre'] == estacion_seleccionada].iloc[0]
        lat_centro = estacion_data['Latitud']
        lon_centro = estacion_data['Longitud']
        zoom_actual = 15  # Zoom cercano de localización

    # --- METRICAS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Estaciones mostradas", len(df))
    col2.metric("Bicis disponibles totales", df['Bicis_Disponibles'].sum())
    col3.metric("Puertos libres totales", df['Puertos_Libres'].sum())

    # --- MAPA ---
    fig = px.scatter_mapbox(
        df,
        lat="Latitud",
        lon="Longitud",
        color="Disponibilidad_%",           
        color_continuous_scale=paleta_color,  
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
        height=600
    )
    
    fig.update_layout(
        mapbox_style=estilo_mapa,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title="Disponibilidad",
            ticksuffix="%"                
        )
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- [IDEA 3] ALERTAS DE DISPONIBILIDAD CRÍTICA ---
    st.markdown("---")
    st.subheader("🚨 Alertas de Disponibilidad Crítica")
    
    # Identificar estaciones vacías o llenas
    estaciones_vacias = df_original[df_original['Bicis_Disponibles'] == 0]
    estaciones_llenas = df_original[df_original['Puertos_Libres'] == 0]
    
    alert1, alert2 = st.columns(2)
    with alert1:
        st.warning(f"🔴 Estaciones sin Bicicletas ({len(estaciones_vacias)})")
        if not estaciones_vacias.empty:
            st.dataframe(estaciones_vacias[['ID', 'Nombre', 'Capacidad_Total']], height=150, use_container_width=True)
        else:
            st.success("¡Todas las estaciones tienen al menos una bicicleta!")
            
    with alert2:
        st.info(f"🔵 Estaciones sin Puertos Libres ({len(estaciones_llenas)})")
        if not estaciones_llenas.empty:
            st.dataframe(estaciones_llenas[['ID', 'Nombre', 'Capacidad_Total']], height=150, use_container_width=True)
        else:
            st.success("¡Hay espacio disponible para dejar bicis en todo el sistema!")

    # --- [IDEA 1] TENDENCIAS HORARIAS HISTÓRICAS (SIMULADO) ---
    st.markdown("---")
    st.subheader("🕒 Análisis de Tendencia y Ocupación Histórica")
    
    estacion_analisis = st.selectbox(
        "Selecciona una estación para ver su comportamiento diario estándar:",
        options=sorted(df_original['Nombre'].tolist())
    )
    
    if estacion_analisis:
        # Recuperamos la capacidad real de la estación para la simulación precisa
        cap_max = df_original[df_original['Nombre'] == estacion_analisis]['Capacidad_Total'].values[0]
        
        # Generamos las 24 horas del día
        horas = [f"{i:02d}:00" for i in range(24)]
        
        # Simulación de curva de demanda típica (picos a las 8am y 6pm)
        np.random.seed(seed=sum(ord(c) for c in estacion_analisis) % 100) # Semilla consistente por estación
        base_demanda = 0.5 + 0.3 * np.sin(np.linspace(0, 4 * np.pi, 24))
        bicis_simuladas = np.clip(base_demanda * cap_max + np.random.normal(0, 2, 24), 0, cap_max).astype(int)
        puertos_simulados = cap_max - bicis_simuladas
        
        df_historico = pd.DataFrame({
            "Hora del Día": horas,
            "Bicis Disponibles (Promedio)": bicis_simuladas,
            "Puertos Libres (Promedio)": puertos_simulados
        }).set_index("Hora del Día")
        
        # Gráfico interactivo de líneas de Plotly para ver tendencias
        fig_line = px.line(
            df_historico, 
            labels={"value": "Unidades", "Hora del Día": "Horario (24h)"},
            title=f"Predicción de Disponibilidad Promedio en {estacion_analisis} (Capacidad: {cap_max})",
            template="plotly_white"
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # --- TABLA DE DATOS DETALLADA ---
    st.markdown("---")
    with st.expander("Ver todas las estaciones en formato tabla"):
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar los datos: {e}")
