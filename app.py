import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from firecrawl import FirecrawlApp

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Conversor Híbrido Saipos", layout="wide")
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    h1 {margin-bottom: 0rem;}
</style>
""", unsafe_allow_html=True)

# API
try:
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    firecrawl_key = st.secrets.get("FIRECRAWL_API_KEY", "")
except:
    gemini_key = ""
    firecrawl_key = ""

# PROMPT
PROMPT_SAIPOS = """
[Contexto] Na empresa Saipos, realizamos a importação de cardápio para tabela excel. Essa tebela compreende em duas planilhas: Produto e Adicionais. Na primeira tabela, estão as colunas:
Categoria | Tipo | Produto | Preço | Descrição | Adicional | Imagem
Na segunda categoria, possuem as colunas:
Tipo | Adicional | Mínimo | Máximo | Item | Preço | Descrição | Imagem

[Observações]
1- Na planilha 1 (produtos), o tipo pode ser: Comida ou Bebida ou Pizza (Detalhe exemplo: Cuidar para que um Pastel sabor pizza não seja considerado como Pizza mas sim como Comida). 
2- O preço será sempre com um . separado os decimais!
3- Caso o item não tenha descrição, deixar em branco.
4- Na planilha 2 (adicionais), o tipo poderá ser 'Outros', 'Sabor Pizza', 'Borda Pizza', 'Massa Pizza'. Ou seja, se não tiver relação com pizza (é o item pizza e não sabor de pastel pizza por exemplo), será sempre 'Outro'.
5- Caso um produto tenha adicional, a coluna Adicional será usada para linkar os adicionais do produto com uma palavra chave que represente o conjunto de adicionais e deve ser a mesma palavra em ambas as tabelas. Caso um item não tenha adicional, basta deixar em branco a linha da coluna.
6- Mínimo e máximo dos adicionais deve ser respeitado o que estiver no cardápio em anexo, mas caso não possua essa informação, deixar o espaço da linha em branco.
7- Atentar ao nome da categoria para respeitar conforme o cardápio em anexo e não gerar categ inexist.
8- Imagem: Se houver link/url da imagem do produto ou adicional, insira. Caso contrário, deixe string vazia "".

[Exemplos]
Planilha 1 (Produtos): 
Hambúrgueres | Comida | Smash Simples | 39.99 | Pão, hambúrguer, alface e tomate. | Escolha seus molhos | ""
Pastéis | Comida | Pastel de Carne | 7.89 | | Sabor extra | "https://linkdaimagem.com/pastel.jpg"

Planilha 2 (Adicionais):
Outro | Escolha seus molhos | 0 | 5 | Molho Mostarda | 2.99 | | ""
Outro | Escolha seus molhos | 0 | 5 | Maionese Verde | 2.99 | Maionese Temperada | ""
Outro | Sabor extra | 0 | 1 | Queijo | 5.00 | | ""

[PIZZA] Caso seja um cardápio de pizza:
A categoria será "Pizzas", no produto o tipo da pizza, no valor sempre 0 e descrição caso houver, e no Adicionais, colocar a palavra chave que vai ligar os sabores da pizza ao produto.
Exemplo:
Categoria | Produto | Valor (somente o numero com . separando o decimal) | Descrição | Adicional
Pizzas | Pizza Tradicional Pequena | 0.0 | Escolha o sabor de sua pizza! | Sabores Pizza Tradicional Pequena

Na segunda planilha, aplicar da seguinte forma:
Tipo | Adicional | Mínimo de sabores na pizza (sempre 1 pelo menos) | Máximo de sabores na pizza | Item (sabor da pizza) | Preço | Descrição
Sabor Pizza | Sabores Pizza Tradicional Pequena | 1 | 1 | Calabresa | 34.99 | molho de tomate, queijo mussarela, calabresa e orégano.

[DETALHES]
Essa planilha subirá para um site de delivery. O nome do produto e o nome do adicional, e os preços serão impressos na via de cozinha para que seja preparado o pedido. Ou seja, se dois itens de categorias diferentes estiverem com o mesmo nome, por exemplo "Carne", o cozinheiro não saberá do que se trata aquele pedido. Exemplo:
Categoria | Produto
Hamburgueres | Carne
Pastéis | Carne
Portanto, deve-se aplicar o nome da categoria a fim de identificar na impressão. Exemplo:
Hamburgueres | Hambúrguer de Carne
Pastéis | Pastel de Carne

Em alguns cardápios, pode ser que um determinado produto não tenha preço direto, onde o preço pode variar com o sabor (ou algum outro) que o cliente escolher. Nesses casos, na primeira tabela (Produtos), deixe o produto com o preço zerado (0.00) e aplique os sabores na segunda tabela 'Adicionais' para que o cliente escolha o sabor do pedido e na coluna 'Mínimo', deixe como "1". Desta forma, o cliente será obrigado a escolher um sabor e pagar o preço determinado. Exemplo:
Categoria | Tipo | Produto | Preço | Descrição | Adicional
Pastéis | Comida | Pastel Premium | 0.0 | Escolha o sabor de seu pastel! | Sabores Pastéis

Tipo | Adicional | Mínimo | Máximo | Item | Preço | Descrição
Outro | Sabores Pastéis | 1 | 1 | Carne | 7.99 | | 
Outro | Sabores Pastéis | 1 | 1 | Frango | 6.99 | | 

Importante! Caso um segundo produto tenha a mesma lista de adicionais do outro (nome, valor), utilize a mesma palavra-chave para não gerar duplicação.
Caso tenha mais de uma lista de adicionais, aplicar junto na mesma coluna porém, com uma vírgula separando as palavras chave: Incremente seu Hamburguer, Escolha uma bebida
Outro detalhe: Se algum item possuir em sua descrição informando que o cliente pode escolher entre determinado ingrediente ou acompanhamento, aplique esses itens que o cliente deverá escolher nos adicionais e deixe como obrigatório a seleção pelo cliente (mínimo 1).

Não crie produtos que não existem no cardápio. Não altere o nome do item que está no cardápio de forma que fique com nome diferente, dando a entender que seja outro item. Extraia o cardápio completo, do início ao fim sem deixar nada faltando.

[REGRAS DE SISTEMA OBRIGATÓRIAS - CRÍTICO]
A partir de agora, você atua como uma API. 
1. A saída deve ser EXCLUSIVAMENTE um objeto JSON. Não escreva NADA além do JSON. Não inicie com "Aqui está" nem use formatação markdown como ```json.
2. Comece a resposta com '{' e termine com '}'.
3. O JSON DEVE SER MINIFICADO: Gere tudo em uma única linha contínua, sem quebras de linha (\\n) e sem espaços em branco desnecessários. Isso é vital para a performance.
4. Siga ESTRITAMENTE esta estrutura de chaves (os nomes devem ser exatos). Se não houver Imagem, mande string vazia "". Se não houver Min/Max, mande 0:
{"produtos":[{"Categoria":"string","Tipo":"string","Produto":"string","Preço":0.0,"Descrição":"string","Adicional":"string","Imagem":"string"}],"adicionais":[{"Tipo":"string","Adicional":"string","Mínimo":0,"Máximo":0,"Item":"string","Preço":0.0,"Descrição":"string","Imagem":"string"}]}
"""

# PROCESSAMENTO
def processar_json_para_excel(texto_json):
    # Limpeza
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

    # Cria DataFrames
    df_prod = pd.DataFrame(data.get("produtos", []))
    df_add = pd.DataFrame(data.get("adicionais", []))

    # PADRONIZAÇÃO TABELA PRODUTOS
    if not df_prod.empty:
        # Colunas fixas
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

    # PADRONIZAÇÃO TABELA ADICIONAIS
    if not df_add.empty:
        # Colunas fixas
        df_add["ATIVO"] = "Sim"
        df_add["CÓDIGO"] = ""
        
        cols_vars_add = ["Tipo", "Adicional", "Mínimo", "Máximo", "Item", "Preço", "Descrição", "Imagem"]
        for col in cols_vars_add:
            if col not in df_add.columns: df_add[col] = ""

        # Renomeia
        df_add = df_add.rename(columns={
            "Tipo": "TIPO", "Adicional": "ADICIONAL", "Mínimo": "MÍNIMO", 
            "Máximo": "MÁXIMO", "Item": "ITEM", "Preço": "PREÇO", 
            "Descrição": "DESCRIÇÃO", "Imagem": "IMAGEM"
        })

        # ORDENAÇÃO FINAL ADICIONAIS
        df_add = df_add[[
            "TIPO", "ADICIONAL", "MÍNIMO", "MÁXIMO", "ATIVO", 
            "ITEM", "PREÇO", "DESCRIÇÃO", "CÓDIGO", "IMAGEM"
        ]]
    
    return df_prod, df_add

# FUNÇÕES AUXILIARES
def limpar_manual():
    st.session_state.json_manual = ""
    st.session_state.df_prod_manual = None
    st.session_state.df_add_manual = None

def limpar_auto():
    st.session_state.df_prod_auto = None
    st.session_state.df_add_auto = None

# INTERFACE PRINCIPAL
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
