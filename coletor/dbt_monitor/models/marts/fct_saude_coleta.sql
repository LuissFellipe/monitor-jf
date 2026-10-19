select
    fonte,
    max(fim) filter (where sucesso) as ultima_coleta_ok,
    max(fim) filter (where not sucesso) as ultima_falha,
    count(*) filter (where fim > now() - interval '7 days') as execucoes_7d,
    count(*) filter (where fim > now() - interval '7 days' and not sucesso) as falhas_7d,
    now() - max(fim) filter (where sucesso) > interval '24 hours' as atrasada
from {{ source('raw', 'execucoes') }}
group by fonte
