from datetime import datetime, date

def calculaValorComJuros(tipo_juros, data_vencimento, valorAtual, valorJuros, valorMulta):
    data_hoje = date.today()
    valorComJuros = valorAtual 
    diferencaDias = abs(data_hoje - data_vencimento).days

    if tipo_juros == 'R$':
        valorComJuros = valorAtual + (diferencaDias * valorJuros) + valorMulta
    elif tipo_juros == '%':
        valorComJuros = valorAtual * (1 + valorJuros / 100) ** diferencaDias + valorMulta

    return valorComJuros

data = date.fromisoformat("2025-12-31")
print(calculaValorComJuros('%', data, 100, 10, 2))
