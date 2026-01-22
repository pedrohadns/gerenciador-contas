import math
import os
import shutil
from datetime import datetime, date, timedelta
from backend.database import get_db_connection, init_db
from sqlite3 import IntegrityError

class BoletoAPI:
    def __init__(self):
        init_db() # Garantir que a tabela exista quando o programa for aberto
        self.usuario_atual = None
        try:
            self.fazer_backup()
        except Exception as e:
            print(f"Alerta: Não foi possível fazer backup automático: {e}")

    def fazer_backup(self):
        # 1. Configurações
        NOME_BANCO = 'sistema_boletos.db'
        PASTA_BACKUP = 'backups'
        
        if not os.path.exists(PASTA_BACKUP):
            os.makedirs(PASTA_BACKUP)
        
        # 2. Gera nome SÓ com a DATA (Sem hora) -> backup_2025-01-06.db
        # Isso garante apenas 1 arquivo por dia
        hoje = datetime.now().strftime('%Y-%m-%d')
        nome_arquivo = f"backup_{hoje}.db"
        caminho_destino = os.path.join(PASTA_BACKUP, nome_arquivo)
        
        msg = ""

        # 3. Só faz o backup se ele AINDA NÃO EXISTIR hoje
        if not os.path.exists(caminho_destino):
            shutil.copy(NOME_BANCO, caminho_destino)
            msg = f"Backup automático criado: {nome_arquivo}"
            
            # 4. ROTAÇÃO: Apaga os antigos para sobrar só 5
            arquivos = sorted([
                os.path.join(PASTA_BACKUP, f) 
                for f in os.listdir(PASTA_BACKUP) 
                if f.endswith('.db')
            ], key=os.path.getmtime)

            while len(arquivos) > 5:
                arquivo_velho = arquivos.pop(0)
                os.remove(arquivo_velho)
        else:
            msg = "Backup de hoje já existe."

        return {'status': 'sucesso', 'msg': msg}

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

    def atualizar_perfil(self, dados):
        if not dados.get('id'):
            return {'status': 'erro', 'msg': 'ID do perfil não informado'}
            
        conn = get_db_connection()
        try:
            conn.execute("UPDATE usuarios SET nome = ?, foto = ? WHERE id = ?", 
                         (dados['nome'], dados['foto'], dados['id']))
            conn.commit()
            conn.close()
            return {'status': 'sucesso', 'msg': 'Perfil atualizado!'}
        except Exception as e:
            conn.close()
            return {'status': 'erro', 'msg': str(e)}

    def excluir_perfil(self, id_usuario):
        conn = get_db_connection()
        # Primeiro, verificamos se é o usuário atual para evitar crash
        if self.usuario_atual and self.usuario_atual['id'] == id_usuario:
            return {'status': 'erro', 'msg': 'Você não pode excluir o perfil que está logado!'}

        # Opcional: Apagar boletos desse usuário também?
        # Por segurança, vamos apagar o usuário e seus boletos (CASCADE manual)
        # conn.execute("DELETE FROM boletos WHERE usuario_id = ?", (id_usuario,))
        conn.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,))
        
        conn.commit()
        conn.close()
        return {'status': 'sucesso', 'msg': 'Perfil e dados excluídos.'}

    def entrar_por_id(self, id_usuario):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (id_usuario,)).fetchone()
        conn.close()

        if user:
            self.usuario_atual = dict(user)
            return {'status': 'sucesso', 'usuario': self.usuario_atual}
        return {'status': 'erro', 'msg': 'Usuário não encontrado'}

    def logout(self):
        self.usuario_atual = None
        return { 'status': 'ok', 'usuario':{ 'nome': '', 'foto': 'https://cdn-icons-png.flaticon.com/512/847/847969.png' } }

    def salvar_lancamento(self, dados):
        """
        Recebe o objeto do Javascript e processa as parcelas
        """
        if not self.usuario_atual:
            return {'status': 'erro', 'msg': 'Não logado'}
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
                        valor_original, juros, tipo_juros, multa, valor_total,
                        vencimento, numero_parcela, total_parcelas
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    self.usuario_atual['id'],
                    dados['boleto']['empresa'],
                    dados['boleto']['categoria'],
                    dados['boleto']['placa'],
                    dados['boleto']['descricao'],
                    valor_por_parcela,
                    dados['boleto']['juros'],
                    dados['boleto']['tipoJuros'],
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

    def calculaValorComJuros(self, boleto):
        tipo_juros = boleto.get('tipo_juros', 'R$')

        # Tratamento das datas (ignora o horário)
        data_hoje = date.today()
        if isinstance(boleto['vencimento'], str):
            data_vencimento = date.fromisoformat(boleto['vencimento'])
        else:
            data_vencimento = boleto['vencimento']

        data_vencimento_util = self.proximo_dia_util(data_vencimento)

        valor_original = float(boleto['valor_original'])
        valor_juros_input = float(boleto['juros']) if boleto['juros'] else 0.0
        valor_multa_input = float(boleto['multa']) if boleto['multa'] else 0.0

        # Retorna o valor original se a data de vencimento é anterior a atual
        if data_hoje <= data_vencimento_util:
            return valor_original

        dias_atraso = (data_hoje - data_vencimento_util).days

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

    def buscar_boletos(self, filtros, pagina=1, itens_por_pagina=30):
        if not self.estaLogado():
            return {'status': 'erro', 'msg': 'Login necessário'}

        conn = get_db_connection()
        params = [self.usuario_atual['id']]
        
        # 1. Construção Dinâmica do SQL
        sql_base = " FROM boletos WHERE usuario_id = ?"

        dt_ini = filtros.get('data_inicio')
        dt_fim = filtros.get('data_fim')
        criterio_data = ""
        params_data = []

        if dt_ini and dt_fim:
            criterio_data = "vencimento BETWEEN ? AND ?"
            params_data = [dt_ini, dt_fim]
        elif dt_ini:
            criterio_data = "vencimento >= ?" # A partir de...
            params_data = [dt_ini]
        elif dt_fim:
            criterio_data = "vencimento <= ?" # Até...
            params_data = [dt_fim]

        if criterio_data:
            if filtros.get('incluir_vencidos'):
                hoje_str = date.today().strftime('%Y-%m-%d')
                
                # Lógica: (Critério escolhido) OU (Pendente e Atrasado)
                sql_base += f""" 
                    AND (
                        ({criterio_data}) 
                        OR 
                        (status = 'Pendente' AND vencimento < ?)
                    )
                """
                params.extend(params_data)
                params.append(hoje_str)
            else:
                # Lógica Estrita (Só o critério)
                sql_base += f" AND ({criterio_data})"
                params.extend(params_data)

        if filtros.get('status'):
            sql_base += " AND status = ?"
            params.append(filtros['status'])

        if filtros.get('empresa'):
            sql_base += " AND empresa LIKE ?"
            params.append(f"%{filtros['empresa']}%")

        if filtros.get('placa'):
            sql_base += " AND placa LIKE ?" # LIKE permite buscar parcial
            params.append(f"%{filtros['placa']}%")

        if filtros.get('categoria'):
            sql_base += " AND categoria LIKE ?"
            params.append(filtros['categoria'])

        if filtros.get('data_pagamento'):
            sql_base += " AND data_pagamento = ?"
            params.append(filtros['data_pagamento'])

        # 2. Paginação
        total_itens = conn.execute(f"SELECT COUNT(*) {sql_base}", params).fetchone()[0]
        total_paginas = math.ceil(total_itens / itens_por_pagina)
        
        offset = (pagina - 1) * itens_por_pagina
        sql_final = f"""
            SELECT * {sql_base} 
            ORDER BY 
                CASE 
                    WHEN status = 'Pendente' AND vencimento < DATE('now', 'localtime') THEN 1 
                    WHEN status = 'Pendente' THEN 2 
                    ELSE 3 
                END ASC,
                vencimento ASC,
                valor_original DESC
            LIMIT ? OFFSET ?
        """
        params.extend([itens_por_pagina, offset])
        
        boletos_db = conn.execute(sql_final, params).fetchall()
        conn.close()

        # 3. Processamento (REUTILIZANDO SUA LÓGICA)
        lista_processada = []
        hoje = date.today()

        for b in boletos_db:
            boleto = dict(b)
            
            # Garante que data é objeto Date
            dt_vencimento = datetime.strptime(boleto['vencimento'], '%Y-%m-%d').date()

            dt_limite = self.proximo_dia_util(dt_vencimento) # Data limite para não ser considerado atraso

            valor_final = boleto['valor_original']
            dias_atraso = 0
            esta_vencido = False

            if boleto['status'] == 'Pendente' and hoje > dt_limite:
                dias_atraso = (hoje - dt_limite).days
                esta_vencido = True
                
                # AQUI ESTÁ A MÁGICA: Reutilizamos sua função!
                valor_final = self.calculaValorComJuros(boleto)

            # Injeta dados extras para o HTML
            boleto['valor_atualizado'] = valor_final
            boleto['dias_atraso'] = dias_atraso
            boleto['esta_vencido'] = esta_vencido
            
            lista_processada.append(boleto)

        return {
            'status': 'sucesso',
            'dados': lista_processada,
            'paginacao': {
                'atual': pagina,
                'total_paginas': total_paginas,
                'total_itens': total_itens
            }
        }

    def excluir_boleto(self, id_boleto):
        if not self.estaLogado():
            return {'status': 'erro', 'msg': 'Login necessário'}
        
        conn = get_db_connection()
        # O filtro usuario_id garante que ninguém apague boleto dos outros
        cursor = conn.execute("DELETE FROM boletos WHERE id = ? AND usuario_id = ?", 
                              (id_boleto, self.usuario_atual['id']))
        conn.commit()
        rows = cursor.rowcount
        conn.close()
        
        if rows > 0:
            return {'status': 'sucesso', 'msg': 'Boleto excluído com sucesso!'}
        return {'status': 'erro', 'msg': 'Boleto não encontrado.'}

    def pagar_boleto(self, dados):
        if not self.estaLogado():
            return {'status': 'erro', 'msg': 'Login necessário'}
        
        conn = get_db_connection()
        id_boleto = dados['id']
        banco = dados['banco']
        data_pagamento = dados['data']
        valor_pago = float(dados['valor'])
        
        conn.execute('''
            UPDATE boletos 
            SET status = 'Pago', 
                data_pagamento = ?, 
                banco_pagamento = ?,
                valor_total = ?
            WHERE id = ? AND usuario_id = ?
        ''', (data_pagamento, banco, valor_pago, id_boleto, self.usuario_atual['id']))
        
        conn.commit()
        conn.close()
        return {'status': 'sucesso', 'msg': 'Pagamento Registrado'}

    def atualizar_boleto(self, dados):
        if not self.estaLogado():
            return {'status': 'erro', 'msg': 'Login necessário'}
        
        boleto = dados['boleto']
        id_boleto = dados['id']
        
        try:
            conn = get_db_connection()
            # Convertendo a data para ISO
            data_venc = datetime.strptime(boleto['vencimento'], '%Y-%m-%d').date()
            
            conn.execute('''
                UPDATE boletos SET
                    empresa = ?, categoria = ?, placa = ?, descricao = ?,
                    vencimento = ?, valor_original = ?, 
                    juros = ?, multa = ?, tipo_juros = ?
                WHERE id = ? AND usuario_id = ?
            ''', (
                boleto['empresa'], boleto['categoria'], boleto['placa'], boleto['descricao'],
                data_venc, float(boleto['valor']), 
                float(boleto['juros'] or 0), float(boleto['multa'] or 0), boleto['tipoJuros'],
                id_boleto, self.usuario_atual['id']
            ))
            
            conn.commit()
            conn.close()
            return {'status': 'sucesso', 'msg': 'Boleto atualizado!'}
        except Exception as e:
            return {'status': 'erro', 'msg': str(e)}

    def cancelar_pagamento(self, id_boleto):
        if not self.estaLogado():
            return {'status': 'erro', 'msg': 'Login necessário'}
        
        conn = get_db_connection()
        # Volta para Pendente, apaga a data, o banco e o valor total pago
        # Mantém o valor original e os dados do boleto intactos
        conn.execute('''
            UPDATE boletos 
            SET status = 'Pendente', 
                data_pagamento = NULL, 
                banco_pagamento = NULL,
                valor_total = valor_original
            WHERE id = ? AND usuario_id = ?
        ''', (id_boleto, self.usuario_atual['id']))
        
        conn.commit()
        conn.close()
        return {'status': 'sucesso', 'msg': 'Pagamento cancelado (Estorno realizado)'}

    def estaLogado(self):
        if not self.usuario_atual: return False
        return True

    def proximo_dia_util(self, data_vencimento):
        """
        Recebe um objeto date e retorna o próximo dia útil,
        pulando Sábados, Domingos e Feriados de Nova Venécia/ES.
        """
        dia_analise = data_vencimento

        # Cache para evitar recálculo de feriados se o ano não mudar
        ano_cache = None
        feriados_cache = set()

        # Loop infinito até achar um dia útil
        while True:
            # Se mudou de ano (ex: boleto vence 31/12), carrega feriados do próximo ano
            if dia_analise.year != ano_cache:
                ano_cache = dia_analise.year
                feriados_cache = self.obter_feriados_nova_venecia(ano_cache)

            dia_semana = dia_analise.weekday() # 0=Seg, 5=Sab, 6=Dom
            str_data = dia_analise.strftime('%Y-%m-%d')

            # Se for Sábado (5), Domingo (6) OU estiver na lista de feriados
            if dia_semana >= 5 or str_data in feriados_cache:
                # Pula para o próximo dia e repete a verificação
                dia_analise += timedelta(days=1)
            else:
                # É um dia útil!
                return dia_analise

    def calcular_pascoa(self, ano):
        """ Calcula a data do Domingo de Páscoa para qualquer ano """
        a = ano % 19
        b = ano // 100
        c = ano % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        
        mes = (h + l - 7 * m + 114) // 31
        dia = ((h + l - 7 * m + 114) % 31) + 1
        
        return date(ano, mes, dia)

    # --- GERADOR DE FERIADOS DINÂMICO ---
    def obter_feriados_nova_venecia(self, ano):
        """ Retorna um SET com as datas dos feriados para o ano solicitado """
        pascoa = self.calcular_pascoa(ano)

        # Feriados Móveis (Baseados na Páscoa)
        carnaval_seg = pascoa - timedelta(days=48)
        carnaval_ter = pascoa - timedelta(days=47)
        quarta_cinzas = pascoa - timedelta(days=46)
        sexta_paixao = pascoa - timedelta(days=2)
        corpus_christi = pascoa + timedelta(days=60)
        
        # N. Sra. da Penha (ES) - Tradicionalmente na segunda-feira, 8 dias após a Páscoa
        nossa_sra_penha = pascoa + timedelta(days=8)

        feriados_moveis = [
            carnaval_seg, carnaval_ter, quarta_cinzas, 
            sexta_paixao, pascoa, corpus_christi, nossa_sra_penha
        ]

        # Feriados Fixos (Nacionais, Estaduais e Municipais de Nova Venécia)
        # Formato (Mês, Dia)
        datas_fixas = [
            (1, 1),   # Confraternização Universal
            (1, 26),  # Aniversário de Nova Venécia (Municipal)
            (4, 21),  # Tiradentes
            (4, 24),  # São Marcos (Municipal)
            (5, 1),   # Dia do Trabalho
            (5, 23),  # Colonização do Solo ES (Estadual)
            (9, 7),   # Independência
            (10, 12), # N. Sra. Aparecida
            (11, 2),  # Finados
            (11, 15), # Proclamação da República
            (11, 20), # Consciência Negra
            (12, 25), # Natal
        ]

        lista_feriados = set()
        
        # Adiciona móveis formatados
        for data in feriados_moveis:
            lista_feriados.add(data.strftime('%Y-%m-%d'))

        # Adiciona fixos formatados
        for mes, dia in datas_fixas:
            lista_feriados.add(date(ano, mes, dia).strftime('%Y-%m-%d'))

        return lista_feriados

    def obter_resumo_dashboard(self):
            if not self.usuario_atual:
                return {'status': 'erro', 'msg': 'Não logado'}

            conn = get_db_connection()
            user_id = self.usuario_atual['id']
            hoje = date.today()
            
            # 1. Definição das Datas Limite (Semana e Mês)
            # Semana (Domingo a Sábado)
            # Se hoje é Domingo (6), volta 0 dias. Se é Segunda (0), volta 1 dia...
            inicio_semana = hoje - timedelta(days=hoje.weekday() + 1) if hoje.weekday() != 6 else hoje
            fim_semana = inicio_semana + timedelta(days=6)
            
            # Mês (Primeiro e Último dia)
            inicio_mes = date(hoje.year, hoje.month, 1)
            proximo_mes = hoje.replace(day=28) + timedelta(days=4)
            fim_mes = proximo_mes - timedelta(days=proximo_mes.day)

            # 2. Estrutura do Resumo
            resumo = {
                'hoje': {'qtd': 0, 'valor': 0, 'inicio': hoje.strftime('%Y-%m-%d'), 'fim': hoje.strftime('%Y-%m-%d')},
                'vencidos': {'qtd': 0, 'valor': 0, 'inicio': '...', 'fim': (hoje - timedelta(days=1)).strftime('%Y-%m-%d')},
                'semana': {'qtd': 0, 'valor': 0, 'inicio': inicio_semana.strftime('%Y-%m-%d'), 'fim': fim_semana.strftime('%Y-%m-%d')},
                'mes': {'qtd': 0, 'valor': 0, 'inicio': inicio_mes.strftime('%Y-%m-%d'), 'fim': fim_mes.strftime('%Y-%m-%d')}
            }

            # 3. Busca TODOS os Pendentes e filtra no Python (para usar a lógica de feriados)
            # Trazemos apenas o necessário para ser rápido
            boletos_db = conn.execute("SELECT vencimento, valor_original FROM boletos WHERE usuario_id = ? AND status = 'Pendente'", (user_id,)).fetchall()
            conn.close()

            for b in boletos_db:
                valor = float(b['valor_original'])
                
                # --- O GRANDE SEGREDO ---
                # Pegamos a data original e "empurramos" se cair em feriado/FDS
                dt_original = datetime.strptime(b['vencimento'], '%Y-%m-%d').date()
                dt_util = self.proximo_dia_util(dt_original) 
                # ------------------------

                # A. Verifica HOJE
                if dt_util == hoje:
                    resumo['hoje']['qtd'] += 1
                    resumo['hoje']['valor'] += valor

                # B. Verifica VENCIDOS (Só é vencido se a data ÚTIL já passou)
                if dt_util < hoje:
                    resumo['vencidos']['qtd'] += 1
                    resumo['vencidos']['valor'] += valor
                
                # C. Verifica SEMANA (Considera a data útil para o fluxo de caixa)
                if inicio_semana <= dt_util <= fim_semana:
                    resumo['semana']['qtd'] += 1
                    resumo['semana']['valor'] += valor

                # D. Verifica MÊS
                if inicio_mes <= dt_util <= fim_mes:
                    resumo['mes']['qtd'] += 1
                    resumo['mes']['valor'] += valor

            return {'status': 'sucesso', 'dados': resumo}

    def gerar_relatorio_mensal(self, mes_ano):
        """ 
        Recebe uma string 'YYYY-MM' (ex: '2026-01') 
        Retorna o balanço total daquele mês de referência (Vencimento).
        """
        if not self.estaLogado():
            return {'status': 'erro', 'msg': 'Login necessário'}

        conn = get_db_connection()
        
        # Filtra boletos onde o vencimento começa com 'YYYY-MM'
        # SQLite usa strftime para pegar parte da data
        sql = """
            SELECT * FROM boletos 
            WHERE usuario_id = ? AND strftime('%Y-%m', vencimento) = ?
        """
        boletos_db = conn.execute(sql, (self.usuario_atual['id'], mes_ano)).fetchall()
        conn.close()

        # Estrutura do Relatório
        relatorio = {
            'total_esperado': 0.0,    # Soma dos valores originais de tudo
            'total_pago': 0.0,        # O que realmente saiu do bolso (valor_total)
            'total_pendente': 0.0,    # O que falta pagar (valor_atualizado)
            'qtd_pagos': 0,
            'qtd_pendentes': 0,
            'por_categoria': {}       # Ex: {'Manutenção': 500.00, 'Luz': 100.00}
        }

        for b in boletos_db:
            boleto = dict(b)
            
            # 1. Soma ao Total Esperado (Planejamento)
            relatorio['total_esperado'] += boleto['valor_original']

            # 2. Verifica Status
            if boleto['status'] == 'Pago':
                relatorio['qtd_pagos'] += 1
                # Se pagou, soma o valor REAL pago (com juros ou desconto)
                relatorio['total_pago'] += boleto['valor_total']
                
                # Soma por Categoria (Usando valor pago)
                cat = boleto['categoria']
                relatorio['por_categoria'][cat] = relatorio['por_categoria'].get(cat, 0) + boleto['valor_total']

            else:
                # Se Pendente
                relatorio['qtd_pendentes'] += 1
                
                # Calcula valor atualizado (reutiliza sua lógica de juros)
                valor_atual = self.calculaValorComJuros(boleto)
                relatorio['total_pendente'] += valor_atual

                # Soma por Categoria (Usando valor atualizado)
                cat = boleto['categoria']
                relatorio['por_categoria'][cat] = relatorio['por_categoria'].get(cat, 0) + valor_atual

        return {'status': 'sucesso', 'dados': relatorio}
