import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# Configuración inicial de la página
st.set_page_config(page_title="Asistente Ecobici CDMX", layout="wide", page_icon="🚲")
st.title("🚲 Asistente de Viaje Ecobici CDMX")
st.caption("Datos en tiempo real para planificar tu ruta y evitar estaciones vacías o llenas.")

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
    
    tabla_final['Latitud'] = pd.to_numeric(tabla_final['Latitud'])
    tabla_final['Longitud'] = pd.to_numeric(tabla_final['Longitud'])
    tabla_final['Bicis_Disponibles'] = pd.to_numeric(tabla_final['Bicis_Disponibles']).fillna(0).astype(int)
    tabla_final['Puertos_Libres'] = pd.to_numeric(tabla_final['Puertos_Libres']).fillna(0).astype(int)
    tabla_final['Capacidad_Total'] = pd.to_numeric(tabla_total = tabla_final['Capacidad_Total']).fillna(0).astype(int)
    
    tabla_final['¿Operativa?'] = tabla_final['¿Operativa?'].map({1: 'SÍ', 0: 'NO'}).fillna('NO')
    tabla_final['Disponibilidad_%'] = (tabla_final['Bicis_Disponibles'] / tabla_final['Capacidad_Total'].replace(0, 1)) * 100
    tabla_final['Disponibilidad_%'] = tabla_final['Disponibilidad_%'].round(1)
    tabla_final['Busqueda_Label'] = "ID: " + tabla_final['ID'].astype(str) + " - " + tabla_final['Nombre']

    return tabla_final

try:
    with st.spinner("Sincronizando con Ecobici..."):
        df_original = obtener_datos_ecobici()
        df = df_original.copy()

    # --- BARRA LATERAL: ALERTAS RÁPIDAS ---
    st.sidebar.header("⚠️ Alertas del Sistema")
    estaciones_vacias = df[df['Bicis_Disponibles'] == 0]
    estaciones_llenas = df[df['Puertos_Libres'] == 0]
    
    st.sidebar.error(f"🔴 Estaciones vacías: {len(estaciones_vacias)}")
    st.sidebar.warning(f"🔵 Estaciones llenas: {len(estaciones_llenas)}")
    
    st.sidebar.markdown("---")
    st.sidebar.header("Filtros")
    solo_con_bicis = st.sidebar.checkbox("Ocultar estaciones sin bicis", value=False)
    if solo_con_bicis:
        df = df[df['Bicis_Disponibles'] > 0]

    # --- MEJORA: PLANIFICADOR DE RUTA (ORIGEN / DESTINO) ---
    st.markdown("### 🗺️ Planifica tu Ruta")
    opciones_ruta = ["Seleccionar estación..."] + sorted(df['Busqueda_Label'].tolist())
    
    col_orig, col_dest = st.columns(2)
    
    with col_orig:
        origen = st.selectbox("1. ¿Dónde buscas bici? (Origen/QR):", options=opciones_ruta, key="orig")
        if origen != "Seleccionar estación...":
            data_o = df[df['Busqueda_Label'] == origen].iloc[0]
            if data_o['Bicis_Disponibles'] > 0:
                st.success(f"✅ ¡Disponible! Hay **{data_o['Bicis_Disponibles']}** bicis listas.")
            else:
                st.error("❌ ¡Alerta! No quedan bicis en esta estación.")

    with col_dest:
        destino = st.selectbox("2. ¿A dónde vas? (Destino/QR):", options=opciones_ruta, key="dest")
        if destino != "Seleccionar estación...":
            data_d = df[df['Busqueda_Label'] == destino].iloc[0]
            if data_d['Puertos_Libres'] > 0:
                st.success(f"✅ ¡Espacio libre! Hay **{data_d['Puertos_Libres']}** puertos para anclar.")
            else:
                st.error("❌ ¡Alerta! Estación llena. No podrás anclar tu bici aquí.")

    # Variables de mapa dinámicas basadas en la ruta seleccionada
    zoom_actual = 11
    lat_centro = df['Latitud'].mean()
    lon_centro = df['Longitud'].mean()

    # Si se selecciona un origen, el mapa se enfoca ahí prioritariamente
    if origen != "Seleccionar estación...":
        data_o = df[df['Busqueda_Label'] == origen].iloc[0]
        lat_centro, lon_centro, zoom_actual = data_o['Latitud'], data_o['Longitud'], 15

    st.markdown("---")

    # --- MAPA CON PALETA DE RELEVANCIA ---
    # Cambiamos a la paleta "Portland" o "Jet" que va de Rojo (Crítico/Vacío) a Azul/Verde (Lleno/Seguro)
    fig = px.scatter_mapbox(
        df,
        lat="Latitud",
        lon="Longitud",
        color="Disponibilidad_%",           
        color_continuous_scale="RdYlBu",  # Rojo = Vacío, Amarillo = Medio, Azul = Con bastantes bicis
        range_color=[0, 100],              
        hover_name="Nombre",
        hover_data={
            "Disponibilidad_%": ":.1f}%",  
            "Bicis_Disponibles": True,     
            "Puertos_Libres": True,
            "Latitud": False,
            "Longitud": False
        },
        zoom=zoom_actual,
        center={"lat": lat_centro, "lon": lon_centro},
        height=600
    )
    
    fig.update_layout(
        mapbox_style="carto-positron", # Cambiado a Carto-Positron para un look más limpio y moderno
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="Ocupación %")
    )
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Error al procesar los datos: {e}")
