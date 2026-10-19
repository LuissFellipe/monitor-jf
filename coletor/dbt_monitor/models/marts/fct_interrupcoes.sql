select
    'luz' as servico,
    data,
    bairro,
    logradouro as local,
    duracao_horas,
    status as situacao
from {{ ref('stg_cemig__desligamentos') }}
where not cancelado

union all

select
    'agua' as servico,
    data,
    bairro,
    titulo as local,
    null as duracao_horas,
    case when data_estimada then 'DATA ESTIMADA' else 'AVISO' end as situacao
from {{ ref('stg_cesama__avisos') }}
