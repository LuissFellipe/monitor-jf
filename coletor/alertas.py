import os
import tomllib
from datetime import date, timedelta
from pathlib import Path

import requests

from texto import normalizar, normalizar_logradouro

CONFIG = Path(os.getenv("CONFIG_LOCAIS", "config.toml"))


def carregar_locais(caminho=CONFIG):
    with open(caminho, "rb") as f:
        locais = tomllib.load(f)["locais"]
    return [
        {
            "nome": l["nome"],
            "bairros": {normalizar(b) for b in l["bairros"]},
            "rua": normalizar_logradouro(l["rua"]) if l.get("rua") else None,
            "numero": str(l["numero"]) if l.get("numero") else None,
        }
        for l in locais
    ]


def sincronizar_locais(conn, locais):
    conn.execute("delete from raw.locais")
    with conn.cursor() as cur:
        cur.executemany(
            "insert into raw.locais (nome, bairros, rua, numero) values (%s, %s, %s, %s)",
            [(l["nome"], sorted(l["bairros"]), l["rua"], l["numero"]) for l in locais],
        )


def numeros_da_lista(texto):
    return {n.strip() for n in texto.split(",") if n.strip()}


def afeta_luz(local, desligamento):
    if normalizar(desligamento["bairro"]) not in local["bairros"]:
        return False
    if local["rua"] and local["rua"] != normalizar_logradouro(desligamento["logradouro"]):
        return False
    numeros = numeros_da_lista(desligamento["numeros"])
    return not (local["numero"] and local["rua"] and numeros and local["numero"] not in numeros)


def afeta_agua(local, aviso):
    return bool(local["bairros"] & set(aviso["bairros"]))


def formatar_data(d):
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    return f"{dias[d.weekday()]}, {d:%d/%m}"


def enviar_telegram(mensagem):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": mensagem},
        timeout=30,
    )
    return resp.ok


def registrar(conn, chaves, local, tipo, mensagem):
    chaves = [chaves] if isinstance(chaves, str) else chaves
    novas = [c for c in chaves if not conn.execute("select 1 from raw.alertas where chave = %s", (c,)).fetchone()]
    if not novas:
        return False
    entregue = enviar_telegram(mensagem)
    print(f"[alerta{'' if entregue else ' sem telegram'}] {mensagem}", flush=True)
    with conn.cursor() as cur:
        cur.executemany(
            "insert into raw.alertas (chave, local, tipo, mensagem, entregue) values (%s, %s, %s, %s, %s)",
            [(c, local, tipo, mensagem, entregue) for c in novas],
        )
    return True


def mensagem_luz(local, data, itens, prefixo):
    linhas = [f"{prefixo} Desligamento de energia (CEMIG) — {local['nome']}", formatar_data(data)]
    for d in sorted(itens, key=lambda d: (d["inicio"], d["logradouro"])):
        numeros = f" (nº {d['numeros']})" if d["numeros"] and len(d["numeros"]) <= 40 else ""
        linhas.append(f"• {d['inicio']:%H:%M}–{d['termino']:%H:%M} {d['logradouro'].title()}, {d['bairro'].title()}{numeros}")
    return "\n".join(linhas)


def chave_luz(local, d, tipo):
    return f"luz|{local['nome']}|{d['data']}|{d['bairro']}|{d['logradouro']}|{d['inicio']}|{tipo}"


def pendentes(conn, local, itens, tipo):
    return [d for d in itens
            if not conn.execute("select 1 from raw.alertas where chave = %s", (chave_luz(local, d, tipo),)).fetchone()]


def verificar(conn, locais, hoje=None):
    hoje = hoje or date.today()
    amanha = hoje + timedelta(days=1)
    enviados = 0
    colunas = ["data", "bairro", "logradouro", "inicio", "termino", "status", "numeros"]
    desligamentos = [
        dict(zip(colunas, linha))
        for linha in conn.execute(
            f"select {', '.join(colunas)} from raw.cemig_desligamentos where data >= %s", (hoje,)
        ).fetchall()
    ]
    avisos = [
        dict(zip(["url", "titulo", "data_evento", "bairros"], linha))
        for linha in conn.execute(
            "select url, titulo, data_evento, bairros from raw.cesama_avisos where coalesce(data_evento, publicado_em) >= %s",
            (hoje,),
        ).fetchall()
    ]
    for local in locais:
        afetados = [d for d in desligamentos if afeta_luz(local, d)]
        for data in sorted({d["data"] for d in afetados}):
            do_dia = [d for d in afetados if d["data"] == data]
            ativos = [d for d in do_dia if "CANCEL" not in d["status"]]
            cancelados = [d for d in do_dia if "CANCEL" in d["status"]
                          and conn.execute("select 1 from raw.alertas where chave = %s",
                                           (chave_luz(local, d, "novo"),)).fetchone()]
            grupos = [("vespera", "⏰ AMANHÃ:", ativos)] if data == amanha else [("novo", "⚡", ativos)]
            grupos.append(("cancelado", "✅ CANCELADO:", cancelados))
            for tipo, prefixo, itens in grupos:
                novos = pendentes(conn, local, itens, tipo)
                if novos:
                    tipos = [tipo, "novo"] if tipo == "vespera" else [tipo]
                    chaves = [chave_luz(local, d, t) for d in novos for t in tipos]
                    enviados += registrar(conn, chaves, local["nome"], tipo, mensagem_luz(local, data, novos, prefixo))
        for a in avisos:
            if not afeta_agua(local, a):
                continue
            quando = formatar_data(a["data_evento"]) if a["data_evento"] else "data não identificada"
            enviados += registrar(
                conn, f"agua|{local['nome']}|{a['url']}", local["nome"], "agua",
                f"💧 Possível falta de água (Cesama) — {local['nome']}\n{quando}\n{a['titulo']}\n{'https://www.cesama.com.br/' + a['url']}",
            )
    return enviados


def alertar_falha(conn, fonte, erro):
    registrar(conn, f"falha|{fonte}|{date.today()}", "monitor", "falha",
              f"🛠️ A coleta da {fonte} falhou hoje: {erro}"[:500])
