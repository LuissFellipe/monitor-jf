import html
import re
from datetime import date, datetime, timedelta

import requests

from texto import bairros_no_texto, normalizar

BASE = "https://www.cesama.com.br"
CABECALHO = {"User-Agent": "Mozilla/5.0 (monitor-jf)"}
JANELA_DIAS = 60
MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS_SEMANA = r"(?:segunda|terca|quarta|quinta|sexta)(?: feira)?|sabado|domingo"
PALAVRAS_CHAVE = ("ABASTECIMENTO", "INTERRUP", "SEM AGUA", "FALTA DE AGUA")


def obter(caminho, params=None):
    resp = requests.get(f"{BASE}/{caminho}", params=params, headers=CABECALHO, timeout=30)
    resp.raise_for_status()
    return resp.text


def listar(pagina):
    pagina_html = obter("getitens-blog", {"tipo": "listagem", "pag": pagina, "maximo": 20,
                                          "categoria": 0, "busca": "abastecimento"})
    itens = re.findall(
        r'href="(noticia/[^"]+)".*?<span class="data">(\d{2}\.\d{2}\.\d{4})</span>\s*(.*?)\s*</div>',
        pagina_html, re.S,
    )
    return [(url, datetime.strptime(d, "%d.%m.%Y").date(), html.unescape(t).strip()) for url, d, t in itens]


def texto_da_noticia(url):
    pagina = obter(url)
    artigo = re.search(r'<article class="a-noticia">(.*?)</article>', pagina, re.S)
    trecho = artigo.group(1) if artigo else ""
    trecho = re.sub(r"<header>.*?</header>", " ", trecho, flags=re.S)
    trecho = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", trecho, flags=re.S)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", trecho))
    return re.sub(r"\s+", " ", texto).strip()


def data_do_evento(titulo, texto, publicado_em):
    alvo = normalizar(f"{titulo} . {texto}").lower()
    completa = re.search(r"\b(\d{1,2})o? de (" + "|".join(MESES) + r")\b", alvo)
    if completa:
        dia, mes = int(completa.group(1)), MESES.index(completa.group(2)) + 1
        ano = publicado_em.year + (1 if mes < publicado_em.month - 6 else 0)
        return date(ano, mes, dia)
    so_dia = re.search(r"\b(?:" + DIAS_SEMANA + r") (\d{1,2})o?\b", alvo)
    if not so_dia:
        return None
    dia = int(so_dia.group(1))
    candidato = publicado_em.replace(day=1)
    while True:
        try:
            evento = candidato.replace(day=dia)
        except ValueError:
            evento = None
        if evento and evento >= publicado_em - timedelta(days=3):
            return evento
        candidato = (candidato + timedelta(days=32)).replace(day=1)


def relevante(titulo):
    return any(p in normalizar(titulo) for p in PALAVRAS_CHAVE)


def coletar(conn):
    bairros = [b for (b,) in conn.execute("select bairro from raw.cemig_bairros").fetchall()]
    conhecidos = {u for (u,) in conn.execute("select url from raw.cesama_avisos").fetchall()}
    limite = date.today() - timedelta(days=JANELA_DIAS)
    novos = 0
    for pagina in range(1, 10):
        itens = listar(pagina)
        if not itens:
            break
        for url, publicado_em, titulo in itens:
            if url in conhecidos or publicado_em < limite or not relevante(titulo):
                continue
            texto = texto_da_noticia(url)
            conn.execute(
                """insert into raw.cesama_avisos (url, titulo, publicado_em, data_evento, bairros, texto)
                   values (%s, %s, %s, %s, %s, %s) on conflict (url) do nothing""",
                (url, titulo, publicado_em, data_do_evento(titulo, texto, publicado_em),
                 bairros_no_texto(f"{titulo} {texto}", bairros), texto),
            )
            novos += 1
        if min(p for _, p, _ in itens) < limite:
            break
    return novos
