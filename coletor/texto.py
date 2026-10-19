import re
import unicodedata


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]", " ", sem_acento)).strip().upper()


ABREVIACOES = {"R": "RUA", "AV": "AVENIDA", "TV": "TRAVESSA", "AL": "ALAMEDA", "PC": "PRACA", "EST": "ESTRADA"}


def normalizar_logradouro(texto):
    palavras = normalizar(texto).split()
    if palavras and palavras[0] in ABREVIACOES:
        palavras[0] = ABREVIACOES[palavras[0]]
    return " ".join(palavras)


REGIOES = r"\bREGI(?:AO|OES)(?: (?:E|CENTRO|CENTRAL|NORTE|SUL|LESTE|OESTE|NORDESTE|NOROESTE|SUDESTE|SUDOESTE))+"


def bairros_no_texto(texto, bairros):
    alvo = f" {re.sub(REGIOES, ' ', normalizar(texto))} "
    encontrados = {b for b in bairros if f" {b} " in alvo}
    return sorted(b for b in encontrados if not any(b != o and f" {b} " in f" {o} " for o in encontrados))
