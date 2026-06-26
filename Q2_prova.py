
import base64
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Configurações iniciais da página Streamlit
st.set_page_config(page_title="Painel SUS", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(BASE_DIR, "CIA014_SUS_Prova_2.xlsx")
LOGO_PATH = os.path.join(BASE_DIR, "Logo_IESB.png")

# Carregamento de dados
@st.cache_data
def load_data():
    return pd.read_excel(XLSX_PATH, sheet_name="SUS_TABLE")

df = load_data()

# Métricas Globais
TOTAL_QTD = df["QTD_Total"].sum()
TOTAL_VL = df["VL_Total"].sum()
CUSTO_MED = TOTAL_VL / TOTAL_QTD

# Agregações (UF)
uf_df = df.groupby("UF", as_index=False).agg(QTD=("QTD_Total", "sum"), VL=("VL_Total", "sum"))
uf_df["VL_Medio"] = uf_df["VL"] / uf_df["QTD"]
uf_df["pct"] = uf_df["VL"] / uf_df["VL"].sum() * 100
uf_sorted = uf_df.sort_values("QTD", ascending=False).reset_index(drop=True)

# Agregações (Regiões)
col_hab = [c for c in df.columns if "Habitantes" in c or "Habitants" in c][0]
pop_df = (
    df.drop_duplicates("Codigo_Municipio")
    .groupby("Regiao_Nome", as_index=False)[col_hab]
    .sum()
    .rename(columns={col_hab: "HAB"})
    .sort_values("HAB", ascending=False)
)

muni_df = (
    df.groupby(["Nome_Municipio", "UF", "Regiao_Nome", "LONGITUDE", "LATITUDE"], as_index=False)
    .agg(QTD=("QTD_Total", "sum"), VL=("VL_Total", "sum"))
)
muni_df = muni_df[muni_df["QTD"] > 0].copy()

ALL_REGIOES = sorted(df["Regiao_Nome"].dropna().unique())
ALL_UFS = sorted(df["UF"].dropna().unique())
uf_regiao = df[["UF", "Regiao_Nome"]].drop_duplicates().set_index("UF")["Regiao_Nome"].to_dict()

COR_REGIAO = {
    "Centro-Oeste": "#1f77b4",
    "Nordeste": "#ff7f0e",
    "Norte": "#2ca02c",
    "Sudeste": "#e377c2",
    "Sul": "#8c564b",
}

# Funções de Gráficos (Mantendo sua lógica do Plotly)
def fig_tabela():
    total_row = pd.DataFrame([{
        "UF": "Total", "QTD": uf_sorted["QTD"].sum(),
        "VL": uf_sorted["VL"].sum(), "pct": 100.0, "VL_Medio": CUSTO_MED,
    }])
    tbl = pd.concat([total_row, uf_sorted], ignore_index=True)
    n = len(tbl)
    fills = ["#DDEEFF" if i == 0 else ("#EEF4FF" if i % 2 == 0 else "white") for i in range(n)]
    fcolors = ["#1565C0" if i == 0 else "#333333" for i in range(n)]

    fig = go.Figure(go.Table(
        header=dict(
            values=["<b>UF</b>", "<b>Qtd. Procedimentos</b>", "<b>Valor Total (R$)</b>",
                    "<b>% Valor Gasto</b>", "<b>Valor Médio (R$)</b>"],
            fill_color="white", line_color="#CCCCCC",
            align=["left", "right", "right", "right", "right"], height=36,
        ),
        cells=dict(
            values=[
                tbl["UF"],
                tbl["QTD"].apply(lambda x: f"{x:,.0f}".replace(",", ".")),
                tbl["VL"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
                tbl["pct"].apply(lambda x: f"{x:.2f}%".replace(".", ",")),
                tbl["VL_Medio"].apply(lambda x: f"{x:.2f}".replace(".", ",")),
            ],
            fill_color=[fills] * 5,
            font=dict(color=[fcolors] * 5, size=12),
            align=["left", "right", "right", "right", "right"], height=30,
        ),
    ))
    fig.update_layout(margin=dict(t=10, b=10, l=0, r=0), height=30 * n + 80)
    return fig

def fig_mapa():
    traces = []
    for reg in sorted(muni_df["Regiao_Nome"].unique()):
        pts = muni_df[muni_df["Regiao_Nome"] == reg]
        size = (pts["VL"] / 1e6).apply(lambda v: max(4, min(22, v**0.45)))
        traces.append(go.Scattergeo(
            lon=pts["LONGITUDE"], lat=pts["LATITUDE"],
            text=pts.apply(lambda r: f"{r['Nome_Municipio']} ({r['UF']})<br>QTD: {r['QTD']:,.0f}<br>VL: R$ {r['VL']/1e6:.2f} mi", axis=1),
            hoverinfo="text", name=reg,
            marker=dict(color=COR_REGIAO.get(reg, "#999"), size=size, opacity=0.75, line=dict(width=0)),
        ))
    fig = go.Figure(traces)
    fig.update_layout(
        geo=dict(scope="south america", showland=True, landcolor="#E8E8E8", showocean=True, oceancolor="#D0E8F0",
                 center=dict(lon=-52, lat=-14), projection=dict(type="mercator", scale=3.2)),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05),
        margin=dict(t=10, b=60, l=0, r=0), height=580,
    )
    return fig

def fig_habitantes(regioes=None):
    data = pop_df if not regioes else pop_df[pop_df["Regiao_Nome"].isin(regioes)]
    fig = go.Figure(go.Bar(
        x=data["Regiao_Nome"], y=data["HAB"] / 1e6,
        marker_color=[COR_REGIAO.get(r, "#888") for r in data["Regiao_Nome"]],
        hovertemplate="%{x}<br>%{y:.1f} mi hab<extra></extra>",
    ))
    fig.update_layout(yaxis=dict(title="Número de habitantes (milhões)", tickformat=".1f", gridcolor="#EEEEEE"), xaxis=dict(title="Região"), height=400)
    return fig

def fig_uf_barras(ufs=None):
    data = uf_sorted if not ufs else uf_sorted[uf_sorted["UF"].isin(ufs)]
    data = data.sort_values("QTD", ascending=True)
    fig = go.Figure(go.Bar(
        x=data["QTD"] / 1e6, y=data["UF"], orientation="h",
        marker_color="#2196F3",
        hovertemplate="%{y}: %{x:.1f} mi<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(title="Quantidade total dos Procedimentos (milhões)", gridcolor="#EEEEEE"), height=max(400, 28 * len(data) + 80))
    return fig

# ── RENDERIZAÇÃO DO LAYOUT STREAMLIT ──

# Header com Logo Lateral
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
with col_title:
    st.markdown("<h2 style='margin-top: 10px;'>Painel SUS — CIA014</h2>", unsafe_allow_html=True)

# Criação das Abas nativas do Streamlit
tab1, tab2, tab3, tab4 = st.tabs(["Painel Geral", "Tabela por UF", "Análise por Região", "Painel por Região"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Quantidade Total Geral", value=f"{TOTAL_QTD/1e6:.0f} mi")
    with col2:
        st.metric(label="Valor Total Geral", value=f"R$ {TOTAL_VL/1e9:.0f} bi")
    
    st.info(f"Ao cruzar os dois valores acima, é possível notar um custo médio aproximado de R$ {CUSTO_MED:.2f} por procedimento. "
            "Esse valor mostra não apenas a importância do SUS no acesso à saúde, mas também o desafio de administrar um grande volume de assistência médica com alta eficiência de custos.")

with tab2:
    st.caption("Made by Victor Rangel")
    st.plotly_chart(fig_tabela(), use_container_width=True)

with tab3:
    st.subheader("Quantidade total dos Procedimentos por Municípios Brasil")
    st.plotly_chart(fig_mapa(), use_container_width=True)

with tab4:
    st.subheader("Filtros Dinâmicos")
    col_reg, col_uf = st.columns(2)
    
    with col_reg:
        regioes_sel = st.multiselect("Filtrar por Região", options=ALL_REGIOES, placeholder="Todas as regiões")
    
    # Lógica de filtro em cascata (Callback implícito do Streamlit)
    if regioes_sel:
        ufs_disponiveis = sorted([u for u, r in uf_regiao.items() if r in regioes_sel])
    else:
        ufs_disponiveis = ALL_UFS
        
    with col_uf:
        ufs_sel = st.multiselect("Filtrar por UF", options=ufs_disponiveis, placeholder="Todas as UFs")

    # Lógica de plotagem condicional baseada nos filtros ativos
    ufs_bar = ufs_sel if ufs_sel else (ufs_disponiveis if regioes_sel else None)
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.plotly_chart(fig_habitantes(regioes_sel if regioes_sel else None), use_container_width=True)
    with col_g2:
        st.plotly_chart(fig_uf_barras(ufs_bar), use_container_width=True)