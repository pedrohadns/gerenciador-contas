# Português

Sistema para gerenciamento de contas e boletos desenvolvido em Python, com interface gráfica seguindo padrão web (HTML, CSS e JS), integrada utilizando a bilioteca Pywebview. Para armazenamento dos dados, foi utilizado Sqlite.

## Funcionalidades

1. Múltiplos perfis para gerenciamento de diversas empresas/usuários.
1. Tela inicial com resumo das contas diárias, semanais, mensais e vencidas.
1. Cálculo automático de juros e multas.
1. Desconsidera feriados nacionais como dias úteis (importante para o cálculo de juros).
1. Algoritmo para inserção de contas parcelas automaticamente, incluindo pagamentos personalizados, por exemplo, uma conta parcelada com datas de vencimento daqui a 15, 30 e 45 dias é inserida corretamente.
1. Filtragem das contas a serem mostradas.
1. Backup automático dos bancos de dados.

## Utilização

O programa é feito para ser um executável, para que o mesmo seja gerado,é necessário que a biblioteca do Python `pyinstaller` esteja instalada, para fazer isso, basta executar:

``` bash
pip install pyinstaller
```

Após isso, execute:
``` bash
pyinstaller --noconsole --onefile --add-data "frontend/index.html;." main.py
```

O arquivo executável gerado estará no diretório dist.
