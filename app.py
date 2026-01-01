import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from firecrawl import FirecrawlApp

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Conversor Inteligente", layout="wide")

# --- CARREGAMENTO DE CHAVES ---
try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    firecrawl_key = st.secrets["FIRECRAWL_API_KEY"]
except Exception:
    st.error("⚠️ ERRO: Chaves de API não configuradas.")
    st.stop()

# --- REGRAS (PROMPT BLINDADO) ---
PROMPT_SAIPOS = """
[Contexto] importamos cardápios para Excel.
Precisamos de duas listas: "produtos" e "adicionais".

[REGRAS ESTRUTURAIS - CRÍTICO]
1. Retorne APENAS o código JSON.
2. NÃO escreva frases como "Aqui está o JSON" ou "Espero ter ajudado".
3. Comece com { e termine com }.

[REGRAS DE NEGÓCIO]
1. Tipo Produto: Comida, Bebida ou Pizza.
2. Preço: Ponto para decimais (Ex: 39.99). Se for 0, use 0.0.
3. [PIZZA]: Categoria="Pizzas", Produto=Tipo, Valor=0. Adicional liga os sabores.
   Na tab adicionais: Tipo="Sabor Pizza".
4. [ADICIONAIS]: Use a mesma palavra-chave na coluna 'Adicional' para vincular tabelas.

[FORMATO OBRIGATÓRIO DO JSON]
{
  "produtos": [
    {"Categoria": "", "Tipo": "", "Produto": "", "Preço": 0.0, "Descrição": "", "Adicional": ""}
  ],
  "adicionais": [
    {"Tipo": "", "Adicional": "", "Mínimo": 0, "Máximo": 0, "Item": "", "Preço": 0.0, "Descrição": ""}
  ]
}
"""

# --- CONFIGURAÇÃO DA IA ---
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('models/gemini-flash-latest')

st.title("🍽️ Conversor de Cardápios para Excel")

# --- OPÇÕES ---
OPT_ARQUIVO = "📂 Arquivo (PDF/Imagem)"
OPT_LINK = "🔗 Link Automático (Site)"

tipo_entrada = st.radio("Fonte:", [OPT_ARQUIVO, OPT_LINK], horizontal=True)

content_parts = []
executar = False

# --- LÓGICA 1: ARQUIVO ---
if tipo_entrada == OPT_ARQUIVO:
    uploaded_file = st.file_uploader("Arraste o arquivo aqui", type=["png", "jpg", "jpeg", "pdf"])
    if uploaded_file:
        # Envio do prompt junto com a imagem
        content_parts = [PROMPT_SAIPOS, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}]
        executar = st.button("Iniciar Conversão")

# --- LÓGICA 2: LINK ---
elif tipo_entrada == OPT_LINK:
    url_input = st.text_input("Cole o Link:")
    if url_input and st.button("Iniciar Conversão"):
        with st.spinner("🕷️ Acessando site..."):
            try:
                app = FirecrawlApp(api_key=firecrawl_key)
                scrape_result = app.scrape(url_input, formats=['markdown'])
                
                markdown_site = ""
                if hasattr(scrape_result, 'markdown'):
                    markdown_site = scrape_result.markdown
                elif isinstance(scrape_result, dict):
                    markdown_site = scrape_result.get('markdown', "")
                    if not markdown_site and 'data' in scrape_result:
                        markdown_site = scrape_result['data'].get('markdown', "")
                
                if markdown_site:
                    user_prompt = f"{PROMPT_SAIPOS}\n\n[DADOS DO SITE]:\n{markdown_site}"
                    content_parts = [user_prompt]
                    executar = True
                else:
                    st.error("Site vazio.")
            except Exception as e:
                st.error(f"Erro no link: {e}")

# --- PROCESSAMENTO ---
if executar and content_parts:
    with st.spinner('Processando...'):
        try:
            response = model.generate_content(content_parts)
            text_resp = response.text
            
            # --- LIMPEZA DO JSON ---
            start_index = text_resp.find('{')
            end_index = text_resp.rfind('}') + 1
            
            if start_index != -1 and end_index != -1:
                json_clean = text_resp[start_index:end_index]
                data = json.loads(json_clean)
            else:
                st.error("A IA não gerou dados válidos. Veja a resposta bruta abaixo:")
                st.code(text_resp)
                st.stop()

            # --- Criação das Tabelas ---
            df_prod = pd.DataFrame(data.get("produtos", []))
            df_add = pd.DataFrame(data.get("adicionais", []))

            # Garante colunas vazias se não existirem
            cols_prod = ["Categoria", "Tipo", "Produto", "Preço", "Descrição", "Adicional"]
            for c in cols_prod: 
                if c not in df_prod.columns: df_prod[c] = ""
            df_prod = df_prod[cols_prod]

            cols_add = ["Tipo", "Adicional", "Mínimo", "Máximo", "Item", "Preço", "Descrição"]
            for c in cols_add: 
                if c not in df_add.columns: df_add[c] = ""
            df_add = df_add[cols_add]

            st.success("✅ Sucesso!")
            
            tab1, tab2 = st.tabs(["📋 Produtos", "➕ Adicionais"])
            with tab1:
                st.dataframe(df_prod, hide_index=True)
                if not df_prod.empty:
                    st.download_button("💾 Baixar Produtos", df_prod.to_csv(index=False, sep=';', encoding='utf-8-sig'), "produtos.csv")
                else:
                    st.warning("Lista vazia. Verifique se o arquivo está legível.")
            
            with tab2:
                st.dataframe(df_add, hide_index=True)
                if not df_add.empty:
                    st.download_button("💾 Baixar Adicionais", df_add.to_csv(index=False, sep=';', encoding='utf-8-sig'), "adicionais.csv")

        except Exception as e:
            st.error(f"Erro ao processar: {e}")