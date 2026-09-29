"""Gera uma amostra SINTÉTICA com o mesmo layout do CSV oficial do consumidor.gov.br.

Empresas e números são fictícios; servem para testar e demonstrar o pipeline sem baixar
os arquivos oficiais (dezenas de MB por mês). Para dados reais, veja o README.

Rodar: python data/gerar_amostra.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

HEADER = [
    "Região", "UF", "Cidade", "Sexo", "Faixa Etária", "Ano Abertura", "Mês Abertura", "Data Abertura",
    "Data Resposta", "Data Finalização", "Tempo Resposta", "Nome Fantasia", "Segmento de Mercado", "Área",
    "Assunto", "Grupo Problema", "Problema", "Como Comprou Contratou", "Procurou Empresa", "Respondida",
    "Situação", "Avaliação Reclamação", "Nota do Consumidor",
]

BANCOS = "Bancos, Financeiras e Administradoras de Cartão"
TELECOM = "Operadoras de Telecomunicações (Telefonia, Internet, TV por assinatura)"
VAREJO = "Comércio Eletrônico"

# empresa: (segmento, peso no volume, prob. de resolver, tempo médio de resposta)
EMPRESAS = {
    "Banco Alfa (fictício)": (BANCOS, 5, 0.70, 6),
    "Fintech Beta (fictícia)": (BANCOS, 4, 0.82, 3),
    "Cartões Zeta (fictícia)": (BANCOS, 2, 0.48, 9),
    "Telecom Gama (fictícia)": (TELECOM, 5, 0.55, 8),
    "Operadora Ômega (fictícia)": (TELECOM, 3, 0.63, 7),
    "Loja Delta (fictícia)": (VAREJO, 4, 0.76, 4),
    "Marketplace Épsilon (fictício)": (VAREJO, 3, 0.66, 5),
}

PROBLEMAS = {
    BANCOS: [("Cobrança / Contestação", "Cobrança por serviço/produto não contratado / não reconhecido / não solicitado"),
             ("Cobrança / Contestação", "Cobrança indevida / abusiva"),
             ("Contrato / Oferta", "Dificuldade para cancelar o cartão"),
             ("Atendimento / SAC", "Dificuldade de contato / acesso a outros canais")],
    TELECOM: [("Cobrança / Contestação", "Cobrança indevida / abusiva"),
              ("Vício de Qualidade", "Serviço não fornecido / interrompido"),
              ("Contrato / Oferta", "Dificuldade / atraso no cancelamento")],
    VAREJO: [("Entrega do Produto", "Não entrega / demora na entrega do produto"),
             ("Vício de Qualidade", "Produto danificado / com defeito"),
             ("Contrato / Oferta", "Dificuldade / atraso na devolução de valores pagos")],
}
UFS = [("Sudeste", "SP", "São Paulo"), ("Sudeste", "RJ", "Rio de Janeiro"), ("Sul", "RS", "Porto Alegre"),
       ("Nordeste", "BA", "Salvador"), ("Sudeste", "MG", "Belo Horizonte")]


def gerar(n: int = 600, seed: int = 42) -> list[list[str]]:
    rng = random.Random(seed)
    nomes = list(EMPRESAS)
    pesos = [EMPRESAS[e][1] for e in nomes]
    rows = []
    for _ in range(n):
        empresa = rng.choices(nomes, pesos)[0]
        segmento, _, p_resolve, tempo_medio = EMPRESAS[empresa]
        grupo, problema = rng.choice(PROBLEMAS[segmento])
        regiao, uf, cidade = rng.choice(UFS)
        abertura = date(2026, 1, 1) + timedelta(days=rng.randrange(0, 243))
        respondida = rng.random() < 0.97
        tempo = max(1, round(rng.gauss(tempo_medio, 2))) if respondida else ""
        avaliada = respondida and rng.random() < 0.7
        if avaliada:
            resolvida = rng.random() < p_resolve
            situacao = "Finalizada avaliada - Resolvida" if resolvida else "Finalizada avaliada - Não Resolvida"
            avaliacao = "Resolvida" if resolvida else "Não Resolvida"
            nota = str(rng.choice([4, 5]) if resolvida else rng.choice([1, 1, 2, 3]))
        else:
            situacao, avaliacao, nota = "Finalizada não avaliada", "Não Avaliada", ""
        rows.append([
            regiao, uf, cidade, rng.choice(["M", "F"]), rng.choice(["entre 21 a 30 anos", "entre 31 a 40 anos", "entre 41 a 50 anos"]),
            str(abertura.year), str(abertura.month), abertura.strftime("%d/%m/%Y"), "", "", str(tempo), empresa,
            segmento, "Serviços Financeiros" if segmento == BANCOS else "Outros", "Assunto", grupo, problema,
            rng.choice(["Internet", "Telefone", "Loja física"]), rng.choice(["S", "N"]), "S" if respondida else "N",
            situacao, avaliacao, nota,
        ])
    return rows


if __name__ == "__main__":
    out = Path(__file__).parent / "amostra_sintetica.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(HEADER)
        writer.writerows(gerar())
    print(f"escrito {out}")
