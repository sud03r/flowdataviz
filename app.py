
from dash import Dash, html, dcc, callback, Output, Input, dash_table
import data_input, visualizer
import plotly.express as px
import pandas as pd
import dash_bootstrap_components as dbc

#Collect measurement objects and establish list of possible input parameters. 
measurements, list_dates, list_sites = data_input.get_measurements()
list_dates = [date.strftime('%Y/%m/%d') for date in list_dates]
variables = ['Depth', 'Velocity', 'Discharge']

dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP, dbc_css])

#Create a dashboard with 3 inputs. Site can only accept 1 value, but multiple allowed for date and plotted variable
app.layout = [
    dbc.Container(
    children = html.Div(
            [
                dbc.Row(html.H2("Watershed Flow Data Visualization", className="text-center m-4 text-muted")),
                dbc.Row(html.Hr()),
                dbc.Row(
                    [
                        dbc.Col(dcc.Dropdown(list_sites, None, id='dropdown-site', placeholder = 'Site')),
                        dbc.Col(dcc.Dropdown(list_dates, [], id='dropdown-date', placeholder = 'Date', multi=True)),
                        dbc.Col(dcc.Dropdown(variables, [], id='dropdown-var', placeholder = 'Variable', multi=True))
                    ],
                    className="m-2 mt-4"
                ),
                dbc.Row(html.Div(id='plots-container'))
            ],
            className="bg-light border border-light rounded p-3"
        ),
    )
]

@callback(
    Output('plots-container', 'children'), 
    [Input('dropdown-site', 'value'), 
     Input('dropdown-date', 'value'), 
     Input('dropdown-var', 'value')]
)
def update_graphs(site, dates, variables): 
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
            paper_bgcolor="rgba(0, 0, 0, 0)") # transparent background
        plot = dbc.Card(
            dbc.CardBody(
                [
                    html.H4(variable, className="card-title text-muted"),
                    dcc.Graph(figure=fig),
                ]
            ),
            className="bg-light border-light"
        )
        figures.append(plot)
        
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
                                 style_cell={'textAlign': 'center'},
                                 style_header={'fontWeight': 'bold',  'backgroundColor': 'lightcyan'},
                                 style_data_conditional = style_cond, 
                                 style_header_conditional = style_head)
    flow_stats = dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Flow Statistics", className="card-title text-muted"),
                    html.Div(children=table, className="p-2 dbc dbc-row-selectable"),
                ]
            ),
            className="border-0 m-4 rounded-2"
        )
    # show table first
    return [flow_stats] + figures



if __name__ == '__main__':
    app.run(debug=True)
