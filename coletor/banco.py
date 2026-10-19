import os

import psycopg

DDL = """
create schema if not exists raw;
create table if not exists raw.cemig_desligamentos (
    data date not null,
    bairro text not null,
    logradouro text not null,
    inicio time not null,
    termino time not null,
    status text not null,
    numeros text not null,
    primeiro_visto timestamptz not null default now(),
    ultimo_visto timestamptz not null default now(),
    primary key (data, bairro, logradouro, inicio)
);
create table if not exists raw.cemig_bairros (
    bairro text primary key,
    atualizado_em timestamptz not null default now()
);
create table if not exists raw.cesama_avisos (
    url text primary key,
    titulo text not null,
    publicado_em date not null,
    data_evento date,
    bairros text[] not null,
    texto text not null,
    coletado_em timestamptz not null default now()
);
create table if not exists raw.execucoes (
    id serial primary key,
    fonte text not null,
    inicio timestamptz not null,
    fim timestamptz not null default now(),
    sucesso boolean not null,
    registros int,
    erro text
);
create table if not exists raw.locais (
    nome text primary key,
    bairros text[] not null,
    rua text,
    numero text
);
create table if not exists raw.alertas (
    chave text primary key,
    local text not null,
    tipo text not null,
    mensagem text not null,
    entregue boolean not null,
    enviado_em timestamptz not null default now()
);
"""


def conectar():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5435"),
        user=os.getenv("PGUSER", "monitor"),
        password=os.getenv("PGPASSWORD", "monitor"),
        dbname=os.getenv("PGDATABASE", "monitor"),
    )


def preparar(conn):
    conn.execute(DDL)
