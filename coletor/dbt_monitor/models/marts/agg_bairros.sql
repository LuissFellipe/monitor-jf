with luz as (
    select
        bairro,
        count(distinct data) as dias_sem_luz,
        count(*) as ruas_afetadas,
        sum(duracao_horas) as horas_sem_luz_ruas
    from {{ ref('stg_cemig__desligamentos') }}
    where not cancelado
    group by bairro
),

agua as (
    select bairro, count(distinct url) as avisos_agua
    from {{ ref('stg_cesama__avisos') }}
    where bairro <> 'Nao Identificado'
    group by bairro
)

select
    coalesce(luz.bairro, agua.bairro) as bairro,
    coalesce(dias_sem_luz, 0) as dias_sem_luz,
    coalesce(ruas_afetadas, 0) as ruas_afetadas,
    coalesce(horas_sem_luz_ruas, 0) as horas_sem_luz_ruas,
    coalesce(avisos_agua, 0) as avisos_agua,
    rank() over (order by coalesce(dias_sem_luz, 0) + coalesce(avisos_agua, 0) desc) as posicao
from luz
full outer join agua on luz.bairro = agua.bairro
order by posicao
