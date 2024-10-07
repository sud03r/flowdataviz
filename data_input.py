import pandas as pd
import requests as r
from io import BytesIO, StringIO
import datetime
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import os
from bs4 import BeautifulSoup


def import_googlesheet(url = None): 
    '''As there is only one google sheet, I just hard code the url. 
    otherwise I would have this function iterate over files within a folder. 
    Returns xlsx file.'''
    if url is None: 
        #Default sheet_id given from the project specifications
        sheet_id = '1mrbBkhl6TDZNPUTZkHOaRw6MqLU5VHyURoRnQNqZ7-M'
        url = "https://docs.google.com/spreadsheets/export?exportFormat=xlsx&id=" + sheet_id
    
    file = r.get(url)
    data = BytesIO(file.content)
    xlsx = pd.ExcelFile(data)    
    
    return xlsx

def auth_google():
    '''
    Authenticates with googledrive to be able to read all uploaded worksheets.
    Uses a service account so that access will persist over a longer period of time (I believe indefinitely). 
    The service account is managed by flowdataviz@gmail.com
    '''
    SERVICE_ACCOUNT_FILE = 'creek-data-viz-9355c63a465b.json'
    SCOPES = ['https://www.googleapis.com/auth/drive']
    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
    drive = GoogleDrive(gauth)
    
    return drive

def read_files(drive): 
    '''
    Loop over all files uploaded via the google form. 
    The google folder is set to public
    Returns filename and a download link. 
    '''
    folderID = '1JcFXUagRISwGaVHmmTzyJiXodLPSjaGhcuzkT7G_8EPdr5KvS2E8Baid7GWcd8S4B-HBE_kG'
    file_list = drive.ListFile({'q': f"'{folderID}' in parents and trashed=false"}).GetList()
    
    tags = ['title', 'webContentLink', 'fileExtension']
    
    #return only a subset of relevant tags. 
    file_tags = [{tag: file[tag] for tag in tags} for file in file_list]

    return file_tags
    

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
        
        try: 
            self.flow_data = flow_data.dropna().copy()
            self.discharge = self.flow_data[self.kDischargeColName].sum()
            self.area = self.flow_data[self.kAreaColName].sum()
            self.average_velocity = self.discharge / self.area
            self.max_observed_depth = self.flow_data[self.kDepthColName].max()
        except KeyError: 
            raise Exception(f'Could not find flow data. Please check {self.name} for formatting issues.')
        
        
        
        
        self.meta_table = meta_data
        for variable, coord in self.meta_table_schema.items(): 
            self.__dict__[variable] = self.meta_table.iloc[coord[0], coord[1]]
            
            if pd.isnull(self.__dict__[variable]) and coord[2:]: 
                #If there is a backup location listed, use that instead. 
                self.__dict__[variable] = self.meta_table.iloc[coord[2][0], coord[2][1]]
        
        if pd.isnull(self.site_code): 
            self.site_code = self.name.split(' ')[0]
        self.crew = self.crew.split(', ')
        
        if pd.isnull(self.site_code) or pd.isnull(self.date):
            raise ValueError(f'Could not find value for location or date. Please check {self.name} for formatting issues.')

        self.flow_data['location'] = self.site_code
        self.flow_data['date'] = self.date.strftime('%Y/%m/%d')
        
        
        
        
def import_slo_water(location, start=datetime.datetime(2024, 10, 1, 0, 0), end=datetime.datetime.now()): 
    '''Copied the URL from the csv-download option, and parsed it for legibility. 
    Currently accepts starting and ending timestamps as arguments, returns csv over that period.
    '''
    
    url_base = 'https://wr.slocountywater.org/export/file/'

    args = {'site_id': '', 
            'site' : '', 
            'device_id': '',
            'device': '',
            'mode' : '',
            'hours' : '',
            'data_start' : start.strftime('%Y-%m-%d %H:%M:%S'),
            'data_end' : end.strftime('%Y-%m-%d %H:%M:%S'),
            'tz' : 'US%2FPacific',
            'format_datetime' : '%25Y-%25m-%25d+%25H%3A%25i%3A%25S',
            'mime' : 'txt',
            'delimiter' : 'comma'}
    args.update(location)
    url = url_base + '?' + '&'.join(['='.join([key, value]) for key, value in args.items()])

    response = r.get(url)
    
    if not response.ok: 
        return pd.DataFrame()

    csv_data = StringIO(response.text)
    df = pd.read_csv(csv_data)
    return df

def get_thresholds(location): 
    '''
    Runs an http request for the stage page for the location. 
    It searches for span tags that include a measurement in ft. 
    The channel bottom tag background color ff9900.
    This is not a robust method of finding the thresholds, but works at this moment. 
    '''
    url_base = 'https://wr.slocountywater.org/sensor/'
    url = url_base + '?' + '&'.join(['='.join([key, value]) for key, value in location.items()])
    response = r.get(url)
    if not response.ok: 
        return 0
    soup = BeautifulSoup(response.content, 'html.parser')
    
    #The thresholds are the only text in span tags. The smallest value should refer to the 
    #lowest point of the feature
    thresholds = soup.find_all('span', string=lambda x: x and 'ft' in x)
    threshold = min([float(thresh.text.split()[0]) for thresh in thresholds])
    return threshold
    
    


def get_measurements(): 
    '''Import the google excel book from the internet, 
    parse the flow data table and the meta data table, 
    iterate over sheets within the sheetbook, and apply the Measurement class to each sheet.
    
    Returns a list of measurements, and summary list of dates and locations (there may not be
    a measurement on every day for every location).'''
    drive = auth_google()
    files = read_files(drive)
    
    list_measurements = []
    list_dates = set()
    list_sites = set()
    for file in files: 
        if file['fileExtension'] != 'xlsx': 
            continue
        xlsx = import_googlesheet(file['webContentLink'])
        flow_data, meta_data = parse_tables(xlsx)
        for name in flow_data.keys(): 
            try:
                measure = Measurement(name, flow_data[name], meta_data[name])
                list_measurements.append(measure)
                list_dates.add(measure.date)
                list_sites.add(measure.site_code)
            except Exception as error: 
                print(repr(error))
                continue
    
    return list_measurements, sorted(list(list_dates)), list(list_sites)