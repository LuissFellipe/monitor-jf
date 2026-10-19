from datetime import date, time
from pathlib import Path

import pytest

import alertas
from cesama import data_do_evento, relevante
from texto import bairros_no_texto, normalizar_logradouro

BAIRROS = ["CENTRO", "RETIRO", "NOSSA SENHORA APARECIDA", "RECANTO DA MATA", "RECANTO DA MATA II", "MANOEL HONORIO"]


def test_data_com_mes_por_extenso():
    texto = "Nesta quinta-feira, 1º de outubro, dois serviços poderão afetar"
    assert data_do_evento("Duas interrupções nesta quinta-feira, 1º", texto, date(2026, 9, 30)) == date(2026, 10, 1)


def test_data_so_com_dia_da_semana_vira_o_mes():
    assert data_do_evento("Manutenção na Região Norte nesta sexta-feira, 2", "", date(2026, 9, 29)) == date(2026, 10, 2)


def test_data_so_com_dia_da_semana_no_mesmo_mes():
    assert data_do_evento("Afeta o Jardim da Serra na quinta-feira, 15", "", date(2026, 10, 9)) == date(2026, 10, 15)


def test_data_ausente():
    assert data_do_evento("Cesama lança concurso", "sem datas aqui", date(2026, 10, 9)) is None


def test_virada_de_ano():
    assert data_do_evento("x", "no dia 5 de janeiro", date(2026, 12, 28)) == date(2027, 1, 5)


def test_bairros_com_acento_e_nome_contido():
    texto = "afeta Nossa Senhora Aparecida, Recanto da Mata II e parte de Manoel Honório"
    assert bairros_no_texto(texto, BAIRROS) == ["MANOEL HONORIO", "NOSSA SENHORA APARECIDA", "RECANTO DA MATA II"]


def test_bairro_nao_casa_dentro_de_palavra():
    assert bairros_no_texto("Avenida Retirolandia", BAIRROS) == []


def test_regiao_centro_nao_e_o_bairro_centro():
    assert bairros_no_texto("afeta as regiões Leste, Centro e Sudeste", BAIRROS) == []
    assert bairros_no_texto("no Centro, na Rua Halfeld", BAIRROS) == ["CENTRO"]


def test_relevancia():
    assert relevante("Manutenção pode afetar abastecimento na Região Norte")
    assert relevante("Duas interrupções no abastecimento de água")
    assert not relevante("Coral Cesama reúne integrantes")


def test_abreviacao_de_logradouro():
    assert normalizar_logradouro("R. Halfeld") == normalizar_logradouro("RUA HALFELD")


def local(**extra):
    base = {"nome": "Casa", "bairros": {"RECANTO DA MATA"}, "rua": None, "numero": None}
    return base | extra


DESLIGAMENTO = {"data": date(2026, 10, 20), "bairro": "RECANTO DA MATA", "logradouro": "RUA DAS FLORES",
                "inicio": time(10), "termino": time(17), "status": "AGENDADA", "numeros": "10, 12, 14"}


def test_luz_por_bairro():
    assert alertas.afeta_luz(local(), DESLIGAMENTO)
    assert not alertas.afeta_luz(local(bairros={"CENTRO"}), DESLIGAMENTO)


def test_luz_por_rua_e_numero():
    assert alertas.afeta_luz(local(rua="RUA DAS FLORES", numero="12"), DESLIGAMENTO)
    assert not alertas.afeta_luz(local(rua="RUA DAS FLORES", numero="99"), DESLIGAMENTO)
    assert not alertas.afeta_luz(local(rua="RUA DOS LIRIOS"), DESLIGAMENTO)


def test_agua_por_bairro():
    assert alertas.afeta_agua(local(), {"bairros": ["CENTRO", "RECANTO DA MATA"]})
    assert not alertas.afeta_agua(local(), {"bairros": []})


EXEMPLO = Path(__file__).resolve().parents[2] / "config.exemplo.toml"


@pytest.mark.skipif(not EXEMPLO.exists(), reason="config de exemplo fica na raiz do repositório")
def test_config_de_exemplo_carrega():
    locais = alertas.carregar_locais(EXEMPLO)
    assert locais[0]["rua"] == "RUA HALFELD" and locais[0]["numero"] == "100"
    assert "SAO MATEUS" in locais[1]["bairros"]
