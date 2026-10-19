select
    data,
    initcap(bairro) as bairro,
    initcap(logradouro) as logradouro,
    inicio,
    termino,
    round((extract(epoch from (termino - inicio)) / 3600)::numeric, 1) as duracao_horas,
    status,
    status like '%CANCEL%' as cancelado,
    cardinality(array_remove(string_to_array(replace(numeros, ' ', ''), ','), '')) as qtd_numeros,
    primeiro_visto,
    data - primeiro_visto::date as dias_de_antecedencia
from {{ source('raw', 'cemig_desligamentos') }}
