from datetime import datetime, date, timedelta
from backend.database import get_db_connection, init_db
from sqlite3 import IntegrityError

class BoletoAPI:
    def __init__(self):
        init_db() # Garantir que a tabela exista quando o programa for aberto
        self.usuario_atual = None

    def listar_perfis(self):
        """ Retorna todos os usuários cadastrados para a tela de seleção """
        conn = get_db_connection()
        perfis = conn.execute("SELECT * FROM usuarios").fetchall()
        conn.close()
        return [dict(p) for p in perfis]

    def criar_perfil(self, dados):
        """ Recebe {nome: 'Joao', foto: 'data:image/png...'} """
        nome = dados['nome']
        foto = dados.get('foto', '')

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO usuarios (nome, foto) VALUES (?, ?)", (nome, foto,))
            conn.commit()
            
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            return {'status': 'sucesso', 'msg': 'Perfil criado!'}
        except IntegrityError:
            conn.close()
            return {'status': 'erro', 'msg': 'Já existe um perfil com este nome.'}

    def entrar_por_id(self, id_usuario):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (id_usuario,)).fetchone()
        conn.close()

        if user:
            self.usuario_atual = dict(user)
            return {'status': 'sucesso', 'usuario': self.usuario_atual}
        return {'status': 'erro', 'msg': 'Usuário não encontrado'}

    # def entrar_perfil(self, nome_usuario):
    #     """
    #     Tenta achar o usuário, se não existir, cria um novo.
    #     """
    #     if not nome_usuario:
    #         return { 'status': 'erro', 'msg': 'Digite um nome!' }
    #     
    #     conn = get_db_connection()
    #
    #     user = conn.execute("SELECT * FROM usuarios WHERE nome = ?", (nome_usuario,)).fetchone()
    #
    #     if not user:
    #         cursor = conn.execute("INSERT INTO usuarios (nome) VALUES (?)", (nome_usuario,))
    #         conn.commit()
    #         user_id = cursor.lastrowid
    #         user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    #     conn.close()
    #
    #     self.usuario_atual = dict(user)
    #     return { 'status': 'sucesso', 'usuario': self.usuario_atual }

    def logout(self):
        self.usuario_atual = None
        return { 'status': 'ok' }

    def salvar_lancamento(self, dados):
        """
        Recebe o objeto do Javascript e processa as parcelas
        """
        if not self.usuario_atual:
            return { 'status': 'erro', 'msg': 'Você precisa estar logado!' }
        try:
            conn = get_db_connection()

            # Preparar dados
            valor_por_parcela = float(dados['boleto']['valor'])
            data_inicial = datetime.strptime(dados['boleto']['vencimento'], '%Y-%m-%d').date()
            qtd_parcelas = int(dados['boleto']['parcelas'])

            # Lógica geração de datas
            datas_vencimento = []

            if dados['modo'] == 'custom' and dados['regra']:
                # Modo personalizado: "15/30/45"
                dias_extras = dados['regra'].split('/')
                for dia in dias_extras:
                    if dia == dias_extras[0]:
                        datas_vencimento.append(data_inicial)
                        continue
                    if dia.strip():
                        # Soma os dias à data inicial
                        nova_data = data_inicial + timedelta(days=int(dia))
                        datas_vencimento.append(nova_data)

                qtd_parcelas = len(datas_vencimento)

            else:
                # Modo mensal padrão
                datas_vencimento.append(data_inicial) # Adiciona a data escolhida como primeira
                for i in range(1, qtd_parcelas):
                    nova_data = data_inicial + timedelta(days=i * 30)
                    datas_vencimento.append(nova_data)

            for indice, data_venc in enumerate(datas_vencimento):
                conn.execute('''
                    INSERT INTO boletos (
                        usuario_id, empresa, categoria, placa, descricao,
                        valor_original, juros, multa, valor_total,
                        vencimento, numero_parcelas, total_parcelas
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    self.usuario_atual['id'],
                    dados['boleto']['empresa'],
                    dados['boleto']['categoria'],
                    dados['boleto']['placa'],
                    dados['boleto']['descricao'],
                    valor_por_parcela,
                    dados['boleto']['juros'],
                    dados['boleto']['multa'],
                    valor_por_parcela, # Aqui você pode somar juros/multa se quiser
                    data_venc.strftime('%Y-%m-%d'), # Converte data volta pra string
                    indice + 1,    # Parcela atual (1, 2, 3...)
                    qtd_parcelas   # Total (de 3)
                    ))

            conn.commit()
            conn.close()
            return { 'status': 'sucesso', 'msg': f'{qtd_parcelas} boletos gerados!' }
        
        except Exception as e:
            return { 'status': 'erro', 'msg': str(e) }

    def listar_boletos(self):
        if not self.usuario_atual:
            return []

        conn = get_db_connection()
        boletos = conn.execute("SELECT * FROM boletos WHERE usuario_id = ? ORDER BY vencimento ASC, valor_total ASC", (self.usuario_atual['id'],)).fetchall()
        conn.close()

        return [dict(b) for b in boletos]


    def calculaValorComJuros(self, dados):
        boleto = dados['boleto']
        tipo_juros = boleto['tipoJuros']

        # Tratamento das datas (ignora o horário)
        data_hoje = date.today()
        data_vencimento = date.fromisoformat(boleto['vencimento'])

        valor_original = float(boleto['valor'])
        valor_juros_input = float(boleto['juros'])
        valor_multa_input = float(boleto['multa'])

        # Retorna o valor original se a data de vencimento é anterior a atual
        if data_hoje <= data_vencimento:
            return valor_original

        dias_atraso = (data_hoje - data_vencimento).days

        valor_juros_total = 0.0

        # Cálculo valor juros
        if tipo_juros == 'R$':
            # Valor fixo diário
            valor_juros_total = dias_atraso * valor_juros_input
        elif tipo_juros == '%':
            # Juros simples diários
            valor_juros_total = valor_original * (valor_juros_input / 100) * dias_atraso

        valor_atualizado = valor_original + valor_juros_total + valor_multa_input
        return round(valor_atualizado, 2)
