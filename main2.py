import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from PIL import Image
import os
import numpy as np
from datetime import datetime
import matplotlib.ticker as ticker
from matplotlib.backends.backend_pdf import PdfPages

# === Corporate Design Colors ===
CORP_GRAY = "#3C3C3C"
CORP_LIGHT_BLUE = "#ABD4D5"
CORP_DARK_BLUE = "#5AB2AD"

# === Technical Constants ===
COPPER_RESISTIVITY = 0.0175  # Ohm·mm²/m
ANODES_PER_HUB = 8
DEFAULT_ANODES = 24
DEFAULT_CURRENT_PER_ANODE = 625  # mA
DEFAULT_CABLE_AREA = 4.0  # mm²
DEFAULT_DISTANCE = 10.0  # m
LINK_VOLTAGE = 48.0  # V
DEFAULT_MIN_VOLTAGE = 36.0  # V
DEFAULT_MAX_LINK_CURRENT = 10.0  # A (as Float)

# === Streamlit Style Customization ===
st.set_page_config(page_title="Voltage Drop Tool", layout="wide")

# Function to add company logo at the top right
def add_logo():
    # Check if logo file exists
    if os.path.exists("logo.png"):
        logo = Image.open("logo.png")
        
        # Display logo in the top right corner using custom HTML/CSS
        logo_bytes = BytesIO()
        logo.save(logo_bytes, format="PNG")
        logo_base64 = base64.b64encode(logo_bytes.getvalue()).decode()
        
        st.markdown(
            f"""
            <style>
            .logo-container {{
                position: absolute;
                top: 0.5rem;
                right: 1rem;
                z-index: 1000;
                height: 8vh;
                max-height: 80px;
                min-height: 40px;
            }}
            .logo-img {{
                height: 100%;
                width: auto;
            }}
            </style>
            
            <div class="logo-container">
                <img class="logo-img" src="data:image/png;base64,{logo_base64}" alt="ActiveControl Logo">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        print("Logo file not found. Please save logo.png in the same directory as the script.")

# Function to get the logo as a pillow image (for PDF export)
def get_logo_image():
    # Load logo from local file
    if os.path.exists("logo.png"):
        return Image.open("logo.png")
    else:
        print("Logo file not found for export. Please save logo.png in the same directory as the script.")
        return None

# PDF Export Function
def create_pdf_download_link(all_plots, df, filename, link_text, project_info, hub_data, system_params, results):
    # Create PDF in memory
    buf = BytesIO()
    
    with PdfPages(buf) as pdf:
        # First page with project information
        fig_info = plt.figure(figsize=(8.5, 11), facecolor=CORP_GRAY)
        ax_info = fig_info.add_subplot(111)
        ax_info.axis('off')
        
        # Add title
        ax_info.text(0.5, 0.95, "APWRLINK / APWRHUB Voltage Drop Analysis", 
                   ha='center', va='top', color=CORP_LIGHT_BLUE, fontsize=18, fontweight='bold')
        
        # Calculate per-APWRLINK currents
        link_currents = {}
        for result in results:
            link_id = result["APWRLINK"]
            if link_id not in link_currents:
                # Find the first row for this APWRLINK
                link_current = next((r["Current [A]"] for r in results if r["APWRLINK"] == link_id and r["From"] == "APWRLINK"), 0)
                link_currents[link_id] = link_current
        
        # Add project information
        info_text = (
            f"Project Name: {project_info['name']}\n"
            f"Project Number: {project_info['number']}\n"
            f"Date: {project_info['date']}\n"
            f"Protection Zone: {project_info['zone']}\n\n"
            f"System Parameters:\n"
            f"Total Anodes: {system_params['total_anodes']}\n"
            f"Current per Anode: {system_params['current_per_anode']} mA\n"
            f"Cable Cross-Section: {system_params['cable_area']} mm²\n"
            f"Reference Voltage: {system_params['reference_voltage']} V\n"
            f"Minimum Working Voltage: {system_params['min_voltage']} V\n"
            f"Maximum APWRLINK Current: {system_params['max_link_current']} A\n"
            f"Total APWRHUBs: {system_params['num_hubs']}\n\n"
            f"APWRHUB Configuration:\n"
        )
        
        for hub in hub_data:
            info_text += f"• {hub['hub_name']} - {hub['link_id']}: Current: {hub['current_mA']} mA, Distance: {hub['distance']} m\n"
        
        # Add system status
        total_current_A = sum(hub["current_mA"] for hub in hub_data) / 1000
        min_voltage = min([row["Remaining Voltage [V]"] for row in results])
        max_drop_percent = max([row["∆Voltage [%]"] for row in results])
        max_drop_mV = max([row["Cumulative ∆Voltage [mV]"] for row in results])
        
        info_text += f"\nSystem Status:\n"
        info_text += f"Total System Current: {total_current_A:.3f} A\n"
        info_text += f"Lowest Voltage Point: {min_voltage:.2f} V\n"
        info_text += f"Maximum ∆Voltage: {max_drop_mV:.1f} mV ({max_drop_percent:.2f}%)\n\n"
        
        # APWRLINK current status
        info_text += f"APWRLINK Current Status:\n"
        for link_id, current in link_currents.items():
            info_text += f"• {link_id}: {current:.2f} A"
            if current > system_params['max_link_current']:
                info_text += f" (EXCEEDS {system_params['max_link_current']} A LIMIT!)"
            info_text += "\n"
        
        if min_voltage < system_params['min_voltage']:
            problem_nodes = [row["To"] for row in results if row["Remaining Voltage [V]"] < system_params['min_voltage']]
            info_text += f"\nWARNING: Voltage below minimum ({system_params['min_voltage']} V) at: {', '.join(problem_nodes)}\n"
        
        overloaded_links = [link_id for link_id, current in link_currents.items() if current > system_params['max_link_current']]
        if overloaded_links:
            for link_id in overloaded_links:
                current = link_currents[link_id]
                info_text += f"\nWARNING: {link_id} current ({current:.2f} A) exceeds maximum ({system_params['max_link_current']} A)!\n"
        
        ax_info.text(0.1, 0.85, info_text, va='top', color='white', fontsize=10, linespacing=1.5)
        
        # Add logo to the info page
        logo_img = get_logo_image()
        if logo_img:
            logo_ax = fig_info.add_axes([0.75, 0.9, 0.2, 0.1], anchor='NE', zorder=10)
            logo_ax.imshow(np.asarray(logo_img))
            logo_ax.axis('off')
        
        pdf.savefig(fig_info)
        plt.close(fig_info)
        
        # Add all plot figures
        for fig in all_plots:
            # Add logo to each figure
            if logo_img and not any(ax.get_title() == 'logo' for ax in fig.axes):
                logo_ax = fig.add_axes([0.85, 0.9, 0.15, 0.1], anchor='NE', zorder=10)
                logo_ax.imshow(np.asarray(logo_img))
                logo_ax.axis('off')
                logo_ax.set_title('logo')  # Mark this axis as the logo
            
            pdf.savefig(fig)
        
        # Add table pages
        if not df.empty:
            # Split the dataframe into chunks if it's too large
            max_rows_per_page = 20
            total_pages = math.ceil(len(df) / max_rows_per_page)
            
            for page in range(total_pages):
                start_idx = page * max_rows_per_page
                end_idx = min((page + 1) * max_rows_per_page, len(df))
                
                df_page = df.iloc[start_idx:end_idx].copy()
                
                # Create a figure for the table
                fig_table = plt.figure(figsize=(11, 8.5), facecolor=CORP_GRAY)
                ax_table = fig_table.add_subplot(111)
                ax_table.axis('off')
                
                # Add title
                page_title = f"Voltage Drop Analysis - Data Table (Page {page+1}/{total_pages})"
                ax_table.text(0.5, 0.97, page_title, ha='center', color=CORP_LIGHT_BLUE, fontsize=14, fontweight='bold')
                
                # Convert the dataframe to a table
                table_data = [df_page.columns.tolist()] + df_page.values.tolist()
                table = ax_table.table(
                    cellText=table_data,
                    loc='center',
                    cellLoc='center',
                    colWidths=[0.12] * len(df_page.columns)
                )
                
                # Style the table
                table.auto_set_font_size(False)
                table.set_fontsize(8)
                table.scale(1, 1.5)  # Adjust the height of rows
                
                # Apply custom styling
                for key, cell in table.get_celld().items():
                    row, col = key
                    if row == 0:  # Header row
                        cell.set_facecolor(CORP_DARK_BLUE)
                        cell.set_text_props(color='white', fontweight='bold')
                    else:  # Data rows
                        cell.set_facecolor(CORP_GRAY)
                        cell.set_text_props(color='white')
                    cell.set_edgecolor('white')
                
                # Add logo
                if logo_img:
                    logo_ax = fig_table.add_axes([0.85, 0.97, 0.15, 0.1], anchor='NE', zorder=10)
                    logo_ax.imshow(np.asarray(logo_img))
                    logo_ax.axis('off')
                
                pdf.savefig(fig_table)
                plt.close(fig_table)
    
    buf.seek(0)
    
    b64 = base64.b64encode(buf.read()).decode()
    # Add the pdf-button class
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}" class="download-button pdf-button">{link_text}</a>'
    return href

# === Calculation Functions ===
def calculate_resistance(length_m, area_mm2):
    return (COPPER_RESISTIVITY * length_m) / area_mm2

def calculate_current(hub_list, start_index):
    return sum(hub["current_mA"] for hub in hub_list[start_index:]) / 1000  # Convert to A

# Call the function to add the logo
add_logo()

# Add padding for the title to avoid overlap with logo
st.markdown(
    """
    <style>
    .title-padding {
        padding-top: 2.5rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <style>
        body {{
            background-color: {CORP_GRAY};
            color: white;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .block-container {{
            background-color: {CORP_GRAY};
            padding-top: 1rem;
        }}
        h1, h2, h3, h4 {{
            color: {CORP_LIGHT_BLUE};
        }}
        .stButton>button {{
            background-color: {CORP_DARK_BLUE};
            color: white;
            border-radius: 5px;
            transition: all 0.3s;
        }}
        .stButton>button:hover {{
            background-color: {CORP_LIGHT_BLUE};
            color: {CORP_GRAY};
        }}
        .stNumberInput input, .stDateInput input, .stTextInput input {{
            background-color: {CORP_LIGHT_BLUE};
            color: black;
            border-radius: 5px;
        }}
        /* Table styling */
        .dataframe {{
            color: white !important;
        }}
        .dataframe th {{
            background-color: {CORP_DARK_BLUE} !important;
            color: white !important;
            font-weight: bold !important;
        }}
        .dataframe td {{
            background-color: {CORP_GRAY} !important;
            color: white !important;
        }}
        div[data-testid="stDataFrameResizable"] {{
            background-color: {CORP_GRAY} !important;
        }}
        div[data-testid="stHorizontalBlock"] {{
            background-color: {CORP_GRAY} !important;
        }}
        .stDataFrame div[data-testid="stTable"] {{
            color: white !important;
            background-color: {CORP_GRAY} !important;
        }}
        div[data-baseweb="select"] {{
            background-color: {CORP_LIGHT_BLUE} !important;
        }}
        div[data-baseweb="base-input"] {{
            background-color: {CORP_LIGHT_BLUE} !important;
        }}
        .stAlert[data-baseweb="notification"][data-kind="error"] {{
            background-color: {CORP_DARK_BLUE};
            color: white;
            border-left: 4px solid white;
        }}
        .stMultiSelect [data-baseweb="tag"] {{
            background-color: {CORP_DARK_BLUE} !important;
            color: white !important;
        }}
        .stMultiSelect [data-baseweb="tag"] svg {{
            fill: white !important;
        }}
        /* Extra styling for table pagination */
        button[kind="pageButton"] {{
            background-color: {CORP_DARK_BLUE} !important;
            color: white !important;
        }}
        /* Force text color for table */
        .stDataFrame {{
            color-scheme: dark !important;
        }}
        /* Download buttons */
        .download-button {{
            background-color: {CORP_DARK_BLUE};
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 5px;
            text-decoration: none !important;
            border: none;
            cursor: pointer;
            margin: 0.5rem;
            display: inline-block;
            font-weight: bold;
            transition: all 0.3s;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.2);
        }}
        .download-button:hover {{
            background-color: {CORP_LIGHT_BLUE};
            color: {CORP_GRAY};
            transform: translateY(-2px);
            box-shadow: 0px 4px 8px rgba(0,0,0,0.3);
        }}
        a.pdf-button {{
            color: #999999 !important;
            text-decoration: none !important;
        }}
        /* Project info section */
        .project-info {{
            background-color: rgba(171, 212, 213, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        /* Responsive design */
        @media (max-width: 768px) {{
            .download-button {{
                width: 100%;
                text-align: center;
                margin: 0.25rem 0;
            }}
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# === App Title ===
st.markdown('<div class="title-padding"></div>', unsafe_allow_html=True)
st.title("APWRLINK / APWRHUB Voltage Drop Analysis Tool")

# === Project Information ===
st.markdown("## Project Information")

# Create a form for project information
with st.container():
    st.markdown('<div class="project-info">', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        project_name = st.text_input("Project Name", value="")
        project_date = st.date_input("Date", value=datetime.now())
        
    with col2:
        project_number = st.text_input("Project Number", value="")
        protection_zone = st.text_input("Protection Zone", value="")
    
    st.markdown('</div>', unsafe_allow_html=True)

# === Introduction and System Parameters ===
st.markdown("""
## Tool Introduction

This tool calculates voltage drops in cathodic protection systems using APWRLINK and APWRHUB components. 
It helps engineers design and validate power distribution layouts for anode systems.

### System Parameters:
- **Input Voltage**: Each APWRLINK supplies 48V DC power
- **Minimum Working Voltage**: By default, APWRHUBs require at least 36V to operate correctly (can be adjusted)
- **Maximum Current per APWRLINK**: An APWRLINK can supply up to 10A (can be adjusted)
- **Copper Resistivity**: 0.0175 Ohm·mm²/m for cable resistance calculations
- **Standard Configuration**: Each APWRHUB supports up to 8 anodes
- **Current Limit**: Standard anode current is 625 mA
""")

# === Inputs ===
st.markdown("## System Configuration")
total_anodes = st.number_input("Total number of anode connections", min_value=1, value=DEFAULT_ANODES, step=1)
current_per_anode = st.number_input("Standard current per anode [mA]", min_value=1, value=DEFAULT_CURRENT_PER_ANODE, step=5)
cable_area = st.number_input("Hybrid cable cross-section [mm²]", min_value=0.1, value=DEFAULT_CABLE_AREA, step=0.1)
reference_voltage = st.number_input("Reference voltage for percentage calculations [V]", min_value=1.0, value=LINK_VOLTAGE, step=0.5)
min_voltage = st.number_input("Minimum working voltage for APWRHUBs [V]", min_value=1.0, value=DEFAULT_MIN_VOLTAGE, step=0.5)
max_link_current = st.number_input("Maximum current per APWRLINK [A]", min_value=1.0, value=DEFAULT_MAX_LINK_CURRENT, step=1.0)

num_hubs = math.ceil(total_anodes / ANODES_PER_HUB)
st.markdown(f"**Total APWRHUBs required:** {num_hubs}")

# Create project info dictionary for exports
project_info = {
    'name': project_name,
    'number': project_number,
    'date': project_date.strftime('%Y-%m-%d'),
    'zone': protection_zone
}

# Create system parameters dictionary for exports
system_params = {
    'total_anodes': total_anodes,
    'current_per_anode': current_per_anode,
    'cable_area': cable_area,
    'reference_voltage': reference_voltage,
    'min_voltage': min_voltage,
    'max_link_current': max_link_current,
    'num_hubs': num_hubs
}

# === APWRLINK Structure ===
with st.expander("APWRLINK Structure Definition", expanded=True):
    hub_names = [f"APWRHUB {i+1}" for i in range(num_hubs)]
    default_links = ["APWRHUB 1"]
    selected_link_starts = st.multiselect(
        "Select APWRHUBs where a new APWRLINK starts (APWRHUB 1 must be included):",
        options=hub_names,
        default=default_links
    )
    if "APWRHUB 1" not in selected_link_starts:
        st.error("APWRHUB 1 must be included.")
        st.stop()

link_assignments = []
current_link = 1
start_indices = sorted([hub_names.index(hub) for hub in selected_link_starts])
for i in range(num_hubs):
    if i in start_indices and i != 0:
        current_link += 1
    link_assignments.append(f"APWRLINK {current_link}")

# === APWRHUB Configuration ===
st.markdown("### APWRHUB Configuration")
hub_data = []
remaining_anodes = total_anodes

for i in range(num_hubs):
    hub_name = f"APWRHUB {i+1}"
    link = link_assignments[i]
    with st.expander(f"{hub_name} – {link}", expanded=False):
        distance = st.number_input(
            f"Distance from previous unit to {hub_name} [m]",
            min_value=0.0,
            value=DEFAULT_DISTANCE,
            step=0.5,
            key=f"dist_{i}"
        )

        manual_config = st.checkbox(f"Manually configure current per anode for {hub_name}?", key=f"manual_{i}")
        anodes_here = min(ANODES_PER_HUB, remaining_anodes)
        anode_currents = []

        if manual_config:
            for a in range(anodes_here):
                curr = st.number_input(
                    f"Current for anode {a+1} [mA]",
                    min_value=0,
                    max_value=625,
                    value=current_per_anode,
                    step=5,
                    key=f"curr_{i}_{a}"
                )
                anode_currents.append(curr)
        else:
            anode_currents = [current_per_anode] * anodes_here

        total_current = sum(anode_currents)
        st.markdown(f"**→ Total current for {hub_name}: {total_current:.1f} mA ({total_current/1000:.3f} A)**")

        hub_data.append({
            "hub_name": hub_name,
            "link_id": link,
            "distance": distance,
            "current_mA": total_current
        })

        remaining_anodes -= anodes_here

# === APWRLINK Parameters ===
st.markdown("### APWRLINK Parameters")
link_groups = {}
link_input_length = {}

for hub in hub_data:
    link = hub["link_id"]
    if link not in link_groups:
        link_groups[link] = []
    link_groups[link].append(hub)

for link_id in link_groups:
    link_input_length[link_id] = st.number_input(
        f"{link_id} cable length to first APWRHUB [m]",
        min_value=0.0,
        value=DEFAULT_DISTANCE,
        step=0.5,
        key=f"input_len_{link_id}"
    )

# === Calculation ===
st.markdown("## Voltage Drop & Segment Analysis")
results = []
all_plots = []
link_results = {}  # Results per APWRLINK

for link_id, hubs in link_groups.items():
    link_results[link_id] = []  # Separate results list for each APWRLINK
    cumulative_drop_mV = 0.0
    segment_labels = [f"{link_id} Source"]
    voltage_values = [LINK_VOLTAGE]
    voltage_drop_mV_values = [0]  # 0 mV drop at source
    percent_values = [0]  # 0% voltage drop at source
    
    # APWRLINK to first APWRHUB
    L = link_input_length[link_id]
    I_A = calculate_current(hubs, 0)
    R = calculate_resistance(L, cable_area)
    
    # Calculate voltage drop in mV
    U_drop_mV = I_A * R * 1000  # Convert V to mV
    cumulative_drop_mV += U_drop_mV
    remaining_voltage = LINK_VOLTAGE - (cumulative_drop_mV / 1000)  # Convert mV back to V for remaining
    percent_drop = (cumulative_drop_mV / (reference_voltage * 1000)) * 100  # Convert reference to mV for %
    
    result_row = {
        "APWRLINK": link_id,
        "From": "APWRLINK",
        "To": hubs[0]["hub_name"],
        "Distance [m]": L,
        "Resistance [Ω]": round(R, 4),
        "Current [A]": round(I_A, 3),
        "∆Voltage [mV]": round(U_drop_mV, 2),
        "Cumulative ∆Voltage [mV]": round(cumulative_drop_mV, 2),
        "Remaining Voltage [V]": round(remaining_voltage, 2),
        "∆Voltage [%]": round(percent_drop, 2)
    }
    
    results.append(result_row)
    link_results[link_id].append(result_row)

    segment_labels.append(hubs[0]["hub_name"])
    voltage_values.append(remaining_voltage)
    voltage_drop_mV_values.append(cumulative_drop_mV)
    percent_values.append(percent_drop)

    # APWRHUB to APWRHUB connections
    for i in range(len(hubs)):
        if i > 0:
            L = hubs[i]["distance"]
            I_A = calculate_current(hubs, i)
            R = calculate_resistance(L, cable_area)
            
            # Calculate voltage drop in mV
            U_drop_mV = I_A * R * 1000  # Convert V to mV
            cumulative_drop_mV += U_drop_mV
            remaining_voltage = LINK_VOLTAGE - (cumulative_drop_mV / 1000)
            percent_drop = (cumulative_drop_mV / (reference_voltage * 1000)) * 100
            
            result_row = {
                "APWRLINK": link_id,
                "From": hubs[i-1]["hub_name"],
                "To": hubs[i]["hub_name"],
                "Distance [m]": L,
                "Resistance [Ω]": round(R, 4),
                "Current [A]": round(I_A, 3),
                "∆Voltage [mV]": round(U_drop_mV, 2),
                "Cumulative ∆Voltage [mV]": round(cumulative_drop_mV, 2),
                "Remaining Voltage [V]": round(remaining_voltage, 2),
                "∆Voltage [%]": round(percent_drop, 2)
            }
            
            results.append(result_row)
            link_results[link_id].append(result_row)

            segment_labels.append(hubs[i]["hub_name"])
            voltage_values.append(remaining_voltage)
            voltage_drop_mV_values.append(cumulative_drop_mV)
            percent_values.append(percent_drop)
    
    # Adjust figure size based on number of hubs to prevent label overlap
    width = max(10, len(segment_labels) * 0.8)  # Dynamic width based on number of segments
    height = 6
    
    # Chart with dual y-axis
    fig, ax1 = plt.subplots(figsize=(width, height), facecolor=CORP_GRAY)
    ax1.set_facecolor(CORP_GRAY)
    
    # Primary axis - Voltage
    ln1 = ax1.plot(segment_labels, voltage_values, marker='o', color=CORP_LIGHT_BLUE, label="Voltage [V]")
    ax1.axhline(min_voltage, color='red', linestyle='--', label="Minimum Voltage")
    ax1.set_title(f"Voltage Profile - {link_id}", color='white', fontsize=14)
    ax1.set_ylabel("Voltage [V]", color=CORP_LIGHT_BLUE, fontsize=12)
    ax1.set_xlabel("Segment", color='white', fontsize=12)
    ax1.tick_params(axis='x', colors='white', rotation=45)  # Rotate x labels for better readability
    ax1.tick_params(axis='y', colors=CORP_LIGHT_BLUE)
    ax1.grid(True, linestyle='--', alpha=0.5, color='white')
    
    # Handle x-axis labels for many hubs (prevent overlapping)
    if len(segment_labels) > 10:
        # For many labels, show every nth label
        def label_formatter(x, pos):
            idx = int(x)
            if idx < len(segment_labels):
                # For many labels, show every nth label
                step = max(1, len(segment_labels) // 10)
                if idx % step == 0 or idx == 0 or idx == len(segment_labels)-1:
                    return segment_labels[idx]
                return ""
            return ""
        
        ax1.xaxis.set_major_formatter(ticker.FuncFormatter(label_formatter))
        ax1.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    
    # Secondary axis - Percentage drop and mV drop
    ax2 = ax1.twinx()
    ln2 = ax2.plot(segment_labels, percent_values, marker='s', color=CORP_DARK_BLUE, label="∆Voltage [%]")
    
    # Set appropriate scale for the right y-axis
    max_percent = max(percent_values) * 1.1 if percent_values else 10
    ax2.set_ylim(0, max_percent)
    
    ax2.set_ylabel("∆Voltage [%]", color=CORP_DARK_BLUE, fontsize=12)
    ax2.tick_params(axis='y', colors=CORP_DARK_BLUE)
    
    # Add maximum acceptable drop line (reference is MIN_VOLTAGE)
    max_drop_percent = ((LINK_VOLTAGE - min_voltage) / reference_voltage) * 100
    ax2.axhline(max_drop_percent, color='yellow', linestyle='-.', label=f"Max ∆Voltage ({max_drop_percent:.1f}%)")
    
    # Combine legends
    lns = ln1 + ln2 + [plt.Line2D([0], [0], color='red', linestyle='--'), 
                     plt.Line2D([0], [0], color='yellow', linestyle='-.')]
    labs = ["Voltage [V]", "∆Voltage [%]", "Min Voltage", f"Max ∆Voltage ({max_drop_percent:.1f}%)"]
    ax1.legend(lns, labs, loc='best', facecolor=CORP_GRAY, edgecolor='white', labelcolor='white')
    
    # Set spines color
    for spine in ax1.spines.values():
        spine.set_color('white')
    for spine in ax2.spines.values():
        spine.set_color('white')
        
    # Adjust layout
    plt.tight_layout()
    
    all_plots.append(fig)

# Analyze each APWRLINK system separately
for link_id, link_data in link_results.items():
    st.markdown(f"## {link_id} System Analysis")
    
    # Display the results table for this APWRLINK
    st.markdown(f"### {link_id} Analysis Results")
    df_link = pd.DataFrame(link_data)
    st.dataframe(df_link, use_container_width=True)
    
    # Find the plot for this APWRLINK and display it
    for fig in all_plots:
        # Check the title to find the correct chart
        if any(ax.get_title() == f"Voltage Profile - {link_id}" for ax in fig.axes):
            st.pyplot(fig)
            break
    
    # Calculate system status for this APWRLINK
    link_current = next((r["Current [A]"] for r in link_data if r["From"] == "APWRLINK"), 0)
    link_min_voltage = min([row["Remaining Voltage [V]"] for row in link_data])
    link_max_drop_percent = max([row["∆Voltage [%]"] for row in link_data])
    link_max_drop_mV = max([row["Cumulative ∆Voltage [mV]"] for row in link_data])
    
    st.markdown(f"### {link_id} Status")
    
    # Display status color and message
    status_color = "green"
    status_message = f"{link_id} System OK"
    
    if link_min_voltage < min_voltage:
        status_color = "red"
        status_message = f"{link_id}: Voltage below minimum ({min_voltage} V) at some nodes!"
    
    if link_current > max_link_current:
        status_color = "red"
        status_message = f"{link_id}: Current ({link_current:.2f} A) exceeds maximum ({max_link_current} A)!"
    
    # Display status message with appropriate color
    st.markdown(
        f"""
        <div style="
            background-color: {'#f63366' if status_color == 'red' else '#0ec976'}; 
            padding: 10px; 
            border-radius: 5px; 
            margin-bottom: 15px;
            color: white;
            font-weight: bold;
            text-align: center;
            ">
            {status_message}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Display metrics for this APWRLINK
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(f"{link_id} Current", f"{link_current:.3f} A")
    with col2:
        st.metric("Lowest Voltage Point", f"{link_min_voltage:.2f} V")
    with col3:
        st.metric("Maximum ∆Voltage", f"{link_max_drop_mV:.1f} mV")
    with col4:
        st.metric("Maximum ∆Voltage", f"{link_max_drop_percent:.2f} %")
    
    # Detailed warnings for this APWRLINK
    if link_min_voltage < min_voltage:
        problem_nodes = [row["To"] for row in link_data if row["Remaining Voltage [V]"] < min_voltage]
        st.error(f"Voltage below minimum ({min_voltage} V) at: {', '.join(problem_nodes)}")
    
    if link_current > max_link_current:
        st.error(f"{link_id} current ({link_current:.2f} A) exceeds maximum ({max_link_current} A)!")

# Complete system analysis (optional)
with st.expander("Complete System Overview", expanded=False):
    # Display the complete results table
    st.markdown("### All Systems Data")
    df_all = pd.DataFrame(results)
    st.dataframe(df_all, use_container_width=True)
    
    # Calculate overall system status
    total_current_A = sum(hub["current_mA"] for hub in hub_data) / 1000
    min_voltage_overall = min([row["Remaining Voltage [V]"] for row in results])
    max_drop_percent = max([row["∆Voltage [%]"] for row in results])
    max_drop_mV = max([row["Cumulative ∆Voltage [mV]"] for row in results])
    
    st.markdown("### Overall System Status")
    
    # Check overall status
    overall_status_color = "green"
    overall_status_message = "All Systems OK"
    
    # Check if any system has voltage issues
    if min_voltage_overall < min_voltage:
        overall_status_color = "red"
        overall_status_message = "Voltage issues detected!"
    
    # Calculate APWRLINK currents
    link_currents = {}
    for link_id, link_data in link_results.items():
        link_current = next((r["Current [A]"] for r in link_data if r["From"] == "APWRLINK"), 0)
        link_currents[link_id] = link_current
        if link_current > max_link_current:
            overall_status_color = "red"
            overall_status_message = "Current limit exceeded!"
    
    # Display overall status with appropriate color
    st.markdown(
        f"""
        <div style="
            background-color: {'#f63366' if overall_status_color == 'red' else '#0ec976'}; 
            padding: 10px; 
            border-radius: 5px; 
            margin-bottom: 15px;
            color: white;
            font-weight: bold;
            text-align: center;
            ">
            {overall_status_message}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Display overall metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total System Current", f"{total_current_A:.3f} A")
    with col2:
        st.metric("Lowest Voltage Point", f"{min_voltage_overall:.2f} V")
    with col3:
        st.metric("Maximum ∆Voltage", f"{max_drop_mV:.1f} mV")
    with col4:
        st.metric("Maximum ∆Voltage", f"{max_drop_percent:.2f} %")

# Create download links for each APWRLINK
st.markdown("### Download Reports")

# Separate download buttons for each APWRLINK
for link_id, link_data in link_results.items():
    st.markdown(f"#### {link_id} Reports")
    
    # Create DataFrame for this APWRLINK
    df_link = pd.DataFrame(link_data)
    
    # Filter plots for this APWRLINK
    link_plots = []
    for fig in all_plots:
        if any(ax.get_title() == f"Voltage Profile - {link_id}" for ax in fig.axes):
            link_plots.append(fig)
    
    # Create PDF download link for this APWRLINK
    pdf_link = create_pdf_download_link(
        link_plots, 
        df_link, 
        f"{link_id}_voltage_drop_analysis.pdf", 
        f"Download {link_id} PDF Report", 
        project_info, 
        [hub for hub in hub_data if hub["link_id"] == link_id], 
        system_params,
        link_data
    )
    
    st.markdown(pdf_link, unsafe_allow_html=True)

# Also offer complete system report
st.markdown("#### Complete System Report")
all_pdf_link = create_pdf_download_link(
    all_plots, 
    pd.DataFrame(results), 
    "complete_voltage_drop_analysis.pdf", 
    "Download Complete PDF Report", 
    project_info, 
    hub_data, 
    system_params,
    results
)

st.markdown(all_pdf_link, unsafe_allow_html=True)