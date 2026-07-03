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

    # --- NUEVO: CÁLCULO PORCENTUAL ---
    # Evitamos división entre cero si una capacidad viene en 0
    tabla_final['Disponibilidad_%'] = (tabla_final['Bicis_Disponibles'] / tabla_final['Capacidad_Total'].replace(0, 1)) * 100
    # Redondeamos a un decimal para que se vea limpio en el mapa
    tabla_final['Disponibilidad_%'] = tabla_final['Disponibilidad_%'].round(1)

    return tabla_final

try:
    with st.spinner("Cargando datos en tiempo real..."):
        df = obtener_datos_ecobici()

    # --- BARRA LATERAL / FILTROS ---
    st.sidebar.header("Filtros de Búsqueda")
    
    # Checkbox solicitado para filtrar si hay o no hay bicis
    solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles", value=False)
    
    # Aplicar filtro si el checkbox está marcado
    if solo_con_bicis:
        df = df[df['Bicis_Disponibles'] > 0]

    # --- METRICAS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Estaciones mostradas", len(df))
    col2.metric("Bicis disponibles", df['Bicis_Disponibles'].sum())
    col3.metric("Puertos libres", df['Puertos_Libres'].sum())

    # --- MAPA MODIFICADO (PALETA SECUENCIAL Y PORCENTAJES) ---
    fig = px.scatter_mapbox(
        df,
        lat="Latitud",
        lon="Longitud",
        color="Disponibilidad_%",           # Ahora el color se rige por el porcentaje calculado
        color_continuous_scale="Viridis",  # Paleta secuencial limpia (puedes cambiarla por "Cividis", "Blues", etc.)
        range_color=[0, 100],              # Fijamos el rango de 0% a 100%
        hover_name="Nombre",
        hover_data={
            "Disponibilidad_%": ":.1f}%",  # Agrega el símbolo de % en el cuadro interactivo
            "Bicis_Disponibles": True,     # Conservamos las nominales como info secundaria opcional
            "Capacidad_Total": True,
            "Latitud": False,
            "Longitud": False
        },
        zoom=11,
        height=700
    )
    
    # Personalización de las etiquetas de la barra de colores y formato
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title="Disponibilidad",
            ticksuffix="%"                # Añade el signo % a las etiquetas de la barra de color lateral
        )
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- TABLA DE DATOS ---
    with st.expander("Ver datos en tabla"):
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar los datos: {e}")
