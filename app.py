import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Ecobici CDMX", layout="wide")
st.title("🚲 Mapa de Estaciones Ecobici")

@st.cache_data(ttl=60)
def obtener_datos_ecobici():
    url_info = "https://gbfs.mex.lyftbikes.com/gbfs/en/station_information.json"
    url_status = "https://gbfs.mex.lyftbikes.com/gbfs/en/station_status.json"

    resp_info = requests.get(url_info).json()
    df_info = pd.DataFrame(resp_info['data']['stations'])

    resp_status = requests.get(url_status).json()
    df_status = pd.DataFrame(resp_status['data']['stations'])

    tabla_final = pd.merge(
        df_info[['station_id', 'name', 'lat', 'lon', 'capacity']],
        df_status[['station_id', 'num_bikes_available', 'num_docks_available', 'is_renting']],
        on='station_id'
    )

    tabla_final.columns = [
        'ID', 'Nombre', 'Latitud', 'Longitud',
        'Capacidad_Total', 'Bicis_Disponibles',
        'Puertos_Libres', '¿Operativa?'
    ]
    tabla_final['¿Operativa?'] = tabla_final['¿Operativa?'].map({1: 'SÍ', 0: 'NO'})

    return tabla_final

try:
    with st.spinner("Cargando datos en tiempo real..."):
        df = obtener_datos_ecobici()

    col1, col2, col3 = st.columns(3)
    col1.metric("Estaciones totales", len(df))
    col2.metric("Bicis disponibles", df['Bicis_Disponibles'].sum())
    col3.metric("Puertos libres", df['Puertos_Libres'].sum())

    fig = px.scatter_mapbox(
        df,
        lat="Latitud",
        lon="Longitud",
        hover_name="Nombre",
        hover_data={
            "Bicis_Disponibles": True,
            "Puertos_Libres": True,
            "Capacidad_Total": True,
            "Latitud": False,
            "Longitud": False
        },
        zoom=11,
        height=700
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos en tabla"):
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar los datos: {e}")
