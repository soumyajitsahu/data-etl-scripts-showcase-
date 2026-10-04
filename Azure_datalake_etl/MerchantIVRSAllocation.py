#!/usr/bin/env python
# coding: utf-8

# In[5]:


import os

from datetime import date, timedelta, datetime
import pymssql
import logging
import subprocess
import csv
from google.cloud import storage
from google.cloud import bigquery
from google.oauth2 import service_account
import time
from dotenv import load_dotenv

load_dotenv('secrets.env')
from presentation import fieldnames


def mysqlconnect():
    conn = pymssql.connect(
        os.getenv('AZURE_HOST'),
        os.getenv('AZURE_USERNAME'),
        os.getenv('AZURE_PASSWORD'),
        os.getenv('AZURE_DATABASE')
    )
    cursor = conn.cursor(as_dict=True)
    if(cursor):
        print("Database connection established", conn.cursor())
    toCSV = []
    try:
        cursor.execute("SELECT * FROM [DL_Gonukkad].[dbo].[MerchantIVRSAllocation]")
        print('Query has been successfully executed')
    except Exception as e:
        print("Exception occurred", exc_info=True)
    toCSV = cursor.fetchall()
    count = 0
    return toCSV

def convert_boolean(value):
    return 1 if value else 0

new_directory = os.path.join(os.getcwd(), 'gon_ivr_allocation_responses')

if not os.path.exists(new_directory):
    os.makedirs(new_directory)

today = date.today()
yesterday = today - timedelta(days=1)
today_filename = today.strftime("%Y-%m-%d")+".csv"
yesterday_filename = 'MerchantIVRSAllocation_'+yesterday.strftime("%Y-%m-%d")+".csv"
rows = mysqlconnect()
csv_file_path = new_directory+'/'+yesterday_filename
fieldnames = list(rows[0].keys())
# fieldnames = ['PK_MerchantIVRS','FK_MerchantID','IVRSNo','TataTele_Department','TataTele_Agents','CreatedBy',
#               'CreatedDateTime','IsActive','IsDeleted','UpdatedBy','UpdatedDateTime']
with open(csv_file_path, mode='w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

    # Write the header row with column names
    writer.writeheader()

    # Write the data rows
    for row in rows:
        cleaned_row = {key: convert_boolean(value) if isinstance(value, bool) else value for key, value in row.items()}
        writer.writerow(cleaned_row)

storage_client = storage.Client.from_service_account_json(
    'path_to_service_account.json')

def upload_to_bucket(blob_name, path_to_file, bucket_name):

    bucket = storage_client.get_bucket(bucket_name)
    print(bucket)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(path_to_file)

    # return blob.public_url

    folder_name = 'live/MerchantIVRSAllocation/'

    files = bucket.list_blobs(prefix=folder_name)
    for file in files:
        if not file.name.endswith('/'):
            if not yesterday_filename in file.name:
                if '.' in file.name:
                    new_name = file.name.replace('.csv','')
                    print(new_name)
                    bucket.rename_blob(file,new_name)

upload_to_bucket('live/MerchantIVRSAllocation/'+yesterday_filename,csv_file_path,'bucket_name')

time.sleep(10)

#Data push into permanent table
project_id = os.getenv('GCP_PROJECT_ID')
credentials = service_account.Credentials.from_service_account_file('path_to_service_account.json')
bq_client = bigquery.Client(credentials=credentials,project=project_id)

source_table = 'gonukkad.temp_Live_Merchant_IVRS_Allocation'
destination_table = 'gonukkad.Live_Merchant_IVRS_Allocation'

sql_query = f'''
    CREATE OR REPLACE TABLE `{destination_table}`
    AS
    SELECT *
    FROM `{source_table}`
'''

# Run the query
query_job = bq_client.query(sql_query)

# Wait for the query to complete
query_job.result()

print(f'Table "{destination_table}" created or replaced successfully.')

# In[ ]: