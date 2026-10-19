with locais as (
    select nome, bairro, rua, numero
    from {{ source('raw', 'locais') }}
    cross join lateral unnest(bairros) as bairro
),

luz as (
    select
        l.nome as local,
        'luz' as servico,
        d.data,
        to_char(d.inicio, 'HH24:MI') || '–' || to_char(d.termino, 'HH24:MI') as horario,
        initcap(d.bairro) as bairro,
        initcap(d.logradouro) as detalhe,
        d.status as situacao
    from {{ source('raw', 'cemig_desligamentos') }} d
    join locais l on d.bairro = l.bairro
    where (l.rua is null or regexp_replace(upper(d.logradouro), '[^A-Z0-9]+', ' ', 'g') = l.rua)
      and (l.numero is null or l.rua is null or d.numeros = ''
           or l.numero = any(string_to_array(replace(d.numeros, ' ', ''), ',')))
),

agua as (
    select distinct
        l.nome as local,
        'agua' as servico,
        coalesce(a.data_evento, a.publicado_em) as data,
        null as horario,
        initcap(l.bairro) as bairro,
        a.titulo as detalhe,
        case when a.data_evento is null then 'DATA ESTIMADA' else 'AVISO' end as situacao
    from {{ source('raw', 'cesama_avisos') }} a
    join locais l on l.bairro = any(a.bairros)
)

select * from luz
union all
select * from agua
