
from dash import Dash, html, dcc, callback, Output, Input, dash_table
import data_input, visualizer
import plotly.express as px
import pandas as pd
import dash_bootstrap_components as dbc
import json
import datetime
from dateutil.relativedelta import relativedelta

#Collect measurement objects and establish list of possible input parameters. 
measurements, list_dates, list_sites = data_input.get_measurements()
list_dates = [date.strftime('%Y/%m/%d') for date in list_dates]
variables = ['Depth', 'Velocity', 'Discharge']

with open('Locations.json') as file: 
    list_sites_SLO = json.load(file)
with open('thresholds.json') as file: 
    thresholds = json.load(file)

dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP, dbc_css])

#Create a dashboard with 3 inputs. Site can only accept 1 value, but multiple allowed for date and plotted variable

app.layout = html.Div([
    dcc.Tabs(id="tabs-example", value='tab-1', children=[
        dcc.Tab(label='Manually measured', value='tab-1', children=[
            html.Div([
                html.H1(children='Waterflow measurements', style = {'textAlign': 'center'}), 
                html.Div(
                    [dcc.Dropdown(list_sites, None, id='dropdown-site', placeholder = 'Site'),
                     dcc.Dropdown(list_dates, [], id='dropdown-date', placeholder = 'Date', multi=True),
                     dcc.Dropdown(variables, [], id='dropdown-var', placeholder = 'Variable', multi=True)]),
                html.Div(id='plots-container')
            ])
        ]),
        dcc.Tab(label='SLO County Reports', value='tab-2', children=[
            html.Div([
                html.H1(children='SLO County Measurements', style = {'textAlign': 'center'}), 
                html.Div(
                    [dcc.Dropdown(list(list_sites_SLO.keys()), value='Stenner Creek at Nipomo', id='dropdown-site-SLO', placeholder = 'Site'),
                     dcc.DatePickerRange(id='date-picker',
                                         start_date=datetime.date.today(),
                                         end_date=datetime.date.today()
                                         )
                     ]),
                html.Div(id='plots-SLO')
            ])
        ]),
    ]),
])
@callback(
    Output('plots-SLO', 'children'),
    Input('dropdown-site-SLO', 'value'),
    Input('date-picker', 'start_date'),
    Input('date-picker', 'end_date')
)
def SLO_measurement_graphs(location, start, end): 
    start = datetime.datetime.strptime(start, '%Y-%m-%d')
    end = datetime.datetime.strptime(end, '%Y-%m-%d')

    df = data_input.import_slo_water(list_sites_SLO[location], start=start, end=end)
    if df.empty: 
        return []
    
    #Channel bottom thresholds are given an orange (ff9900) background color. 
    channel_bottom = [threshold[1] for threshold in thresholds[location] if threshold[2].lower() == 'ff9900']
    bottom = channel_bottom[0] if channel_bottom else 0
    df['Value'] -= bottom
    
    fig = px.line(df, 'Reading', 'Value')
    for threshold in thresholds[location]: 
        df[[threshold[0]]] = threshold[1] - bottom
        fig.add_scatter(x = df['Reading'], y = df[threshold[0]], mode='lines', name=threshold[0])
    fig.update_layout(
        xaxis_title = 'Date', 
        yaxis_title = 'Depth (ft)'
    )
    figures = [dcc.Graph(figure=fig)]
    
    if bottom: 
        avg = df['Value'].mean()
        current_val = df.loc[0, 'Value']
        perc_change = round(100 * current_val/avg, 1)
        figures.append(html.H3(f'Current water levels are {perc_change}% of average over this period'))
        
        days_diff = (end-start).days
        if days_diff >= 31: 
            month_ago = pd.Timestamp(end - relativedelta(months = 1))
            time_series = pd.to_datetime(df['Reading']).sort_values()
            closest_index = df.shape[0] - time_series.searchsorted(month_ago)
            figures.append(html.H3(f"Current water levels are \
                                   {round(100 * (df.loc[0, 'Value']) / (df.loc[closest_index, 'Value']), 1)}% \
                                   of last month's level"))
        if days_diff >= 366: 
            year_ago = pd.Timestamp(end - relativedelta(years = 1))
            time_series = pd.to_datetime(df['Reading']).sort_values()
            closest_index = df.shape[0] - time_series.searchsorted(year_ago)
            figures.append(html.H3(f"Current water levels are \
                                   {round(100 * (df.loc[0, 'Value']) / (df.loc[closest_index, 'Value']), 1)}% \
                                   of last year's level"))
    return figures
    

@callback(
    Output('plots-container', 'children'), 
    [Input('dropdown-site', 'value'), 
     Input('dropdown-date', 'value'), 
     Input('dropdown-var', 'value')]
)
def manual_measurement_graphs(site, dates, variables): 
    flow_measure = [measure for measure in measurements if 
                    (measure.date.strftime('%Y/%m/%d') in dates) and 
                    (measure.site_code == site)]
    if not flow_measure: 
        #if no data provided (like at initialization), then return empty list
        return []
    
    df = pd.concat([measure.flow_data for measure in flow_measure])
    var_dict = {'Distance': flow_measure[0].kDistColName, 
                'Depth':    flow_measure[0].kDepthColName,
                'Velocity': flow_measure[0].kVeloColName, 
                'Discharge':flow_measure[0].kDischargeColName}
    
    ylabels = {'Depth': 'DEPTH, IN FEET', 'Velocity': 'VELOCITY, IN FT/S', 'Discharge': 'DISCHARGE, CFS'}
    
    figures = []
    for variable in variables: 
        #For each variable requested, add a new figure.
        #Each figure draws 1 line for each date. 
        fig = px.line(df, x=var_dict['Distance'], y=var_dict[variable], color='date')
        fig.update_layout(
            xaxis_title = 'DISTANCE ALONG SECTION, IN FEET', 
            yaxis_title = ylabels[variable], 
            title = variable
        )
        figures.append(dcc.Graph(figure=fig))
        
    #Return the list of summary statistics for each figure.
    df = visualizer.get_statistics(flow_measure)
    style_columns = list(df.columns[2:6])
    
    #The table has rows between each measurement that correspond to the change between measurements. 
    #These changes are colored green for positive or red for negative change. 
    style_cond = [{'if': {'filter_query': f'{{delta}} = 1 AND {{{col}}} < 0',
                          'column_id': col},
                   'backgroundColor': 'salmon'} for col in style_columns] + [
                  {'if': {'filter_query': f'{{delta}} = 1 AND {{{col}}} > 0',
                          'column_id': col},
                   'backgroundColor': 'palegreen'} for col in style_columns] + [
                  {'if': {'column_id': 'delta'}, 
                   'display': 'none'}]
    #Delta is the dummy variable that says if a row is a measurement or a difference. 
    style_head=[{'if': {'column_id': 'delta'},
                 'display': 'none'}]

    table = dash_table.DataTable(df.to_dict('records'), 
                                 [{"name": i, "id": i} for i in df.columns],
                                 style_data_conditional = style_cond, 
                                 style_header_conditional = style_head)
    
    figures.append(table)
    return figures




if __name__ == '__main__':
    app.run(debug=True)
