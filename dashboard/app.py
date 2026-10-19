import os
import re
import tomllib
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg://monitor:monitor@localhost:5435/monitor"))
CONFIG = os.getenv("CONFIG_LOCAIS", "config.toml")

st.set_page_config(page_title="Monitor de luz e água — Juiz de Fora", layout="wide")


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]", " ", sem_acento)).strip().upper()


@st.cache_data(ttl=300)
def consultar(sql):
    with engine.connect() as con:
        return pd.read_sql(text(sql), con)


def existe(tabela):
    return consultar(f"select to_regclass('{tabela}') is not null as existe").existe[0]


st.title("Monitor de luz e água — Juiz de Fora")
st.caption("Desligamentos programados da CEMIG e avisos de abastecimento da Cesama, coletados duas vezes por dia.")

if not existe("marts.fct_interrupcoes"):
    st.info("A primeira coleta ainda está rodando (leva cerca de 1 minuto). Recarregue a página em seguida.")
    st.stop()

try:
    with open(CONFIG, "rb") as f:
        locais = tomllib.load(f)["locais"]
except FileNotFoundError:
    locais = []

proximos = consultar("select * from marts.fct_interrupcoes where data >= current_date order by data, servico, bairro")
proximos["chave_bairro"] = proximos.bairro.map(normalizar)

st.header("Meus locais")
if not locais:
    st.warning("Nenhum local configurado. Copie config.exemplo.toml para config.toml e preencha.")
for local in locais:
    bairros = {normalizar(b) for b in local["bairros"]}
    meus = proximos[proximos.chave_bairro.isin(bairros)]
    if local.get("rua"):
        meus = meus[(meus.servico == "agua") | (meus.local.map(normalizar) == normalizar(local["rua"]))]
    titulo = f"{local['nome']} — {', '.join(local['bairros'])}"
    if meus.empty:
        st.success(f"**{titulo}**: nenhuma interrupção programada.")
    else:
        st.error(f"**{titulo}**: {len(meus)} interrupção(ões) programada(s).")
        st.dataframe(meus.drop(columns="chave_bairro"), hide_index=True, width="stretch")

if existe("raw.alertas"):
    alertas = consultar("select enviado_em, local, tipo, mensagem, entregue from raw.alertas order by enviado_em desc limit 20")
    with st.expander(f"Alertas enviados ({len(alertas)})"):
        st.dataframe(alertas, hide_index=True, width="stretch")

st.header("Próximos dias na cidade")
luz = proximos[proximos.servico == "luz"]
c1, c2, c3 = st.columns(3)
c1.metric("Ruas com desligamento de luz", len(luz))
c2.metric("Bairros afetados (luz)", luz.bairro.nunique())
c3.metric("Avisos de água ativos", proximos[proximos.servico == "agua"].local.nunique())
if not luz.empty:
    por_dia = luz.groupby(["data", "bairro"]).size().reset_index(name="ruas")
    st.plotly_chart(
        px.bar(por_dia, x="data", y="ruas", color="bairro", labels={"data": "", "ruas": "Ruas sem luz"}),
        width="stretch",
    )
st.dataframe(proximos.drop(columns="chave_bairro"), hide_index=True, width="stretch")

st.header("Histórico por bairro")
st.caption("O histórico começa na primeira coleta. A CEMIG só publica os próximos dias, então este banco é o registro.")
bairros = consultar("select * from marts.agg_bairros order by posicao limit 20")
st.plotly_chart(
    px.bar(bairros.sort_values("dias_sem_luz"), x=["dias_sem_luz", "avisos_agua"], y="bairro", orientation="h",
           labels={"value": "Ocorrências", "bairro": "", "variable": ""}, height=600),
    width="stretch",
)

st.header("Saúde da coleta")
st.dataframe(consultar("select * from marts.fct_saude_coleta"), hide_index=True, width="stretch")
