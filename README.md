# ⚽ Ranking Galático

Sistema de ranking e sorteio de times para peladas de futebol.

## 🚀 Acesso Rápido

- **Ranking Principal**: [index.html](index.html)
- **Sorteio de Times**: [sorteio.html](sorteio.html)

## 📋 Funcionalidades

### 1. Ranking de Jogadores
- Visualização de estatísticas dos jogadores
- Comparação com jogadores de futebol profissionais
- Retrospectiva personalizada estilo Spotify Wrapped
- Rankings por categoria (gols, assistências, vitórias, etc.)

### 2. Sorteio de Times
- Sorteio balanceado com distribuição de posições
- 4 times fechados: 2 Zagueiros, 1 Meia, 2 Atacantes
- Restrições automáticas (jogadores que não podem estar juntos)
- Time 5 para jogadores restantes

## 🌐 GitHub Pages

Este projeto está configurado para funcionar no GitHub Pages.

### Como Publicar

1. Faça commit de todos os arquivos
2. Vá em **Settings > Pages** no GitHub
3. Selecione a branch (geralmente `main`)
4. Selecione a pasta `/ (root)`
5. Aguarde o deploy (alguns minutos)

### Arquivos Importantes

- ✅ `index.html` - Página principal
- ✅ `sorteio.html` - Sorteio de times
- ✅ `.nojekyll` - Desabilita Jekyll (necessário)
- ✅ `GITHUB_PAGES_SETUP.md` - Guia completo de configuração

## 📁 Estrutura do Projeto

```
RetroGalatica/
├── index.html              # Página principal do ranking
├── ranking_awards.html     # Ranking alternativo
├── sorteio.html            # Sorteio de times (100% estático)
├── .nojekyll               # Configuração GitHub Pages
├── players.json            # Dados dos jogadores
├── gerar_ranking.py        # Script para gerar ranking (local)
├── app.py                  # Servidor Flask (não funciona no GitHub Pages)
└── README.md               # Este arquivo
```

## 🎲 Como Usar o Sorteio

1. Acesse `sorteio.html` ou clique no botão "🎲 Sorteio de Times" na página principal
2. Clique em "Sortear Times"
3. Os times serão sorteados e exibidos na tela

### Regras do Sorteio

- **4 Times Fechados**: Cada time tem 2 Zagueiros, 1 Meia e 2 Atacantes
- **Restrições**: Arnaldo, Kelvin, Tavares e Vertinho não podem estar no mesmo time
- **Time 5**: Jogadores restantes vão automaticamente para o Time 5

## 🔧 Desenvolvimento Local

### Gerar Ranking

```bash
# Instalar dependências
pip install -r requirements.txt

# Gerar ranking
python gerar_ranking.py
```

### Servidor Flask (Opcional)

```bash
# Executar servidor local
python app.py

# Acessar API
curl http://localhost:5000/sorteio
```

**Nota**: O servidor Flask não funciona no GitHub Pages. Use `sorteio.html` para GitHub Pages.

## 📚 Documentação Adicional

- [GITHUB_PAGES_SETUP.md](GITHUB_PAGES_SETUP.md) - Guia completo de configuração
- [README_SORTEIO.md](README_SORTEIO.md) - Detalhes do sistema de sorteio
- [README_API.md](README_API.md) - Configuração da API OpenAI (opcional)

## ✅ Status

- ✅ Ranking funcionando
- ✅ Sorteio funcionando (100% estático)
- ✅ Pronto para GitHub Pages
- ✅ Navegação entre páginas configurada

## 🎯 Tecnologias

- HTML5
- CSS3 (Glassmorphism, Gradients)
- JavaScript (Vanilla)
- Python (para geração local do ranking)

## 📝 Licença

Este projeto é privado e destinado ao uso interno.

---

**Desenvolvido para o Ranking Galático** ⚽

