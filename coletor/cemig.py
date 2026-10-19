import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://www.cemig.com.br/wp-json"
CIDADE = "JUIZ DE FORA"
CABECALHO = {"User-Agent": "Mozilla/5.0 (monitor-jf)"}


def post(caminho, dados=None, tentativas=4):
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(f"{BASE}/{caminho}/v1/send-form", data=dados, headers=CABECALHO, timeout=30)
            resp.raise_for_status()
            return resp.json() if resp.text.strip() else {}
        except (requests.RequestException, ValueError):
            if tentativa == tentativas:
                raise
            time.sleep(2 ** tentativa)


def listar_bairros():
    return [b["id"] for b in post("api-form-desligamento-bairro", {"cidade": CIDADE})]


def desligamentos_do_bairro(bairro):
    resposta = post("api-form-desligamento", {"cidade": CIDADE, "bairro": bairro})
    if not isinstance(resposta, dict):
        return []
    linhas = []
    for data, ruas in resposta.items():
        for logradouro, info in ruas.items():
            linhas.append({
                "data": data,
                "bairro": info.get("bairro") or bairro,
                "logradouro": logradouro.strip(),
                "inicio": info["inicio"],
                "termino": info["termino"],
                "status": info["status"].strip().upper(),
                "numeros": info.get("numeros", ""),
            })
    return linhas


def coletar(conn):
    bairros = listar_bairros()
    if len(bairros) < 100:
        raise RuntimeError(f"API da CEMIG devolveu só {len(bairros)} bairros")
    with ThreadPoolExecutor(max_workers=4) as pool:
        linhas = [l for lote in pool.map(desligamentos_do_bairro, bairros) for l in lote]
    with conn.cursor() as cur:
        cur.executemany(
            "insert into raw.cemig_bairros (bairro) values (%s) on conflict (bairro) do update set atualizado_em = now()",
            [(b,) for b in bairros],
        )
        cur.executemany(
            """insert into raw.cemig_desligamentos (data, bairro, logradouro, inicio, termino, status, numeros)
               values (%(data)s, %(bairro)s, %(logradouro)s, %(inicio)s, %(termino)s, %(status)s, %(numeros)s)
               on conflict (data, bairro, logradouro, inicio) do update set
                   termino = excluded.termino,
                   status = excluded.status,
                   numeros = excluded.numeros,
                   ultimo_visto = now()""",
            linhas,
        )
    return len(linhas)
