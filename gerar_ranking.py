#!/usr/bin/env python3
"""
Script para gerar ranking visual dos awards dos jogadores.
Extrai o top 3 de cada categoria de prêmios e gera uma visualização HTML.
Integra com API do OpenAI para gerar backgrounds e textos dinâmicos.
"""

import json
import re
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Configura encoding UTF-8 para o stdout (necessário no Windows)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Carrega variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Se python-dotenv não estiver instalado, continua sem erro
    pass


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


def extrair_awards_jogadores(players: List[Dict]) -> Tuple[Dict[str, List[Tuple[str, int]]], Dict[str, str], List[str]]:
    """
    Extrai os awards e estatísticas de cada jogador e agrupa por categoria.
    Extrai os dados APENAS do time em includedTeams que corresponde ao teamCode do jogador.
    Separa goleiros dos demais jogadores para estatísticas de partidas.
    
    Retorna uma tupla com:
    - Dicionário onde chave é categoria e valor é lista de tuplas (nome_jogador, quantidade)
    - Dicionário mapeando nome_jogador para URL da imagem
    - Lista com todos os nomes únicos de jogadores
    """
    # Dados separados para goleiros e não-goleiros
    dados_por_jogador = defaultdict(lambda: defaultdict(int))
    dados_por_goleiro = defaultdict(lambda: defaultdict(int))
    
    # Mapeamento de nome do jogador para URL da imagem
    imagens_jogadores = {}
    
    # Lista de todos os nomes únicos de jogadores
    nomes_todos_jogadores = set()
    
    # Campos de estatísticas gerais (todos os jogadores)
    campos_estatisticas_gerais = [
        'totalAssistence',
        'totalGoals'
    ]
    
    # Campos de estatísticas de partidas (apenas não-goleiros)
    campos_estatisticas_partidas = [
        'totalGamePlayed',
        'totalWins',
        'totalDefeat',
        'totalDraw'
    ]
    
    # Campos de estatísticas de partidas para goleiros (separado)
    campos_estatisticas_goleiros = [
        'totalGamePlayed',
        'totalWins',
        'totalDefeat',
        'totalDraw'
    ]
    
    # Categorias de awards (goleiros não devem aparecer nessas categorias)
    categorias_awards = [
        'craque',
        'artilheiro',
        'garcom',
        'muralha',
        'pereba',
        'bolaMurcha',
        'xerifao'
    ]
    
    for player in players:
        # Normaliza o nome removendo espaços extras no início/fim
        nome = player.get('fullName', 'Sem nome').strip()
        if nome and nome != 'Sem nome':
            nomes_todos_jogadores.add(nome)
        
        position = player.get('position', '').lower()
        is_goleiro = 'goleiro' in position
        
        # Armazena a URL da imagem do jogador (só se for válida)
        image_url = player.get('imagePlayer', '').strip()
        if image_url and image_url.startswith('http') and nome not in imagens_jogadores:
            imagens_jogadores[nome] = image_url
        
        # Determina qual dicionário usar
        dados_alvo = dados_por_goleiro if is_goleiro else dados_por_jogador
        
        # Obtém o teamCode do jogador no nível raiz
        player_team_code = player.get('teamCode', '').strip()
        
        # Busca o time correspondente em includedTeams
        included_teams = player.get('includedTeams', [])
        team_data = None
        
        if isinstance(included_teams, list) and player_team_code:
            for team in included_teams:
                if isinstance(team, dict):
                    team_code = team.get('teamCode', '').strip()
                    if team_code == player_team_code:
                        team_data = team
                        break
        
        # Se encontrou o time correspondente, extrai os dados apenas desse time
        if team_data:
            # Awards do time
            awards_team = team_data.get('awards', {})
            for categoria, quantidade in awards_team.items():
                if isinstance(quantidade, (int, str)):
                    try:
                        qtd = int(quantidade)
                        if qtd > 0:
                            dados_alvo[nome][categoria] += qtd
                    except (ValueError, TypeError):
                        continue
            
            # Estatísticas gerais do time
            for campo in campos_estatisticas_gerais:
                valor = team_data.get(campo, 0)
                if isinstance(valor, (int, str)):
                    try:
                        qtd = int(valor)
                        if qtd > 0:
                            dados_alvo[nome][campo] += qtd
                    except (ValueError, TypeError):
                        continue
            
            # Estatísticas de partidas do time (separadas por tipo de jogador)
            campos_partidas = campos_estatisticas_goleiros if is_goleiro else campos_estatisticas_partidas
            for campo in campos_partidas:
                valor = team_data.get(campo, 0)
                if isinstance(valor, (int, str)):
                    try:
                        qtd = int(valor)
                        if qtd > 0:
                            dados_alvo[nome][campo] += qtd
                    except (ValueError, TypeError):
                        continue
    
    # Cria dicionário com dados completos de cada jogador para desempate
    # Mapeia nome_jogador -> (vitórias, partidas)
    dados_completos_jogadores = {}
    dados_completos_goleiros = {}
    
    # Preenche dados completos de jogadores não-goleiros
    for nome_jogador, dados in dados_por_jogador.items():
        vitorias = dados.get('totalWins', 0)
        partidas = dados.get('totalGamePlayed', 0)
        dados_completos_jogadores[nome_jogador] = (vitorias, partidas)
    
    # Preenche dados completos de goleiros
    for nome_jogador, dados in dados_por_goleiro.items():
        vitorias = dados.get('totalWins', 0)
        partidas = dados.get('totalGamePlayed', 0)
        dados_completos_goleiros[nome_jogador] = (vitorias, partidas)
    
    # Agora agrupa por categoria
    categorias = defaultdict(list)
    
    # Processa jogadores não-goleiros
    for nome_jogador, dados in dados_por_jogador.items():
        for categoria, quantidade_total in dados.items():
            if quantidade_total > 0:
                categorias[categoria].append((nome_jogador, quantidade_total))
    
    # Processa goleiros com prefixo "goleiro_"
    for nome_jogador, dados in dados_por_goleiro.items():
        for categoria, quantidade_total in dados.items():
            if quantidade_total > 0:
                # Ignora awards para goleiros (eles têm seção própria)
                if categoria in categorias_awards:
                    continue
                # Adiciona prefixo "goleiro_" para categorias de partidas
                if categoria in campos_estatisticas_goleiros:
                    categoria_prefixo = f'goleiro_{categoria}'
                else:
                    # Estatísticas gerais dos goleiros (não awards) vão para categorias normais
                    categoria_prefixo = categoria
                categorias[categoria_prefixo].append((nome_jogador, quantidade_total))
    
    # Ordena cada categoria por quantidade (decrescente) com desempate
    # Critério de desempate: mais vitórias, depois menos partidas
    def chave_ordenacao(item):
        nome_jogador, quantidade = item
        # Busca dados de desempate (vitórias e partidas)
        # Tenta primeiro em jogadores normais, depois em goleiros
        vitorias, partidas = dados_completos_jogadores.get(nome_jogador, dados_completos_goleiros.get(nome_jogador, (0, 999999)))
        # Retorna tupla: (quantidade, vitórias, -partidas)
        # Com reverse=True:
        # - quantidade: maior é melhor ✓ (ordena decrescente)
        # - vitórias: maior é melhor ✓ (ordena decrescente)
        # - -partidas: valores negativos maiores = partidas menores ✓ (ordena decrescente)
        return (quantidade, vitorias, -partidas)
    
    for categoria in categorias:
        categorias[categoria].sort(key=chave_ordenacao, reverse=True)
    
    # Converte set para lista ordenada
    nomes_todos_jogadores_lista = sorted(list(nomes_todos_jogadores))
    
    return categorias, imagens_jogadores, nomes_todos_jogadores_lista


def obter_dados_jogador(nome_jogador: str, categorias: Dict[str, List[Tuple[str, int]]], imagens_jogadores: Dict[str, str]) -> Dict:
    """
    Obtém todos os dados de um jogador específico.
    """
    dados = {
        'nome': nome_jogador,
        'imagem': imagens_jogadores.get(nome_jogador, ''),
        'stats': {}
    }
    
    for categoria, rankings in categorias.items():
        for nome, quantidade in rankings:
            if nome == nome_jogador:
                dados['stats'][categoria] = quantidade
                break
    
    return dados


def comparar_com_jogador_futebol(stats: Dict[str, int]) -> Dict:
    """
    Compara as estatísticas do jogador com jogadores de futebol reais.
    Retorna o jogador de futebol mais similar.
    """
    # Jogadores de futebol com perfis típicos
    jogadores_futebol = {
        'Cristiano Ronaldo': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/8198-1671435885.jpg',
            'posicao': 'Atacante',
            'perfil': {
                'totalGoals': 850,
                'totalAssistence': 250,
                'totalWins': 600,
                'artilheiro': 50,
                'craque': 30
            },
            'descricao': 'Maior artilheiro da história, líder nato e vencedor'
        },
        'Lionel Messi': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/28003-1671435885.jpg',
            'posicao': 'Atacante',
            'perfil': {
                'totalGoals': 800,
                'totalAssistence': 350,
                'totalWins': 550,
                'artilheiro': 45,
                'craque': 40,
                'garcom': 20
            },
            'descricao': 'Mestre das assistências e gols, criatividade única'
        },
        'Neymar Jr': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/68290-1671435885.jpg',
            'posicao': 'Atacante',
            'perfil': {
                'totalGoals': 400,
                'totalAssistence': 280,
                'totalWins': 400,
                'artilheiro': 25,
                'craque': 35,
                'garcom': 15
            },
            'descricao': 'Drible, velocidade e assistências decisivas'
        },
        'Kevin De Bruyne': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/88755-1671435885.jpg',
            'posicao': 'Meia',
            'perfil': {
                'totalGoals': 150,
                'totalAssistence': 300,
                'totalWins': 450,
                'garcom': 50,
                'craque': 45
            },
            'descricao': 'Maestro do meio-campo, rei das assistências'
        },
        'Manuel Neuer': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/26399-1671435885.jpg',
            'posicao': 'Goleiro',
            'perfil': {
                'totalWins': 500,
                'muralha': 200,
                'xerifao': 30
            },
            'descricao': 'Goleiro moderno, líder da defesa'
        },
        'Virgil van Dijk': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/5925-1671435885.jpg',
            'posicao': 'Zagueiro',
            'perfil': {
                'totalWins': 400,
                'muralha': 150,
                'xerifao': 40
            },
            'descricao': 'Muralha defensiva, líder da zaga'
        },
        'Luka Modrić': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/30972-1671435885.jpg',
            'posicao': 'Meia',
            'perfil': {
                'totalGoals': 100,
                'totalAssistence': 200,
                'totalWins': 500,
                'craque': 50,
                'garcom': 30
            },
            'descricao': 'Meia completo, controle de jogo e visão'
        },
        'Kylian Mbappé': {
            'imagem': 'https://img.a.transfermarkt.technology/portrait/header/342229-1671435885.jpg',
            'posicao': 'Atacante',
            'perfil': {
                'totalGoals': 300,
                'totalAssistence': 150,
                'totalWins': 350,
                'artilheiro': 30,
                'craque': 25
            },
            'descricao': 'Velocidade, gols e impacto decisivo'
        }
    }
    
    # Calcula similaridade com cada jogador
    melhor_match = None
    melhor_score = 0
    
    for nome_jogador, perfil in jogadores_futebol.items():
        score = 0
        matches = 0
        
        for stat, valor_jogador in stats.items():
            if stat in perfil['perfil']:
                valor_referencia = perfil['perfil'][stat]
                # Normaliza os valores para comparar
                if valor_referencia > 0:
                    similaridade = min(valor_jogador / valor_referencia, valor_referencia / valor_jogador) if valor_jogador > 0 else 0
                    score += similaridade
                    matches += 1
        
        if matches > 0:
            score_medio = score / matches
            if score_medio > melhor_score:
                melhor_score = score_medio
                melhor_match = {
                    'nome': nome_jogador,
                    **perfil,
                    'similaridade': score_medio
                }
    
    # Se não encontrou match bom, usa um padrão baseado nas estatísticas principais
    if melhor_match is None or melhor_score < 0.3:
        if stats.get('totalGoals', 0) > stats.get('totalAssistence', 0) * 2:
            melhor_match = jogadores_futebol['Cristiano Ronaldo']
            melhor_match['nome'] = 'Cristiano Ronaldo'
        elif stats.get('totalAssistence', 0) > stats.get('totalGoals', 0) * 1.5:
            melhor_match = jogadores_futebol['Kevin De Bruyne']
            melhor_match['nome'] = 'Kevin De Bruyne'
        elif 'goleiro' in str(stats.keys()):
            melhor_match = jogadores_futebol['Manuel Neuer']
            melhor_match['nome'] = 'Manuel Neuer'
        else:
            melhor_match = jogadores_futebol['Luka Modrić']
            melhor_match['nome'] = 'Luka Modrić'
    
    return melhor_match


def gerar_ranking_html(categorias: Dict[str, List[Tuple[str, int]]], imagens_jogadores: Dict[str, str], nomes_todos_jogadores: List[str]) -> str:
    """
    Gera HTML visual com o ranking top 3 de cada categoria.
    Exibe todos os rankings em um grid responsivo.
    """
    # Mapeamento de nomes de categorias para nomes amigáveis
    nomes_categorias = {
        'garcom': 'Garçom',
        'artilheiro': 'Artilheiro',
        'craque': 'Craque',
        'muralha': 'Muralha',
        'bolaMurcha': 'Bola Murcha',
        'xerifao': 'Xerifão',
        'pereba': 'Pereba',
        'totalAssistence': 'Assistências',
        'totalGoals': 'Gols',
        'totalGamePlayed': 'Partidas Jogadas',
        'totalWins': 'Vitórias',
        'totalDefeat': 'Derrotas',
        'totalDraw': 'Empates',
        # Categorias de goleiros
        'goleiro_totalGamePlayed': 'Partidas (Goleiros)',
        'goleiro_totalWins': 'Vitórias (Goleiros)',
        'goleiro_totalDefeat': 'Derrotas (Goleiros)',
        'goleiro_totalDraw': 'Empates (Goleiros)'
    }
    
    # Ícones para cada categoria
    icones_categorias = {
        'garcom': '🍽️',
        'artilheiro': '⚽',
        'craque': '⭐',
        'muralha': '🛡️',
        'bolaMurcha': '😞',
        'xerifao': '👮',
        'pereba': '🤦',
        'totalAssistence': '🎯',
        'totalGoals': '⚽',
        'totalGamePlayed': '🎮',
        'totalWins': '🏆',
        'totalDefeat': '😔',
        'totalDraw': '🤝',
        # Categorias de goleiros
        'goleiro_totalGamePlayed': '🥅',
        'goleiro_totalWins': '🥅',
        'goleiro_totalDefeat': '🥅',
        'goleiro_totalDraw': '🥅'
    }

    # Frases de elogio para o campeão de cada categoria
    frases_elogio_por_categoria = {
        'totalGoals': [
            "{nome} foi artilheiro nato: {valor} gols, especialista em furar redes a temporada inteira!",
            "{nome} não perdoou ninguém: {valor} gols e sentindo o cheiro da Ballon d'Or próximo ano.",
            "{nome} é máquina de fazer gol: {valor} gols marcados e goleiros chorando até agora.",
        ],
        'totalAssistence': [
            "{nome} é garçom de luxo: {valor} assistências servindo gol na bandeja.",
            "Com {valor} assistências, {nome} faz a bola falar e os companheiros brilharem.",
            "{nome} é o assistente oficial da pelada: {valor} assistências e muito respeito.",
        ],
        'totalWins': [
            "{nome} é sinônimo de vitória: {valor} vitórias e muita resenha no pós-jogo.",
            "Quando {nome} está em campo, as {valor} vitórias mostram quem manda na pelada.",
            "{nome} é garantia de vitória: {valor} vitórias e time sempre na frente.",
        ],
        'totalGamePlayed': [
            "{nome} é presença garantida: {valor} partidas disputadas, dedicação garantida!",
            "Com {valor} partidas no currículo, {nome} prova que não falta em nenhuma pelada.",
            "{nome} não falta nunca: {valor} partidas e sempre pronto pra jogar.",
        ],
        'totalDefeat': [
            "{nome} colecionou {valor} derrotas, mas nunca desistiu de jogar...continua perdendo mais e mais.",
            "Mesmo com {valor} derrotas, {nome} sempre volta mais forte...pra perder a próxima partida.",
            "{nome} teve {valor} derrotas, mas a não desistiu...por que não é ruim perder, é ruim perder sem tentar.",
        ],
        'totalDraw': [
            "{nome} empatou {valor} vezes, sempre equilibrado e justo.",
            "Com {valor} empates, {nome} mostra que sabe equilibrar o jogo.",
            "{nome} tem {valor} empates no histórico, sempre deixando tudo no meio termo.",
        ],
        'artilheiro': [
            "Craque de bola e próximo ganhador da bola de ouro! {nome} foi artilheiro {valor} vezes.",
            "{nome} tem faro de gol absurdo: {valor} vezes como artilheiro, impossível marcar esse cara.",
            "{nome} é o goleador oficial: {valor} vezes artilheiro e sempre no topo.",
        ],
        'craque': [
            "Craque de bola e próximo ganhador da bola de ouro! {nome} levou {valor} prêmios de craque da partida.",
            "{nome} liga o modo destaque e o resto é história: {valor} vezes craque do jogo.",
            "{nome} é o craque da pelada: {valor} vezes eleito e sempre brilhando.",
        ],
        'garcom': [
            "{nome} é o garçom oficial: {valor} assistências servidas e todos agradecem!",
            "Com {valor} assistências, {nome} serve gol na bandeja e faz a diferença.",
            "{nome} é especialista em servir: {valor} assistências e muito respeito.",
        ],
        'muralha': [
            "{nome} é uma muralha intransponível: {valor} defesas e goleiros invejando.",
            "Com {valor} defesas, {nome} prova que é a muralha da pelada.",
            "{nome} é sinônimo de defesa: {valor} vezes como muralha e sempre seguro.",
        ],
        'bolaMurcha': [
            "{nome} teve {valor} momentos como bola murcha, mas sempre vai em busca de mais momentos...",
            "Mesmo com {valor} bolas murchas, {nome} não desiste e sempre volta pior.",
            "{nome} colecionou {valor} bolas murchas, mas a determinação continua pra colecionando mais.",
        ],
        'xerifao': [
            "{nome} é o xerifão da pelada: {valor} vezes no comando e sempre casca grossa.",
            "Com {valor} atuações como xerifão, {nome} mantém a ordem em campo.",
            "{nome} é o guardião da pelada: {valor} vezes como xerifão e sempre presente.",
        ],
        'pereba': [
            "Mais pereba impossível: {nome} garantiu o troféu com {valor}x o mais perebento da pelada.",
            "Com {valor} perebas no currículo, {nome} prova que até nos melhores dias, tem dias ruins.",
            "{nome} colecionou {valor} perebas, mas sempre volta a ser ruim só pela resenha.",
        ],
        'goleiro_totalGamePlayed': [
            "{nome} é o goleiro mais presente: {valor} partidas defendendo o gol!",
            "Com {valor} partidas como goleiro, {nome} é garantia de segurança no gol.",
            "{nome} não falta nunca: {valor} partidas defendendo e sempre no seu melhor.",
        ],
        'goleiro_totalWins': [
            "{nome} é sinônimo de vitória no gol: {valor} vitórias e muito respeito.",
            "Com {valor} vitórias como goleiro, {nome} prova que é fundamental pro time.",
            "{nome} é garantia de vitória: {valor} triunfos defendendo o gol.",
        ],
        'goleiro_totalDefeat': [
            "{nome} teve {valor} derrotas no gol, mas sempre volta mais forte!",
            "Mesmo com {valor} derrotas, {nome} continua firme defendendo o gol.",
            "{nome} colecionou {valor} derrotas, mas a determinação nunca acaba.",
        ],
        'goleiro_totalDraw': [
            "{nome} empatou {valor} vezes no gol, sempre equilibrado e justo.",
            "Com {valor} empates, {nome} mostra que sabe equilibrar o jogo no gol.",
            "{nome} tem {valor} empates defendendo, sempre deixando tudo no meio termo.",
        ],
    }

    def gerar_frase_elogio(categoria_key: str, nome: str, valor: int) -> str:
        """Gera uma frase divertida de elogio/zoeira para o campeão da categoria."""
        templates = frases_elogio_por_categoria.get(categoria_key)
        if templates:
            template = random.choice(templates)
            return template.format(nome=nome, valor=valor)
        # Frases genéricas mais divertidas caso não haja template específico
        frases_genericas = [
            "{nome} dominou essa categoria com {valor} no total, simplesmente absurdo!",
            "Com {valor} nessa categoria, {nome} provou que é brabo demais!",
            "{nome} fez {valor} e mostrou que é o cara nessa categoria!",
            "Impossível não reconhecer: {nome} arrasou com {valor} nessa categoria!",
            "{nome} é sinônimo de excelência: {valor} e muito respeito!",
        ]
        template = random.choice(frases_genericas)
        return template.format(nome=nome, valor=valor)
    
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#0a1929">
    <title>Ranking Galático - Sua Jornada</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }
        
        @keyframes slideInLeft {
            from {
                opacity: 0;
                transform: translateX(-50px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(50px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @keyframes scaleIn {
            from {
                opacity: 0;
                transform: scale(0.9);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }
        
        @keyframes barGrow {
            from {
                width: 0% !important;
            }
        }
        
        @keyframes shimmer {
            0% {
                background-position: -1000px 0;
            }
            100% {
                background-position: 1000px 0;
            }
        }
        
        * {
            box-sizing: border-box;
        }
        
        html {
            height: 100%;
            height: 100dvh;
            overflow: hidden;
            -webkit-overflow-scrolling: touch;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0a1929 0%, #1a2332 50%, #0f1419 100%);
            height: 100vh;
            height: 100dvh;
            overflow: hidden;
            color: #1a1a1a;
            margin: 0;
            padding: 0;
            position: fixed;
            width: 100%;
            top: 0;
            left: 0;
        }
        
        .slides-container {
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            display: flex;
            overflow-x: auto;
            overflow-y: hidden;
            scroll-snap-type: x mandatory;
            scroll-behavior: smooth;
            -webkit-overflow-scrolling: touch;
            cursor: grab;
            user-select: none;
            position: fixed;
            top: 0;
            left: 0;
        }
        
        .slides-container:active {
            cursor: grabbing;
        }
        
        .slide {
            min-width: 100vw;
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 0;
            scroll-snap-align: start;
            position: relative;
            opacity: 1;
            animation: fadeIn 0.8s ease;
            box-sizing: border-box;
            background: radial-gradient(circle at top left, #f97316 0%, transparent 55%), 
                        radial-gradient(circle at bottom right, #22c55e 0%, transparent 55%),
                        linear-gradient(135deg, #1d1b4c, #3b0764);
        }
        
        .slide.active {
            opacity: 1;
        }
        
        /* Formato 9:16 para mobile */
        @media (max-width: 768px) {
            .slide {
                padding: 15px;
            }
            
            /* Força formato vertical 9:16 */
            html, body {
                height: 100vh;
                height: -webkit-fill-available;
                overflow: hidden;
            }
            
            .slides-container {
                height: 100vh;
                height: -webkit-fill-available;
            }
            
            .motivacional-slide,
            .perfil-completo-slide,
            .slide {
                height: 100vh;
                height: -webkit-fill-available;
                min-height: 100vh;
                min-height: -webkit-fill-available;
            }
        }
        
        .slide-content {
            max-width: 420px;
            width: 100%;
            padding: 28px 24px 30px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: stretch;
            text-align: center;
            color: #f9fafb;
            position: relative;
            z-index: 1;
        }
        
        .slide-header {
            text-align: center;
            margin-bottom: 18px;
            padding-bottom: 0;
            border-bottom: none;
            animation: fadeInUp 0.8s ease 0.2s both;
        }
        
        .categoria-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 24px;
        }
        
        .categoria-icone {
            font-size: 3.5em;
            filter: grayscale(20%);
            animation: scaleIn 0.6s ease 0.4s both;
        }
        
        .story-year {
            font-size: clamp(0.85rem, 1.5vw, 1rem);
            font-weight: 600;
            color: rgba(255, 255, 255, 0.95);
            margin-bottom: 8px;
            letter-spacing: 0.12em;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }
        
        .story-subtitle {
            font-size: clamp(1rem, 2.5vw, 1.3rem);
            font-weight: 600;
            color: rgba(255, 255, 255, 0.95);
            margin-bottom: 12px;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }
        
        .story-body {
            font-size: clamp(0.95rem, 2.2vw, 1.15rem);
            font-weight: 500;
            color: rgba(255, 255, 255, 0.95);
            line-height: 1.5;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }
        
        .categoria-titulo {
            font-size: clamp(2.4rem, 6vw, 3.5rem);
            font-weight: 900;
            color: #ffffff;
            letter-spacing: -0.03em;
            text-shadow: 0 4px 16px rgba(0, 0, 0, 0.6), 0 2px 8px rgba(0, 0, 0, 0.4);
        }
        
        /* Ranking simples dentro do story */
        .ranking-highlight {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin-top: 12px;
            margin-bottom: 8px;
            gap: 10px;
        }
        
        .ranking-highlight-visual {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .ranking-highlight-image {
            width: 120px;
            height: 120px;
            border-radius: 24px;
            object-fit: cover;
            border: 4px solid rgba(255, 255, 255, 0.9);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            display: block;
        }
        
        .ranking-highlight-placeholder {
            width: 120px;
            height: 120px;
            border-radius: 24px;
            border: 4px solid rgba(255, 255, 255, 0.9);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            background: linear-gradient(135deg, #22c55e, #16a34a);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3rem;
            font-weight: 900;
            color: #f9fafb;
        }
        
        .ranking-highlight-text {
            text-align: center;
            max-width: 80vw;
        }
        
        .ranking-highlight-name {
            font-size: clamp(1.3rem, 3vw, 1.6rem);
            font-weight: 800;
            margin-bottom: 6px;
            color: #ffffff;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.6), 0 1px 4px rgba(0, 0, 0, 0.4);
        }
        
        .ranking-highlight-phrase {
            font-size: clamp(0.95rem, 2.2vw, 1.15rem);
            font-weight: 500;
            color: rgba(255, 255, 255, 0.98);
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.6), 0 1px 4px rgba(0, 0, 0, 0.4);
            line-height: 1.4;
        }
        
        .ranking-simple-list {
            margin-top: 14px;
        }
        
        .ranking-simple-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding: 8px 0;
            font-size: clamp(0.95rem, 2.2vw, 1.1rem);
            color: rgba(255, 255, 255, 0.98);
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }
        
        .ranking-simple-pos {
            font-weight: 800;
            font-size: 1.1em;
        }
        
        .ranking-simple-name {
            font-weight: 600;
            margin: 0 8px;
        }
        
        .ranking-simple-value {
            font-weight: 700;
            opacity: 0.95;
        }
        
        .ranking-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 0;
            background: linear-gradient(90deg, rgba(37, 99, 235, 0.1), transparent);
            transition: width 0.4s ease;
        }
        
        .ranking-item:hover {
            background: #ffffff;
            transform: translateX(8px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.04);
        }
        
        .ranking-item:hover::before {
            width: 100%;
        }
        
        .ranking-item:nth-child(1) {
            animation: fadeInUp 0.6s ease 0.5s both;
        }
        
        .ranking-item:nth-child(2) {
            animation: fadeInUp 0.6s ease 0.7s both;
        }
        
        .ranking-item:nth-child(3) {
            animation: fadeInUp 0.6s ease 0.9s both;
        }
        
        .posicao {
            font-size: 1.75em;
            font-weight: 700;
            width: 64px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            color: white;
            flex-shrink: 0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease;
        }
        
        .ranking-item:hover .posicao {
            transform: scale(1.05);
        }
        
        .posicao.ouro {
            background: linear-gradient(135deg, #f59e0b, #d97706);
            border: 2px solid rgba(245, 158, 11, 0.3);
        }
        
        .posicao.prata {
            background: linear-gradient(135deg, #6b7280, #4b5563);
            border: 2px solid rgba(107, 114, 128, 0.3);
        }
        
        .posicao.bronze {
            background: linear-gradient(135deg, #92400e, #78350f);
            border: 2px solid rgba(146, 64, 14, 0.3);
        }
        
        .jogador-imagem {
            width: 72px;
            height: 72px;
            border-radius: 12px;
            object-fit: cover;
            border: 3px solid #ffffff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(0, 0, 0, 0.05);
            flex-shrink: 0;
            background: #e5e7eb;
            transition: all 0.3s ease;
        }
        
        .ranking-item:hover .jogador-imagem {
            transform: scale(1.08);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        }
        
        .jogador-info {
            flex: 1;
        }
        
        .jogador-nome {
            font-size: 1.4em;
            font-weight: 600;
            color: #111827;
            margin-bottom: 8px;
            letter-spacing: -0.01em;
        }
        
        .jogador-quantidade {
            font-size: 1em;
            color: #6b7280;
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 500;
        }
        
        .badge {
            display: inline-block;
            background: linear-gradient(135deg, #2563eb, #1e40af);
            color: white;
            padding: 6px 16px;
            border-radius: 8px;
            font-size: 0.95em;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
            letter-spacing: 0.01em;
        }
        
        .grafico-section {
            display: flex;
            flex-direction: column;
            gap: 16px;
            justify-content: center;
            border-radius: 18px;
            background: rgba(15, 23, 42, 0.9);
            padding: 20px 18px 22px;
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.7);
            position: relative;
            overflow: hidden;
            margin-top: 18px;
        }
        
        .grafico-titulo {
            font-size: 1.5em;
            font-weight: 600;
            color: #374151;
            text-align: center;
            margin-bottom: 32px;
            letter-spacing: -0.01em;
        }
        
        .grafico-container {
            display: flex;
            flex-direction: column;
            gap: 24px;
            padding: 40px;
            background: #f9fafb;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
        }
        
        .barra-grafico {
            display: flex;
            align-items: center;
            gap: 20px;
            min-height: 64px;
        }
        
        .barra-label {
            min-width: 140px;
            font-weight: 600;
            color: #111827;
            font-size: 1.1em;
            letter-spacing: -0.01em;
        }
        
        .barra-wrapper {
            flex: 1;
            height: 48px;
            background: #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        
        .barra {
            height: 100%;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 16px;
            color: white;
            font-weight: 600;
            font-size: 1em;
            transition: width 1.2s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .barra::after {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            animation: shimmer 2s infinite;
        }
        
        .barra.ouro {
            background: linear-gradient(90deg, #f59e0b, #d97706);
        }
        
        .barra.prata {
            background: linear-gradient(90deg, #6b7280, #4b5563);
        }
        
        .barra.bronze {
            background: linear-gradient(90deg, #92400e, #78350f);
        }
        
        .barra-valor {
            min-width: 70px;
            text-align: right;
            font-weight: 700;
            color: #111827;
            font-size: 1.15em;
            letter-spacing: -0.01em;
        }
        
        .navegacao {
            position: fixed;
            top: 16px;
            right: 16px;
            display: flex;
            gap: 8px;
            z-index: 1000;
            animation: fadeInUp 0.8s ease 0.5s both;
            justify-content: flex-end;
            align-items: center;
        }
        
        .nav-btn {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 255, 255, 0.3);
            cursor: pointer;
            font-size: 1.8em;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            color: #ffffff;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        
        .nav-btn:hover {
            background: rgba(255, 255, 255, 0.4);
            transform: scale(1.1) translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 0, 0, 0.3);
        }
        
        .nav-btn:active {
            transform: scale(0.95);
        }
        
        .nav-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .indicador-slide {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
            z-index: 1000;
            border: 1px solid rgba(255, 255, 255, 0.3);
            font-size: 0.8em;
            letter-spacing: 0.02em;
            animation: fadeIn 0.6s ease 0.5s both;
            opacity: 0.6;
            transition: opacity 0.3s ease;
        }
        
        .indicador-slide:hover {
            opacity: 1;
        }
        
        .btn-alterar-jogador {
            position: fixed;
            top: 40px;
            left: 40px;
            background: rgba(255, 255, 255, 0.95);
            padding: 12px 24px;
            border-radius: 12px;
            font-weight: 600;
            color: #374151;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 1000;
            border: 1px solid rgba(0, 0, 0, 0.08);
            backdrop-filter: blur(10px);
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            display: none;
        }
        
        .btn-alterar-jogador:hover {
            background: #ffffff;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
            color: #2563eb;
        }
        
        /* Slides Motivacionais (Formato 9:16 - Estilo Spotify Wrapped) */
        .motivacional-slide {
            min-width: 100vw;
            width: 100vw;
            height: 100vh;
            height: 100dvh; /* Dynamic viewport height para mobile */
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 20px 20px;
            scroll-snap-align: start;
            text-align: center;
            position: relative;
            overflow: hidden;
            background-size: 200% 200%;
            animation: backgroundMove 30s ease-in-out infinite;
            box-sizing: border-box;
        }
        
        @keyframes backgroundMove {
            0% {
                background-position: 0% 0%;
            }
            25% {
                background-position: 100% 50%;
            }
            50% {
                background-position: 100% 100%;
            }
            75% {
                background-position: 0% 50%;
            }
            100% {
                background-position: 0% 0%;
            }
        }
        
        .motivacional-decorativo {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            z-index: 0;
        }
        
        .motivacional-decorativo::before {
            content: '';
            position: absolute;
            width: 200px;
            height: 200px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.1);
            top: -50px;
            left: -50px;
            animation: float 6s ease-in-out infinite;
        }
        
        .motivacional-decorativo::after {
            content: '';
            position: absolute;
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.08);
            bottom: -30px;
            right: -30px;
            animation: float 8s ease-in-out infinite reverse;
        }
        
        @keyframes float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            50% { transform: translate(20px, -20px) scale(1.1); }
        }
        
        .motivacional-content {
            position: relative;
            z-index: 1;
            max-width: 80vw;
            width: 100%;
            animation: fadeInUp 0.8s ease;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            flex: 0 0 70vh; /* bloco de texto ocupa ~70% da altura */
            min-height: 70vh;
        }
        
        .motivacional-ano {
            font-size: clamp(0.9rem, 1.6vw, 1.1rem);
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
            margin-bottom: 18px;
            letter-spacing: 0.14em;
        }
        
        .motivacional-titulo {
            font-size: clamp(2.6rem, 6vw, 3.8rem);
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 18px;
            line-height: 1.1;
            text-shadow: 0 3px 14px rgba(0, 0, 0, 0.35);
            letter-spacing: -0.03em;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: baseline;
            gap: 0.2em;
        }
        
        .motivacional-titulo .palavra-grande {
            font-size: 1.6em;
            font-weight: 900;
            line-height: 1;
            display: inline-block;
            transform: scale(1);
            transition: transform 0.3s ease;
        }
        
        .motivacional-titulo .palavra-media {
            font-size: 1.1em;
            font-weight: 700;
            line-height: 1;
            display: inline-block;
        }
        
        .motivacional-titulo .palavra-pequena {
            font-size: 0.65em;
            font-weight: 500;
            line-height: 1;
            opacity: 0.85;
            display: inline-block;
        }
        
        .motivacional-mensagem {
            font-size: clamp(1.4rem, 3.2vw, 2rem);
            font-weight: 500;
            color: rgba(255, 255, 255, 0.96);
            line-height: 1.35;
            margin-bottom: 10px;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: baseline;
            gap: 0.25em;
        }
        
        .motivacional-mensagem .palavra-destaque {
            font-size: 1.4em;
            font-weight: 800;
            color: #ffffff;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.4);
            display: inline-block;
            letter-spacing: -0.01em;
        }
        
        .motivacional-mensagem .palavra-normal {
            font-size: 1em;
            font-weight: 500;
            display: inline-block;
        }
        
        .motivacional-mensagem .palavra-pequena {
            font-size: 0.8em;
            font-weight: 400;
            opacity: 0.8;
            display: inline-block;
        }
        
        /* Deixamos de usar um bloco numérico separado: tudo entra no título/mensagem */
        .motivacional-destaque {
            display: none;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        .motivacional-extra {
            font-size: 0.9em;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.85);
            margin-top: 10px;
            text-shadow: 0 1px 5px rgba(0, 0, 0, 0.2);
        }
        
        /* Elementos decorativos flutuantes estilo Spotify */
        .motivacional-slide::before {
            content: '';
            position: absolute;
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.08);
            top: 10%;
            right: 8%;
            animation: float 8s ease-in-out infinite;
            box-shadow: 0 0 40px rgba(255, 255, 255, 0.1);
        }
        
        .motivacional-slide::after {
            content: '';
            position: absolute;
            width: 90px;
            height: 90px;
            border-radius: 30% 70% 70% 30% / 30% 30% 70% 70%;
            background: rgba(255, 255, 255, 0.06);
            bottom: 15%;
            left: 10%;
            animation: float 10s ease-in-out infinite reverse;
            box-shadow: 0 0 30px rgba(255, 255, 255, 0.08);
        }
        
        /* Padrões decorativos adicionais */
        .motivacional-pattern {
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            pointer-events: none;
            z-index: 0;
            opacity: 0.1;
        }
        
        .motivacional-pattern::before {
            content: '';
            position: absolute;
            width: 60px;
            height: 60px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            top: 25%;
            left: 5%;
            animation: rotate 20s linear infinite;
        }
        
        .motivacional-pattern::after {
            content: '';
            position: absolute;
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            bottom: 30%;
            right: 8%;
            animation: pulse 3s ease-in-out infinite;
        }
        
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        /* Perfil Completo (Estilo Wrapped - Story Full Screen) */
        .perfil-completo-slide {
            min-width: 100vw;
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 20px;
            scroll-snap-align: start;
            text-align: center;
            position: relative;
            overflow: hidden;
            background-size: 200% 200%;
            animation: backgroundMove 30s ease-in-out infinite;
            box-sizing: border-box;
            background: radial-gradient(circle at top left, #ff4b8b 0%, transparent 55%), 
                        radial-gradient(circle at bottom right, #ffb800 0%, transparent 55%),
                        linear-gradient(135deg, #1d1b4c, #3b0764);
        }
        
        .perfil-completo-content {
            max-width: 85vw;
            width: 100%;
            animation: fadeInUp 0.8s ease;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: center;
            padding: 20px 0;
            position: relative;
            z-index: 1;
        }
        
        .perfil-header {
            text-align: center;
            margin-bottom: 16px;
            width: 100%;
        }
        
        .perfil-imagem-grande {
            width: 100px;
            height: 100px;
            border-radius: 24px;
            object-fit: cover;
            border: 3px solid rgba(255, 255, 255, 0.95);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            margin: 0 auto 12px;
            display: block;
            background: linear-gradient(135deg, #22c55e, #16a34a);
        }
        
        .perfil-nome-grande {
            font-size: clamp(2rem, 5vw, 2.8rem);
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 10px;
            text-shadow: 0 3px 14px rgba(0, 0, 0, 0.35);
            letter-spacing: -0.03em;
        }
        
        .perfil-subtitulo {
            font-size: clamp(1rem, 2.5vw, 1.3rem);
            font-weight: 600;
            color: rgba(255, 255, 255, 0.95);
            margin-bottom: 16px;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.5);
        }
        
        .perfil-stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 0;
            width: 100%;
        }
        
        .perfil-stat-card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 14px 10px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
        }
        
        .perfil-stat-numero {
            font-size: clamp(1.6rem, 4vw, 2.2rem);
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 4px;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.5);
        }
        
        .perfil-stat-label {
            font-size: clamp(0.75rem, 1.8vw, 0.95rem);
            color: rgba(255, 255, 255, 0.95);
            font-weight: 600;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }
        
        .perfil-comparacao-card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 14px 16px;
            margin-top: 8px;
            margin-bottom: 16px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
            width: 100%;
        }
        
        .perfil-comparacao-titulo {
            font-size: clamp(0.85rem, 2vw, 1.1rem);
            font-weight: 700;
            color: rgba(255, 255, 255, 0.9);
            margin-bottom: 8px;
            text-align: center;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }
        
        .perfil-comparacao-nome {
            font-size: clamp(1.1rem, 2.8vw, 1.5rem);
            font-weight: 800;
            color: #ffffff;
            text-align: center;
            margin-bottom: 6px;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.5);
        }
        
        .perfil-comparacao-desc {
            font-size: clamp(0.8rem, 1.8vw, 1rem);
            color: rgba(255, 255, 255, 0.95);
            text-align: center;
            line-height: 1.4;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            margin-bottom: 8px;
        }
        
        .perfil-similaridade {
            text-align: center;
            margin-top: 8px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 12px;
        }
        
        .perfil-similaridade-valor {
            font-size: clamp(1.5rem, 3.5vw, 2rem);
            font-weight: 900;
            color: #ffffff;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.5);
        }
        
        .perfil-similaridade-label {
            font-size: clamp(0.7rem, 1.6vw, 0.85rem);
            color: rgba(255, 255, 255, 0.9);
            margin-top: 4px;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }
        
        /* Slides de Storytelling */
        .storytelling-slide {
            min-width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 60px;
            scroll-snap-align: start;
            background: linear-gradient(135deg, #0a1929 0%, #1a2332 50%, #0f1419 100%);
        }
        
        .storytelling-content {
            background: #ffffff;
            border-radius: 20px;
            padding: 60px;
            max-width: 1000px;
            width: 100%;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.2);
            text-align: center;
            animation: fadeInUp 0.8s ease;
        }
        
        .storytelling-numero {
            font-size: 5em;
            font-weight: 800;
            background: linear-gradient(135deg, #2563eb, #1e40af);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
            line-height: 1;
        }
        
        .storytelling-titulo {
            font-size: 2.5em;
            font-weight: 700;
            color: #111827;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
        }
        
        .storytelling-descricao {
            font-size: 1.3em;
            color: #6b7280;
            line-height: 1.8;
            margin-bottom: 40px;
        }
        
        .storytelling-comparacao {
            background: #f9fafb;
            border-radius: 16px;
            padding: 30px;
            margin-top: 30px;
            border: 1px solid #e5e7eb;
        }
        
        .storytelling-comparacao-texto {
            font-size: 1.1em;
            color: #374151;
            line-height: 1.6;
        }
        
        .storytelling-comparacao-texto strong {
            color: #2563eb;
            font-weight: 700;
        }
        
        .sem-dados {
            text-align: center;
            color: #999;
            font-style: italic;
            padding: 50px 20px;
            font-size: 1.3em;
            grid-column: 1 / -1;
        }
        
        /* Tela Inicial */
        .tela-inicial {
            min-width: 100vw;
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 40px 20px;
            position: relative;
            overflow: hidden;
            background-size: 200% 200%;
            animation: backgroundMove 30s ease-in-out infinite;
            background: radial-gradient(circle at top left, #ff4b8b 0%, transparent 55%), 
                        radial-gradient(circle at bottom right, #ffb800 0%, transparent 55%),
                        linear-gradient(135deg, #1d1b4c, #3b0764);
        }
        
        .tela-inicial-content {
            background: transparent;
            border-radius: 0;
            padding: 0;
            max-width: 420px;
            width: 100%;
            box-shadow: none;
            text-align: center;
            animation: fadeInUp 0.8s ease;
            position: relative;
            z-index: 1;
        }
        
        .tela-inicial h1 {
            font-size: clamp(2.4rem, 6vw, 3.5rem);
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 16px;
            text-shadow: 0 4px 16px rgba(0, 0, 0, 0.6), 0 2px 8px rgba(0, 0, 0, 0.4);
            letter-spacing: -0.03em;
        }
        
        .tela-inicial p {
            font-size: clamp(1rem, 2.5vw, 1.3rem);
            color: rgba(255, 255, 255, 0.95);
            margin-bottom: 32px;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
            font-weight: 500;
        }
        
        .input-nome {
            width: 100%;
            padding: 16px 20px;
            font-size: clamp(1rem, 2.5vw, 1.1rem);
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 16px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
            font-family: 'Inter', sans-serif;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            color: #ffffff;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        
        .input-nome::placeholder {
            color: rgba(255, 255, 255, 0.7);
        }
        
        .input-nome:focus {
            outline: none;
            border-color: rgba(255, 255, 255, 0.6);
            box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.2);
            background: rgba(255, 255, 255, 0.2);
        }
        
        .btn-iniciar {
            width: 100%;
            padding: 16px;
            font-size: clamp(1rem, 2.5vw, 1.1rem);
            font-weight: 700;
            color: white;
            background: rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 255, 255, 0.4);
            border-radius: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }
        
        .btn-iniciar:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
            background: rgba(255, 255, 255, 0.3);
            border-color: rgba(255, 255, 255, 0.5);
        }
        
        .btn-iniciar:active {
            transform: translateY(0);
        }
        
        .btn-iniciar:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-nao-sei-nome {
            width: 100%;
            padding: 12px;
            font-size: clamp(0.9rem, 2.2vw, 1rem);
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            text-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
            margin-bottom: 12px;
        }
        
        .btn-nao-sei-nome:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
            background: rgba(255, 255, 255, 0.2);
            border-color: rgba(255, 255, 255, 0.4);
        }
        
        .btn-nao-sei-nome:active {
            transform: translateY(0);
        }
        
        /* Modal de Jogadores */
        .modal-jogadores {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(5px);
            z-index: 10000;
            animation: fadeIn 0.3s ease;
            overflow-y: auto;
        }
        
        .modal-jogadores.active {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .modal-content {
            background: linear-gradient(135deg, #1d1b4c, #3b0764);
            border-radius: 20px;
            max-width: 600px;
            width: 100%;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            animation: scaleIn 0.3s ease;
            overflow: hidden;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .modal-header h2 {
            font-size: clamp(1.5rem, 4vw, 2rem);
            font-weight: 700;
            color: #ffffff;
            margin: 0;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }
        
        .modal-close {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: #ffffff;
            font-size: 2rem;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            line-height: 1;
        }
        
        .modal-close:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: rotate(90deg);
        }
        
        .modal-body {
            padding: 24px;
            overflow-y: auto;
            flex: 1;
        }
        
        .modal-busca {
            width: 100%;
            padding: 12px 16px;
            font-size: 1rem;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            margin-bottom: 16px;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            color: #ffffff;
            font-family: 'Inter', sans-serif;
        }
        
        .modal-busca::placeholder {
            color: rgba(255, 255, 255, 0.7);
        }
        
        .modal-busca:focus {
            outline: none;
            border-color: rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.2);
        }
        
        .modal-lista {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 12px;
            max-height: 50vh;
            overflow-y: auto;
        }
        
        .modal-item {
            padding: 12px 16px;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: #ffffff;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
            font-weight: 500;
            font-size: 0.95rem;
        }
        
        .modal-item:hover {
            background: rgba(255, 255, 255, 0.25);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .modal-item:active {
            transform: translateY(0);
        }
        
        @media (max-width: 768px) {
            .modal-content {
                max-width: 90vw;
                max-height: 90vh;
            }
            
            .modal-lista {
                grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
                gap: 10px;
            }
            
            .modal-item {
                padding: 10px 12px;
                font-size: 0.9rem;
            }
        }
        
        /* Retrospectiva */
        .retrospectiva-slide {
            min-width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 40px;
            scroll-snap-align: start;
            background: linear-gradient(135deg, #0a1929 0%, #1a2332 50%, #0f1419 100%);
        }
        
        .retrospectiva-content {
            background: #ffffff;
            border-radius: 20px;
            padding: 50px;
            max-width: 1200px;
            width: 100%;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.2);
            animation: fadeInUp 0.8s ease;
        }
        
        .retrospectiva-header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 30px;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .retrospectiva-titulo {
            font-size: 2.5em;
            font-weight: 700;
            color: #111827;
            margin-bottom: 10px;
        }
        
        .retrospectiva-subtitulo {
            font-size: 1.2em;
            color: #6b7280;
        }
        
        .comparacao-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        .comparacao-card {
            background: #f9fafb;
            border-radius: 16px;
            padding: 30px;
            border: 1px solid #e5e7eb;
            transition: all 0.3s ease;
        }
        
        .comparacao-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
        }
        
        .comparacao-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 20px;
        }
        
        .comparacao-imagem {
            width: 80px;
            height: 80px;
            border-radius: 12px;
            object-fit: cover;
            border: 3px solid #ffffff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        .comparacao-nome {
            font-size: 1.5em;
            font-weight: 600;
            color: #111827;
        }
        
        .comparacao-posicao {
            font-size: 1em;
            color: #6b7280;
            margin-top: 4px;
        }
        
        .comparacao-stats {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: white;
            border-radius: 8px;
        }
        
        .stat-label {
            font-weight: 500;
            color: #374151;
        }
        
        .stat-valor {
            font-weight: 700;
            color: #111827;
        }
        
        .jornada-timeline {
            margin-top: 40px;
            padding-top: 40px;
            border-top: 2px solid #e5e7eb;
        }
        
        .jornada-titulo {
            font-size: 1.8em;
            font-weight: 600;
            color: #111827;
            margin-bottom: 30px;
            text-align: center;
        }
        
        .timeline-item {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            padding-left: 20px;
            border-left: 3px solid #2563eb;
            position: relative;
        }
        
        .timeline-item::before {
            content: '';
            position: absolute;
            left: -8px;
            top: 0;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #2563eb;
            border: 3px solid white;
            box-shadow: 0 0 0 3px #2563eb;
        }
        
        .timeline-content {
            flex: 1;
            background: #f9fafb;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
        }
        
        .timeline-titulo {
            font-size: 1.2em;
            font-weight: 600;
            color: #111827;
            margin-bottom: 8px;
        }
        
        .timeline-descricao {
            color: #6b7280;
            line-height: 1.6;
        }
        
        @media (max-width: 1024px) {
            .slide-content {
                grid-template-columns: 1fr;
                padding: 40px;
                gap: 40px;
            }
            
            .categoria-titulo {
                font-size: 2em;
            }
            
            .slide {
                padding: 40px 20px;
            }
            
            .comparacao-grid {
                grid-template-columns: 1fr;
            }
            
            .retrospectiva-content {
                padding: 40px;
            }
            
            .storytelling-content {
                padding: 40px;
            }
            
            .storytelling-numero {
                font-size: 4em;
            }
            
            .storytelling-titulo {
                font-size: 2em;
            }
            
            .motivacional-titulo {
                font-size: 1.8em;
            }
            
            .motivacional-mensagem {
                font-size: 1.2em;
            }
            
            .motivacional-destaque {
                font-size: 2.5em;
            }
            
            .perfil-completo-content {
                padding: 25px;
            }
            
            .perfil-nome-grande {
                font-size: 1.8em;
            }
        }
        
        @media (max-width: 768px) {
            .slide-content {
                padding: 30px 20px;
                min-height: auto;
                grid-template-columns: 1fr;
                gap: 30px;
            }
            
            .categoria-titulo {
                font-size: 1.8em;
            }
            
            .motivacional-slide {
                padding: 30px 20px;
            }
            
            .motivacional-content {
                max-width: 92%;
            }
            
            .motivacional-ano {
                font-size: 0.85em;
                margin-bottom: 20px;
            }
            
            .motivacional-titulo {
                font-size: 1.8em;
                margin-bottom: 25px;
            }
            
            .motivacional-mensagem {
                font-size: 1.15em;
                margin-bottom: 25px;
            }
            
            .motivacional-destaque {
                font-size: 3.5em;
                margin: 30px 0;
            }
            
            .motivacional-extra {
                font-size: 1em;
            }
            
            .perfil-completo-content {
                padding: 25px;
            }
            
            .perfil-stats-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            
            .categoria-icone {
                font-size: 2.5em;
            }
            
            .categoria-header {
                flex-direction: column;
                gap: 12px;
            }
            
            .jogador-nome {
                font-size: 1.2em;
            }
            
            .posicao {
                width: 56px;
                height: 56px;
                font-size: 1.4em;
            }
            
            .jogador-imagem {
                width: 60px;
                height: 60px;
            }
            
            .ranking-item {
                padding: 20px;
                min-height: 100px;
                gap: 16px;
            }
            
            .grafico-container {
                padding: 24px;
            }
            
            .barra-wrapper {
                height: 40px;
            }
            
            .barra-label {
                min-width: 100px;
                font-size: 1em;
            }
            
            .barra-valor {
                min-width: 50px;
                font-size: 1em;
            }
            
            .navegacao {
                top: 12px;
                right: 12px;
                left: auto;
                bottom: auto;
                gap: 8px;
                width: auto;
                max-width: none;
                justify-content: flex-end;
            }
            
            .nav-btn {
                width: 48px;
                height: 48px;
                font-size: 1.2em;
            }
            
            .indicador-slide {
                top: 20px;
                right: 20px;
                padding: 10px 16px;
                font-size: 0.85em;
            }
            
            .tela-inicial {
                padding: 30px 20px;
            }
            
            .tela-inicial-content {
                max-width: 90vw;
                padding: 0;
            }
            
            .tela-inicial h1 {
                font-size: clamp(2rem, 5vw, 2.8rem);
            }
            
            .tela-inicial p {
                font-size: clamp(0.9rem, 2.2vw, 1.1rem);
                margin-bottom: 24px;
            }
            
            .input-nome {
                padding: 14px 18px;
                font-size: clamp(0.95rem, 2.3vw, 1.05rem);
            }
            
            .btn-iniciar {
                padding: 14px;
                font-size: clamp(0.95rem, 2.3vw, 1.05rem);
            }
            
            .retrospectiva-content {
                padding: 30px 20px;
            }
            
            .retrospectiva-titulo {
                font-size: 2em;
            }
            
            .comparacao-card {
                padding: 20px;
            }
            
            .comparacao-nome {
                font-size: 1.2em;
            }
            
            .comparacao-imagem {
                width: 60px;
                height: 60px;
            }
            
            .storytelling-content {
                padding: 30px 20px;
            }
            
            .storytelling-numero {
                font-size: 3.5em;
            }
            
            .storytelling-titulo {
                font-size: 1.8em;
            }
            
            .storytelling-descricao {
                font-size: 1.1em;
            }
            
            .btn-alterar-jogador {
                top: 20px;
                left: 20px;
                padding: 10px 16px;
                font-size: 0.85em;
            }
        }
        
        @media (max-width: 480px) {
            .slide {
                padding: 15px 10px;
            }
            
            .slide-content {
                padding: 20px 15px;
                border-radius: 12px;
                grid-template-columns: 1fr;
                gap: 20px;
                min-height: auto;
            }
            
            .categoria-titulo {
                font-size: 1.4em;
            }
            
            .slide-header {
                margin-bottom: 25px;
                padding-bottom: 25px;
            }
            
            .ranking-item {
                flex-direction: column;
                text-align: center;
                gap: 12px;
                padding: 18px;
            }
            
            .jogador-info {
                width: 100%;
            }
            
            .barra-grafico {
                flex-direction: column;
                gap: 12px;
            }
            
            .barra-label {
                min-width: auto;
                width: 100%;
                text-align: center;
            }
            
            .barra-wrapper {
                width: 100%;
            }
            
            .barra-valor {
                width: 100%;
                text-align: center;
            }
            
            .grafico-container {
                padding: 20px;
            }
            
            .storytelling-content {
                padding: 24px 16px;
            }
            
            .storytelling-numero {
                font-size: 3em;
            }
            
            .storytelling-titulo {
                font-size: 1.5em;
            }
            
            .storytelling-descricao {
                font-size: 1em;
            }
            
            .storytelling-comparacao {
                padding: 20px;
            }
            
            .btn-alterar-jogador {
                top: 10px;
                left: 10px;
                padding: 8px 12px;
                font-size: 0.75em;
                opacity: 0.7;
                transition: opacity 0.3s ease;
            }
            
            .btn-alterar-jogador:active {
                opacity: 1;
            }
            
            /* Esconde indicador de slide em mobile - torna menos "slide-like" */
            .indicador-slide {
                display: none !important;
            }
            
            /* Navegação fixa no topo direito em mobile */
            .navegacao {
                top: 10px;
                right: 10px;
                left: auto;
                bottom: auto;
                opacity: 0.8;
                transition: opacity 0.3s ease;
            }
            
            .navegacao:active {
                opacity: 1;
            }
            
            .nav-btn {
                width: 40px;
                height: 40px;
                font-size: 1em;
            }
            
            .motivacional-slide {
                padding: 15px 15px;
                height: 100vh;
                height: 100dvh;
            }
            
            .motivacional-content {
                max-width: 95%;
                padding: 0;
            }
            
            .motivacional-ano {
                font-size: 0.65em;
                margin-bottom: 8px;
            }
            
            .motivacional-titulo {
                font-size: 1.4em;
                margin-bottom: 12px;
                line-height: 1.1;
            }
            
            .motivacional-titulo .palavra-grande {
                font-size: 1.4em;
            }
            
            .motivacional-titulo .palavra-media {
                font-size: 1em;
            }
            
            .motivacional-titulo .palavra-pequena {
                font-size: 0.6em;
            }
            
            .motivacional-mensagem {
                font-size: 0.9em;
                margin-bottom: 12px;
                line-height: 1.5;
            }
            
            .motivacional-mensagem .palavra-destaque {
                font-size: 1.2em;
            }
            
            .motivacional-mensagem .palavra-normal {
                font-size: 0.9em;
            }
            
            .motivacional-mensagem .palavra-pequena {
                font-size: 0.7em;
            }
            
            .motivacional-destaque {
                font-size: 3em;
                margin: 15px 0;
            }
            
            .motivacional-extra {
                font-size: 0.8em;
                margin-top: 8px;
            }
            
            .motivacional-slide::before,
            .motivacional-slide::after {
                width: 60px;
                height: 60px;
            }
            
            .motivacional-pattern::before {
                width: 30px;
                height: 30px;
            }
            
            .motivacional-pattern::after {
                width: 25px;
                height: 25px;
            }
            
            .motivacional-decorativo::before {
                width: 120px;
                height: 120px;
            }
            
            .motivacional-decorativo::after {
                width: 90px;
                height: 90px;
            }
            
            .perfil-completo-slide {
                padding: 20px 15px;
            }
            
            .perfil-completo-content {
                padding: 20px;
                max-width: 95%;
            }
            
            .perfil-imagem-grande {
                width: 90px;
                height: 90px;
                margin-bottom: 10px;
            }
            
            .perfil-nome-grande {
                font-size: clamp(1.8rem, 4.5vw, 2.4rem);
            }
            
            .perfil-subtitulo {
                font-size: clamp(0.9rem, 2.2vw, 1.1rem);
            }
            
            .perfil-stats-grid {
                gap: 10px;
                margin-bottom: 0;
            }
            
            .perfil-stat-card {
                padding: 12px 8px;
            }
            
            .perfil-stat-numero {
                font-size: clamp(1.4rem, 3.5vw, 1.9rem);
            }
            
            .perfil-stat-label {
                font-size: clamp(0.7rem, 1.6vw, 0.85rem);
            }
            
            .perfil-comparacao-card {
                padding: 12px 14px;
                margin-top: 6px;
                margin-bottom: 12px;
            }
            
            .perfil-comparacao-titulo {
                font-size: clamp(0.8rem, 1.9vw, 1rem);
            }
            
            .perfil-comparacao-nome {
                font-size: clamp(1rem, 2.5vw, 1.3rem);
            }
            
            .perfil-comparacao-desc {
                font-size: clamp(0.75rem, 1.7vw, 0.9rem);
            }
            
            .perfil-similaridade-valor {
                font-size: clamp(1.3rem, 3vw, 1.7rem);
            }
            
            .perfil-similaridade-label {
                font-size: clamp(0.65rem, 1.5vw, 0.8rem);
            }
        }
    </style>
</head>
<body>
    <div class="indicador-slide" id="indicador-slide" style="display: none;">
        <span id="slide-indicador">1 / 1</span>
    </div>
    
    <button class="btn-alterar-jogador" id="btn-alterar-jogador" onclick="alterarJogador()">
        ↻ Alterar Jogador
    </button>
    
    <!-- Tela Inicial -->
    <div class="tela-inicial" id="tela-inicial">
        <div class="tela-inicial-content">
            <h1>Ranking Galático</h1>
            <p>Descubra sua jornada e compare-se com os grandes do futebol</p>
            <input type="text" id="input-nome-jogador" class="input-nome" placeholder="Digite seu nome completo (opcional)" autocomplete="off">
            <button class="btn-nao-sei-nome" onclick="abrirModalJogadores()">Não sei meu nome no app</button>
            <button class="btn-iniciar" onclick="iniciarRetrospectiva()">Iniciar Minha Jornada</button>
            <p style="margin-top: 20px; font-size: 0.9em; color: rgba(255, 255, 255, 0.8); text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);">Ou pressione Enter para ver o ranking geral</p>
        </div>
    </div>
    
    <!-- Modal de Lista de Jogadores -->
    <div class="modal-jogadores" id="modal-jogadores" onclick="fecharModalJogadores(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2>Lista de Jogadores</h2>
                <button class="modal-close" onclick="fecharModalJogadores()">&times;</button>
            </div>
            <div class="modal-body">
                <input type="text" id="modal-busca" class="modal-busca" placeholder="Buscar jogador..." onkeyup="filtrarJogadores()">
                <div class="modal-lista" id="modal-lista">
                    <!-- Lista será populada via JavaScript -->
                </div>
            </div>
        </div>
    </div>
    
    <!-- Container da Retrospectiva (inicialmente oculto) -->
    <div id="retrospectiva-container" style="display: none;"></div>
    
    <div class="slides-container" id="slides-container" style="display: none;">
"""
    
    # Backgrounds diferentes por categoria (cores vibrantes mas legíveis)
    backgrounds_por_categoria = {
        'totalGoals': 'radial-gradient(circle at top left, #ff6b35 0%, transparent 55%), radial-gradient(circle at bottom right, #f7931e 0%, transparent 55%), linear-gradient(135deg, #8b2e00, #cc4400)',
        'totalAssistence': 'radial-gradient(circle at top left, #667eea 0%, transparent 55%), radial-gradient(circle at bottom right, #764ba2 0%, transparent 55%), linear-gradient(135deg, #2d1b4c, #4a2c6b)',
        'totalWins': 'radial-gradient(circle at top left, #11998e 0%, transparent 55%), radial-gradient(circle at bottom right, #38ef7d 0%, transparent 55%), linear-gradient(135deg, #0a4d3a, #0d6b4f)',
        'totalGamePlayed': 'radial-gradient(circle at top left, #8360c3 0%, transparent 55%), radial-gradient(circle at bottom right, #2ebf91 0%, transparent 55%), linear-gradient(135deg, #3d2a5c, #1a4d3a)',
        'totalDefeat': 'radial-gradient(circle at top left, #ee0979 0%, transparent 55%), radial-gradient(circle at bottom right, #ff6a00 0%, transparent 55%), linear-gradient(135deg, #5a0a2e, #7a0f3e)',
        'totalDraw': 'radial-gradient(circle at top left, #a8edea 0%, transparent 55%), radial-gradient(circle at bottom right, #fed6e3 0%, transparent 55%), linear-gradient(135deg, #2d4a4a, #4a6b6b)',
        'artilheiro': 'radial-gradient(circle at top left, #ffd700 0%, transparent 55%), radial-gradient(circle at bottom right, #ff8c00 0%, transparent 55%), linear-gradient(135deg, #8b6f00, #cc9900)',
        'craque': 'radial-gradient(circle at top left, #1e3c72 0%, transparent 55%), radial-gradient(circle at bottom right, #2a5298 0%, transparent 55%), linear-gradient(135deg, #0f1a2e, #1a2d4a)',
        'garcom': 'radial-gradient(circle at top left, #4facfe 0%, transparent 55%), radial-gradient(circle at bottom right, #00f2fe 0%, transparent 55%), linear-gradient(135deg, #1a3a5c, #2a5a7c)',
        'muralha': 'radial-gradient(circle at top left, #22c55e 0%, transparent 55%), radial-gradient(circle at bottom right, #16a34a 0%, transparent 55%), linear-gradient(135deg, #0d3a1e, #145a2e)',
        'bolaMurcha': 'radial-gradient(circle at top left, #6b7280 0%, transparent 55%), radial-gradient(circle at bottom right, #9ca3af 0%, transparent 55%), linear-gradient(135deg, #2d2d2d, #4a4a4a)',
        'xerifao': 'radial-gradient(circle at top left, #f59e0b 0%, transparent 55%), radial-gradient(circle at bottom right, #d97706 0%, transparent 55%), linear-gradient(135deg, #5a3a00, #7a4f00)',
        'pereba': 'radial-gradient(circle at top left, #ef4444 0%, transparent 55%), radial-gradient(circle at bottom right, #dc2626 0%, transparent 55%), linear-gradient(135deg, #5a0a0a, #7a0f0f)',
    }
    
    # Gera o HTML para cada categoria (story de ranking)
    # +1 slide final de encerramento
    total_slides = len(categorias) + 1
    slide_num = 0
    
    for categoria, rankings in categorias.items():
        slide_num += 1
        nome_amigavel = nomes_categorias.get(categoria, categoria.capitalize())
        icone = icones_categorias.get(categoria, '🏆')
        
        # Background específico para esta categoria
        background_categoria = backgrounds_por_categoria.get(categoria, 
            'radial-gradient(circle at top left, #f97316 0%, transparent 55%), radial-gradient(circle at bottom right, #22c55e 0%, transparent 55%), linear-gradient(135deg, #1d1b4c, #3b0764)')
        
        html += f"""
        <div class="slide" style="background: {background_categoria}; background-size: 200% 200%; animation: backgroundMove 30s ease-in-out infinite;">
            <div class="slide-content">
                <div class="slide-header">
                    <div class="story-year">Categoria</div>
                    <div class="categoria-titulo">{nome_amigavel}</div>
                    <div class="story-subtitle">Top 4 da temporada</div>
                </div>
"""
        
        if rankings:
            # Pega o top 4
            top4 = rankings[:4]
            
            # Destaque do campeão da categoria
            primeiro_nome, primeiro_valor = top4[0]
            # Busca imagem com flexibilidade (normaliza espaços, lowercase)
            def normalizar_nome(nome):
                if not nome:
                    return ''
                return nome.strip().lower().replace(' ', '').replace('\t', '')
            
            nome_normalizado = normalizar_nome(primeiro_nome)
            imagem_primeiro = ''
            
            # Tenta match exato primeiro
            if primeiro_nome in imagens_jogadores:
                imagem_primeiro = imagens_jogadores[primeiro_nome]
            else:
                # Busca com normalização (sem espaços, lowercase)
                for nome_key, img_url in imagens_jogadores.items():
                    if nome_key and img_url:
                        if normalizar_nome(nome_key) == nome_normalizado:
                            imagem_primeiro = img_url
                            break
            
            # Se ainda não encontrou, tenta match parcial (primeira palavra)
            if not imagem_primeiro and primeiro_nome:
                primeiro_palavra = primeiro_nome.split()[0] if primeiro_nome else ''
                if primeiro_palavra:
                    primeiro_palavra_lower = primeiro_palavra.lower()
                    for nome_key, img_url in imagens_jogadores.items():
                        if nome_key and img_url:
                            nome_key_lower = nome_key.lower()
                            if primeiro_palavra_lower in nome_key_lower or nome_key_lower.startswith(primeiro_palavra_lower):
                                imagem_primeiro = img_url
                                break
            
            inicial = primeiro_nome[0].upper() if primeiro_nome else '?'
            # Verifica se a imagem é válida (não vazia e começa com http)
            imagem_valida = imagem_primeiro and imagem_primeiro.strip() and (imagem_primeiro.startswith('http://') or imagem_primeiro.startswith('https://'))
            
            if imagem_valida:
                # Usa JavaScript para fallback caso a imagem não carregue
                # Escapa aspas simples usando HTML entities
                destaque_imagem = (
                    f'<img src="{imagem_primeiro}" alt="{primeiro_nome}" '
                    f'class="ranking-highlight-image" '
                    f'onerror="this.onerror=null; this.style.display=&#39;none&#39;; const placeholder = this.nextElementSibling; if (placeholder) placeholder.style.display=&#39;flex&#39;;">'
                    f'<div class="ranking-highlight-placeholder" style="display: none;">{inicial}</div>'
                )
            else:
                destaque_imagem = f'<div class="ranking-highlight-placeholder">{inicial}</div>'
            
            elogio = gerar_frase_elogio(categoria, primeiro_nome, primeiro_valor)
            
            html += f"""
                <div class="ranking-highlight">
                    <div class="ranking-highlight-visual">
                        {destaque_imagem}
                    </div>
                    <div class="ranking-highlight-text">
                        <div class="ranking-highlight-name">{primeiro_nome}</div>
                        <div class="ranking-highlight-phrase">{elogio}</div>
                    </div>
                </div>
                <div class="ranking-simple-list">
"""
            for idx, (nome, quantidade) in enumerate(top4, 1):
                sufixo = "º"
                html += f"""
                    <div class="ranking-simple-row">
                        <span class="ranking-simple-pos">{idx}{sufixo}</span>
                        <span class="ranking-simple-name">{nome}</span>
                        <span class="ranking-simple-value">{quantidade}</span>
                    </div>
"""
            html += """
                </div>
"""
        else:
            html += """
                <div class="sem-dados">Nenhum dado disponível</div>
"""
        
        html += """
            </div>
        </div>
"""

    # Slide final de encerramento da jornada
    html += """
        <div class="slide">
            <div class="slide-content">
                <div class="slide-header">
                    <div class="story-year">Temporada Encerrada</div>
                    <div class="categoria-titulo">Isso não é o fim da sua carreira</div>
                    <div class="story-subtitle">A próxima temporada já está te esperando!</div>
                </div>
                <div class="categoria-titulo" style="margin-top: 12px;">
                   #GalaticosFC
                </div>
            </div>
        </div>
"""
    
    # Prepara dados para JavaScript (serializa categorias e imagens)
    import json as json_module
    # Converte tuplas para listas para serialização JSON
    categorias_para_json = {}
    for cat, rankings in categorias.items():
        categorias_para_json[cat] = [[nome, qtd] for nome, qtd in rankings]
    categorias_json = json_module.dumps(categorias_para_json)
    imagens_json = json_module.dumps(imagens_jogadores)
    
    # Prepara lista de nomes de jogadores para o modal
    nomes_jogadores_json = json_module.dumps(nomes_todos_jogadores)
    
    # Lê variáveis de ambiente para API OpenAI
    openai_api_key = os.getenv('OPENAI_API_KEY', 'null')
    openai_model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    
    # Formata para JavaScript (com aspas se não for null)
    openai_api_key_js = f"'{openai_api_key}'" if openai_api_key and openai_api_key != 'null' else 'null'
    openai_model_js = f"'{openai_model}'"
    
    html += f"""
    </div>
    
    <div class="navegacao" id="navegacao" style="display: none;">
        <button class="nav-btn" onclick="slideAnterior()">‹</button>
        <button class="nav-btn" onclick="slideProximo()">›</button>
    </div>
    
    <!-- Configuração da API OpenAI via variáveis de ambiente -->
    <script>
        // Variáveis de ambiente injetadas pelo servidor
        window.OPENAI_API_KEY = {openai_api_key_js};
        window.OPENAI_MODEL = {openai_model_js};
        
        // Dados globais
        const categoriasData = {categorias_json};
        const imagensJogadores = {imagens_json};
        const totalSlidesRanking = {total_slides};
        const nomesJogadores = {nomes_jogadores_json};
        
        // Elementos DOM
        const telaInicial = document.getElementById('tela-inicial');
        const retrospectivaContainer = document.getElementById('retrospectiva-container');
        const slidesContainer = document.getElementById('slides-container');
        const navegacao = document.getElementById('navegacao');
        const indicadorSlide = document.getElementById('indicador-slide');
        const inputNome = document.getElementById('input-nome-jogador');
        
        // Funções do Modal de Jogadores
        function abrirModalJogadores() {{
            const modal = document.getElementById('modal-jogadores');
            const lista = document.getElementById('modal-lista');
            
            // Limpa a lista
            lista.innerHTML = '';
            
            // Popula a lista com os nomes dos jogadores
            nomesJogadores.forEach(nome => {{
                const item = document.createElement('div');
                item.className = 'modal-item';
                item.textContent = nome;
                item.onclick = () => {{
                    inputNome.value = nome;
                    fecharModalJogadores();
                    inputNome.focus();
                }};
                lista.appendChild(item);
            }});
            
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }}
        
        function fecharModalJogadores(event) {{
            if (event && event.target && event.target.id !== 'modal-jogadores') {{
                return;
            }}
            const modal = document.getElementById('modal-jogadores');
            modal.classList.remove('active');
            document.body.style.overflow = '';
            // Limpa o campo de busca
            const busca = document.getElementById('modal-busca');
            if (busca) busca.value = '';
        }}
        
        function filtrarJogadores() {{
            const busca = document.getElementById('modal-busca').value.toLowerCase();
            const itens = document.querySelectorAll('.modal-item');
            
            itens.forEach(item => {{
                const nome = item.textContent.toLowerCase();
                if (nome.includes(busca)) {{
                    item.style.display = '';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}
        
        // Cache para backgrounds e textos gerados
        const backgroundsCache = {{}};
        const textosCache = {{}};
        
        // Função para gerar background usando OpenAI DALL-E (com fallback para gradientes CSS)
        async function gerarBackground(statTipo, valor) {{
            const cacheKey = statTipo + '_' + valor;
            if (backgroundsCache[cacheKey]) {{
                return backgroundsCache[cacheKey];
            }}
            
            // Gradientes dinâmicos baseados no tipo e valor
            const gradientes = {{
                'gols': [
                    'linear-gradient(135deg, #ff6b35 0%, #f7931e 30%, #ffd700 60%, #ff8c00 100%)',
                    'linear-gradient(135deg, #ff4500 0%, #ff6347 50%, #ffa500 100%)',
                    'linear-gradient(135deg, #ff8c00 0%, #ffd700 50%, #ffa500 100%)'
                ],
                'assistencias': [
                    'linear-gradient(135deg, #667eea 0%, #764ba2 30%, #f093fb 60%, #4facfe 100%)',
                    'linear-gradient(135deg, #4facfe 0%, #00f2fe 50%, #667eea 100%)',
                    'linear-gradient(135deg, #8360c3 0%, #2ebf91 50%, #667eea 100%)'
                ],
                'vitorias': [
                    'linear-gradient(135deg, #11998e 0%, #38ef7d 30%, #f7ff00 60%, #00c9ff 100%)',
                    'linear-gradient(135deg, #00f260 0%, #0575e6 50%, #38ef7d 100%)',
                    'linear-gradient(135deg, #0ba360 0%, #3cba92 50%, #f7ff00 100%)'
                ],
                'partidas': [
                    'linear-gradient(135deg, #8360c3 0%, #2ebf91 30%, #ff6b6b 60%, #f093fb 100%)',
                    'linear-gradient(135deg, #a8edea 0%, #fed6e3 50%, #8360c3 100%)',
                    'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)'
                ],
                'artilheiro': [
                    'linear-gradient(135deg, #ee0979 0%, #ff6a00 30%, #ffd700 60%, #ff4500 100%)',
                    'linear-gradient(135deg, #f12711 0%, #f5af19 50%, #ee0979 100%)',
                    'linear-gradient(135deg, #ff6b6b 0%, #ee0979 50%, #ffd700 100%)'
                ],
                'craque': [
                    'linear-gradient(135deg, #1e3c72 0%, #2a5298 30%, #7e8ba3 60%, #667eea 100%)',
                    'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
                    'linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #4facfe 100%)'
                ]
            }};
            
            const opcoesGradientes = gradientes[statTipo] || ['linear-gradient(135deg, #667eea 0%, #764ba2 100%)'];
            const backgroundBase = opcoesGradientes[valor % opcoesGradientes.length];
            
            // Adiciona padrões dinâmicos e elementos decorativos
            const backgroundStyle = backgroundBase + ', ' +
                'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.15) 0%, transparent 40%), ' +
                'radial-gradient(circle at 80% 70%, rgba(255,255,255,0.1) 0%, transparent 50%), ' +
                'radial-gradient(ellipse at 50% 50%, rgba(255,255,255,0.05) 0%, transparent 70%)';
            
            backgroundsCache[cacheKey] = backgroundStyle;
            return backgroundStyle;
        }}
        
        // Configuração da API OpenAI (carregada via variáveis de ambiente)
        // As variáveis são injetadas pelo servidor em window.OPENAI_API_KEY e window.OPENAI_MODEL
        
        // Função para chamar API do OpenAI
        async function chamarOpenAI(prompt, tipo = 'text', opcoes = {{}}) {{
            // Usa a API key das variáveis de ambiente injetadas pelo servidor
            const apiKey = window.OPENAI_API_KEY;
            const model = opcoes.model || window.OPENAI_MODEL || 'gpt-3.5-turbo';
            
            if (!apiKey || apiKey === 'null' || apiKey === '') {{
                console.log('API key não configurada. Usando textos padrão.');
                return null;
            }}
            
            try {{
                if (tipo === 'image') {{
                    // Chamada para DALL-E
                    const response = await fetch('https://api.openai.com/v1/images/generations', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + apiKey
                        }},
                        body: JSON.stringify({{
                            model: 'dall-e-3',
                            prompt: prompt,
                            n: 1,
                            size: '1024x1024'
                        }})
                    }});
                    
                    if (!response.ok) {{
                        const errorData = await response.json();
                        console.error('Erro na API DALL-E:', errorData);
                        return null;
                    }}
                    
                    const data = await response.json();
                    return data.data[0].url;
                }} else {{
                    // Chamada para ChatGPT
                    const response = await fetch('https://api.openai.com/v1/chat/completions', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + apiKey
                        }},
                        body: JSON.stringify({{
                            model: model,
                            messages: [{{
                                role: 'system',
                                content: 'Você é um assistente criativo especializado em criar mensagens motivacionais e celebratórias no estilo do Spotify Wrapped, focadas em estatísticas de futebol e peladas. Seja entusiasmado, positivo e use linguagem natural e descontraída em português brasileiro.'
                            }}, {{
                                role: 'user',
                                content: prompt
                            }}],
                            max_tokens: opcoes.max_tokens || 200,
                            temperature: opcoes.temperature || 0.9 // Mais criatividade
                        }})
                    }});
                    
                    if (!response.ok) {{
                        const errorData = await response.json();
                        console.error('Erro na API ChatGPT:', errorData);
                        return null;
                    }}
                    
                    const data = await response.json();
                    const texto = data.choices[0].message.content.trim();
                    return texto;
                }}
            }} catch (error) {{
                console.error('Erro ao chamar OpenAI:', error);
                return null;
            }}
        }}
        
        // Função para gerar texto motivacional usando OpenAI (com fallback)
        async function gerarTextoMotivacional(statTipo, valor, nomeJogador, contextoAdicional = {{}}) {{
            const cacheKey = statTipo + '_' + valor + '_' + nomeJogador;
            if (textosCache[cacheKey]) {{
                return textosCache[cacheKey];
            }}
            
            // Mapeia tipos de estatísticas para descrições mais ricas
            const statInfo = {{
                'gols': {{
                    desc: 'gols marcados',
                    contexto: 'cada gol foi uma celebração, uma conquista, um momento de glória',
                    estilo: 'energético e celebratório'
                }},
                'assistencias': {{
                    desc: 'assistências',
                    contexto: 'você sempre pensou no coletivo, criando oportunidades para seus companheiros',
                    estilo: 'generoso e tático'
                }},
                'vitorias': {{
                    desc: 'vitórias conquistadas',
                    contexto: 'cada vitória foi fruto de dedicação, garra e trabalho em equipe',
                    estilo: 'vitorioso e motivador'
                }},
                'partidas': {{
                    desc: 'partidas disputadas',
                    contexto: 'cada partida foi uma oportunidade de mostrar seu amor pelo jogo',
                    estilo: 'dedicado e apaixonado'
                }},
                'artilheiro': {{
                    desc: 'vezes como artilheiro',
                    contexto: 'você foi o goleador, o destaque, aquele que fez a diferença',
                    estilo: 'excepcional e destacado'
                }},
                'craque': {{
                    desc: 'vezes como craque da partida',
                    contexto: 'seu desempenho foi excepcional, sempre elevando o nível do jogo',
                    estilo: 'excepcional e inspirador'
                }}
            }};
            
            const info = statInfo[statTipo] || {{ desc: 'conquista', contexto: '', estilo: 'motivador' }};
            
            // Cria prompt mais rico e variado
            const promptsVariados = [
                `Crie uma mensagem motivacional no estilo Spotify Wrapped para ${{nomeJogador}}, que marcou ${{valor}} ${{info.desc}} na pelada. ${{info.contexto}}. A mensagem deve ser ${{info.estilo}}, celebratória, em português brasileiro e ter no máximo 2 frases curtas. Use emojis se fizer sentido, mas seja sutil.`,
                `Escreva uma frase de celebração estilo Spotify Wrapped para ${{nomeJogador}}: ${{valor}} ${{info.desc}}! ${{info.contexto}}. Seja entusiasmado, natural e use português brasileiro. Máximo 2 frases.`,
                `Crie uma mensagem de retrospectiva no estilo Spotify Wrapped: ${{nomeJogador}} conquistou ${{valor}} ${{info.desc}}. ${{info.contexto}}. A mensagem deve ser ${{info.estilo}} e celebratória, em português brasileiro, máximo 2 frases curtas.`
            ];
            
            // Seleciona um prompt aleatório para mais variedade
            const promptEscolhido = promptsVariados[Math.floor(Math.random() * promptsVariados.length)];
            
            // Adiciona contexto adicional se fornecido
            let promptFinal = promptEscolhido;
            if (contextoAdicional.partidas) {{
                promptFinal += ' Contexto: o jogador disputou ' + contextoAdicional.partidas + ' partidas no total.';
            }}
            if (contextoAdicional.mediaGols) {{
                promptFinal += ' Média de gols por partida: ' + contextoAdicional.mediaGols + '.';
            }}
            
            const textoIA = await chamarOpenAI(promptFinal, 'text', {{
                temperature: 0.9, // Alta criatividade
                max_tokens: 200
            }});
            
            if (textoIA) {{
                // Limpa o texto (remove aspas extras, quebras de linha desnecessárias)
                const textoLimpo = textoIA.replace(/^["']|["']$/g, '').trim();
                textosCache[cacheKey] = textoLimpo;
                return textoLimpo;
            }}
            
            // Fallback: Textos base personalizados
            const textosBase = {{
                'gols': [
                    nomeJogador + ', você foi o goleador do ano! ' + valor + ' gols marcados mostram sua capacidade de finalização e determinação em campo.',
                    valor + ' gols! Cada um deles foi uma conquista, cada celebração uma memória inesquecível.',
                    'Artilheiro nato! ' + valor + ' gols que fizeram a diferença e marcaram sua trajetória na pelada.',
                    'Goleador de respeito! ' + valor + ' gols que mostram sua classe e qualidade em campo.'
                ],
                'assistencias': [
                    'Você foi o assistente do ano! ' + valor + ' assistências mostram sua visão de jogo e generosidade em campo.',
                    valor + ' assistências! Você sempre pensa no coletivo, criando oportunidades e fazendo seus companheiros brilharem.',
                    'Mestre das assistências! ' + valor + ' passes decisivos que transformaram jogos.',
                    'Criador de jogadas! ' + valor + ' assistências que mostram sua inteligência tática.'
                ],
                'vitorias': [
                    valor + ' vitórias conquistadas! Você é um verdadeiro vencedor, sempre dando o melhor em campo.',
                    'Campeão! ' + valor + ' vitórias que mostram sua determinação e espírito competitivo.',
                    'Vencedor nato! ' + valor + ' triunfos que marcaram sua jornada na pelada.',
                    'Líder vencedor! ' + valor + ' vitórias que comprovam sua qualidade.'
                ],
                'partidas': [
                    valor + ' partidas disputadas! Uma jornada de dedicação, paixão e comprometimento com o jogo.',
                    'Presença constante! ' + valor + ' partidas que mostram seu amor pelo futebol e pela pelada.',
                    'Dedicação exemplar! ' + valor + ' partidas de muito suor, garra e momentos inesquecíveis.',
                    'Comprometimento total! ' + valor + ' partidas que mostram sua paixão pelo jogo.'
                ],
                'artilheiro': [
                    'Você foi artilheiro ' + valor + ' vezes! O goleador da equipe em múltiplas ocasiões, sempre decisivo.',
                    valor + ' vezes como artilheiro! Sua capacidade de marcar gols importantes não passa despercebida.',
                    'Goleador de respeito! ' + valor + ' vezes como artilheiro, sempre fazendo a diferença.',
                    'Artilheiro de elite! ' + valor + ' vezes como goleador, sempre decisivo quando mais importa.'
                ],
                'craque': [
                    valor + ' vezes eleito craque da partida! Seu desempenho excepcional sempre se destaca.',
                    'Craque da pelada! ' + valor + ' vezes reconhecido como o melhor em campo.',
                    'Destaque constante! ' + valor + ' vezes como craque, sempre elevando o nível do jogo.',
                    'Estrela da pelada! ' + valor + ' vezes como craque, sempre brilhando em campo.'
                ]
            }};
            
            const textos = textosBase[statTipo] || [valor + ' - Uma conquista marcante!'];
            const textoEscolhido = textos[Math.floor(Math.random() * textos.length)];
            
            textosCache[cacheKey] = textoEscolhido;
            return textoEscolhido;
        }}
        
        // Função para buscar dados do jogador
        function obterDadosJogador(nome) {{
            // Normaliza o nome para busca (remove espaços extras e converte para minúsculas)
            const nomeNormalizado = nome.trim().toLowerCase();
            const nomeSemEspacos = nomeNormalizado.replace(/\\s+/g, '');
            let nomeEncontrado = null;
            let imagemEncontrada = '';
            
            // Busca o nome exato primeiro
            if (imagensJogadores[nome]) {{
                nomeEncontrado = nome;
                imagemEncontrada = imagensJogadores[nome];
            }} else {{
                // Busca com normalização (ignora espaços extras e case)
                for (const [nomeJogador, imagem] of Object.entries(imagensJogadores)) {{
                    const nomeJogadorNormalizado = nomeJogador.trim().toLowerCase();
                    const nomeJogadorSemEspacos = nomeJogadorNormalizado.replace(/\\s+/g, '');
                    
                    if (nomeJogadorNormalizado === nomeNormalizado || nomeJogadorSemEspacos === nomeSemEspacos) {{
                        nomeEncontrado = nomeJogador;
                        imagemEncontrada = imagem;
                        break;
                    }}
                }}
                
                // Se ainda não encontrou, tenta match parcial (primeira palavra)
                if (!imagemEncontrada) {{
                    const primeiraPalavra = nome.split(' ')[0];
                    if (primeiraPalavra) {{
                        for (const [nomeJogador, imagem] of Object.entries(imagensJogadores)) {{
                            if (nomeJogador.toLowerCase().includes(primeiraPalavra.toLowerCase()) || 
                                nomeJogador.toLowerCase().startsWith(primeiraPalavra.toLowerCase())) {{
                                nomeEncontrado = nomeJogador;
                                imagemEncontrada = imagem;
                                break;
                            }}
                        }}
                    }}
                }}
            }}
            
            const dados = {{
                nome: nomeEncontrado || nome,
                imagem: imagemEncontrada,
                stats: {{}}
            }};
            
            const nomeParaBusca = nomeEncontrado || nome;
            
            for (const [categoria, rankings] of Object.entries(categoriasData)) {{
                for (const ranking of rankings) {{
                    const [nomeRanking, quantidade] = ranking;
                    // Compara com normalização
                    if (nomeRanking.trim().toLowerCase() === nomeNormalizado || nomeRanking === nomeParaBusca) {{
                        dados.stats[categoria] = quantidade;
                        break;
                    }}
                }}
            }}
            
            return dados;
        }}
        
        // Função para comparar com jogador de futebol
        function compararComJogadorFutebol(stats) {{
            const jogadoresFutebol = {{
                'Cristiano Ronaldo': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/8198-1671435885.jpg',
                    posicao: 'Atacante',
                    perfil: {{ totalGoals: 850, totalAssistence: 250, totalWins: 600, artilheiro: 50, craque: 30 }},
                    descricao: 'Maior artilheiro da história, líder nato e vencedor'
                }},
                'Lionel Messi': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/28003-1671435885.jpg',
                    posicao: 'Atacante',
                    perfil: {{ totalGoals: 800, totalAssistence: 350, totalWins: 550, artilheiro: 45, craque: 40, garcom: 20 }},
                    descricao: 'Mestre das assistências e gols, criatividade única'
                }},
                'Kevin De Bruyne': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/88755-1671435885.jpg',
                    posicao: 'Meia',
                    perfil: {{ totalGoals: 150, totalAssistence: 300, totalWins: 450, garcom: 50, craque: 45 }},
                    descricao: 'Maestro do meio-campo, rei das assistências'
                }},
                'Manuel Neuer': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/26399-1671435885.jpg',
                    posicao: 'Goleiro',
                    perfil: {{ totalWins: 500, muralha: 200, xerifao: 30 }},
                    descricao: 'Goleiro moderno, líder da defesa'
                }},
                'Virgil van Dijk': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/5925-1671435885.jpg',
                    posicao: 'Zagueiro',
                    perfil: {{ totalWins: 400, muralha: 150, xerifao: 40 }},
                    descricao: 'Muralha defensiva, líder da zaga'
                }},
                'Luka Modrić': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/30972-1671435885.jpg',
                    posicao: 'Meia',
                    perfil: {{ totalGoals: 100, totalAssistence: 200, totalWins: 500, craque: 50, garcom: 30 }},
                    descricao: 'Meia completo, controle de jogo e visão'
                }},
                'Kylian Mbappé': {{
                    imagem: 'https://img.a.transfermarkt.technology/portrait/header/342229-1671435885.jpg',
                    posicao: 'Atacante',
                    perfil: {{ totalGoals: 300, totalAssistence: 150, totalWins: 350, artilheiro: 30, craque: 25 }},
                    descricao: 'Velocidade, gols e impacto decisivo'
                }}
            }};
            
            let melhorMatch = null;
            let melhorScore = 0;
            
            for (const [nomeJogador, perfil] of Object.entries(jogadoresFutebol)) {{
                let score = 0;
                let matches = 0;
                
                for (const [stat, valorJogador] of Object.entries(stats)) {{
                    if (perfil.perfil[stat]) {{
                        const valorReferencia = perfil.perfil[stat];
                        if (valorReferencia > 0) {{
                            const similaridade = valorJogador > 0 
                                ? Math.min(valorJogador / valorReferencia, valorReferencia / valorJogador)
                                : 0;
                            score += similaridade;
                            matches++;
                        }}
                    }}
                }}
                
                if (matches > 0) {{
                    const scoreMedio = score / matches;
                    if (scoreMedio > melhorScore) {{
                        melhorScore = scoreMedio;
                        melhorMatch = {{
                            nome: nomeJogador,
                            ...perfil,
                            similaridade: scoreMedio
                        }};
                    }}
                }}
            }}
            
            if (!melhorMatch || melhorScore < 0.3) {{
                if ((stats.totalGoals || 0) > (stats.totalAssistence || 0) * 2) {{
                    melhorMatch = {{ ...jogadoresFutebol['Cristiano Ronaldo'], nome: 'Cristiano Ronaldo', similaridade: 0.5 }};
                }} else if ((stats.totalAssistence || 0) > (stats.totalGoals || 0) * 1.5) {{
                    melhorMatch = {{ ...jogadoresFutebol['Kevin De Bruyne'], nome: 'Kevin De Bruyne', similaridade: 0.5 }};
                }} else {{
                    melhorMatch = {{ ...jogadoresFutebol['Luka Modrić'], nome: 'Luka Modrić', similaridade: 0.5 }};
                }}
            }}
            
            // Garante que sempre tenha similaridade
            if (!melhorMatch.similaridade || isNaN(melhorMatch.similaridade)) {{
                melhorMatch.similaridade = melhorScore || 0.5;
            }}
            
            return melhorMatch;
        }}
        
        // Função de texto SEM variação de tamanho entre palavras
        // Mantém apenas o texto original para tipografia consistente
        function formatarTextoVariado(texto, tipo = 'mensagem') {{
            return (texto || '').trim();
        }}
        
        // Função para gerar slides motivacionais (assíncrona para usar backgrounds dinâmicos)
        async function gerarSlidesMotivacionais(dadosJogador) {{
            const stats = dadosJogador.stats || {{}};
            const nome = dadosJogador.nome;
            const slides = [];
            
            // Obtém o ano atual
            const anoAtual = new Date().getFullYear();
            
            // Calcula estatísticas principais
            const gols = stats.totalGoals || 0;
            const assistencias = stats.totalAssistence || 0;
            const vitorias = stats.totalWins || 0;
            const partidas = stats.totalGamePlayed || 0;
            const artilheiro = stats.artilheiro || 0;
            const craque = stats.craque || 0;
            
            // Calcula médias e contexto adicional
            const mediaGols = partidas > 0 ? (gols / partidas).toFixed(2) : 0;
            const taxaVitoria = partidas > 0 ? ((vitorias / partidas) * 100).toFixed(0) : 0;
            
            // Contexto adicional para enriquecer os prompts
            const contextoAdicional = {{
                partidas: partidas,
                mediaGols: mediaGols,
                taxaVitoria: taxaVitoria,
                gols: gols,
                assistencias: assistencias,
                vitorias: vitorias
            }};
            
            // Determina o maior destaque
            const maiorDestaque = Math.max(gols, assistencias, vitorias, artilheiro, craque);
            
            // Slide 1: Introdução do ano
            const bgIntro = await gerarBackground('partidas', partidas);
            const textoIntro = await gerarTextoMotivacional('partidas', partidas, nome, contextoAdicional);
            slides.push(
                '<div class="motivacional-slide" style="background: ' + bgIntro + ';">' +
                    '<div class="motivacional-decorativo"></div>' +
                    '<div class="motivacional-pattern"></div>' +
                    '<div class="motivacional-content">' +
                        '<div class="motivacional-ano">Ano ' + anoAtual + '</div>' +
                        '<div class="motivacional-titulo">' + formatarTextoVariado('Uma jornada de altos e baixos', 'titulo') + '</div>' +
                        '<div class="motivacional-mensagem">' +
                            formatarTextoVariado(nome + ', este foi um ano de dedicação, superação e muito futebol na pelada.', 'mensagem') +
                        '</div>' +
                    '</div>' +
                '</div>'
            );
            
            // Slide 2: Partidas disputadas
            if (partidas > 0) {{
                const bgPartidas = await gerarBackground('partidas', partidas);
                const textoPartidas = await gerarTextoMotivacional('partidas', partidas, nome, contextoAdicional);
                slides.push(
                    '<div class="motivacional-slide" style="background: ' + bgPartidas + ';">' +
                        '<div class="motivacional-decorativo"></div>' +
                        '<div class="motivacional-pattern"></div>' +
                        '<div class="motivacional-content">' +
                            '<div class="motivacional-titulo">' + formatarTextoVariado(partidas + ' partidas disputadas', 'titulo') + '</div>' +
                            '<div class="motivacional-mensagem">' + formatarTextoVariado(textoPartidas, 'mensagem') + '</div>' +
                        '</div>' +
                    '</div>'
                );
            }}
            
            // Slide 3: Gols
            if (gols > 0) {{
                const bgGols = await gerarBackground('gols', gols);
                const textoGols = await gerarTextoMotivacional('gols', gols, nome, contextoAdicional);
                slides.push(
                    '<div class="motivacional-slide" style="background: ' + bgGols + ';">' +
                        '<div class="motivacional-decorativo"></div>' +
                        '<div class="motivacional-pattern"></div>' +
                        '<div class="motivacional-content">' +
                            '<div class="motivacional-titulo">' + formatarTextoVariado(gols + ' gols marcados', 'titulo') + '</div>' +
                            '<div class="motivacional-mensagem">' + formatarTextoVariado(textoGols, 'mensagem') + '</div>' +
                        '</div>' +
                    '</div>'
                );
            }}
            
            // Slide 4: Assistências
            if (assistencias > 0) {{
                const bgAssist = await gerarBackground('assistencias', assistencias);
                const textoAssist = await gerarTextoMotivacional('assistencias', assistencias, nome, contextoAdicional);
                slides.push(
                    '<div class="motivacional-slide" style="background: ' + bgAssist + ';">' +
                        '<div class="motivacional-decorativo"></div>' +
                        '<div class="motivacional-pattern"></div>' +
                        '<div class="motivacional-content">' +
                            '<div class="motivacional-titulo">' + formatarTextoVariado(assistencias + ' assistências', 'titulo') + '</div>' +
                            '<div class="motivacional-mensagem">' + formatarTextoVariado(textoAssist, 'mensagem') + '</div>' +
                        '</div>' +
                    '</div>'
                );
            }}
            
            // Slide 5: Vitórias
            if (vitorias > 0) {{
                const bgVitorias = await gerarBackground('vitorias', vitorias);
                const textoVitorias = await gerarTextoMotivacional('vitorias', vitorias, nome, contextoAdicional);
                slides.push(
                    '<div class="motivacional-slide" style="background: ' + bgVitorias + ';">' +
                        '<div class="motivacional-decorativo"></div>' +
                        '<div class="motivacional-pattern"></div>' +
                        '<div class="motivacional-content">' +
                            '<div class="motivacional-titulo">' + formatarTextoVariado(vitorias + ' vitórias conquistadas', 'titulo') + '</div>' +
                            '<div class="motivacional-mensagem">' + formatarTextoVariado(textoVitorias, 'mensagem') + '</div>' +
                            '<div class="motivacional-extra">Taxa de ' + taxaVitoria + '% de aproveitamento</div>' +
                        '</div>' +
                    '</div>'
                );
            }}
            
            // Slide 6: Artilheiro (se tiver)
            if (artilheiro > 0) {{
                const bgArtilheiro = await gerarBackground('artilheiro', artilheiro);
                const textoArtilheiro = await gerarTextoMotivacional('artilheiro', artilheiro, nome, contextoAdicional);
                slides.push(
                    '<div class="motivacional-slide" style="background: ' + bgArtilheiro + ';">' +
                        '<div class="motivacional-decorativo"></div>' +
                        '<div class="motivacional-pattern"></div>' +
                        '<div class="motivacional-content">' +
                            '<div class="motivacional-titulo">' + formatarTextoVariado(artilheiro + ' vezes artilheiro', 'titulo') + '</div>' +
                            '<div class="motivacional-mensagem">' + formatarTextoVariado(textoArtilheiro, 'mensagem') + '</div>' +
                        '</div>' +
                    '</div>'
                );
            }}
            
            // Slide 7: Craque (se tiver)
            if (craque > 0) {{
                const bgCraque = await gerarBackground('craque', craque);
                const textoCraque = await gerarTextoMotivacional('craque', craque, nome, contextoAdicional);
                slides.push(
                    '<div class="motivacional-slide" style="background: ' + bgCraque + ';">' +
                        '<div class="motivacional-decorativo"></div>' +
                        '<div class="motivacional-pattern"></div>' +
                        '<div class="motivacional-content">' +
                            '<div class="motivacional-titulo">' + formatarTextoVariado(craque + ' vezes craque da partida', 'titulo') + '</div>' +
                            '<div class="motivacional-mensagem">' + formatarTextoVariado(textoCraque, 'mensagem') + '</div>' +
                        '</div>' +
                    '</div>'
                );
            }}
            
            return slides.join('');
        }}
        
        // Função para gerar perfil completo
        function gerarPerfilCompleto(dadosJogador, comparacao) {{
            const nome = dadosJogador.nome;
            const imagem = dadosJogador.imagem || '';
            const stats = dadosJogador.stats || {{}};
            
            const gols = stats.totalGoals || 0;
            const assistencias = stats.totalAssistence || 0;
            const vitorias = stats.totalWins || 0;
            const partidas = stats.totalGamePlayed || 0;
            const artilheiro = stats.artilheiro || 0;
            const craque = stats.craque || 0;
            const garcom = stats.garcom || 0;
            const muralha = stats.muralha || 0;
            const xerifao = stats.xerifao || 0;
            const pereba = stats.pereba || 0;
            const bolaMurcha = stats.bolaMurcha || 0;
            
            const mediaGols = partidas > 0 ? (gols / partidas).toFixed(2) : 0;
            const taxaVitoria = partidas > 0 ? ((vitorias / partidas) * 100).toFixed(1) : 0;
            
            const inicial = nome && nome[0] ? nome[0].toUpperCase() : '?';
            const imagemHTML = imagem && imagem.trim() !== ''
                ? '<img src="' + imagem + '" alt="' + nome + '" class="perfil-imagem-grande" onerror="this.onerror=null; this.style.background=\\'linear-gradient(135deg, #2563eb, #1e40af)\\'; this.style.display=\\'flex\\'; this.style.alignItems=\\'center\\'; this.style.justifyContent=\\'center\\'; this.style.color=\\'white\\'; this.style.fontSize=\\'2.2em\\'; this.style.fontWeight=\\'bold\\'; this.style.borderRadius=\\'20px\\'; this.innerHTML=\\'' + inicial + '\\'">'
                : '<div class="perfil-imagem-grande" style="display: flex; align-items: center; justify-content: center; color: white; font-size: 2.2em; font-weight: bold;">' + inicial + '</div>';
            
            const similaridade = comparacao.similaridade || 0.5;
            
            let statsExtras = '';
            if (garcom > 0) statsExtras += '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + garcom + '</div><div class="perfil-stat-label">Garçom</div></div>';
            if (muralha > 0) statsExtras += '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + muralha + '</div><div class="perfil-stat-label">Muralha</div></div>';
            if (xerifao > 0) statsExtras += '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + xerifao + '</div><div class="perfil-stat-label">Xerifão</div></div>';
            
            return '<div class="perfil-completo-slide">' +
                '<div class="perfil-completo-content">' +
                    '<div class="perfil-header">' +
                        imagemHTML +
                        '<div class="perfil-nome-grande">' + nome + '</div>' +
                        '<div class="perfil-comparacao-card">' +
                            '<div class="perfil-comparacao-titulo">Seu Estilo de Jogo</div>' +
                            '<div class="perfil-comparacao-nome">' + (comparacao.nome || 'Comparação') + '</div>' +
                            '<div class="perfil-comparacao-desc">' + (comparacao.descricao || 'Jogador completo') + '</div>' +
                            '<div class="perfil-similaridade">' +
                                '<div class="perfil-similaridade-valor">' + Math.round(similaridade * 100) + '%</div>' +
                                '<div class="perfil-similaridade-label">Similaridade</div>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="perfil-stats-grid">' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + partidas + '</div><div class="perfil-stat-label">Partidas</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + gols + '</div><div class="perfil-stat-label">Gols</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + assistencias + '</div><div class="perfil-stat-label">Assistências</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + vitorias + '</div><div class="perfil-stat-label">Vitórias</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + mediaGols + '</div><div class="perfil-stat-label">Média de Gols</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + taxaVitoria + '%</div><div class="perfil-stat-label">Taxa Vitória</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + artilheiro + '</div><div class="perfil-stat-label">Artilheiro</div></div>' +
                        '<div class="perfil-stat-card"><div class="perfil-stat-numero">' + craque + '</div><div class="perfil-stat-label">Craque</div></div>' +
                        statsExtras +
                    '</div>' +
                '</div>' +
            '</div>';
        }}
        
        // Função para gerar slides de storytelling
        function gerarSlidesStorytelling(dadosJogador, comparacao) {{
            const stats = dadosJogador.stats || {{}};
            const nome = dadosJogador.nome;
            const slides = [];
            
            const estatisticas = [
                {{
                    chave: 'totalGamePlayed',
                    numero: stats.totalGamePlayed || 0,
                    titulo: 'Partidas disputadas',
                    descricao: `Você disputou ${{stats.totalGamePlayed || 0}} partidas na pelada, demonstrando dedicação e paixão pelo jogo.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'totalGoals',
                    numero: stats.totalGoals || 0,
                    titulo: 'Gols marcados',
                    descricao: `${{stats.totalGoals || 0}} gols marcados! Uma média impressionante de ${{stats.totalGamePlayed > 0 ? (stats.totalGoals / stats.totalGamePlayed).toFixed(2) : 0}} gols por partida.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'totalAssistence',
                    numero: stats.totalAssistence || 0,
                    titulo: 'Assistências',
                    descricao: `${{stats.totalAssistence || 0}} assistências! Você sempre pensa no coletivo e cria oportunidades para seus companheiros.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'totalWins',
                    numero: stats.totalWins || 0,
                    titulo: 'Vitórias',
                    descricao: `${{stats.totalWins || 0}} vitórias conquistadas! Taxa de vitória de ${{stats.totalGamePlayed > 0 ? ((stats.totalWins / stats.totalGamePlayed) * 100).toFixed(1) : 0}}%.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'artilheiro',
                    numero: stats.artilheiro || 0,
                    titulo: 'Vezes artilheiro',
                    descricao: `Você foi artilheiro ${{stats.artilheiro || 0}} vezes, sendo o goleador da equipe em múltiplas ocasiões.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'craque',
                    numero: stats.craque || 0,
                    titulo: 'Craque da partida',
                    descricao: `${{stats.craque || 0}} vezes eleito craque da partida! Seu desempenho excepcional não passa despercebido.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'garcom',
                    numero: stats.garcom || 0,
                    titulo: 'Garçom',
                    descricao: `${{stats.garcom || 0}} vezes como garçom, sempre servindo gols para seus companheiros.`,
                    comparacao: comparacao.nome
                }},
                {{
                    chave: 'muralha',
                    numero: stats.muralha || 0,
                    titulo: 'Muralha',
                    descricao: `${{stats.muralha || 0}} vezes como muralha, uma defesa sólida e impenetrável.`,
                    comparacao: comparacao.nome
                }}
            ];
            
            estatisticas.forEach((stat, index) => {{
                if (stat.numero > 0) {{
                    slides.push(`
                        <div class="storytelling-slide">
                            <div class="storytelling-content">
                                <div class="storytelling-numero">${{stat.numero}}</div>
                                <div class="storytelling-titulo">${{stat.titulo}}</div>
                                <div class="storytelling-descricao">${{stat.descricao}}</div>
                                <div class="storytelling-comparacao">
                                    <div class="storytelling-comparacao-texto">
                                        Seu estilo se assemelha a <strong>${{comparacao.nome}}</strong> - ${{comparacao.descricao}}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `);
                }}
            }});
            
            return slides.join('');
        }}
        
        // Função para alterar jogador
        function alterarJogador() {{
            // Volta para tela inicial
            telaInicial.style.display = 'flex';
            retrospectivaContainer.style.display = 'none';
            slidesContainer.style.display = 'none';
            navegacao.style.display = 'none';
            indicadorSlide.style.display = 'none';
            document.getElementById('btn-alterar-jogador').style.display = 'none';
            
            // Limpa input
            inputNome.value = '';
            inputNome.focus();
            
            // Reseta o botão "Iniciar Minha Jornada" (corrige bug de loading infinito)
            const btnIniciar = document.querySelector('.btn-iniciar');
            if (btnIniciar) {{
                btnIniciar.textContent = 'Iniciar Minha Jornada';
                btnIniciar.disabled = false;
            }}
            
            // Remove todos os slides personalizados
            const motivacionaisSlides = document.querySelectorAll('.motivacional-slide');
            const perfilSlides = document.querySelectorAll('.perfil-completo-slide');
            const retrospectivaSlide = document.querySelector('.retrospectiva-slide');
            const storytellingSlides = document.querySelectorAll('.storytelling-slide');
            
            motivacionaisSlides.forEach(slide => slide.remove());
            perfilSlides.forEach(slide => slide.remove());
            if (retrospectivaSlide) retrospectivaSlide.remove();
            storytellingSlides.forEach(slide => slide.remove());
            
            // Reseta flags
            temRetrospectiva = false;
            slideAtual = 0;
            totalSlides = totalSlidesRanking;
        }}
        
        // Função para gerar HTML da retrospectiva
        function gerarRetrospectivaHTML(dadosJogador, comparacao) {{
            const nome = dadosJogador.nome;
            const imagem = dadosJogador.imagem || '';
            const stats = dadosJogador.stats || {{}};
            
            const gols = stats.totalGoals || 0;
            const assistencias = stats.totalAssistence || 0;
            const vitorias = stats.totalWins || 0;
            const partidas = stats.totalGamePlayed || 0;
            const artilheiro = stats.artilheiro || 0;
            const craque = stats.craque || 0;
            const garcom = stats.garcom || 0;
            const muralha = stats.muralha || 0;
            
            const mediaGols = partidas > 0 ? (gols / partidas).toFixed(2) : 0;
            const taxaVitoria = partidas > 0 ? ((vitorias / partidas) * 100).toFixed(1) : 0;
            
            const imagemHTML = imagem && imagem.trim() !== ''
                ? `<img src="${{imagem}}" alt="${{nome}}" class="comparacao-imagem" onerror="this.onerror=null; this.style.background='linear-gradient(135deg, #2563eb, #1e40af)'; this.style.display='flex'; this.style.alignItems='center'; this.style.justifyContent='center'; this.style.color='white'; this.style.fontSize='2em'; this.style.fontWeight='bold'; this.style.borderRadius='12px'; this.innerHTML='${{nome[0] ? nome[0].toUpperCase() : '?'}}'">`
                : `<div class="comparacao-imagem" style="background: linear-gradient(135deg, #2563eb, #1e40af); display: flex; align-items: center; justify-content: center; color: white; font-size: 2em; font-weight: bold;">${{nome[0] ? nome[0].toUpperCase() : '?'}}</div>`;
            
            const timelineItems = [];
            if (partidas > 0) timelineItems.push({{ titulo: `${{partidas}} Partidas Disputadas`, descricao: `Uma jornada de ${{partidas}} partidas, demonstrando dedicação e paixão pelo jogo.` }});
            if (gols > 0) timelineItems.push({{ titulo: `${{gols}} Gols Marcados`, descricao: `Média de ${{mediaGols}} gols por partida. Um verdadeiro artilheiro em campo!` }});
            if (assistencias > 0) timelineItems.push({{ titulo: `${{assistencias}} Assistências`, descricao: `Visão de jogo excepcional, sempre pensando no coletivo e criando oportunidades.` }});
            if (vitorias > 0) timelineItems.push({{ titulo: `${{vitorias}} Vitórias`, descricao: `Taxa de vitória de ${{taxaVitoria}}%. Um verdadeiro vencedor!` }});
            if (artilheiro > 0) timelineItems.push({{ titulo: `${{artilheiro}} Vezes Artilheiro`, descricao: 'Destaque constante como goleador da equipe.' }});
            if (craque > 0) timelineItems.push({{ titulo: `${{craque}} Vezes Craque da Partida`, descricao: 'Reconhecimento pelo desempenho excepcional em campo.' }});
            
            let timelineHTML = '';
            if (timelineItems.length > 0) {{
                timelineHTML = `
                    <div class="jornada-timeline">
                        <div class="jornada-titulo">Sua Jornada</div>
                        ${{timelineItems.slice(0, 5).map(item => `
                            <div class="timeline-item">
                                <div class="timeline-content">
                                    <div class="timeline-titulo">${{item.titulo}}</div>
                                    <div class="timeline-descricao">${{item.descricao}}</div>
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                `;
            }}
            
            return `
                <div class="retrospectiva-slide">
                    <div class="retrospectiva-content">
                        <div class="retrospectiva-header">
                            <div class="retrospectiva-titulo">Sua Jornada: ${{nome}}</div>
                            <div class="retrospectiva-subtitulo">Uma retrospectiva da sua trajetória na pelada</div>
                        </div>
                        <div class="comparacao-grid">
                            <div class="comparacao-card">
                                <div class="comparacao-header">
                                    ${{imagemHTML}}
                                    <div>
                                        <div class="comparacao-nome">${{nome}}</div>
                                        <div class="comparacao-posicao">Jogador da Pelada</div>
                                    </div>
                                </div>
                                <div class="comparacao-stats">
                                    <div class="stat-item"><span class="stat-label">Gols</span><span class="stat-valor">${{gols}}</span></div>
                                    <div class="stat-item"><span class="stat-label">Assistências</span><span class="stat-valor">${{assistencias}}</span></div>
                                    <div class="stat-item"><span class="stat-label">Vitórias</span><span class="stat-valor">${{vitorias}}</span></div>
                                    <div class="stat-item"><span class="stat-label">Partidas</span><span class="stat-valor">${{partidas}}</span></div>
                                    <div class="stat-item"><span class="stat-label">Artilheiro</span><span class="stat-valor">${{artilheiro}}x</span></div>
                                    <div class="stat-item"><span class="stat-label">Craque</span><span class="stat-valor">${{craque}}x</span></div>
                                </div>
                            </div>
                            <div class="comparacao-card">
                                <div class="comparacao-header">
                                    <img src="${{comparacao.imagem || ''}}" alt="${{comparacao.nome}}" class="comparacao-imagem" onerror="this.onerror=null; this.style.background='linear-gradient(135deg, #2563eb, #1e40af)'; this.style.display='flex'; this.style.alignItems='center'; this.style.justifyContent='center'; this.style.color='white'; this.style.fontSize='2em'; this.style.fontWeight='bold'; this.style.borderRadius='12px'; this.innerHTML='${{comparacao.nome ? comparacao.nome[0] : '?'}}'">
                                    <div>
                                        <div class="comparacao-nome">${{comparacao.nome || 'Comparação'}}</div>
                                        <div class="comparacao-posicao">${{comparacao.posicao || 'Jogador Profissional'}}</div>
                                    </div>
                                </div>
                                <div class="comparacao-stats">
                                    <div class="stat-item"><span class="stat-label">Estilo de Jogo</span><span class="stat-valor" style="font-size: 0.9em;">${{comparacao.descricao}}</span></div>
                                    <div class="stat-item" style="background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(30, 64, 175, 0.1)); border: 1px solid rgba(37, 99, 235, 0.2);">
                                        <span class="stat-label">Similaridade</span><span class="stat-valor" style="color: #2563eb;">${{Math.round((comparacao.similaridade || 0.5) * 100)}}%</span>
                                    </div>
                                </div>
                                <div style="margin-top: 20px; padding: 16px; background: #f0f9ff; border-radius: 8px; border-left: 4px solid #2563eb;">
                                    <div style="font-size: 0.9em; color: #1e40af; line-height: 1.6;">
                                        Seu estilo de jogo se assemelha a <strong>${{comparacao.nome}}</strong>. ${{comparacao.descricao}}
                                    </div>
                                </div>
                            </div>
                        </div>
                        ${{timelineHTML}}
                    </div>
                </div>
            `;
        }}
        
        // Função para iniciar retrospectiva (assíncrona)
        async function iniciarRetrospectiva() {{
            const nomeJogador = inputNome.value.trim();
            
            // Mostra loading
            const btnIniciar = document.querySelector('.btn-iniciar');
            const textoOriginal = btnIniciar.textContent;
            btnIniciar.textContent = 'Carregando...';
            btnIniciar.disabled = true;
            
            // Se não houver nome, vai direto para o ranking geral
            if (!nomeJogador) {{
                // Esconde tela inicial e mostra slides
                telaInicial.style.display = 'none';
                slidesContainer.style.display = 'flex';
                navegacao.style.display = 'flex';
                indicadorSlide.style.display = 'block';
                document.getElementById('btn-alterar-jogador').style.display = 'block';
                
                // Atualiza flags
                temRetrospectiva = false;
                slideAtual = 0;
                totalSlides = totalSlidesRanking;
                
                // Garante que todos os slides estejam visíveis
                const slides = document.querySelectorAll('.slide');
                slides.forEach(slide => {{
                    slide.style.opacity = '1';
                    slide.classList.add('active');
                }});
                
                // Atualiza indicador
                atualizarIndicador();
                
                // Scroll para primeiro slide
                setTimeout(() => {{
                    slidesContainer.scrollTo({{ left: 0, behavior: 'smooth' }});
                    animarSlide(0);
                }}, 100);
                
                btnIniciar.textContent = textoOriginal;
                btnIniciar.disabled = false;
                return;
            }}
            
            try {{
                // Busca dados do jogador
                const dadosJogador = obterDadosJogador(nomeJogador);
                
                if (Object.keys(dadosJogador.stats).length === 0) {{
                    alert('Jogador não encontrado. Verifique se o nome está correto.');
                    btnIniciar.textContent = textoOriginal;
                    btnIniciar.disabled = false;
                    return;
                }}
                
                // Compara com jogador de futebol
                const comparacao = compararComJogadorFutebol(dadosJogador.stats);
                
                // Garante que similaridade existe e é válida
                if (!comparacao.similaridade || isNaN(comparacao.similaridade)) {{
                    comparacao.similaridade = 0.5;
                }}
                
                // Gera slides motivacionais (assíncrono)
                const motivacionaisHTML = await gerarSlidesMotivacionais(dadosJogador);
                
                // Gera perfil completo
                const perfilHTML = gerarPerfilCompleto(dadosJogador, comparacao);
                
                // Salva os slides de ranking antes de limpar
                const rankingSlides = Array.from(slidesContainer.querySelectorAll('.slide'));
                
                // Esconde tela inicial e mostra slides
                telaInicial.style.display = 'none';
                slidesContainer.style.display = 'flex';
                navegacao.style.display = 'flex';
                indicadorSlide.style.display = 'block';
                document.getElementById('btn-alterar-jogador').style.display = 'block';
                
                // Limpa slides personalizados anteriores (mantém os de ranking)
                const motivacionaisAntigos = slidesContainer.querySelectorAll('.motivacional-slide');
                const perfilAntigos = slidesContainer.querySelectorAll('.perfil-completo-slide');
                const retrospectivaAntiga = slidesContainer.querySelector('.retrospectiva-slide');
                const storytellingAntigos = slidesContainer.querySelectorAll('.storytelling-slide');
                
                motivacionaisAntigos.forEach(slide => slide.remove());
                perfilAntigos.forEach(slide => slide.remove());
                if (retrospectivaAntiga) retrospectivaAntiga.remove();
                storytellingAntigos.forEach(slide => slide.remove());
                
                // Adiciona slides motivacionais primeiro
                const tempDivMotiv = document.createElement('div');
                tempDivMotiv.innerHTML = motivacionaisHTML;
                while (tempDivMotiv.firstChild) {{
                    slidesContainer.insertBefore(tempDivMotiv.firstChild, rankingSlides[0] || null);
                }}
                
                // Adiciona perfil completo após os motivacionais
                const tempDivPerfil = document.createElement('div');
                tempDivPerfil.innerHTML = perfilHTML;
                while (tempDivPerfil.firstChild) {{
                    const motivacionaisAtuais = slidesContainer.querySelectorAll('.motivacional-slide');
                    const ultimoMotivacional = motivacionaisAtuais[motivacionaisAtuais.length - 1];
                    if (ultimoMotivacional) {{
                        slidesContainer.insertBefore(tempDivPerfil.firstChild, ultimoMotivacional.nextSibling);
                    }} else {{
                        slidesContainer.insertBefore(tempDivPerfil.firstChild, rankingSlides[0] || null);
                    }}
                }}
                
                // Conta slides
                const motivacionaisSlides = document.querySelectorAll('.motivacional-slide').length;
                const perfilSlides = document.querySelectorAll('.perfil-completo-slide').length;
                
                // Atualiza flags
                temRetrospectiva = true;
                slideAtual = 0;
                totalSlides = motivacionaisSlides + perfilSlides + totalSlidesRanking;
                
                // Atualiza indicador
                atualizarIndicador();
                
                // Scroll para primeiro slide
                setTimeout(() => {{
                    slidesContainer.scrollTo({{ left: 0, behavior: 'smooth' }});
                    animarSlide(0);
                }}, 100);
            }} catch (error) {{
                console.error('Erro ao gerar retrospectiva:', error);
                alert('Erro ao gerar a retrospectiva. Tente novamente.');
                btnIniciar.textContent = textoOriginal;
                btnIniciar.disabled = false;
            }}
        }}
        
        // Enter no input
        inputNome.addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') {{
                iniciarRetrospectiva();
            }}
        }});
        
        // Foco automático no input
        setTimeout(() => {{
            inputNome.focus();
        }}, 500);
        
        const indicador = document.getElementById('slide-indicador');
        const navBtns = document.querySelectorAll('.nav-btn');
        let totalSlides = totalSlidesRanking;
        let slideAtual = 0;
        let isAnimating = false;
        let temRetrospectiva = false;
        
        function atualizarIndicador() {{
            let total = totalSlidesRanking;
            if (temRetrospectiva) {{
                const motivacionaisSlides = document.querySelectorAll('.motivacional-slide').length;
                const perfilSlides = document.querySelectorAll('.perfil-completo-slide').length;
                total = motivacionaisSlides + perfilSlides + totalSlidesRanking;
            }}
            indicador.textContent = `${{slideAtual + 1}} / ${{total}}`;
            // Atualiza estado dos botões
            if (navBtns.length > 0) {{
                navBtns[0].disabled = slideAtual === 0;
                navBtns[1].disabled = slideAtual === total - 1;
            }}
        }}
        
        function animarSlide(slideIndex) {{
            const slides = document.querySelectorAll('.slide');
            slides.forEach((slide, index) => {{
                slide.classList.remove('active');
                if (index === slideIndex) {{
                    slide.classList.add('active');
                    // Anima elementos do slide
                    const rankingItems = slide.querySelectorAll('.ranking-item');
                    const barras = slide.querySelectorAll('.barra');
                    
                    rankingItems.forEach((item, idx) => {{
                        item.style.opacity = '0';
                        item.style.transform = 'translateY(20px)';
                        setTimeout(() => {{
                            item.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
                            item.style.opacity = '1';
                            item.style.transform = 'translateY(0)';
                        }}, idx * 100);
                    }});
                    
                    barras.forEach((barra, idx) => {{
                        const width = barra.style.width;
                        barra.style.width = '0%';
                        setTimeout(() => {{
                            barra.style.transition = 'width 1.2s cubic-bezier(0.4, 0, 0.2, 1)';
                            barra.style.width = width;
                        }}, 300 + idx * 150);
                    }});
                }}
            }});
        }}
        
        function slideProximo() {{
            if (slideAtual < totalSlides - 1 && !isAnimating) {{
                isAnimating = true;
                slideAtual++;
                slidesContainer.scrollTo({{
                    left: slideAtual * window.innerWidth,
                    behavior: 'smooth'
                }});
                atualizarIndicador();
                setTimeout(() => {{
                    animarSlide(slideAtual);
                    isAnimating = false;
                }}, 500);
            }}
        }}
        
        function slideAnterior() {{
            if (slideAtual > 0 && !isAnimating) {{
                isAnimating = true;
                slideAtual--;
                slidesContainer.scrollTo({{
                    left: slideAtual * window.innerWidth,
                    behavior: 'smooth'
                }});
                atualizarIndicador();
                setTimeout(() => {{
                    animarSlide(slideAtual);
                    isAnimating = false;
                }}, 500);
            }}
        }}
        
        // Navegação por teclado
        document.addEventListener('keydown', (e) => {{
            if (isAnimating) return;
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'PageDown') {{
                e.preventDefault();
                slideProximo();
            }} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') {{
                e.preventDefault();
                slideAnterior();
            }} else if (e.key === 'Home') {{
                e.preventDefault();
                slideAtual = 0;
                slidesContainer.scrollTo({{ left: 0, behavior: 'smooth' }});
                atualizarIndicador();
                animarSlide(0);
            }} else if (e.key === 'End') {{
                e.preventDefault();
                slideAtual = totalSlides - 1;
                slidesContainer.scrollTo({{ left: (totalSlides - 1) * window.innerWidth, behavior: 'smooth' }});
                atualizarIndicador();
                animarSlide(totalSlides - 1);
            }}
        }});
        
        // Atualiza indicador ao fazer scroll
        let scrollTimeout;
        slidesContainer.addEventListener('scroll', () => {{
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {{
                const newSlide = Math.round(slidesContainer.scrollLeft / window.innerWidth);
                if (newSlide !== slideAtual) {{
                    slideAtual = newSlide;
                    atualizarIndicador();
                    animarSlide(slideAtual);
                }}
            }}, 100);
        }});
        
        // Inicializa
        // Garante que todos os slides estejam visíveis inicialmente
        const slidesIniciais = document.querySelectorAll('.slide');
        if (slidesIniciais.length > 0) {{
            slidesIniciais.forEach(slide => {{
                slide.style.opacity = '1';
            }});
            slidesIniciais[0].classList.add('active');
        }}
        atualizarIndicador();
        animarSlide(0);
        
        // Anima elementos quando entram em viewport
        const observer = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    entry.target.classList.add('active');
                }}
            }});
        }}, {{ threshold: 0.3 }});
        
        document.querySelectorAll('.slide').forEach(slide => {{
            observer.observe(slide);
        }});
        
        // Suporte a swipe horizontal para navegação (touch e mouse)
        let touchStartX = 0;
        let touchStartY = 0;
        let touchEndX = 0;
        let touchEndY = 0;
        let isSwiping = false;
        let isMouseDown = false;
        const minSwipeDistance = 50; // Distância mínima em pixels para considerar um swipe
        
        slidesContainer.addEventListener('touchstart', (e) => {{
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            isSwiping = false;
        }}, {{ passive: true }});
        
        slidesContainer.addEventListener('touchmove', (e) => {{
            const currentX = e.touches[0].clientX;
            const currentY = e.touches[0].clientY;
            const deltaX = Math.abs(currentX - touchStartX);
            const deltaY = Math.abs(currentY - touchStartY);
            
            // Se o movimento horizontal for maior que o vertical, é um swipe horizontal
            if (deltaX > deltaY && deltaX > 10) {{
                isSwiping = true;
                // Previne scroll vertical durante swipe horizontal
                e.preventDefault();
            }}
        }}, {{ passive: false }});
        
        slidesContainer.addEventListener('touchend', (e) => {{
            if (!isSwiping) {{
                // Reset mesmo se não foi swipe
                touchStartX = 0;
                touchStartY = 0;
                return;
            }}
            
            touchEndX = e.changedTouches[0].clientX;
            touchEndY = e.changedTouches[0].clientY;
            
            const deltaX = touchEndX - touchStartX;
            const deltaY = Math.abs(touchEndY - touchStartY);
            
            // Verifica se é um swipe horizontal válido
            if (Math.abs(deltaX) > minSwipeDistance && Math.abs(deltaX) > deltaY) {{
                if (deltaX > 0) {{
                    // Swipe para direita = slide anterior
                    slideAnterior();
                }} else {{
                    // Swipe para esquerda = próximo slide
                    slideProximo();
                }}
            }}
            
            // Reset
            touchStartX = 0;
            touchStartY = 0;
            touchEndX = 0;
            touchEndY = 0;
            isSwiping = false;
        }}, {{ passive: true }});
        
        // Suporte a arrastar com mouse (desktop)
        slidesContainer.addEventListener('mousedown', (e) => {{
            isMouseDown = true;
            touchStartX = e.clientX;
            touchStartY = e.clientY;
            slidesContainer.style.cursor = 'grabbing';
        }});
        
        slidesContainer.addEventListener('mousemove', (e) => {{
            if (!isMouseDown) return;
            
            const currentX = e.clientX;
            const currentY = e.clientY;
            const deltaX = Math.abs(currentX - touchStartX);
            const deltaY = Math.abs(currentY - touchStartY);
            
            if (deltaX > deltaY && deltaX > 10) {{
                isSwiping = true;
            }}
        }});
        
        slidesContainer.addEventListener('mouseup', (e) => {{
            if (!isMouseDown) return;
            
            touchEndX = e.clientX;
            touchEndY = e.clientY;
            
            const deltaX = touchEndX - touchStartX;
            const deltaY = Math.abs(touchEndY - touchStartY);
            
            if (isSwiping && Math.abs(deltaX) > minSwipeDistance && Math.abs(deltaX) > deltaY) {{
                if (deltaX > 0) {{
                    slideAnterior();
                }} else {{
                    slideProximo();
                }}
            }}
            
            // Reset
            isMouseDown = false;
            isSwiping = false;
            touchStartX = 0;
            touchStartY = 0;
            touchEndX = 0;
            touchEndY = 0;
            slidesContainer.style.cursor = '';
        }});
        
        slidesContainer.addEventListener('mouseleave', () => {{
            isMouseDown = false;
            isSwiping = false;
            slidesContainer.style.cursor = '';
        }});
    </script>
</body>
</html>
"""
    
    return html


def main():
    """Função principal do script."""
    print("📊 Iniciando geração do ranking de awards...")
    
    # Lê o arquivo JSON
    try:
        with open('players.json', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Erro: Arquivo 'players.json' não encontrado!")
        return
    except Exception as e:
        print(f"❌ Erro ao ler arquivo: {e}")
        return
    
    # Parse do JSON (formato MongoDB)
    print("🔄 Processando dados...")
    players = parse_mongodb_json(content)
    
    if not players:
        print("❌ Nenhum jogador encontrado no arquivo!")
        return
    
    print(f"✅ {len(players)} jogador(es) encontrado(s)")
    
    # Extrai awards e estatísticas por categoria
    print("📈 Extraindo awards e estatísticas...")
    categorias, imagens_jogadores, nomes_todos_jogadores = extrair_awards_jogadores(players)
    
    if not categorias:
        print("❌ Nenhum dado encontrado!")
        return
    
    print(f"✅ {len(categorias)} categoria(s) encontrada(s)")
    print(f"✅ {len(imagens_jogadores)} imagem(ns) de jogador(es) encontrada(s)")
    
    # Gera o HTML
    print("🎨 Gerando visualização HTML...")
    html = gerar_ranking_html(categorias, imagens_jogadores, nomes_todos_jogadores)
    
    # Salva o arquivo HTML
    output_file = 'ranking_awards.html'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ Ranking gerado com sucesso: {output_file}")
        
        # Também copia para index.html para GitHub Pages
        try:
            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✅ index.html atualizado para GitHub Pages")
        except Exception as e:
            print(f"⚠️  Aviso: Não foi possível atualizar index.html: {e}")
        
        print(f"🌐 Abra o arquivo no navegador para visualizar o ranking!")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
        return
    
    # Mostra resumo no console
    print("\n" + "="*60)
    print("📊 RESUMO DO RANKING - TOP 3 POR CATEGORIA")
    print("="*60)
    
    nomes_categorias = {
        'garcom': 'Garçom',
        'artilheiro': 'Artilheiro',
        'craque': 'Craque',
        'muralha': 'Muralha',
        'bolaMurcha': 'Bola Murcha',
        'xerifao': 'Xerifão',
        'pereba': 'Pereba',
        'totalAssistence': 'Assistências',
        'totalGoals': 'Gols',
        'totalGamePlayed': 'Partidas Jogadas',
        'totalWins': 'Vitórias',
        'totalDefeat': 'Derrotas',
        'totalDraw': 'Empates',
        # Categorias de goleiros
        'goleiro_totalGamePlayed': 'Partidas (Goleiros)',
        'goleiro_totalWins': 'Vitórias (Goleiros)',
        'goleiro_totalDefeat': 'Derrotas (Goleiros)',
        'goleiro_totalDraw': 'Empates (Goleiros)'
    }
    
    for categoria, rankings in sorted(categorias.items()):
        nome_amigavel = nomes_categorias.get(categoria, categoria.capitalize())
        print(f"\n🏆 {nome_amigavel}:")
        
        if rankings:
            top3 = rankings[:3]
            for idx, (nome, quantidade) in enumerate(top3, 1):
                medalha = ['🥇', '🥈', '🥉'][idx - 1]
                print(f"   {medalha} {idx}º - {nome}: {quantidade}")
        else:
            print("   (Nenhum dado disponível)")


if __name__ == '__main__':
    main()
