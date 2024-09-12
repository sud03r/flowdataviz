import pandas as pd
import requests as r
from io import BytesIO, StringIO
import datetime

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
    '''A class to cluster both tabular flow data and untabled meta data. '''
    
    #Properties and the indicies where they are reported on the sheets
    meta_table_schema = {'station': [0, 3], 
                    'coordinates': [0, 6], 
                    'site_code': [0, 13],
                    'date': [2, 2], 
                    'start_time': [2, 4],
                    'end_time': [3, 4],
                    'timezone': [2, 5], 
                    'meter_type': [2, 13],
                    'crew': [4, 1, [4, 2]]}
    
    #Column names as they appear from flow_data
    kDistColName = 'Dist. From initial point'
    kWidthColName = 'Width'
    kDepthColName = 'Depth'
    kVeloColName = 'V'
    kAreaColName = 'Area, ft2'
    kDischargeColName = 'Dis-charge, ft3/s'
    
    def __init__(self, name, flow_data, meta_data):
        self.name = name
        
        
        self.flow_data = flow_data.dropna()
        self.discharge = self.flow_data[self.kDischargeColName].sum()
        self.area = self.flow_data[self.kAreaColName].sum()
        self.average_velocity = self.discharge / self.area
        self.max_observed_depth = self.flow_data[self.kDepthColName].max()
        
        
        
        
        self.meta_table = meta_data
        for variable, coord in self.meta_table_schema.items(): 
            self.__dict__[variable] = self.meta_table.iloc[coord[0], coord[1]]
            
            if pd.isnull(self.__dict__[variable]) and coord[2:]: 
                #If there is a backup location listed, use that instead. 
                self.__dict__[variable] = self.meta_table.iloc[coord[2][0], coord[2][1]]
        if pd.isnull(self.site_code): 
            self.site_code = self.name.split(' ')[0]
        self.crew = self.crew.split(', ')
        
        
def import_slo_water(start=datetime.datetime(2024, 9, 1, 0, 0), end=datetime.datetime.now()): 
    '''Copied the URL from the csv-download option, and parsed it for legibility. 
    Currently accepts starting and ending timestamps as arguments, returns csv over that period.
    Hardcoded for one specific url, but could accept arguments for multiple devices (if we identify need).'''
    
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


def get_measurements(): 
    '''Import the google excel book from the internet, 
    parse the flow data table and the meta data table, 
    iterate over sheets within the sheetbook, and apply the Measurement class to each sheet.
    
    Returns a list of measurements, and summary list of dates and locations (there may not be
    a measurement on every day for every location).'''
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