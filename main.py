import streamlit as st
import math
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
from fpdf import FPDF
import tempfile
import os

st.set_page_config(page_title="KKS Systemplanung", layout="wide")

# Projektinformationen
st.title("🛠️ Planungshilfe für KKS-Fremdstromanlagen")
projektname = st.text_input("📁 Projektname")
datum = st.date_input("📅 Datum")

st.markdown("Dieses Tool berechnet die benötigte Anzahl an **APWRHUBs**, organisiert die Kanalverteilung und berechnet den Spannungsabfall entlang der Leitung auf Basis von Leitungsquerschnitt und Streckenlängen.")

# Eingabe: Anzahl der Anodenanschlüsse
anoden_total = st.number_input("🔌 Anzahl der Anodenanschlüsse", min_value=1, step=1)
leitung_querschnitt = st.number_input("📏 Hybridleitungsquerschnitt (in mm²)", min_value=0.1, step=0.1)

# Konstanten
leitfaehigkeit_kupfer = 56  # in m/(Ohm*mm²)
anschluesse_pro_hub = 4 * 2  # 4 Kanäle à 2 Anschlüsse
anzahl_hubs = math.ceil(anoden_total / anschluesse_pro_hub)

st.markdown(f"### 🔢 Benötigte Anzahl APWRHUBs: **{anzahl_hubs}**")

# Initialisierung
anoden_counter = 1
hub_stroeme = []
hub_distanzen = []

st.markdown("### 📋 Verteilung der Anodenanschlüsse auf APWRHUBs")

for hub_index in range(1, anzahl_hubs + 1):
    with st.expander(f"📦 APWRHUB {hub_index}", expanded=True):
        cols = st.columns(4)
        hub_strom = 0

        for ch in range(1, 5):  # 4 Channels
            with cols[ch - 1]:
                st.markdown(f"**CH{ch}**")
                for anschluss in range(1, 3):  # 2 Anschlüsse pro Channel
                    if anoden_counter <= anoden_total:
                        label = f"CH{ch}-{anschluss} (Anode {anoden_counter})"
                        value = st.number_input(f"{label} [mA]", min_value=0, max_value=625, step=1, key=f"{hub_index}_{ch}_{anschluss}")
                        hub_strom += value
                        anoden_counter += 1
                    else:
                        st.markdown("_nicht belegt_")

        hub_stroeme.append(hub_strom)

        # Abstand zum vorherigen Abschnitt
        if hub_index == 1:
            distanz = st.number_input(f"Abstand von APWRLINK zu HUB {hub_index} (m)", min_value=0.0, step=0.1, key=f"dist_{hub_index}")
        else:
            distanz = st.number_input(f"Abstand von HUB {hub_index - 1} zu HUB {hub_index} (m)", min_value=0.0, step=0.1, key=f"dist_{hub_index}")

        hub_distanzen.append(distanz)

# Berechnungen
cumulative_current = 0  # in mA
cumulative_voltage = 0.0  # in V
spannungsabfall_liste = []
spannung_kumuliert_liste = []
spannungsabfall_mV = []
spannungsabfall_prozent = []
leitungswiderstaende = []

max_erlaubter_spannungsabfall = 2.0  # Realistischer Grenzwert in Volt

for i in range(anzahl_hubs):
    strom_A = (cumulative_current + hub_stroeme[i]) / 1000  # in A
    laenge = hub_distanzen[i]  # in m
    querschnitt = leitung_querschnitt  # in mm²

    if i == 0:
        leitungswiderstand = 0.0
        spannungsabfall = 0.0
    else:
        leitungswiderstand = (2 * laenge) / (leitfaehigkeit_kupfer * querschnitt)
        spannungsabfall = leitungswiderstand * strom_A

    cumulative_current += hub_stroeme[i]
    cumulative_voltage += spannungsabfall

    leitungswiderstaende.append(leitungswiderstand)
    spannungsabfall_liste.append(spannungsabfall)
    spannung_kumuliert_liste.append(cumulative_voltage)
    spannungsabfall_mV.append(cumulative_voltage * 1000)
    spannungsabfall_prozent.append((cumulative_voltage / max_erlaubter_spannungsabfall) * 100)

if cumulative_voltage > max_erlaubter_spannungsabfall:
    st.warning(f"⚠️ Der maximale empfohlene Spannungsabfall von {max_erlaubter_spannungsabfall} V wurde überschritten! Gesamt: {cumulative_voltage:.2f} V")

# Tabelle
st.markdown("#### 📄 Übersichtstabelle")
df = pd.DataFrame({
    "HUB": list(range(1, anzahl_hubs + 1)),
    "Strom (mA)": hub_stroeme,
    "Abstand (m)": hub_distanzen,
    "Widerstand (Ohm)": leitungswiderstaende,
    "Spannungsabfall (V)": spannungsabfall_liste,
    "Spannung bis HUB (V)": spannung_kumuliert_liste,
    "Spannung bis HUB (mV)": spannungsabfall_mV,
    "Spannung bis HUB (%)": spannungsabfall_prozent
})

st.dataframe(df.style.format({
    "Widerstand (Ohm)": "{:.4f}",
    "Spannungsabfall (V)": "{:.4f}",
    "Spannung bis HUB (V)": "{:.4f}",
    "Spannung bis HUB (mV)": "{:.1f}",
    "Spannung bis HUB (%)": "{:.2f}"
}))

# Excel Export
excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
    df.to_excel(writer, index=False)

st.download_button(
    label="📥 Tabelle als Excel-Datei herunterladen",
    data=excel_buffer.getvalue(),
    file_name="spannungsabfall_apwr.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# PDF Export mit Logo und Tabellenlayout
class CustomPDF(FPDF):
    def header(self):
        if os.path.exists("A LOGO11052020 Hochkant.png"):
            self.image("A LOGO11052020 Hochkant.png", x=165, y=8, w=30)
        self.set_font("Arial", 'B', 12)
        self.set_text_color(60, 60, 60)
        self.cell(0, 10, f"Projekt: {projektname}", ln=True)
        self.cell(0, 10, f"Datum: {datum}", ln=True)
        self.ln(5)

pdf = CustomPDF()
pdf.add_page()
pdf.set_font("Arial", 'B', 11)
pdf.set_fill_color(160, 213, 214)  # Tabellenüberschrift
pdf.set_text_color(60, 60, 60)
pdf.set_draw_color(44, 181, 174)   # Rahmenfarbe

col_widths = [12, 25, 25, 30, 30, 30, 28]
headers = ["HUB", "Strom (mA)", "Abstand (m)", "Widerstand (Ohm)", "U (V)", "U (mV)", "U (%)"]
for i, header in enumerate(headers):
    pdf.cell(col_widths[i], 8, header, 1, 0, 'C', fill=True)
pdf.ln()

pdf.set_font("Arial", '', 10)
for i, row in df.iterrows():
    pdf.cell(col_widths[0], 8, str(int(row['HUB'])), 1)
    pdf.cell(col_widths[1], 8, f"{row['Strom (mA)']:.0f}", 1)
    pdf.cell(col_widths[2], 8, f"{row['Abstand (m)']:.1f}", 1)
    pdf.cell(col_widths[3], 8, f"{row['Widerstand (Ohm)']:.4f}", 1)
    pdf.cell(col_widths[4], 8, f"{row['Spannungsabfall (V)']:.4f}", 1)
    pdf.cell(col_widths[5], 8, f"{row['Spannung bis HUB (mV)']:.0f}", 1)
    pdf.cell(col_widths[6], 8, f"{row['Spannung bis HUB (%)']:.1f}", 1)
    pdf.ln()

with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
    pdf.output(tmp_pdf.name)
    st.download_button(
        label="📄 PDF-Bericht herunterladen",
        data=open(tmp_pdf.name, "rb").read(),
        file_name=f"Spannungsabfall_{projektname.replace(' ', '_')}_{datum}.pdf",
        mime="application/pdf"
    )

# Diagramm
st.markdown("#### 📉 Spannungsverlauf (mV / %)")

x_labels = ["APWRLINK"] + [f"HUB {i}" for i in range(1, anzahl_hubs + 1)]
fig = go.Figure()

fig.add_trace(go.Scatter(x=x_labels, y=[0] + spannungsabfall_mV, name="Spannung (mV)", yaxis="y1", mode='lines+markers'))
fig.add_trace(go.Scatter(x=x_labels, y=[0] + spannungsabfall_prozent, name="Spannung (%)", yaxis="y2", mode='lines+markers'))

fig.update_layout(
    title="Verlauf des Spannungsabfalls entlang der Leitung",
    xaxis=dict(title="Position (APWRLINK → Hubs)"),
    yaxis=dict(title="Spannung (mV)", side="left", showgrid=False),
    yaxis2=dict(title="Spannung (%)", overlaying="y", side="right"),
    legend=dict(x=0.01, y=0.99),
    margin=dict(l=50, r=50, t=50, b=50)
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.info("Der Spannungsabfall wird aus dem spezifischen Widerstand berechnet: R = 2 · l / (κ · A), U = R · I")
