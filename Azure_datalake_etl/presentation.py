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
        cursor.execute("SELECT * FROM [master].[dbo].[Gonukkad_Presentation]")
        print('Query has been successfully executed')
    except Exception as e:
        print("Exception occurred", exc_info=True)
    toCSV = cursor.fetchall()
    count = 0
    return toCSV

def convert_boolean(value):
    return 1 if value else 0

# today = date.today()
# yesterday = today - timedelta(days=1)
# today_filename = today.strftime("%Y-%m-%d")+".csv"
# yesterday_filename = yesterday.strftime("%Y-%m-%d")+".csv"
rows = mysqlconnect()
# print(rows[0].keys())
# exit()


new_directory = os.path.join(os.getcwd(), 'gon_presentation_responses')

if not os.path.exists(new_directory):
    os.makedirs(new_directory)

csv_file_path = new_directory+'/'+'presentation_data.csv'
# print(csv_file_path)
fieldnames = list(rows[0].keys())
with open(csv_file_path, mode='w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

    # Write the header row with column names
    writer.writeheader()

    # Write the data rows
    for row in rows:
        cleaned_row = {key: convert_boolean(value) if isinstance(value, bool) else value for key, value in row.items()}
        writer.writerow(cleaned_row)
# exit()


def upload_to_bucket(blob_name, path_to_file, bucket_name):
    """ Upload data to a bucket"""

    storage_client = storage.Client.from_service_account_json(
        'path_to_service_account.json')

    #print(buckets = list(storage_client.list_buckets())

    bucket = storage_client.get_bucket(bucket_name)
    print(bucket)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(path_to_file)

upload_to_bucket('live/presentation/'+'presentation_data.csv',csv_file_path,'bucket_name')