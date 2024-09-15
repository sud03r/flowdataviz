
from dash import Dash, html, dcc, callback, Output, Input, dash_table
import data_input, visualizer
import plotly.express as px
import pandas as pd

#Collect measurement objects and establish list of possible input parameters. 
measurements, list_dates, list_sites = data_input.get_measurements()
list_dates = [date.strftime('%Y/%m/%d') for date in list_dates]
variables = ['Depth', 'Velocity', 'Discharge']


app = Dash()

#Create a dashboard with 3 inputs. Site can only accept 1 value, but multiple allowed for date and plotted variable
app.layout = [
    html.H1(children='Waterflow measurements', style = {'textAlign': 'center'}), 
    html.Div(
        [dcc.Dropdown(list_sites, None, id='dropdown-site', placeholder = 'Site'),
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
            title = variable)
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
