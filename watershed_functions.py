import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import requests as r
from io import BytesIO, StringIO
import datetime
import mpl_axes_aligner

def import_googlesheet(): 
    '''As there is only one google sheet, I just hard code the url. 
    otherwise I would have this function iterate over files within a folder. 
    Returns xlsx file.'''
    sheet_id = '1mrbBkhl6TDZNPUTZkHOaRw6MqLU5VHyURoRnQNqZ7-M'
    url = "https://docs.google.com/spreadsheets/export?exportFormat=xlsx&id=" + sheet_id
    
    file = r.get(url)
    data = BytesIO(file.content)
    xlsx = pd.ExcelFile(data)    
    
    return xlsx

def parse_tables(xlsx_file): 
    '''Takes in the xlsx file, and extracts the table where meta data can be found, and the flow data. 
    This function also checks the filenames and skips sheets that are summaries or invalid. 
    '''
    flow_data = {}
    meta_data = {}
    
    for name in xlsx_file.sheet_names:
        if name == 'Summary': 
            #ignore the summary sheet
            continue
        if '!' in name: 
            #ignore any sheet indicated to be erronous
            continue
        flow_data[name] = pd.read_excel(xlsx_file, sheet_name = name, usecols='A:F', skiprows=12)
        meta_data[name] = pd.read_excel(xlsx_file, sheet_name = name, nrows = 12, header=None)
    
    return flow_data, meta_data

class Measurement(): 
    #A class to cluster both tabular flow data and untabled meta data. 
    
    
    #Properties and the indicies where they are reported on the sheets
    
    def __init__(self, name, flow_data, meta_data):
        self.name = name
        
        
        self.flow_data = flow_data.dropna()
        self.discharge = self.flow_data['Dis-charge, ft3/s'].sum()
        self.area = self.flow_data['Area, ft2'].sum()
        self.average_velocity = self.discharge / self.area
        self.max_observed_depth = self.flow_data['Depth'].max()
        
        
        
        table_schema = {'station': [0, 3], 
                    'coordinates': [0, 6], 
                    'site_code': [0, 13],
                    'date': [2, 2], 
                    'start_time': [2, 4],
                    'end_time': [3, 4],
                    'timezone': [2, 5], 
                    'meter_type': [2, 13],
                    'crew': [4, 1, [4, 2]]}
        
        self.meta_table = meta_data
        for variable, coord in table_schema.items(): 
            self.__dict__[variable] = self.meta_table.iloc[coord[0], coord[1]]
            
            if pd.isnull(self.__dict__[variable]) and coord[2:]: 
                #If there is a backup location listed, use that instead. 
                self.__dict__[variable] = self.meta_table.iloc[coord[2][0], coord[2][1]]
        if pd.isnull(self.site_code): 
            self.site_code = self.name.split(' ')[0]
        print(name)
        self.crew = self.crew.split(', ')
        
def get_measurements(): 
    xlsx = import_googlesheet()
    flow_data, meta_data = parse_tables(xlsx)
    list_measurements = []
    list_dates = set()
    list_sites = set()
    for name in flow_data.keys(): 
        measure = Measurement(name, flow_data[name], meta_data[name])
        list_measurements.append(measure)
        list_dates.add(measure.date)
        list_sites.add(measure.site_code)
    return list_measurements, sorted(list(list_dates)), list(list_sites)
        
        
def plotmany(list_measurements, location, dates, variables, l_axis=False, r_axis=False): 
    #l_axis and r_axis are optional to be able to control 
    #which variable is labeled on which axis, but probably unnecessary.
    
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
    
    
    #Most recent data is darkest. Older data fades more and more. 
    alpha = 1
    for measure in data: 
        measure.alpha = alpha
        alpha = alpha - 1/(len(dates))
    
    ylabels = {'Depth': 'DEPTH, IN FEET', 'Velocity': 'VELOCITY, IN FT/S', 'Discharge': 'DISCHARGE, CFS'}
    col_names = {'Depth': 'Depth', 'Velocity': 'V', 'Discharge': 'Dis-charge, ft3/s'}
    
    #Colors directly correspond to the property being examined. Date is handled by alpha. 
    color_dict = {'Depth': 'k', 'Velocity': 'C0', 'Discharge': 'C1'}
    xlabel = 'DISTANCE ALONG SECTION, IN FEET'
    
    color = color_dict[l_axis]
    ax1.set_ylabel(ylabels[l_axis], color=color)
    ax1.set_xlabel(xlabel)
    ax1.tick_params(axis='y', labelcolor=color)
    
    for measure in data: 
        ax1.plot(measure.flow_data[col_names[variables[0]]], alpha=measure.alpha, color=color)
        
    if r_axis: 
        ax2 = ax1.twinx()
        color = color_dict[r_axis]
        ax2.set_ylabel(ylabels[r_axis], color=color)
        ax2.tick_params(axis='y', labelcolor=color)
        for measure in data: 
            ax2.plot(measure.flow_data[col_names[variables[1]]], alpha=measure.alpha, color=color)
        #Align the axes so that 0 is at the same height for all variables. 
        mpl_axes_aligner.align.yaxes(ax1, 0, ax2, 0, 0.1)
    
    if len(variables) == 3: 
        ax3 = ax1.twinx()
        color = color_dict[variables[2]]
        ax3.spines.right.set_position(('axes', 1.2))
        ax3.tick_params(axis='y', labelcolor=color)
        ax3.set_ylabel(ylabels[variables[2]], color=color)


        for measure in data:
            ax3.plot(measure.flow_data[col_names[variables[2]]], alpha=measure.alpha, color=color)
        #Align the axes so that 0 is at the same height for all variables. 
        mpl_axes_aligner.align.yaxes(ax1, 0, ax3, 0, 0.1)
    
    
    
    
    fig.tight_layout()
    plt.show()
    
    

def import_slo_water(start=datetime.datetime(2024, 9, 1, 0, 0), end=datetime.datetime.now()): 
    #Copied the URL from the csv-download option, and parsed it for legibility. 
    
    url_base = 'https://wr.slocountywater.org/export/file/'

    args = {'site_id': '29', 
            'site' : '5952eafd-17d9-4cb6-a6dd-c949a99525f0', 
            'device_id': '1',
            'device': '1c308219-4b72-4307-a5c0-76ed02cdba41',
            'mode' : '',
            'hours' : '',
            'data_start' : start.strftime('%Y-%m-%d %H:%M:%S'),
            'data_end' : end.strftime('%Y-%m-%d %H:%M:%S'),
            'tz' : 'US%2FPacific',
            'format_datetime' : '%25Y-%25m-%25d+%25H%3A%25i%3A%25S',
            'mime' : 'txt',
            'delimiter' : 'comma'}
    url = url_base + '?' + '&'.join(['='.join([key, value]) for key, value in args.items()])

    response = r.get(url)


    csv_data = io.StringIO(response.text)
    df = pd.read_csv(csv_data)
    return df
