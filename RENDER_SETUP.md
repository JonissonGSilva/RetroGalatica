# Guia de Deploy no Render

Este guia explica como fazer deploy desta aplicação no Render.

## 📋 Pré-requisitos

1. Conta no Render (gratuita): https://render.com
2. Conta na OpenAI com API key
3. Repositório Git (GitHub, GitLab, etc.)

## 🚀 Passo a Passo

### 1. Preparar o Repositório

Certifique-se de que os seguintes arquivos estão no repositório:
- `gerar_ranking.py`
- `players.json`
- `requirements.txt`
- `.env.example`
- `.gitignore` (com `.env` incluído)

### 2. Criar um Serviço Web no Render

Você tem duas opções:

#### Opção A: Serviço Web (Recomendado para uso dinâmico)

1. **Criar novo Web Service:**
   - No dashboard do Render, clique em "New +"
   - Selecione "Web Service"
   - Conecte seu repositório

2. **Configurações do Build:**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: python3 gerar_ranking.py && python3 -m http.server 8000
   ```

3. **Variáveis de Ambiente:**
   - Vá em "Environment"
   - Adicione:
     - `OPENAI_API_KEY`: Sua chave da API OpenAI
     - `OPENAI_MODEL`: `gpt-3.5-turbo` (ou `gpt-4`)

#### Opção B: Serviço Estático (Mais simples)

1. **Criar novo Static Site:**
   - No dashboard do Render, clique em "New +"
   - Selecione "Static Site"
   - Conecte seu repositório

2. **Build Command:**
   ```
   pip install -r requirements.txt && python3 gerar_ranking.py
   ```

3. **Publish Directory:**
   ```
   . (raiz do projeto)
   ```

4. **Variáveis de Ambiente:**
   - Mesmas variáveis da Opção A

### 3. Configurar Variáveis de Ambiente no Render

No dashboard do Render:

1. Vá em **Environment** do seu serviço
2. Clique em **Add Environment Variable**
3. Adicione:

   ```
   OPENAI_API_KEY = sk-sua-chave-aqui
   OPENAI_MODEL = gpt-3.5-turbo
   ```

4. Clique em **Save Changes**

### 4. Deploy

1. Render automaticamente fará o deploy quando você fizer push
2. Ou clique em **Manual Deploy** > **Deploy latest commit**

## 🔧 Configuração Avançada

### Usar um Servidor Web Personalizado

Se quiser criar um servidor web que gere o HTML dinamicamente:

1. Crie um arquivo `app.py`:

```python
from flask import Flask, send_file
import os
from gerar_ranking import main

app = Flask(__name__)

@app.route('/')
def index():
    # Gera o ranking
    main()
    # Retorna o HTML gerado
    return send_file('ranking_awards.html')
```

2. Atualize `requirements.txt`:
```
python-dotenv>=1.0.0
flask>=2.0.0
```

3. No Render, configure:
   - **Start Command**: `gunicorn app:app`

## 📝 Checklist de Deploy

- [ ] Repositório conectado ao Render
- [ ] `requirements.txt` está no repositório
- [ ] `.env.example` está no repositório
- [ ] `.gitignore` inclui `.env`
- [ ] Variáveis de ambiente configuradas no Render
- [ ] Build command configurado
- [ ] Deploy realizado com sucesso

## 🐛 Troubleshooting

### Erro: "Module not found: dotenv"

- Certifique-se de que `requirements.txt` inclui `python-dotenv`
- Verifique se o build command instala as dependências

### Variáveis de ambiente não estão sendo lidas

- Verifique se as variáveis estão configuradas no dashboard do Render
- Reinicie o serviço após adicionar variáveis
- Verifique os logs do Render

### HTML não está sendo gerado

- Verifique se `players.json` está no repositório
- Verifique os logs do build para erros
- Certifique-se de que o caminho do arquivo está correto

## 💡 Dicas

1. **Monitoramento:**
   - Use os logs do Render para debug
   - Configure alertas para erros

2. **Performance:**
   - O HTML é gerado a cada request (Opção A) ou no build (Opção B)
   - Considere cache se necessário

3. **Segurança:**
   - Nunca faça commit do `.env`
   - Use sempre variáveis de ambiente no Render
   - Rotacione sua API key periodicamente

## 📚 Recursos

- [Documentação do Render](https://render.com/docs)
- [Variáveis de Ambiente no Render](https://render.com/docs/environment-variables)
- [OpenAI API Documentation](https://platform.openai.com/docs)

