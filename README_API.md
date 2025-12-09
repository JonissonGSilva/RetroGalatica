# Configuração da API OpenAI para Mensagens Dinâmicas

Este projeto suporta a integração com a API do ChatGPT para gerar mensagens motivacionais dinâmicas e personalizadas no estilo Spotify Wrapped.

## 🚀 Como Configurar

### Passo 1: Instalar Dependências

```bash
pip install -r requirements.txt
```

### Passo 2: Obter API Key

1. Acesse [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Faça login ou crie uma conta
3. Clique em "Create new secret key"
4. Copie a chave gerada (ela começa com `sk-`)

### Passo 3: Configurar Variáveis de Ambiente

1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```

2. Abra o arquivo `.env` e cole sua API key:
   ```bash
   OPENAI_API_KEY=sk-sua-chave-aqui
   OPENAI_MODEL=gpt-3.5-turbo
   ```

3. Salve o arquivo

### Passo 4: Gerar o Ranking

Execute o script Python normalmente:
```bash
python3 gerar_ranking.py
```

O arquivo `ranking_awards.html` será gerado com as variáveis de ambiente injetadas automaticamente.

## 🌐 Deploy no Render

### Configuração no Render

1. **Adicione as variáveis de ambiente no Render:**
   - Acesse seu serviço no Render Dashboard
   - Vá em "Environment"
   - Adicione as seguintes variáveis:
     - `OPENAI_API_KEY`: Sua chave da API OpenAI
     - `OPENAI_MODEL`: `gpt-3.5-turbo` (ou `gpt-4`)

2. **O Render automaticamente:**
   - Carrega as variáveis de ambiente
   - O script Python lê essas variáveis
   - As variáveis são injetadas no HTML gerado

### Exemplo de configuração no Render

```
OPENAI_API_KEY=sk-proj-abc123def456ghi789
OPENAI_MODEL=gpt-3.5-turbo
```

## 📋 Modelos Disponíveis

- **gpt-3.5-turbo** (Recomendado)
  - Mais barato (~$0.0015 por 1K tokens)
  - Rápido
  - Boa qualidade para mensagens motivacionais

- **gpt-4**
  - Melhor qualidade
  - Mais caro (~$0.03 por 1K tokens)
  - Mais lento

## 💡 Como Funciona

1. Quando você insere o nome de um jogador, o sistema:
   - Coleta todas as estatísticas do jogador
   - Cria prompts contextuais e variados
   - Chama a API do ChatGPT para gerar mensagens personalizadas
   - Usa cache para evitar chamadas repetidas

2. As variáveis de ambiente são:
   - Lidas pelo Python usando `python-dotenv`
   - Injetadas diretamente no HTML gerado
   - Disponíveis no JavaScript via `window.OPENAI_API_KEY`

3. Se a API não estiver configurada ou falhar:
   - O sistema usa textos padrão (fallback)
   - Funciona normalmente sem a API

## 🔒 Segurança

⚠️ **IMPORTANTE**: 
- NUNCA compartilhe seu arquivo `.env`
- O arquivo `.env` já está no `.gitignore`
- No Render, use as variáveis de ambiente do dashboard (não faça commit)
- Não compartilhe sua API key publicamente

## 💰 Custos

Com `gpt-3.5-turbo`:
- ~$0.0015 por 1K tokens
- Uma mensagem típica usa ~50-100 tokens
- 1000 mensagens ≈ $0.15

Exemplo: Se você gerar retrospectivas para 10 jogadores com 7 slides cada:
- 10 jogadores × 7 slides = 70 mensagens
- 70 × 100 tokens = 7.000 tokens
- Custo: ~$0.01 (um centavo)

## 🐛 Troubleshooting

### Mensagens não estão sendo geradas dinamicamente

1. Verifique se o arquivo `.env` existe na mesma pasta do script
2. Verifique se a API key está correta no `.env`
3. Verifique se instalou as dependências: `pip install -r requirements.txt`
4. Abra o console do navegador (F12) e verifique se há erros
5. Verifique se você tem créditos na conta OpenAI

### Erro: "API key não configurada"

- Certifique-se de que o arquivo `.env` existe
- Verifique se a variável está definida corretamente: `OPENAI_API_KEY=sk-...`
- No Render, verifique se as variáveis de ambiente estão configuradas

### Erro: "Insufficient quota"

- Você não tem créditos suficientes na conta OpenAI
- Adicione créditos em: https://platform.openai.com/account/billing

### No Render: Variáveis não estão sendo lidas

- Verifique se as variáveis estão configuradas no dashboard do Render
- Certifique-se de que o serviço foi reiniciado após adicionar as variáveis
- Verifique os logs do Render para erros

## 📝 Exemplo de .env

```bash
# Configuração da API OpenAI
OPENAI_API_KEY=sk-proj-abc123def456ghi789
OPENAI_MODEL=gpt-3.5-turbo
```

## 🎯 Próximos Passos

- [ ] Instalar dependências: `pip install -r requirements.txt`
- [ ] Configurar seu `.env` com a API key
- [ ] Testar gerando uma retrospectiva
- [ ] Configurar variáveis no Render (se for fazer deploy)
- [ ] Ajustar o modelo se necessário (gpt-4 para melhor qualidade)
- [ ] Monitorar os custos na dashboard da OpenAI

