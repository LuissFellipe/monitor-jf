import os
import subprocess
import time
from datetime import datetime, timedelta

import psycopg

import alertas
import cemig
import cesama
from banco import conectar, preparar

HORAS = sorted(int(h) for h in os.getenv("HORAS_EXECUCAO", "7,19").split(","))


def aguardar_banco():
    for _ in range(30):
        try:
            with conectar():
                return
        except psycopg.OperationalError:
            time.sleep(2)
    raise RuntimeError("Postgres indisponível")


def executar_fonte(conn, nome, funcao):
    inicio = datetime.now().astimezone()
    try:
        registros = funcao(conn)
        conn.execute(
            "insert into raw.execucoes (fonte, inicio, sucesso, registros) values (%s, %s, true, %s)",
            (nome, inicio, registros),
        )
        conn.commit()
        print(f"{nome}: {registros} registros", flush=True)
    except Exception as erro:
        conn.rollback()
        conn.execute(
            "insert into raw.execucoes (fonte, inicio, sucesso, erro) values (%s, %s, false, %s)",
            (nome, inicio, repr(erro)[:2000]),
        )
        alertas.alertar_falha(conn, nome, erro)
        conn.commit()
        print(f"{nome}: falhou ({erro!r})", flush=True)


def executar():
    with conectar() as conn:
        preparar(conn)
        conn.commit()
        executar_fonte(conn, "CEMIG", cemig.coletar)
        executar_fonte(conn, "Cesama", cesama.coletar)
    dbt = subprocess.run(["dbt", "build", "--profiles-dir", "dbt_monitor", "--project-dir", "dbt_monitor"],
                         capture_output=True, text=True)
    print(dbt.stdout[-1500:], dbt.stderr[-1500:], flush=True)
    with conectar() as conn:
        if dbt.returncode != 0:
            alertas.alertar_falha(conn, "dbt", "dbt build falhou")
        enviados = alertas.verificar(conn, alertas.carregar_locais())
        print(f"{enviados} alertas novos", flush=True)


def proxima_execucao(agora):
    for hora in HORAS:
        alvo = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
        if alvo > agora:
            return alvo
    return agora.replace(hour=HORAS[0], minute=0, second=0, microsecond=0) + timedelta(days=1)


def main():
    aguardar_banco()
    executar()
    while True:
        alvo = proxima_execucao(datetime.now())
        print(f"próxima execução em {alvo:%d/%m/%Y %H:%M}", flush=True)
        time.sleep((alvo - datetime.now()).total_seconds())
        executar()


if __name__ == "__main__":
    main()
