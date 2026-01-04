# -*- coding: utf-8 -*-
import pandas as pd
from io import BytesIO
import requests
import datetime
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, dash_table
import re

def haglstr(x):
    try:
        x = re.sub("([\(\[]).*?([\)\]])", "\g<1>\g<2>", x).replace(' ()', '')
        f = float(x.replace(',', '.'))
        mm = round(f * 4) / 4
        if mm == 2.0:
            nr = '9'
        elif mm == 2.25:
            nr = '8'
        elif mm == 2.5:
            nr = '7'
        elif mm == 2.75:
            nr = '6'
        elif mm == 3.0:
            nr = '5'
        elif mm == 3.25:
            nr = '4'
        elif mm == 3.5:
            nr = '3'
        elif mm == 3.75:
            nr = '2'
        elif mm == 4.0:
            nr = '1'
    except:
        nr = 'Mix'
    return nr

def load_data():
    """Load and preprocess the hunting log data"""
    r = requests.get('https://docs.google.com/spreadsheet/ccc?key=1O0aq_r43Y3twUZknICL0Czax_k_6H1osAXjRYualJyU&output=csv')
    data = r.content
    df = pd.read_csv(BytesIO(data), parse_dates=['Dato'], dayfirst=True)
    del df['Tidsstempel']
    df.replace('nan', np.nan)
    df['Haglnr'] = df['Hagl størrelse (mm)'].apply(lambda col: haglstr(col))
    
    infostr = ('65mm-'+df['Ammo Længde (mm) og ladning (gram) [65]'].astype(str)+ ' ' + \
              '67,5mm-'+df['Ammo Længde (mm) og ladning (gram) [67,5]'].astype(str)+ ' ' + \
              '70mm-'+df['Ammo Længde (mm) og ladning (gram) [70]'].astype(str)+ ' ' + \
              '76mm-'+df['Ammo Længde (mm) og ladning (gram) [76]'].astype(str))
    infostr = infostr.str.replace('65mm-nan', '')
    infostr = infostr.str.replace('67,5mm-nan', '')
    infostr = infostr.str.replace('70mm-nan', '')
    infostr = infostr.str.replace('76mm-nan', '')
    df['Ammo'] = df['Ammunition fabrikant'] + ' ' +df['type'] +' Hagl ' + df['Haglnr']  + ' ' + infostr
    df['Ammo'] = df['Ammo'].replace(np.nan, 'Mix', regex=True)
    df['nedlagt'] = df.fillna(0)['Antal Art 1'] + df.fillna(0)['Antal Art 2'] + df.fillna(0)['Antal Art 3'] + df.fillna(0)['Antal Art 4']
    
    return df

def process_hunting_data(df, start_year, start_month, end_year, end_month):
    """Process hunting data for the selected year range"""
    stdag = datetime.datetime(int(start_year), int(start_month), 1)
    endag = datetime.datetime(int(end_year), int(end_month), 1)
    # Add one month to end date to include the entire month
    if int(end_month) == 12:
        endag = datetime.datetime(int(end_year) + 1, 1, 1)
    else:
        endag = datetime.datetime(int(end_year), int(end_month) + 1, 1)
    
    subset = df[(df['Dato'] < endag) & ((df['Dato'] >= stdag))]
    
    # Get unique species
    art = [x for x in subset['Art 1'].unique() if str(x) != 'nan']
    art = np.append(art, [x for x in subset['Art 2'].unique() if str(x) != 'nan'])
    art = np.append(art, [x for x in subset['Art 3'].unique() if str(x) != 'nan'])
    art = np.append(art, [x for x in subset['Art 4'].unique() if str(x) != 'nan'])
    art = np.unique(art)
    
    # Count animals by species
    dyr = {}
    sumdyr = 0.
    for nn in art:
        for ii in range(1, 5):
            num = subset['Antal Art ' + str(ii)][subset['Art ' + str(ii)] == nn]
            if not num.empty:
                if nn in dyr.keys():
                    dyr[nn] = np.sum(num) + dyr[nn]
                else:
                    dyr[nn] = np.sum(num)
                sumdyr += dyr[nn]
    
    # Ammunition statistics - simplified by manufacturer and shot size
    ammo_simple = {}
    N_total = 0.
    S_total = 0.
    
    for idx, row in subset.iterrows():
        manufacturer = row['Ammunition fabrikant']
        hagl_size = row['Haglnr']
        
        # Skip if missing data
        if pd.isna(manufacturer) or manufacturer == 'nan':
            manufacturer = 'Unknown'
        if pd.isna(hagl_size) or hagl_size == 'nan' or hagl_size == 'Mix':
            hagl_size = 'Mix'
        
        key = f"{manufacturer} #{hagl_size}"
        
        nedlagt = row['nedlagt'] if not pd.isna(row['nedlagt']) else 0
        skud = row['Antal Skud'] if not pd.isna(row['Antal Skud']) else 0
        
        if key not in ammo_simple:
            ammo_simple[key] = {'nedlagt': 0, 'skud': 0}
        
        ammo_simple[key]['nedlagt'] += nedlagt
        ammo_simple[key]['skud'] += skud
        N_total += nedlagt
        S_total += skud
    
    # Calculate percentages
    ammosat = {}
    ammo = {}
    for key, values in ammo_simple.items():
        n = values['nedlagt']
        s = values['skud']
        if s > 0:
            percentage = np.round(n / s * 100., decimals=1)
            ammosat[key] = percentage
            ammo[key] = [n, s, percentage]
        else:
            ammosat[key] = 0
            ammo[key] = [n, s, 0]
    
    # Add total
    if S_total > 0:
        ammosat['Total'] = np.round(N_total / S_total * 100., decimals=1)
        ammo['Total'] = [N_total, S_total, ammosat['Total']]
    else:
        ammosat['Total'] = 0
        ammo['Total'] = [N_total, S_total, 0]
    
    # Kommune statistics
    kom = {}
    dyr_list = []
    dum = []
    for nn in art:
        try:
            np.isnan(nn)
        except:
            dum.append(0.)
            dyr_list.append(nn)
    
    for kk in subset['Kommune'].unique():
        if str(kk) != 'nan':
            temp = np.zeros(len(dum))
            tmpdf = subset[subset['Kommune'] == kk]
            count = 0
            for nn in dyr_list:
                for ii in range(1, 5):
                    num = tmpdf['Antal Art ' + str(ii)][tmpdf['Art ' + str(ii)] == nn]
                    if not num.empty:
                        temp[count] = np.sum(num) + temp[count]
                count += 1
            kom[kk] = temp
    
    return dyr, sumdyr, ammo, ammosat, kom, dyr_list, subset, stdag, endag

def create_season_table(df):
    """Create the hunting season statistics table"""
    col_labels = ['Jagtdage', 'Nedlagt', 'Skud', 'Skud stat. [%]']
    row_labels = ['Total']
    
    tmp = df['Dato'].iloc[-1]
    # Determine the last complete season
    if tmp.month >= 9:  # September or later
        eyr = tmp.year
    else:
        eyr = tmp.year - 1
    
    # Generate season labels from first year to last year
    for ii in range(df['Dato'].iloc[0].year, eyr + 1):
        row_labels.append(str(ii) + '/' + str(ii + 1))
    
    table_data = []
    for ii, season_label in enumerate(row_labels):
        if ii == 0:
            season = df
        else:
            # Season runs from Sept 1 to Aug 31 of next year
            stdate = datetime.datetime(int(season_label[0:4]), 9, 1)
            endate = datetime.datetime(int(season_label[5:9]), 8, 31, 23, 59, 59)
            season = df[(df['Dato'] >= stdate) & (df['Dato'] <= endate)]
        
        jagtdage = len(season['Dato'].unique())
        nedlagt = int(season['nedlagt'].sum())
        skud = int(season['Antal Skud'].sum())
        skud_stat = int(float(nedlagt) / float(skud) * 100.) if skud > 0 else 0
        
        table_data.append({
            'Season': season_label,
            'Jagtdage': jagtdage,
            'Nedlagt': nedlagt,
            'Skud': skud,
            'Skud stat. [%]': skud_stat
        })
    
    return table_data

# Initialize the Dash app
app = Dash(__name__)

# Load initial data
df = load_data()

# Get year range for dropdowns
min_year = df['Dato'].min().year
max_year = df['Dato'].max().year
if df['Dato'].max().month >= 5:
    max_year += 1

year_options = [{'label': str(year), 'value': year} for year in range(min_year, max_year + 1)]

month_options = [
    {'label': 'January', 'value': 1},
    {'label': 'February', 'value': 2},
    {'label': 'March', 'value': 3},
    {'label': 'April', 'value': 4},
    {'label': 'May', 'value': 5},
    {'label': 'June', 'value': 6},
    {'label': 'July', 'value': 7},
    {'label': 'August', 'value': 8},
    {'label': 'September', 'value': 9},
    {'label': 'October', 'value': 10},
    {'label': 'November', 'value': 11},
    {'label': 'December', 'value': 12}
]

# App layout
app.layout = html.Div([
    html.H1('Jagtlog Dashboard', style={'textAlign': 'center', 'marginBottom': 30}),
    
    html.Div([
        html.Div([
            html.Label('Start Year:', style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='start-year',
                options=year_options,
                value=max_year - 1,
                clearable=False
            )
        ], style={'width': '150px', 'display': 'inline-block', 'marginRight': 10}),
        
        html.Div([
            html.Label('Start Month:', style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='start-month',
                options=month_options,
                value=9,  # September
                clearable=False
            )
        ], style={'width': '150px', 'display': 'inline-block', 'marginRight': 30}),
        
        html.Div([
            html.Label('End Year:', style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='end-year',
                options=year_options,
                value=max_year,
                clearable=False
            )
        ], style={'width': '150px', 'display': 'inline-block', 'marginRight': 10}),
        
        html.Div([
            html.Label('End Month:', style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='end-month',
                options=month_options,
                value=10,  # October
                clearable=False
            )
        ], style={'width': '150px', 'display': 'inline-block'}),
    ], style={'textAlign': 'center', 'marginBottom': 30}),
    
    html.Div([
        html.Div([
            dcc.Graph(id='species-pie-chart')
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            html.H3('Overall Season Statistics', style={'textAlign': 'center'}),
            html.Div(
                dash_table.DataTable(
                    id='season-table',
                    style_table={'overflowY': 'auto', 'maxHeight': '400px'},
                    style_cell={'textAlign': 'center', 'padding': '10px'},
                    style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
                    style_data_conditional=[
                        {'if': {'row_index': 0}, 'backgroundColor': '#e6f3ff', 'fontWeight': 'bold'}
                    ]
                ),
                style={'width': '90%', 'margin': 'auto'}
            )
        ], style={'width': '50%', 'display': 'inline-block', 'verticalAlign': 'top'}),
    ]),
    
    html.Div([
        html.Div([
            dcc.Graph(id='ammo-bar-chart')
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(id='kommune-bar-chart')
        ], style={'width': '50%', 'display': 'inline-block'}),
    ], style={'marginTop': 30}),
    
    html.Div([
        html.Div([
            dcc.Graph(id='ammo-type-bar-chart')
        ], style={'width': '100%', 'display': 'inline-block'}),
    ], style={'marginTop': 30})
], style={'padding': '20px'})

@app.callback(
    [Output('species-pie-chart', 'figure'),
     Output('ammo-bar-chart', 'figure'),
     Output('kommune-bar-chart', 'figure'),
     Output('season-table', 'data'),
     Output('season-table', 'columns'),
     Output('ammo-type-bar-chart', 'figure')],
    [Input('start-year', 'value'),
     Input('start-month', 'value'),
     Input('end-year', 'value'),
     Input('end-month', 'value')]
)
def update_dashboard(start_year, start_month, end_year, end_month):
    # Process data
    dyr, sumdyr, ammo, ammosat, kom, dyr_list, subset, stdag, endag = process_hunting_data(df, start_year, start_month, end_year, end_month)
    
    # Species pie chart
    labels = [f"{nn}\n({int(dyr[nn])} stk.)" for nn in dyr.keys()]
    values = list(dyr.values())
    pie_fig = go.Figure(data=[go.Pie(labels=labels, values=values, textposition='inside')])
    pie_fig.update_layout(
        title=f'Jagtlog<br>{stdag.date()} til {endag.date()}',
        height=550
    )
    
    # Ammunition bar chart - grouped by manufacturer with shot sizes
    # Organize data by manufacturer first, then shot size
    manufacturer_data = {}
    
    for name in ammosat.keys():
        if name == 'Total':
            continue
        
        if '#' in name:
            manufacturer = name.split('#')[0].strip()
            shot_size = name.split('#')[1].strip()
        else:
            manufacturer = 'Unknown'
            shot_size = 'Unknown'
        
        if manufacturer not in manufacturer_data:
            manufacturer_data[manufacturer] = {}
        
        manufacturer_data[manufacturer][shot_size] = {
            'percentage': ammosat[name],
            'nedlagt': ammo[name][0],
            'skud': ammo[name][1],
            'text': f"{int(ammo[name][0])}/{int(ammo[name][1])}<br>{int(ammo[name][2])}%"
        }
    
    # Sort manufacturers alphabetically
    sorted_manufacturers = sorted(manufacturer_data.keys())
    
    # Create colors based on shot size
    size_color_map = {
        '1': '#8B0000',   # Dark red
        '2': '#DC143C',   # Crimson
        '3': '#FF6347',   # Tomato
        '4': '#FF8C00',   # Dark orange
        '5': '#FFA500',   # Orange
        '6': '#FFD700',   # Gold
        '7': '#90EE90',   # Light green
        '8': '#00CED1',   # Dark turquoise
        '9': '#4169E1',   # Royal blue
        'Mix': '#808080', # Gray
        'Unknown': '#A9A9A9'  # Dark gray
    }
    
    # Create figure
    ammo_fig = go.Figure()
    
    # Build data organized by shot size for proper legend
    shot_order = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'Mix', 'Unknown']
    x_pos = 0
    
    # Store all data points by shot size
    shot_size_data = {size: {'x': [], 'y': [], 'text': []} for size in shot_order}
    
    # Add spacing between manufacturers
    spacing = 0.5  # Half bar width of space between manufacturers
    
    for idx, manufacturer in enumerate(sorted_manufacturers):
        if idx > 0:
            x_pos += spacing  # Add space before each new manufacturer (except first)
        
        shot_sizes = sorted(manufacturer_data[manufacturer].keys())
        for shot_size in shot_sizes:
            data = manufacturer_data[manufacturer][shot_size]
            shot_size_data[shot_size]['x'].append(x_pos)
            shot_size_data[shot_size]['y'].append(data['percentage'])
            shot_size_data[shot_size]['text'].append(data['text'])
            x_pos += 1
    
    # Add traces for each shot size (for legend)
    for shot_size in shot_order:
        if shot_size_data[shot_size]['x']:  # Only add if there's data
            color = size_color_map.get(shot_size, '#808080')
            ammo_fig.add_trace(go.Bar(
                name=f'#{shot_size}' if shot_size not in ['Mix', 'Unknown'] else shot_size,
                x=shot_size_data[shot_size]['x'],
                y=shot_size_data[shot_size]['y'],
                text=shot_size_data[shot_size]['text'],
                textposition='inside',
                marker_color=color,
                hovertemplate='%{y:.1f}%<extra></extra>'
            ))
    
    # Add Total bar with extra spacing
    total_x = x_pos + spacing + 0.5
    ammo_fig.add_trace(go.Bar(
        name='Total',
        x=[total_x],
        y=[ammosat['Total']],
        text=[f"{int(ammo['Total'][0])}/{int(ammo['Total'][1])}<br>{int(ammo['Total'][2])}%"],
        textposition='inside',
        marker_color='darkgray',
        hovertemplate='%{y:.1f}%<extra></extra>'
    ))
    
    # Create custom x-axis tick labels and positions
    tickvals = []
    ticktext = []
    
    x_pos = 0
    for idx, manufacturer in enumerate(sorted_manufacturers):
        if idx > 0:
            x_pos += spacing
        
        shot_count = len(manufacturer_data[manufacturer])
        # Place label in the middle of the group
        middle_pos = x_pos + (shot_count - 1) / 2.0
        tickvals.append(middle_pos)
        ticktext.append(manufacturer)
        x_pos += shot_count
    
    # Add Total label
    tickvals.append(total_x)
    ticktext.append('Total')
    
    ammo_fig.update_layout(
        title='Skud statistik',
        xaxis_title='',
        yaxis_title='',
        showlegend=True,
        legend=dict(
            x=1.02,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='lightgray',
            borderwidth=1
        ),
        height=400,
        xaxis=dict(
            tickmode='array',
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=-45
        ),
        bargap=0.0  # No gap between bars within a manufacturer
    )
    ammo_fig.update_yaxes(showticklabels=False)
    
    # Kommune stacked bar chart
    if kom:
        kommune_fig = go.Figure()
        for idx, species in enumerate(dyr_list):
            values = [kom[k][idx] if k in kom else 0 for k in kom.keys()]
            kommune_fig.add_trace(go.Bar(name=species, x=list(kom.keys()), y=values))
        
        kommune_fig.update_layout(
            title='Stk. vild pr. kommune',
            barmode='stack',
            xaxis_title='',
            yaxis_title='Antal',
            height=400
        )
    else:
        kommune_fig = go.Figure()
        kommune_fig.update_layout(title='Stk. vild pr. kommune (No data)', height=400)
    
    # Season table
    table_data = create_season_table(df)
    table_columns = [{"name": i, "id": i} for i in table_data[0].keys()]
    
    # Ammunition type statistics chart
    type_stats = {}
    type_total_n = 0
    type_total_s = 0
    
    for idx, row in subset.iterrows():
        ammo_type = row['type']
        
        if pd.isna(ammo_type) or ammo_type == 'nan':
            ammo_type = 'Unknown'
        
        nedlagt = row['nedlagt'] if not pd.isna(row['nedlagt']) else 0
        skud = row['Antal Skud'] if not pd.isna(row['Antal Skud']) else 0
        
        if ammo_type not in type_stats:
            type_stats[ammo_type] = {'nedlagt': 0, 'skud': 0}
        
        type_stats[ammo_type]['nedlagt'] += nedlagt
        type_stats[ammo_type]['skud'] += skud
        type_total_n += nedlagt
        type_total_s += skud
    
    # Calculate percentages for types
    type_names = sorted(type_stats.keys())
    type_percentages = []
    type_text = []
    
    for type_name in type_names:
        n = type_stats[type_name]['nedlagt']
        s = type_stats[type_name]['skud']
        if s > 0:
            percentage = np.round(n / s * 100., decimals=1)
        else:
            percentage = 0
        type_percentages.append(percentage)
        type_text.append(f"{int(n)}/{int(s)}<br>{int(percentage)}%")
    
    # Add Total for types
    if type_total_s > 0:
        total_percentage = np.round(type_total_n / type_total_s * 100., decimals=1)
    else:
        total_percentage = 0
    type_names.append('Total')
    type_percentages.append(total_percentage)
    type_text.append(f"{int(type_total_n)}/{int(type_total_s)}<br>{int(total_percentage)}%")
    
    # Create type bar chart
    type_colors = px.colors.qualitative.Set3
    colors_type = [type_colors[i % len(type_colors)] if name != 'Total' else 'darkgray' for i, name in enumerate(type_names)]
    
    type_fig = go.Figure(data=[go.Bar(
        x=type_names,
        y=type_percentages,
        text=type_text,
        textposition='inside',
        marker_color=colors_type
    )])
    
    type_fig.update_layout(
        title='Skud statistik efter ammunition type',
        xaxis_title='',
        yaxis_title='',
        showlegend=False,
        height=400,
        xaxis={'tickangle': -45}
    )
    type_fig.update_yaxes(showticklabels=False)
    
    return pie_fig, ammo_fig, kommune_fig, table_data, table_columns, type_fig

if __name__ == '__main__':
    app.run(debug=True, port=8050)