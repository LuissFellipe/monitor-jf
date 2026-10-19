select
    url,
    titulo,
    publicado_em,
    coalesce(data_evento, publicado_em) as data,
    data_evento is null as data_estimada,
    initcap(bairro) as bairro
from {{ source('raw', 'cesama_avisos') }}
cross join lateral unnest(case when cardinality(bairros) = 0 then array['NAO IDENTIFICADO'] else bairros end) as bairro
