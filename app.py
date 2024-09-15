
from dash import Dash, html, dcc, callback, Output, Input
import data_input, visualizer
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

measurements, list_dates, list_sites = data_input.get_measurements()
list_dates = [date.strftime('%Y/%m/%d') for date in list_dates]
variables = ['Depth', 'Velocity', 'Discharge']


app = Dash()
app.layout = [
    html.H1(children='Waterflow measurements', style = {'textAlign': 'center'}), 
    html.Div(
        [dcc.Dropdown(list_sites, [], id='dropdown-site', placeholder = 'Site'),
         dcc.Dropdown(list_dates, [], id='dropdown-date', placeholder = 'Date', multi=True),
         dcc.Dropdown(variables, [], id='dropdown-var', placeholder = 'Variable', multi=True)]),
    html.Div(id='plots-container')
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
        return []
    
    df = pd.concat([measure.flow_data for measure in flow_measure])
    var_dict = {'Distance': flow_measure[0].kDistColName, 
                'Depth':    flow_measure[0].kDepthColName,
                'Velocity': flow_measure[0].kVeloColName, 
                'Discharge':flow_measure[0].kDischargeColName}
    
    ylabels = {'Depth': 'DEPTH, IN FEET', 'Velocity': 'VELOCITY, IN FT/S', 'Discharge': 'DISCHARGE, CFS'}
    
    figures = []
    for variable in variables: 
        fig = px.line(df, x=var_dict['Distance'], y=var_dict[variable], color='date')
        fig.update_layout(
            xaxis_title = 'DISTANCE ALONG SECTION, IN FEET', 
            yaxis_title = ylabels[variable], 
            title = variable)
        figures.append(dcc.Graph(figure=fig))
    return figures



if __name__ == '__main__':
    app.run(debug=True)
