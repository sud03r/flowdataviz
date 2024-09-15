import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime
import mpl_axes_aligner


def plotmany(list_measurements, location, dates, variables, l_axis=False, r_axis=False): 
    '''Accepts list of measurement class objects, location (site_code) str, list of dates, and list of variables to plot.
    Returns fig object.
    l_axis and r_axis are optional to be able to control 
    which variable is labeled on which axis, but probably unnecessary.'''
    
    fig, ax1 = plt.subplots()
    
    l_axis = l_axis or variables[0]
    variables.remove(l_axis)
    variables.insert(0, l_axis)
    
    if len(variables) > 1: 
        r_axis = r_axis or variables[1]
        variables.remove(r_axis)
        variables.insert(1, r_axis)
    
    data = [measure for measure in list_measurements if (measure.date in dates and measure.site_code == location)]
    data = sorted(data, key = lambda x: x.date, reverse=True)
    
    
    
    xlabel = 'DISTANCE ALONG SECTION, IN FEET'
    ylabels = {'Depth': 'DEPTH, IN FEET', 'Velocity': 'VELOCITY, IN FT/S', 'Discharge': 'DISCHARGE, CFS'}
    color_dict = {'Depth': 'k', 'Velocity': 'C0', 'Discharge': 'C1'}
    #Colors directly correspond to the property being examined. Date is handled by alpha. 
    alpha = 1
    for measure in data: 
        measure.alpha = alpha
        alpha = alpha - 1/(len(dates))
        #Most recent data is darkest. Older data fades more and more. 
        
        measure.col_names = {'Depth': measure.kDepthColName, 
                             'Velocity': measure.kVeloColName, 
                             'Discharge': measure.kDischargeColName}
        #Map plotted variable to column from each measure's flow data column name

    
    color = color_dict[l_axis]
    ax1.set_ylabel(ylabels[l_axis], color=color)
    ax1.set_xlabel(xlabel)
    ax1.tick_params(axis='y', labelcolor=color)
    
    for measure in data: 
        ax1.plot(measure.flow_data[measure.kDistColName], measure.flow_data[measure.col_names[variables[0]]], alpha=measure.alpha, color=color)
        
    if r_axis: 
        ax2 = ax1.twinx()
        color = color_dict[r_axis]
        ax2.set_ylabel(ylabels[r_axis], color=color)
        ax2.tick_params(axis='y', labelcolor=color)
        for measure in data: 
            ax2.plot(measure.flow_data[measure.kDistColName], measure.flow_data[measure.col_names[variables[1]]], alpha=measure.alpha, color=color)
        #Align the axes so that 0 is at the same height for all variables. 
        mpl_axes_aligner.align.yaxes(ax1, 0, ax2, 0, 0.1)
    
    if len(variables) == 3: 
        ax3 = ax1.twinx()
        color = color_dict[variables[2]]
        ax3.spines.right.set_position(('axes', 1.2))
        ax3.tick_params(axis='y', labelcolor=color)
        ax3.set_ylabel(ylabels[variables[2]], color=color)


        for measure in data:
            ax3.plot(measure.flow_data[measure.kDistColName], measure.flow_data[measure.col_names[variables[2]]], alpha=measure.alpha, color=color)
        #Align the axes so that 0 is at the same height for all variables. 
        mpl_axes_aligner.align.yaxes(ax1, 0, ax3, 0, 0.1)
    
    
    
    
    fig.tight_layout()
    return fig
    
    
def get_statistics(list_measurements): 
    '''Display summary statistics for the list of measurements, along with changes between measurements. '''
    
    
    col_names = ['Location', 'Date', 'Max Depth (ft)', 'Avg Depth (ft)', 
                 'Total Discharge (CFS)', 'Average Velocity (ft/s)']
    
    #If no measurements, return empty dataframe
    if not list_measurements: 
        return pd.DataFrame(columns = col_names)
        
    #Collect the data from each measurement and turn it into a dataframe. 
    statistics = [[measure.site_code,      
                   measure.date.date(),       
                   measure.max_observed_depth,   
                   (measure.flow_data[measure.kDepthColName] * measure.flow_data[measure.kWidthColName]).sum()/(measure.flow_data[measure.kDistColName].iloc[-1]-measure.flow_data[measure.kDistColName].iloc[0]),
                   #Average depth is each depth measurement times its respective width, divided by total distance. 
                   measure.discharge, 
                   measure.average_velocity] for measure in list_measurements]
    
    statistics = pd.DataFrame(statistics)
    statistics.columns = col_names
    #Sort by location and date, so that differences can be taken by date. Location and Date are 
    #set to the index so they are ignored by the next step
    statistics = statistics.sort_values(['Location', 'Date']).set_index(['Location', 'Date'])
    
    #Take a difference between each row and the previous row. 
    #Remove the first row per location (it is invalid as it compares different locations). 
    diff = (statistics - statistics.shift(1)).groupby('Location').apply(lambda group: group.iloc[1:, :])
    diff.index = diff.index.droplevel(0)
    
    #Add a dummy variable so that new diff dataframe can be merged with the original and order preserved.
    #Integers are used for compatibilty with plotly style backend. 
    diff['delta'] = 1
    statistics['delta'] = 0
    joined = pd.concat([statistics, diff],axis = 0).round(2).sort_values(['Location', 'Date', 'delta'], ascending=[False, True, False]).reset_index()
    
    return joined
    
    
    

def display_statistics(list_measurements):
    '''Accepts a list of measurements and returns a stylized dataframe for display purposes.'''
    joined = get_statistics(list_measurements)
    

    #Color changes to the depth/flow green if increased, or red if decreased, but only along the rows that show change. 
    def color_red_green(val): 
        if val.delta: 
            return np.select([val < 0, val > 0, val == 0], ['background-color: salmon', 'background-color: palegreen', 'background-color: lightgray'])
        else: 
            return [""] * len(val)

    return joined.style.apply(color_red_green,subset=['Max Depth (ft)', 'Avg Depth (ft)', 'Total Discharge (CFS)', 
                                               'Average Velocity (ft/s)', 'delta'], axis=1)\
                .hide('delta', axis=1)\
                .hide(axis='index')\
                .format(precision=2)
