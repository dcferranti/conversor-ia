import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from firecrawl import FirecrawlApp

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Conversor Híbrido Saipos", layout="wide")

# --- CSS PARA DEIXAR A TELA LIMPA ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    h1 {margin-bottom: 0rem;}
</style>
""", unsafe_allow_html=True)

# --- CARREGAMENTO DE CHAVES ---
try:
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    firecrawl_key = st.secrets.get("FIRECRAWL_API_KEY", "")
except:
    gemini_key = ""
    firecrawl_key = ""

# --- PROMPT DEFINITIVO (ATUALIZADO PARA VELOCIDADE) ---
PROMPT_SAIPOS = """
[CONTEXTO]
Na empresa Saipos, realizamos a importação de cardápio para tabela Excel.
A saída deve ser EXCLUSIVAMENTE um objeto JSON contendo duas listas: "produtos" e "adicionais".

[REGRAS ESTRUTURAIS - CRÍTICO]
1. Você é uma API. Retorne APENAS o JSON. Não inicie com frases como "Aqui está".
2. Comece a resposta com '{' e termine com '}'.
3. O JSON DEVE SER MINIFICADO: Gere tudo em uma única linha contínua, sem quebras de linha (\\n) e sem espaços desnecessários. Isso é vital para a performance.

[REGRAS DE NEGÓCIO DETALHADAS]
1. PLANILHA 1 (PRODUTOS):
   - Tipo: 'Comida', 'Bebida' ou 'Pizza'.
   - Cuidado: "Pastel sabor pizza" é 'Comida', não 'Pizza'.
   - Preço: Use ponto para decimais (Ex: 39.99). Se não tiver preço ou for variável, use 0.0.
   - Descrição: Se não houver, deixe string vazia "".
   - Imagem: Se houver link/url da imagem, insira. Caso contrário, vazio.

2. PLANILHA 2 (ADICIONAIS):
   - Tipo Obrigatório: Use APENAS: 'Sabor Pizza', 'Borda Pizza', 'Massa Pizza' ou 'Outros'.
   - Se o item não for estrutura de pizza (ex: Molhos, Bebidas, Complementos), o tipo é SEMPRE 'Outros'.

3. VÍNCULOS (IMPORTANTE):
   - A coluna 'Adicional' é a chave de ligação. Use EXATAMENTE a mesma palavra-chave na tabela de Produtos e na de Adicionais para conectá-los.

4. REGRAS ESPECÍFICAS:
   - [PIZZA]: Categoria="Pizzas", Produto="Nome da Pizza", Preço=0. O 'Adicional' liga aos sabores.
     Na aba Adicionais: Tipo="Sabor Pizza", Item="Calabresa", Preço=35.90.
   - [NOMES DUPLICADOS]: Se existir "Carne" em Hamburguer e em Pastel, renomeie para "Hambúrguer de Carne" e "Pastel de Carne".
   - [PREÇO VARIÁVEL]: Se o preço varia pelo sabor/tamanho, o Produto fica com Preço=0 e os itens na aba Adicionais recebem o preço. Defina Mínimo=1 para obrigar a escolha.

[ESTRUTURA JSON OBRIGATÓRIA]
{
  "produtos": [
    {
      "Categoria": "string", "Tipo": "string", "Produto": "string", 
      "Preço": 0.0, "Descrição": "string", "Adicional": "string", "Imagem": "string"
    }
  ],
  "adicionais": [
    {
      "Tipo": "string", "Adicional": "string", "Mínimo": 0, "Máximo": 0, 
      "Item": "string", "Preço": 0.0, "Descrição": "string", "Imagem": "string"
    }
  ]
}
"""

# --- FUNÇÃO DE PROCESSAMENTO
def processar_json_para_excel(texto_json):
    # 1. Limpeza
    start_index = texto_json.find('{')
    end_index = texto_json.rfind('}') + 1
    
    if start_index != -1 and end_index != -1:
        json_clean = texto_json[start_index:end_index]
        try:
            data = json.loads(json_clean)
        except json.JSONDecodeError:
             raise ValueError("Erro de formatação no JSON gerado.")
    else:
        raise ValueError("JSON não encontrado na resposta.")

    # 2. Cria DataFrames
    df_prod = pd.DataFrame(data.get("produtos", []))
    df_add = pd.DataFrame(data.get("adicionais", []))

    # --- PADRONIZAÇÃO TABELA PRODUTOS ---
    if not df_prod.empty:
        # Injeta colunas fixas
        df_prod["COR"] = "Padrão"
        df_prod["ATIVO"] = "Sim"
        df_prod["DISPONIBILIDADE"] = "Delivery e Salão"
        df_prod["CÓDIGO"] = "" # Código vazio
        
        # Garante colunas variáveis
        cols_vars = ["Categoria", "Tipo", "Produto", "Preço", "Descrição", "Adicional", "Imagem"]
        for col in cols_vars:
            if col not in df_prod.columns: df_prod[col] = ""

        # Renomeia para Maiúsculas
        df_prod = df_prod.rename(columns={
            "Categoria": "CATEGORIA", "Tipo": "TIPO", "Produto": "PRODUTO", 
            "Preço": "PREÇO", "Descrição": "DESCRIÇÃO", "Adicional": "ADICIONAL",
            "Imagem": "IMAGEM"
        })
        
        # ORDENAÇÃO PRODUTOS
        df_prod = df_prod[[
            "COR", "CATEGORIA", "ATIVO", "DISPONIBILIDADE", "TIPO", 
            "PRODUTO", "PREÇO", "DESCRIÇÃO", "ADICIONAL", "CÓDIGO", "IMAGEM"
        ]]

    # --- PADRONIZAÇÃO TABELA ADICIONAIS ---
    if not df_add.empty:
        # Injeta colunas fixas
        df_add["ATIVO"] = "Sim"
        df_add["CÓDIGO"] = "" # COLUNA DE CÓDIGO VAZIA
        
        
        cols_vars_add = ["Tipo", "Adicional", "Mínimo", "Máximo", "Item", "Preço", "Descrição", "Imagem"]
        for col in cols_vars_add:
            if col not in df_add.columns: df_add[col] = ""

       
        df_add = df_add.rename(columns={
            "Tipo": "TIPO", "Adicional": "ADICIONAL", "Mínimo": "MÍNIMO", 
            "Máximo": "MÁXIMO", "Item": "ITEM", "Preço": "PREÇO", 
            "Descrição": "DESCRIÇÃO", "Imagem": "IMAGEM"
        })

       
        df_add = df_add[[
            "TIPO", "ADICIONAL", "MÍNIMO", "MÁXIMO", "ATIVO", 
            "ITEM", "PREÇO", "DESCRIÇÃO", "CÓDIGO", "IMAGEM"
        ]]
    
    return df_prod, df_add

# --- FUNÇÕES AUXILIARES ---
def limpar_manual():
    st.session_state.json_manual = ""
    st.session_state.df_prod_manual = None
    st.session_state.df_add_manual = None

def limpar_auto():
    st.session_state.df_prod_auto = None
    st.session_state.df_add_auto = None

st.title("🍽️ Conversor de Cardápios")

modo = st.radio("Modo:", ["🤖 Automático (API)", "🧠 Manual (Gemini Site)"], horizontal=True, label_visibility="collapsed")
st.markdown("---")

# MODO MANUAL
if modo == "🧠 Manual (Gemini Site)":
    
    with st.expander("📄 CLIQUE AQUI PARA PEGAR O PROMPT (COPIAR)", expanded=False):
        st.code(PROMPT_SAIPOS, language="json")
        st.caption("👆 Copie este prompt completo e cole no Gemini.")

    col_esq, col_dir = st.columns([1, 1])

    with col_esq:
        if "json_manual" not in st.session_state:
            st.session_state.json_manual = ""

        input_area = st.text_area(
            "Cole a resposta da IA aqui:", 
            value=st.session_state.json_manual,
            height=400, 
            key="json_manual",
            placeholder='Cole aqui o JSON gerado...'
        )
        
        c_btn1, c_btn2 = st.columns([2, 1])
        with c_btn1:
            btn_converter = st.button("🔄 CONVERTER", type="primary", use_container_width=True)
        with c_btn2:
            st.button("🧹 LIMPAR", on_click=limpar_manual, use_container_width=True)

    with col_dir:
        # Processamento Manual
        if btn_converter and input_area:
            try:
                df_p, df_a = processar_json_para_excel(input_area)
                st.session_state.df_prod_manual = df_p
                st.session_state.df_add_manual = df_a
                st.success("✅ Convertido com Sucesso!")
            except Exception as e:
                st.error("Erro ao ler JSON. Verifique se copiou a resposta inteira.")
                with st.expander("Detalhes do erro"):
                    st.write(e)

        # Exibição Persistente
        if st.session_state.get('df_prod_manual') is not None:
            tab_p, tab_a = st.tabs(["Produtos", "Adicionais"])
            with tab_p:
                df_p = st.session_state.df_prod_manual
                st.dataframe(df_p, hide_index=True, use_container_width=True)
                st.download_button("💾 Baixar Produtos", df_p.to_csv(index=False, sep=';', encoding='utf-8-sig'), "produtos.csv", use_container_width=True)
            with tab_a:
                df_a = st.session_state.df_add_manual
                st.dataframe(df_a, hide_index=True, use_container_width=True)
                st.download_button("💾 Baixar Adicionais", df_a.to_csv(index=False, sep=';', encoding='utf-8-sig'), "adicionais.csv", use_container_width=True)
        elif not input_area:
            st.info("👈 Cole o JSON na esquerda e clique em Converter.")

# MODO AUTOMÁTICO
elif modo == "🤖 Automático (API)":
    if not gemini_key:
        st.error("⚠️ Chave GEMINI_API_KEY não configurada.")
        st.stop()

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('models/gemini-flash-latest')

    # Inicializa memória
    if "df_prod_auto" not in st.session_state: st.session_state.df_prod_auto = None
    if "df_add_auto" not in st.session_state: st.session_state.df_add_auto = None

    tipo_entrada = st.radio("Fonte:", ["📂 Arquivo", "🔗 Link"], horizontal=True)
    executar_auto = False
    content_parts = []

    if tipo_entrada == "📂 Arquivo":
        f = st.file_uploader("Upload", type=["png", "jpg", "pdf"])
        if f:
            content_parts = [PROMPT_SAIPOS, {"mime_type": f.type, "data": f.getvalue()}]
            if st.button("🚀 INICIAR CONVERSÃO", type="primary"):
                executar_auto = True

    elif tipo_entrada == "🔗 Link":
        url = st.text_input("Link:")
        if url and st.button("🚀 INICIAR CONVERSÃO", type="primary"):
            try:
                app = FirecrawlApp(api_key=firecrawl_key)
                res = app.scrape(url, formats=['markdown'])
                md = res.get('markdown', "") or res.get('data', {}).get('markdown', "")
                if md:
                    content_parts = [f"{PROMPT_SAIPOS}\nSITE:\n{md}"]
                    executar_auto = True
            except: st.error("Erro no link")

    # Processamento Automático
    if executar_auto and content_parts:
        with st.spinner('🤖 Inteligência Artificial processando...'):
            try:
                resp = model.generate_content(content_parts)
                df_p, df_a = processar_json_para_excel(resp.text)
                
                # Salva na memória
                st.session_state.df_prod_auto = df_p
                st.session_state.df_add_auto = df_a
                st.success("✅ Sucesso!")
            except Exception as e: 
                st.error(f"Erro: {e}")

    # Exibição Automática
    if st.session_state.df_prod_auto is not None:
        st.markdown("---")
        tab_p, tab_a = st.tabs(["Produtos", "Adicionais"])
        
        with tab_p:
            df_p = st.session_state.df_prod_auto
            st.dataframe(df_p, hide_index=True, use_container_width=True)
            st.download_button("💾 Baixar Produtos", df_p.to_csv(index=False, sep=';', encoding='utf-8-sig'), "produtos_auto.csv", use_container_width=True)
        
        with tab_a:
            df_a = st.session_state.df_add_auto
            st.dataframe(df_a, hide_index=True, use_container_width=True)
            st.download_button("💾 Baixar Adicionais", df_a.to_csv(index=False, sep=';', encoding='utf-8-sig'), "adicionais_auto.csv", use_container_width=True)
            
        if st.button("🔄 Nova Conversão (Limpar)", on_click=limpar_auto):
            pass
