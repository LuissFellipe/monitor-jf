import json
from pathlib import Path

DS = {"type": "grafana-postgresql-datasource", "uid": "monitor-pg"}
paineis = []
DIA = "to_char(data, 'DD/MM') || ' (' || (array['dom','seg','ter','qua','qui','sex','sáb'])[extract(dow from data)::int + 1] || ')'"


def painel(tipo, titulo, sql, x, y, w, h, formato="table", **extra):
    paineis.append({
        "id": len(paineis) + 1,
        "type": tipo,
        "title": titulo,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"refId": "A", "datasource": DS, "rawQuery": True, "editorMode": "code",
                     "format": formato, "rawSql": sql}],
        **extra,
    })


def linha(titulo, y):
    paineis.append({"id": len(paineis) + 1, "type": "row", "title": titulo, "collapsed": False,
                    "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})


def limites(*passos):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in passos]}


def stat(titulo, sql, x, y, w, cores):
    painel("stat", titulo, sql, x, y, w, 4,
           fieldConfig={"defaults": {"thresholds": limites(*cores), "color": {"mode": "thresholds"}}, "overrides": []},
           options={"colorMode": "background", "graphMode": "none", "textMode": "value",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}})


def tabela(titulo, sql, x, y, w, h, vazio="Sem registros"):
    painel("table", titulo, sql, x, y, w, h,
           fieldConfig={"defaults": {"noValue": vazio, "custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
                        "overrides": []},
           options={"showHeader": True, "cellHeight": "sm"})


linha("Meus locais", 0)
stat("Interrupções programadas nos meus locais",
     "select count(*) as total from marts.fct_meus_locais where data >= current_date",
     0, 1, 6, [(None, "green"), (1, "red")])
tabela("Próximas interrupções nos meus locais",
       f"""select local, servico, {DIA} as dia, horario, bairro, detalhe, situacao
          from marts.fct_meus_locais where data >= current_date order by data, local""",
       6, 1, 18, 8, vazio="Nenhuma interrupção programada nos seus locais")
tabela("Locais monitorados",
       "select nome as local, array_to_string(bairros, ', ') as bairros, rua, numero from raw.locais",
       0, 5, 6, 4)

linha("Próximos dias em Juiz de Fora", 9)
stat("Ruas com desligamento de luz",
     "select count(*) from marts.fct_interrupcoes where servico = 'luz' and data >= current_date",
     0, 10, 8, [(None, "blue")])
stat("Bairros afetados (luz)",
     "select count(distinct bairro) from marts.fct_interrupcoes where servico = 'luz' and data >= current_date",
     8, 10, 8, [(None, "blue")])
stat("Avisos de água ativos",
     "select count(distinct local) from marts.fct_interrupcoes where servico = 'agua' and data >= current_date",
     16, 10, 8, [(None, "blue")])
painel("barchart", "Ruas sem luz por dia",
       f"""select {DIA} as dia, count(*) as ruas
          from marts.fct_interrupcoes where servico = 'luz' and data >= current_date
          group by data order by data""",
       0, 14, 8, 9,
       fieldConfig={"defaults": {"color": {"mode": "fixed", "fixedColor": "orange"}}, "overrides": []},
       options={"orientation": "auto", "showValue": "always", "legend": {"showLegend": False},
                "xTickLabelRotation": 0})
tabela("Desligamentos programados (CEMIG)",
       f"""select {DIA} as dia, to_char(inicio, 'HH24:MI') || '–' || to_char(termino, 'HH24:MI') as horario,
                 bairro, logradouro, status
          from staging.stg_cemig__desligamentos where data >= current_date order by data, bairro, logradouro""",
       8, 14, 16, 9)

linha("Histórico", 23)
painel("bargauge", "Bairros com mais interrupções registradas",
       """select bairro,
                 count(distinct data) filter (where servico = 'luz')
                 + count(distinct local) filter (where servico = 'agua' and bairro <> 'Nao Identificado') as ocorrencias
          from marts.fct_interrupcoes where $__timeFilter(data)
          group by bairro order by ocorrencias desc limit 15""",
       0, 24, 12, 12,
       fieldConfig={"defaults": {"color": {"mode": "continuous-YlRd"}, "min": 0}, "overrides": []},
       options={"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                "reduceOptions": {"calcs": [], "fields": "", "values": True}})
tabela("Avisos de abastecimento (Cesama)",
       """select to_char(coalesce(data_evento, publicado_em), 'DD/MM/YYYY') as data, titulo,
                 array_to_string(bairros, ', ') as bairros
          from raw.cesama_avisos where $__timeFilter(coalesce(data_evento, publicado_em)) order by coalesce(data_evento, publicado_em) desc""",
       12, 24, 12, 12)

linha("Saúde da coleta", 36)
tabela("Situação por fonte",
       """select fonte, ultima_coleta_ok, ultima_falha, execucoes_7d, falhas_7d,
                 case when atrasada then 'ATRASADA' else 'OK' end as situacao
          from marts.fct_saude_coleta order by fonte""",
       0, 37, 12, 6)
painel("timeseries", "Registros por coleta",
       """select fim as time, fonte as metric, registros as value
          from raw.execucoes where sucesso and $__timeFilter(fim) order by fim""",
       12, 37, 12, 6, formato="time_series",
       fieldConfig={"defaults": {"custom": {"drawStyle": "points", "pointSize": 8}}, "overrides": []})
tabela("Alertas enviados",
       "select enviado_em, local, tipo, entregue, mensagem from raw.alertas where $__timeFilter(enviado_em) order by enviado_em desc limit 50",
       0, 43, 24, 8, vazio="Nenhum alerta enviado ainda")

dashboard = {
    "uid": "monitor-jf",
    "title": "Monitor de luz e água — Juiz de Fora",
    "tags": ["cemig", "cesama", "juiz de fora"],
    "timezone": "browser",
    "refresh": "5m",
    "time": {"from": "now-30d", "to": "now"},
    "schemaVersion": 39,
    "panels": paineis,
}
destino = Path(__file__).parent / "dashboards" / "monitor-jf.json"
destino.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2))
print(f"{len(paineis)} painéis em {destino}")
