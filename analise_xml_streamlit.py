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

st.set_page_config(page_title="Leitor de XML - DI", layout="wide")

st.title("📦 Leitor de XMLs - Declaração de Importação")
st.markdown("**v2.3** - Com reconciliação de valores vs PDF")

# ---------------------- FUNÇÕES AUXILIARES ----------------------

def extrair_texto(elemento, caminho, ns=None, default="0"):
    """Retorna o valor do nó se existir"""
    if ns:
        el = elemento.find(caminho, ns)
    else:
        el = elemento.find(caminho)
    return el.text if el is not None else default

def ler_xml_di(uploaded_file):
    """Carrega e parseia o XML da DI"""
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    return root

def gerar_excel(df, nome_planilha="Resumo"):
    """Cria arquivo Excel em memória para download"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=nome_planilha)
    return output.getvalue()

def reconciliar_valores(xml_value, pdf_value, tolerancia=0.10):
    """
    Compara valores do XML com PDF e indica se estão dentro da tolerância
    Tolerância padrão: R$ 0,10
    """
    diferenca = abs(xml_value - pdf_value)
    
    if diferenca < tolerancia:
        status = "✅ OK"
        cor = "green"
    elif diferenca < 1.0:
        status = "⚠️ Margem"
        cor = "orange"
    else:
        status = "❌ Diferença"
        cor = "red"
    
    return {
        "status": status,
        "cor": cor,
        "diferenca": diferenca,
        "percentual": (diferenca / pdf_value * 100) if pdf_value > 0 else 0
    }

# ---------------------- ENTRADA ----------------------

st.header("1️⃣ Leitura da Declaração de Importação (DI)")

xml_di = st.file_uploader("📋 Upload do XML da DI:", type="xml", key="di")

if xml_di:
    root_di = ler_xml_di(xml_di)
    
    # Encontrar a declaração
    declaracao = root_di.find('.//declaracaoImportacao')
    
    if declaracao is not None:
        # Extrair informações gerais
        numero_di = declaracao.findtext('numeroDI', 'N/A')
        modalidade = declaracao.findtext('modalidadeDespachoNome', 'N/A')
        tipo_declaracao = declaracao.findtext('tipoDeclaracaoNome', 'N/A')
        total_adicoes = int(declaracao.findtext('totalAdicoes', '0'))
        
        st.success(f"✅ DI **{numero_di}** carregada com sucesso!")
        
        # Exibir informações gerais
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Número DI", numero_di)
        with col2:
            st.metric("Modalidade", modalidade)
        with col3:
            st.metric("Tipo", tipo_declaracao)
        with col4:
            st.metric("Total de Adições", total_adicoes)
        
        st.divider()
        
        # ===== PROCESSAR ADIÇÕES =====
        adicoes = declaracao.findall('.//adicao')
        
        if adicoes:
            # Inicializar totalizadores com Decimal para máxima precisão
            total_valor_reais = Decimal(0)
            total_valor_moeda = Decimal(0)
            total_frete_reais = Decimal(0)
            total_frete_moeda = Decimal(0)
            total_ipi = Decimal(0)
            total_pis = Decimal(0)
            total_cofins = Decimal(0)
            total_ii = Decimal(0)
            
            # Dados para tabela de adições
            dados_adicoes = []
            
            # Processar cada adição
            for idx, adicao in enumerate(adicoes, 1):
                valor_reais = Decimal(adicao.findtext('condicaoVendaValorReais', '0') or '0')
                valor_moeda = Decimal(adicao.findtext('condicaoVendaValorMoeda', '0') or '0')
                frete_reais = Decimal(adicao.findtext('freteValorReais', '0') or '0')
                frete_moeda = Decimal(adicao.findtext('freteValorMoedaNegociada', '0') or '0')
                ipi = Decimal(adicao.findtext('ipiAliquotaValorRecolher', '0') or '0')
                pis = Decimal(adicao.findtext('pisPasepAliquotaValorRecolher', '0') or '0')
                cofins = Decimal(adicao.findtext('cofinsAliquotaValorRecolher', '0') or '0')
                ii = Decimal(adicao.findtext('iiAliquotaValorRecolher', '0') or '0')
                ncm = adicao.findtext('dadosMercadoriaCodigoNcm', 'N/A')
                
                # Acumular
                total_valor_reais += valor_reais
                total_valor_moeda += valor_moeda
                total_frete_reais += frete_reais
                total_frete_moeda += frete_moeda
                total_ipi += ipi
                total_pis += pis
                total_cofins += cofins
                total_ii += ii
                
                dados_adicoes.append({
                    "Adição": idx,
                    "NCM": ncm,
                    "Valor R$": round(float(valor_reais / 100), 2),
                    "Valor USD": round(float(valor_moeda / 100), 2),
                    "Frete R$": round(float(frete_reais / 100), 2),
                    "IPI": round(float(ipi / 100), 2),
                    "PIS": round(float(pis / 100), 2),
                    "COFINS": round(float(cofins / 100), 2),
                    "II": round(float(ii / 100), 2)
                })
            
            # Converter totais para reais com 2 casas decimais
            valor_reais_total = round(float(total_valor_reais / 100), 2)
            valor_moeda_total = round(float(total_valor_moeda / 100), 2)
            frete_reais_total = round(float(total_frete_reais / 100), 2)
            frete_moeda_total = round(float(total_frete_moeda / 100), 2)
            ipi_total = round(float(total_ipi / 100), 2)
            pis_total = round(float(total_pis / 100), 2)
            cofins_total = round(float(total_cofins / 100), 2)
            ii_total = round(float(total_ii / 100), 2)
            
            # Taxa de câmbio
            taxa_cambial = valor_reais_total / valor_moeda_total if valor_moeda_total > 0 else 0
            
            # Exibir tabela de adições
            st.subheader("📊 Detalhamento das Adições")
            df_adicoes = pd.DataFrame(dados_adicoes)
            st.dataframe(df_adicoes, use_container_width=True)
            
            # Exibir totalizações
            st.subheader("💰 Resumo de Totalizações")
            
            cols_resumo = st.columns(4)
            with cols_resumo[0]:
                st.metric("Valor Total (R$)", f"R$ {valor_reais_total:,.2f}")
            with cols_resumo[1]:
                st.metric("Frete Total (R$)", f"R$ {frete_reais_total:,.2f}")
            with cols_resumo[2]:
                st.metric("Taxa de Câmbio", f"1 USD = R$ {taxa_cambial:.4f}")
            with cols_resumo[3]:
                st.metric("Total de Tributos", f"R$ {ipi_total + pis_total + cofins_total + ii_total:,.2f}")
            
            st.divider()
            
            # ===== SEÇÃO DE RECONCILIAÇÃO COM PDF =====
            st.subheader("🔍 Reconciliação com Valores do PDF")
            
            col_info = st.info(
                "📌 Os valores do PDF devem ser inseridos manualmente para comparação. "
                "Pequenas variações de centavos são normais e resultam de arredondamentos em múltiplas adições.",
                icon="ℹ️"
            )
            
            col_rec1, col_rec2 = st.columns(2)
            
            with col_rec1:
                st.markdown("### Valores Extraídos do XML")
                st.write(f"**II (Imposto Importação):** R$ {ii_total:,.2f}")
                st.write(f"**IPI:** R$ {ipi_total:,.2f}")
                st.write(f"**PIS:** R$ {pis_total:,.2f}")
                st.write(f"**COFINS:** R$ {cofins_total:,.2f}")
            
            with col_rec2:
                st.markdown("### Valores do PDF (para comparação)")
                pdf_ii = st.number_input("II (Imposto Importação) do PDF", value=0.0, format="%.2f", key="pdf_ii")
                pdf_ipi = st.number_input("IPI do PDF", value=0.0, format="%.2f", key="pdf_ipi")
                pdf_pis = st.number_input("PIS do PDF", value=0.0, format="%.2f", key="pdf_pis")
                pdf_cofins = st.number_input("COFINS do PDF", value=0.0, format="%.2f", key="pdf_cofins")
            
            if pdf_ii > 0 or pdf_ipi > 0 or pdf_pis > 0 or pdf_cofins > 0:
                st.divider()
                st.markdown("### 📋 Resultado da Reconciliação")
                
                reconciliacoes = {
                    "II": reconciliar_valores(ii_total, pdf_ii),
                    "IPI": reconciliar_valores(ipi_total, pdf_ipi),
                    "PIS": reconciliar_valores(pis_total, pdf_pis),
                    "COFINS": reconciliar_valores(cofins_total, pdf_cofins)
                }
                
                cols_rec = st.columns(4)
                for idx, (campo, rec) in enumerate(reconciliacoes.items()):
                    with cols_rec[idx]:
                        st.metric(
                            campo,
                            f"{rec['status']}",
                            delta=f"Δ R$ {rec['diferenca']:.2f} ({rec['percentual']:.4f}%)"
                        )
                
                # Tabela de reconciliação
                st.markdown("### Tabela de Comparação")
                dados_reconciliacao = {
                    "Tributo": ["II", "IPI", "PIS", "COFINS"],
                    "XML": [ii_total, ipi_total, pis_total, cofins_total],
                    "PDF": [pdf_ii, pdf_ipi, pdf_pis, pdf_cofins],
                    "Diferença": [
                        reconciliacoes["II"]["diferenca"],
                        reconciliacoes["IPI"]["diferenca"],
                        reconciliacoes["PIS"]["diferenca"],
                        reconciliacoes["COFINS"]["diferenca"]
                    ],
                    "Status": [
                        reconciliacoes["II"]["status"],
                        reconciliacoes["IPI"]["status"],
                        reconciliacoes["PIS"]["status"],
                        reconciliacoes["COFINS"]["status"]
                    ]
                }
                
                df_reconciliacao = pd.DataFrame(dados_reconciliacao)
                st.dataframe(df_reconciliacao, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # ===== EXPORTAÇÃO =====
            st.subheader("📥 Exportar Dados")
            
            # Preparar dados para Excel
            dados_exportacao = {
                "Campo": [
                    "Valor Produtos (R$)",
                    "Frete (R$)",
                    "IPI",
                    "PIS",
                    "COFINS",
                    "II (Imposto Importação)",
                    "Total de Tributos"
                ],
                "Valor": [
                    valor_reais_total,
                    frete_reais_total,
                    ipi_total,
                    pis_total,
                    cofins_total,
                    ii_total,
                    ipi_total + pis_total + cofins_total + ii_total
                ]
            }
            
            df_exportacao = pd.DataFrame(dados_exportacao)
            excel_bytes = gerar_excel(df_exportacao, "DI_Resumo")
            
            col_export1, col_export2 = st.columns(2)
            with col_export1:
                st.download_button(
                    label="💾 Baixar Resumo (Excel)",
                    data=excel_bytes,
                    file_name=f"di_{numero_di}_resumo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col_export2:
                # Exportar tabela completa de adições
                excel_addicoes = gerar_excel(df_adicoes, "Adições")
                st.download_button(
                    label="📋 Baixar Detalhes das Adições",
                    data=excel_addicoes,
                    file_name=f"di_{numero_di}_adicoes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.warning("⚠️ Nenhuma adição encontrada no XML da DI")
    else:
        st.error("❌ Arquivo XML não possui estrutura válida de DI")
else:
    st.info("👈 Carregue um arquivo XML de Declaração de Importação para começar")
