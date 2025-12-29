#!/usr/bin/env python3
"""
Servidor Flask para o Ranking Galático.
Inclui rota para sorteio de times balanceados.
"""

import json
import re
import random
from flask import Flask, jsonify
from flask_cors import CORS
from typing import Dict, List, Tuple, Optional

app = Flask(__name__)
CORS(app)  # Permite requisições de qualquer origem


def parse_mongodb_json(content: str) -> List[Dict]:
    """
    Converte o formato MongoDB exportado para JSON válido.
    Remove ObjectId, NumberInt, ISODate, etc.
    Processa múltiplos objetos JSON separados.
    """
    players = []
    
    # Remove ObjectId
    content = re.sub(r'ObjectId\("([^"]+)"\)', r'"\1"', content)
    
    # Remove NumberInt
    content = re.sub(r'NumberInt\((\d+)\)', r'\1', content)
    
    # Remove ISODate (mantém apenas a string da data)
    content = re.sub(r'ISODate\("([^"]+)"\)', r'"\1"', content)
    
    # Processa linha por linha para encontrar objetos JSON completos
    lines = content.split('\n')
    current_obj_lines = []
    depth = 0
    in_string = False
    escape_next = False
    
    for line in lines:
        if not current_obj_lines and '{' not in line:
            continue
            
        current_obj_lines.append(line)
        
        # Conta chaves e colchetes (mas ignora dentro de strings)
        for char in line:
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{' or char == '[':
                    depth += 1
                elif char == '}' or char == ']':
                    depth -= 1
        
        # Se depth for 0, temos um objeto completo
        if depth == 0 and current_obj_lines:
            obj_str = '\n'.join(current_obj_lines)
            try:
                data = json.loads(obj_str)
                if isinstance(data, dict) and 'fullName' in data:
                    players.append(data)
            except json.JSONDecodeError:
                # Ignora objetos inválidos
                pass
            current_obj_lines = []
    
    # Se ainda não encontrou nada, tenta parsear tudo de uma vez
    if not players:
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                players = [data]
            elif isinstance(data, list):
                players = data
        except json.JSONDecodeError:
            pass
    
    return players


def buscar_posicao_jogador(nome: str, players: List[Dict]) -> Optional[str]:
    """
    Busca a posição de um jogador no players.json.
    Retorna a posição normalizada (ZAG, MEI, ATA, PE, LD) ou None.
    Aceita busca parcial por nome.
    """
    nome_normalizado = nome.strip().lower()
    palavras_nome = nome_normalizado.split()
    
    # Primeiro tenta match exato
    for player in players:
        full_name = player.get('fullName', '').strip()
        full_name_lower = full_name.lower()
        
        # Match exato
        if full_name_lower == nome_normalizado:
            return extrair_posicao_normalizada(player)
        
        # Match por palavras (ex: "Luiz" encontra "Luiz Kelvin")
        if palavras_nome:
            if all(palavra in full_name_lower for palavra in palavras_nome):
                return extrair_posicao_normalizada(player)
    
    # Se não encontrou, tenta match parcial (primeira palavra)
    if palavras_nome:
        primeira_palavra = palavras_nome[0]
        for player in players:
            full_name = player.get('fullName', '').strip().lower()
            if full_name.startswith(primeira_palavra) or primeira_palavra in full_name:
                return extrair_posicao_normalizada(player)
    
    return None


def extrair_posicao_normalizada(player: Dict) -> str:
    """
    Extrai e normaliza a posição de um jogador.
    """
    position = player.get('position', '').strip()
    prize_draw_position = player.get('prizeDrawPosition', '').strip()
    
    # Prioriza prizeDrawPosition se existir
    posicao_final = prize_draw_position if prize_draw_position else position
    
    # Normaliza a posição
    posicao_lower = posicao_final.lower()
    if 'zagueiro' in posicao_lower or 'lateral' in posicao_lower:
        return 'ZAG'
    elif 'meia' in posicao_lower or 'volante' in posicao_lower:
        return 'MEI'
    elif 'atacante' in posicao_lower or 'ponta' in posicao_lower:
        return 'ATA'
    elif 'ponta esquerda' in posicao_lower or 'ponta direita' in posicao_lower:
        return 'ATA'  # PE é tratado como ATA
    elif 'lateral direito' in posicao_lower or 'lateral esquerdo' in posicao_lower:
        return 'ZAG'  # LD é tratado como ZAG
    
    return posicao_final


def normalizar_posicao(posicao: str) -> str:
    """
    Normaliza a posição para o formato usado no sorteio.
    ZAG/LD, MEI, ATA/PE
    """
    if not posicao:
        return 'ATA'  # Padrão se não encontrar
    
    posicao_lower = posicao.lower()
    
    # Zagueiros e laterais
    if 'zag' in posicao_lower or 'lateral' in posicao_lower:
        return 'ZAG'
    
    # Meias
    if 'mei' in posicao_lower or 'volante' in posicao_lower:
        return 'MEI'
    
    # Atacantes e pontas
    if 'ata' in posicao_lower or 'ponta' in posicao_lower:
        return 'ATA'
    
    return 'ATA'  # Padrão


def sortear_times() -> Dict:
    """
    Realiza o sorteio balanceado dos times.
    
    Estrutura desejada por time (4 times fechados):
    - 2 Zagueiros (ZAG/LD)
    - 1 Meia (MEI)
    - 2 Atacantes (ATA/PE)
    
    Restrições:
    - Arnaldo, Kelvin, Tavares (Matheus Tavares), Vertinho não podem estar no mesmo time
    
    Todos os jogadores podem ser sorteados para os 4 times:
    - Arnaldo, Ronald, Luiz Kelvin, Kawa Messi, Henrique, Vertinho, Cabinha, 
      Weslly, Guilherme, Nilson, Tavares, Samuel, Jonis, Adelson, Deyvde, 
      Kelvin, Andrew, Lito, Caio, Luan, Matador, Israel, Luiz, Vini, Arthur
    
    O time 5 será formado pelos jogadores restantes após distribuir 5 jogadores
    para cada um dos 4 primeiros times.
    """
    # Carrega players.json
    try:
        with open('players.json', 'r', encoding='utf-8') as f:
            content = f.read()
        players = parse_mongodb_json(content)
    except Exception as e:
        return {'erro': f'Erro ao carregar players.json: {str(e)}'}
    
    # Lista de jogadores com posições conhecidas
    jogadores_com_posicao = {
        'Arnaldo': 'ATA',
        'Ronald': 'ZAG',
        'Luiz Kelvin': 'ZAG',  # Será buscado no players.json se necessário
        'Kawa Messi': 'ZAG',
        'Henrique': 'ZAG',
        'Vertinho': 'ATA',
        'Cabinha': 'ZAG',  # ZAG/MLD -> ZAG
        'Weslly': 'ZAG',
        'Guilherme': 'ZAG',
        'Nilson': 'ATA',  # Será buscado no players.json se necessário
        'Tavares': 'MEI',  # Matheus Tavares
        'Samuel': 'ZAG',
        'Jonis': 'ATA',  # PE -> ATA
        'Adelson': 'MEI',  # Será buscado no players.json se necessário
        'Deyvde': 'ATA',
        'Kelvin': 'ATA',
        'Andrew': 'ATA',
        'Lito': 'ZAG',
        'Caio': 'ZAG',
        'Luan': 'ZAG',  # Será buscado no players.json se necessário
        'Matador': 'ATA',
        'Israel': 'ATA',
        'Luiz': 'ZAG',
        'Vini': 'MEI',  # MEI/LD -> MEI
        'Arthur': 'ATA'
    }
    
    # Jogadores sem posição definida - busca no players.json
    jogadores_sem_posicao = ['Luiz Kelvin', 'Nilson', 'Adelson', 'Luan']
    
    # Busca posições dos jogadores sem posição
    for nome in jogadores_sem_posicao:
        posicao = buscar_posicao_jogador(nome, players)
        if posicao:
            jogadores_com_posicao[nome] = normalizar_posicao(posicao)
        else:
            # Se não encontrar, usa padrão baseado no nome
            if 'Luiz' in nome:
                jogadores_com_posicao[nome] = 'ZAG'  # Provável zagueiro
            elif nome == 'Adelson':
                jogadores_com_posicao[nome] = 'MEI'  # Já encontramos que é Volante
            else:
                jogadores_com_posicao[nome] = 'ATA'  # Padrão
    
    # Todos os jogadores que podem ser sorteados (incluindo os que antes iam para o time 5)
    todos_jogadores = [
        'Arnaldo', 'Ronald', 'Luiz Kelvin', 'Kawa Messi', 'Henrique', 
        'Vertinho', 'Cabinha', 'Weslly', 'Guilherme', 'Nilson', 
        'Tavares', 'Samuel', 'Jonis', 'Adelson', 'Deyvde', 
        'Kelvin', 'Andrew', 'Lito', 'Caio', 'Luan',
        'Matador', 'Israel', 'Luiz', 'Vini', 'Arthur'
    ]
    
    # Grupo de jogadores que não podem estar juntos
    # Nota: "Tavares" é o mesmo que "Matheus Tavares"
    grupo_restrito = ['Arnaldo', 'Kelvin', 'Tavares', 'Vertinho']
    
    # Mapeamento de nomes alternativos
    nome_alternativo = {
        'Matheus Tavares': 'Tavares'
    }
    
    # Separa jogadores por posição (incluindo todos os jogadores agora)
    zagueiros = []
    meias = []
    atacantes = []
    
    for nome in todos_jogadores:
        posicao = jogadores_com_posicao.get(nome, 'ATA')
        if posicao == 'ZAG':
            zagueiros.append(nome)
        elif posicao == 'MEI':
            meias.append(nome)
        else:  # ATA, PE
            atacantes.append(nome)
    
    # Embaralha as listas
    random.shuffle(zagueiros)
    random.shuffle(meias)
    random.shuffle(atacantes)
    
    # Cria os 4 times (cada um com exatamente 5 jogadores)
    times = [[] for _ in range(4)]
    
    # Distribui exatamente 5 jogadores por time: 2 ZAG, 1 MEI, 2 ATA
    for i in range(4):
        # 2 Zagueiros
        if zagueiros:
            times[i].append(zagueiros.pop(0))
        if zagueiros:
            times[i].append(zagueiros.pop(0))
        
        # 1 Meia
        if meias:
            times[i].append(meias.pop(0))
        
        # 2 Atacantes
        if atacantes:
            times[i].append(atacantes.pop(0))
        if atacantes:
            times[i].append(atacantes.pop(0))
    
    # Se algum time não tiver 5 jogadores, preenche com jogadores restantes
    todos_restantes = zagueiros + meias + atacantes
    
    for i in range(4):
        while len(times[i]) < 5 and todos_restantes:
            times[i].append(todos_restantes.pop(0))
    
    # Garante que cada time tenha exatamente 5 jogadores
    # Se algum time tiver mais de 5, move os extras para restantes
    for i in range(4):
        while len(times[i]) > 5:
            todos_restantes.append(times[i].pop())
    
    # Verifica e corrige restrição (grupo_restrito não pode estar no mesmo time)
    # Reorganiza os times para garantir que jogadores restritos não estejam juntos
    max_tentativas = 50
    tentativa = 0
    
    while tentativa < max_tentativas:
        violacao = False
        
        # Verifica cada time
        for idx, time in enumerate(times):
            # Verifica jogadores restritos (incluindo nomes alternativos)
            jogadores_restritos_no_time = []
            for j in time:
                if j in grupo_restrito:
                    jogadores_restritos_no_time.append(j)
                elif j in nome_alternativo and nome_alternativo[j] in grupo_restrito:
                    jogadores_restritos_no_time.append(j)
            if len(jogadores_restritos_no_time) > 1:
                violacao = True
                # Move um jogador restrito para outro time
                jogador_para_mover = jogadores_restritos_no_time[0]
                time.remove(jogador_para_mover)
                
                # Encontra um time que não tenha jogadores restritos e tenha menos de 5
                time_encontrado = False
                for outro_idx, outro_time in enumerate(times):
                    tem_restrito = any(j in grupo_restrito or (j in nome_alternativo and nome_alternativo[j] in grupo_restrito) for j in outro_time)
                    tem_espaco = len(outro_time) < 5
                    if outro_idx != idx and not tem_restrito and tem_espaco:
                        outro_time.append(jogador_para_mover)
                        time_encontrado = True
                        break
                
                # Se não encontrou, coloca em qualquer time que não seja o atual e tenha espaço
                if not time_encontrado:
                    for outro_idx, outro_time in enumerate(times):
                        if outro_idx != idx and len(outro_time) < 5:
                            outro_time.append(jogador_para_mover)
                            break
                break
        
        if not violacao:
            break
        
        tentativa += 1
    
    # Se ainda houver violação após tentativas, redistribui completamente
    if tentativa >= max_tentativas:
        # Reorganiza: distribui um jogador restrito por time
        jogadores_restritos_restantes = []
        for j in grupo_restrito:
            if any(j in t for t in times):
                jogadores_restritos_restantes.append(j)
        # Também verifica nomes alternativos
        for j in nome_alternativo:
            nome_alt = nome_alternativo[j]
            if nome_alt in grupo_restrito and any(j in t for t in times):
                jogadores_restritos_restantes.append(j)
        random.shuffle(jogadores_restritos_restantes)
        
        # Remove todos os restritos dos times
        for time in times:
            time[:] = [j for j in time if j not in grupo_restrito and j not in nome_alternativo]
        
        # Distribui um restrito por time
        for i, jogador in enumerate(jogadores_restritos_restantes[:4]):
            times[i].append(jogador)
        
        # Redistribui os demais jogadores
        todos_jogadores = []
        for time in times:
            todos_jogadores.extend(time)
            time.clear()
        
        # Reorganiza por posição
        zagueiros_rest = [j for j in todos_jogadores if jogadores_com_posicao.get(j) == 'ZAG']
        meias_rest = [j for j in todos_jogadores if jogadores_com_posicao.get(j) == 'MEI']
        atacantes_rest = [j for j in todos_jogadores if jogadores_com_posicao.get(j) == 'ATA']
        
        random.shuffle(zagueiros_rest)
        random.shuffle(meias_rest)
        random.shuffle(atacantes_rest)
        
        # Distribui novamente
        for i in range(4):
            # Zagueiros
            if zagueiros_rest:
                times[i].append(zagueiros_rest.pop(0))
            if zagueiros_rest:
                times[i].append(zagueiros_rest.pop(0))
            # Meias
            if meias_rest:
                times[i].append(meias_rest.pop(0))
            # Atacantes
            if atacantes_rest:
                times[i].append(atacantes_rest.pop(0))
            if atacantes_rest:
                times[i].append(atacantes_rest.pop(0))
    
    # Coleta jogadores restantes para o time 5 (os que não foram distribuídos nos 4 times)
    todos_jogadores_nos_times = set()
    for time in times:
        todos_jogadores_nos_times.update(time)
    
    time_5 = [j for j in todos_jogadores if j not in todos_jogadores_nos_times]
    
    # Monta resultado
    resultado = {
        'times': [],
        'time_5': time_5,
        'posicoes': {}
    }
    
    for i, time in enumerate(times, 1):
        time_info = {
            'numero': i,
            'jogadores': time,
            'posicoes': {}
        }
        
        # Conta posições
        for jogador in time:
            posicao = jogadores_com_posicao.get(jogador, 'ATA')
            time_info['posicoes'][jogador] = posicao
            resultado['posicoes'][jogador] = posicao
        
        resultado['times'].append(time_info)
    
    # Adiciona posições dos jogadores do time 5
    for jogador in time_5:
        if jogador in jogadores_com_posicao:
            resultado['posicoes'][jogador] = jogadores_com_posicao[jogador]
        else:
            # Busca no players.json
            posicao = buscar_posicao_jogador(jogador, players)
            resultado['posicoes'][jogador] = normalizar_posicao(posicao) if posicao else 'ATA'
    
    return resultado


@app.route('/sorteio', methods=['GET'])
def sorteio():
    """
    Rota para realizar o sorteio dos times.
    Retorna JSON com os times sorteados.
    """
    try:
        resultado = sortear_times()
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({'erro': f'Erro ao realizar sorteio: {str(e)}'}), 500


@app.route('/health', methods=['GET'])
def health():
    """Rota de health check."""
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

