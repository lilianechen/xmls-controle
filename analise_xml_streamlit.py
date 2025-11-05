import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import re
from collections import defaultdict
from io import BytesIO
from decimal import Decimal

st.set_page_config(page_title="Leitor de XML - Importação e Saídas", layout="centered")

st.title("📦 Leitor de XMLs - Entrada e Saídas de Importação")

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
xml_entrada = st.file_uploader("Faça upload do XML de entrada (importação):", type="xml", key="entrada")

if xml_entrada:
    root, ns = ler_xml_conteudo(xml_entrada)
    total = root.find(".//ns:ICMSTot", ns)
    
    vProd = float(extrair_texto(total, "ns:vProd", ns))
    vIPI = float(extrair_texto(total, "ns:vIPI", ns))
    vPIS = float(extrair_texto(total, "ns:vPIS", ns))
    vCOFINS = float(extrair_texto(total, "ns:vCOFINS", ns))
    vICMS = float(extrair_texto(total, "ns:vICMS", ns))
    vOutro = float(extrair_texto(total, "ns:vOutro", ns))

    # AFRMM (somar se houver vários) - com Decimal para melhor precisão
    afrmm_total = Decimal(0)
    for v in root.findall(".//ns:vAFRMM", ns):
        afrmm_total += Decimal(v.text)
    afrmm_total = float(afrmm_total)

    # Taxa Siscomex (extraída via regex de infAdic)
    inf_cpl = root.find(".//ns:infCpl", ns)
    taxa_siscomex = 0
    if inf_cpl is not None and inf_cpl.text:
        match = re.search(r"([\d,]+\.\d{2})", inf_cpl.text)
        if match:
            taxa_siscomex = float(match.group(1).replace(",", ""))

    # Extrair valor total da nota
    vNF = float(extrair_texto(total, "ns:vNF", ns))

    dados_entrada = {
        "Imposto / Taxa": [
            "Valor dos Produtos", "AFRMM", "Taxa Siscomex",
            "IPI", "PIS", "COFINS", "ICMS", "Outros",
            "VALOR TOTAL DA NOTA"
        ],
        "Valor (R$)": [
            vProd, afrmm_total, taxa_siscomex,
            vIPI, vPIS, vCOFINS, vICMS, vOutro,
            vNF
        ]
    }

    df_entrada = pd.DataFrame(dados_entrada)
    st.dataframe(df_entrada)
    
    st.markdown(f"### 💰 **Total da Nota: R$ {vNF:,.2f}**")

    excel_bytes = gerar_excel(df_entrada, "Entrada")
    st.download_button(
        label="💾 Baixar resumo de entrada (Excel)",
        data=excel_bytes,
        file_name="resumo_entrada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

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
    consolidado = defaultdict(lambda: {"vProd":0, "IPI":0, "PIS":0, "COFINS":0, "ICMS":0, "ICMSST":0})
    
    for arquivo in xml_saida2:
        root, ns = ler_xml_conteudo(arquivo)
        total = root.find(".//ns:ICMSTot", ns)

        vProd = float(extrair_texto(total, "ns:vProd", ns))
        vIPI = float(extrair_texto(total, "ns:vIPI", ns))
        vPIS = float(extrair_texto(total, "ns:vPIS", ns))
        vCOFINS = float(extrair_texto(total, "ns:vCOFINS", ns))
        vICMS = float(extrair_texto(total, "ns:vICMS", ns))
        vICMSST = float(extrair_texto(total, "ns:vST", ns))

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

    df_saida2 = pd.DataFrame([
        {"Pedido": ped,
         "Produtos": val["vProd"],
         "IPI": val["IPI"],
         "PIS": val["PIS"],
         "COFINS": val["COFINS"],
         "ICMS": val["ICMS"],
         "ICMS ST": val["ICMSST"]}
        for ped, val in consolidado.items()
    ])

    st.dataframe(df_saida2)

    total_geral = df_saida2[["Produtos","IPI","PIS","COFINS","ICMS","ICMS ST"]].sum()
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
