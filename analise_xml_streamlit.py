import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import re
from collections import defaultdict
from io import BytesIO
from decimal import Decimal
import time

# Forçar limpeza de cache
st.cache_data.clear()

st.set_page_config(page_title="Leitor de XML - Importação e Saídas", layout="centered")

st.title("📦 Leitor de XMLs - Entrada e Saídas de Importação")

# Versão v2.1 - Remove linha "Outros" duplicada

# ---------------------- FUNÇÕES AUXILIARES ----------------------
def extrair_texto(elemento, caminho, ns=None, default="0"):
    """Retorna o valor do nó se existir"""
    if ns:
        el = elemento.find(caminho, ns)
    else:
        el = elemento.find(caminho)
    return el.text if el is not None else default

def ler_xml_conteudo(uploaded_file):
    """Carrega e parseia o XML"""
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    ns = {"ns": "http://www.portalfiscal.inf.br/nfe"}
    return root, ns

def gerar_excel(df, nome_planilha="Resumo"):
    """Cria arquivo Excel em memória para download"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=nome_planilha)
    return output.getvalue()

# ---------------------- ENTRADA ----------------------
st.header("1️⃣ Nota de Entrada (Importação)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 Declaração de Importação (DI)")
    xml_di = st.file_uploader("Upload do XML da DI:", type="xml", key="di")

with col2:
    st.subheader("📦 NFe de Entrada")
    xml_nfe_entrada = st.file_uploader("Upload do XML da NFe de Entrada:", type="xml", key="nfe_entrada")

if xml_di and xml_nfe_entrada:
    # ===== LER DI =====
    tree_di = ET.parse(xml_di)
    root_di = tree_di.getroot()
    
    # Somar dados de todas as adições na DI
    total_frete_di = 0
    total_ipi_di = 0
    total_pis_di = 0
    total_cofins_di = 0
    total_ii_di = 0
    total_valor_di = 0
    total_valor_moeda = 0
    total_frete_moeda = 0
    numero_di = ""
    
    for adicao in root_di.findall('.//adicao'):
        if not numero_di:
            numero_di = adicao.find('numeroDI').text
        
        total_valor_di += int(adicao.find('condicaoVendaValorReais').text)
        total_valor_moeda += int(adicao.find('condicaoVendaValorMoeda').text)
        total_frete_di += int(adicao.find('freteValorReais').text)
        total_frete_moeda += int(adicao.find('freteValorMoedaNegociada').text)
        total_ipi_di += int(adicao.find('ipiAliquotaValorRecolher').text)
        total_pis_di += int(adicao.find('pisPasepAliquotaValorRecolher').text)
        total_cofins_di += int(adicao.find('cofinsAliquotaValorRecolher').text)
        total_ii_di += int(adicao.find('iiAliquotaValorRecolher').text)
    
    # Converter de centavos para reais
    valor_produtos = total_valor_di / 100
    valor_produtos_usd = total_valor_moeda / 100
    frete_internacional = total_frete_di / 100
    frete_internacional_usd = round(total_frete_moeda / 100)  # Arredondar para inteiro
    ipi_di = total_ipi_di / 100
    pis_di = total_pis_di / 100
    cofins_di = total_cofins_di / 100
    ii_imposto = total_ii_di / 100
    
    # ===== LER NFe =====
    root_nfe, ns_nfe = ler_xml_conteudo(xml_nfe_entrada)
    total_nfe = root_nfe.find(".//ns:ICMSTot", ns_nfe)
    
    vICMS = float(extrair_texto(total_nfe, "ns:vICMS", ns_nfe))
    vNF = float(extrair_texto(total_nfe, "ns:vNF", ns_nfe))

    # AFRMM (somar se houver vários) - com Decimal para melhor precisão
    afrmm_total = Decimal(0)
    for v in root_nfe.findall(".//ns:vAFRMM", ns_nfe):
        afrmm_total += Decimal(v.text)
    afrmm_total = float(afrmm_total)

    # Taxa Siscomex (extraída via regex de infAdic)
    inf_cpl = root_nfe.find(".//ns:infCpl", ns_nfe)
    taxa_siscomex = 0
    if inf_cpl is not None and inf_cpl.text:
        match = re.search(r"SISCOMEX foi de R\$ ([\d.]+,\d{2})", inf_cpl.text)
        if match:
            taxa_text = match.group(1).replace(".", "").replace(",", ".")
            taxa_siscomex = float(taxa_text)

    # Montar tabela com valores em R$ e USD
    dados_entrada = {
        "Imposto / Taxa": [
            "Valor dos Produtos", "Frete Internacional", "AFRMM", "Taxa Siscomex",
            "IPI", "PIS", "COFINS", "ICMS",
            "II - Imposto de Importação",
            "VALOR TOTAL DA NOTA"
        ],
        "Valor (R$)": [
            valor_produtos, frete_internacional, afrmm_total, taxa_siscomex,
            ipi_di, pis_di, cofins_di, vICMS,
            ii_imposto,
            vNF
        ],
        "Valor (USD)": [
            valor_produtos_usd, frete_internacional_usd, "—", "—",
            "—", "—", "—", "—",
            "—",
            "—"
        ]
    }

    df_entrada = pd.DataFrame(dados_entrada)
    st.dataframe(df_entrada)
    
    st.markdown(f"### 💰 **Total da Nota: R$ {vNF:,.2f}**")
    st.markdown(f"*DI: {numero_di}*")

    excel_bytes = gerar_excel(df_entrada, "Entrada")
    st.download_button(
        label="💾 Baixar resumo de entrada (Excel)",
        data=excel_bytes,
        file_name="resumo_entrada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
elif xml_di or xml_nfe_entrada:
    st.warning("⚠️ Por favor, faça upload dos DOIS XMLs (DI e NFe) para processar a entrada!")

# ---------------------- SAÍDA 1 ----------------------
st.header("2️⃣ Nota de Saída 1 (individual)")
xml_saida1 = st.file_uploader("Faça upload do XML da Saída 1:", type="xml", key="saida1")

if xml_saida1:
    root, ns = ler_xml_conteudo(xml_saida1)
    total = root.find(".//ns:ICMSTot", ns)
    
    vProd = float(extrair_texto(total, "ns:vProd", ns))
    vIPI = float(extrair_texto(total, "ns:vIPI", ns))
    vPIS = float(extrair_texto(total, "ns:vPIS", ns))
    vCOFINS = float(extrair_texto(total, "ns:vCOFINS", ns))
    vICMS = float(extrair_texto(total, "ns:vICMS", ns))
    vICMSST = float(extrair_texto(total, "ns:vST", ns))

    # Extrair valor total da nota
    vNF_saida = float(extrair_texto(total, "ns:vNF", ns))

    dados_saida1 = {
        "Campo": [
            "Valor dos Produtos",
            "IPI", "PIS", "COFINS", "ICMS", "ICMS ST",
            "VALOR TOTAL DA NOTA"
        ],
        "Valor (R$)": [
            vProd, vIPI, vPIS, vCOFINS, vICMS, vICMSST,
            vNF_saida
        ]
    }

    df_saida1 = pd.DataFrame(dados_saida1)
    st.dataframe(df_saida1)
    
    st.markdown(f"### 💰 **Total da Nota: R$ {vNF_saida:,.2f}**")

    excel_bytes = gerar_excel(df_saida1, "Saida1")
    st.download_button(
        label="💾 Baixar resumo Saída 1 (Excel)",
        data=excel_bytes,
        file_name="resumo_saida1.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------------- SAÍDA 2 (LOTE) ----------------------
st.header("3️⃣ Lote de Saída 2 (múltiplos XMLs)")
xml_saida2 = st.file_uploader("Faça upload dos XMLs da Saída 2 (vários arquivos):", type="xml", accept_multiple_files=True, key="saida2")

if xml_saida2:
    consolidado = defaultdict(lambda: {"vProd":0, "IPI":0, "PIS":0, "COFINS":0, "ICMS":0, "ICMSST":0, "vNF":0})
    
    for arquivo in xml_saida2:
        root, ns = ler_xml_conteudo(arquivo)
        total = root.find(".//ns:ICMSTot", ns)

        vProd = float(extrair_texto(total, "ns:vProd", ns))
        vIPI = float(extrair_texto(total, "ns:vIPI", ns))
        vPIS = float(extrair_texto(total, "ns:vPIS", ns))
        vCOFINS = float(extrair_texto(total, "ns:vCOFINS", ns))
        vICMS = float(extrair_texto(total, "ns:vICMS", ns))
        vICMSST = float(extrair_texto(total, "ns:vST", ns))
        vNF = float(extrair_texto(total, "ns:vNF", ns))

        xPed_tag = root.find(".//ns:xPed", ns)
        if xPed_tag is not None and xPed_tag.text:
            num_pedido = xPed_tag.text.strip()  # número de pedido completo
        else:
            num_pedido = "N/A"

        consolidado[num_pedido]["vProd"] += vProd
        consolidado[num_pedido]["IPI"] += vIPI
        consolidado[num_pedido]["PIS"] += vPIS
        consolidado[num_pedido]["COFINS"] += vCOFINS
        consolidado[num_pedido]["ICMS"] += vICMS
        consolidado[num_pedido]["ICMSST"] += vICMSST
        consolidado[num_pedido]["vNF"] += vNF

    df_saida2 = pd.DataFrame([
        {"Pedido": ped,
         "Produtos": val["vProd"],
         "IPI": val["IPI"],
         "PIS": val["PIS"],
         "COFINS": val["COFINS"],
         "ICMS": val["ICMS"],
         "ICMS ST": val["ICMSST"],
         "Total da Nota": val["vNF"]}
        for ped, val in consolidado.items()
    ])

    st.dataframe(df_saida2)

    total_geral = df_saida2[["Produtos","IPI","PIS","COFINS","ICMS","ICMS ST","Total da Nota"]].sum()
    total_df = pd.DataFrame(total_geral).T
    total_df.index = ["TOTAL GERAL"]

    st.subheader("🧮 Total Geral do Lote")
    st.dataframe(total_df)

    # Exportação Excel
    excel_bytes = gerar_excel(df_saida2, "Saida2_Lote")
    st.download_button(
        label="💾 Baixar resumo Saída 2 (Excel)",
        data=excel_bytes,
        file_name="resumo_saida2_lote.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
