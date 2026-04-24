import streamlit as st
import pandas as pd
import pydeck as pdk
import numpy as np

# --- CONFIG ---
st.set_page_config(page_title="AZ AI Water Model", layout="wide")
st.title("🏜️ Arizona 'Day Zero' AI Water Model")

# --- 1. DATA LOADING ---
@st.cache_data
def load_data():
    pool_df = pd.read_csv('pool_elevation.csv')
    gw_df = pd.read_csv('ADWR_Groundwater_Subbasin_2024.csv')
    
    phx_subbasins = gw_df[gw_df['AMA_CODE'] == 'C'].copy()
    
    coords = {
        'EAST SALT RIVER VALLEY': {'lat': 33.41, 'lon': -111.72},
        'WEST SALT RIVER VALLEY': {'lat': 33.50, 'lon': -112.15},
        'LAKE PLEASANT': {'lat': 33.85, 'lon': -112.25},
        'CAREFREE': {'lat': 33.82, 'lon': -111.91},
        'HASSAYAMPA': {'lat': 33.45, 'lon': -112.70},
        'FOUNTAIN HILLS': {'lat': 33.60, 'lon': -111.71},
        'RAINBOW VALLEY': {'lat': 33.20, 'lon': -112.45}
    }
    
    phx_subbasins['lat'] = phx_subbasins['SUBBASIN_NAME'].map(lambda x: coords.get(x, {}).get('lat'))
    phx_subbasins['lon'] = phx_subbasins['SUBBASIN_NAME'].map(lambda x: coords.get(x, {}).get('lon'))
    
    return pool_df, phx_subbasins.dropna(subset=['lat'])

pool_df, phx_data = load_data()

# --- 2. RECALIBRATED SIMULATION CONTROLS ---
st.sidebar.header("🕹️ Simulation Controls")

years = st.sidebar.slider("Timeline (Years into Future)", 1, 100, 25)
ai_growth = st.sidebar.slider("New AI Data Centers", 0, 100, 30)
temp_rise = st.sidebar.slider("Temperature Rise (°C)", 0.0, 5.0, 1.5, step=0.01)

# --- 3. THE "REALISTIC" MATH ENGINE ---
# RECALIBRATION: 
# A typical hyperscale data center uses ~1,000 acre-feet/year.
# Spread across a massive sub-basin, the "regional" impact is small but cumulative.
base_decline = 2.1 
ai_impact_per_center = 0.08  # Each center adds ~1 inch of regional drawdown/yr
climate_mult = 1.0 + (temp_rise * 0.05) # 5% increase in evaporation/demand per degree

# Calculate annual rate
total_annual_drop = (base_decline + (ai_growth * ai_impact_per_center)) * climate_mult

# Calculate total depth over time
current_avg_depth = 144.0 
total_drawdown = total_annual_drop * years
predicted_depth = current_avg_depth + total_drawdown

# --- 4. 2D COLOR LOGIC (Balanced for Capstone) ---
def get_color(depth):
    # These thresholds reflect actual Arizona water management tiers
    if depth < 250: return [40, 180, 99, 140]    # Green (Safe)
    elif depth < 400: return [241, 196, 15, 160] # Yellow (Caution)
    elif depth < 600: return [230, 126, 34, 180] # Orange (Critical)
    else: return [192, 57, 43, 220]              # Red (Economic Failure)

phx_data['fill_color'] = [get_color(predicted_depth)] * len(phx_data)

# --- 5. DASHBOARD ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📊 Model Output")
    # Using 'Drawdown' as the delta to make sense of the direction
    st.metric("Future Water Depth", f"{predicted_depth:,.1f} ft", f"{total_annual_drop:+.2f} ft/yr", delta_color="inverse")
    
    st.markdown(f"**Current Year:** {2026 + years}")
    st.line_chart(pool_df.set_index('datetime')['pool elevation'])
    
    # Contextual Explanation
    with st.expander("📚 What does 'Future Water Depth' mean?"):
        st.write("""
        **Future Water Depth** is the distance from the ground surface down to the water table.
        
        - **144 ft (Today):** Shallow. Pumping is cheap.
        - **400 ft (Yellow):** Many domestic wells in the East Valley begin to go dry and must be deepened.
        - **600 ft+ (Orange/Red):** Critical stress. Pumping costs for data centers and cities double due to the energy required to lift water.
        """)

with col2:
    st.subheader("🗺️ Subbasin Depletion Map")
    
    layer = pdk.Layer(
        "ScatterplotLayer",
        phx_data,
        get_position='[lon, lat]',
        get_fill_color='fill_color',
        get_radius='Shape__Area / 60000', 
        pickable=True,
        opacity=0.6,
        stroked=True,
        line_width_min_pixels=2,
        get_line_color=[255, 255, 255]
    )

    view_state = pdk.ViewState(latitude=33.5, longitude=-112.0, zoom=8, pitch=0)

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json', 
        tooltip={"text": "Subbasin: {SUBBASIN_NAME}\nPredicted Depth: {predicted_depth:.1f} ft"}
    ))