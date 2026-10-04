#!/usr/bin/env python
# coding: utf-8

# In[2]:


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

# getting input mids from jiradata active merchants from google big query
project_id = os.getenv('GCP_PROJECT_ID')
credentials = service_account.Credentials.from_service_account_file('path_to_service_account.json')
bq_client = bigquery.Client(credentials=credentials,project=project_id)

source_table = 'gpay-327406.gonukkad.jiradata_all_merchants'

sql_query = f'''
    SELECT rwm_id
    FROM `{source_table}`
'''

# Run the query
query_job = bq_client.query(sql_query).result()

input_mid = []
for row in query_job:
    if row.rwm_id is not None and row.rwm_id.isdigit():
        input_mid.append((row.rwm_id).strip())

# Convert the list to a comma-separated string
input_rwmid_str = ','.join(map(str, input_mid))
# print(input_rwmid_str)
# exit()


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
        cursor.execute(f"SELECT * FROM [DL_Gonukkad].[dbo].[Gonukkad_Merchants] where [PK_GMBId] in ({input_rwmid_str})")
        print('Query has been successfully executed')
    except Exception as e:
        print("Exception occurred")
    toCSV = cursor.fetchall()
    conn.commit()
    count = 0
    return toCSV

#Function to handle boolean values
def convert_boolean(value):
    return 1 if value else 0

new_directory = os.path.join(os.getcwd(), 'gon_merchants_responses')

if not os.path.exists(new_directory):
    os.makedirs(new_directory)

today = date.today()
yesterday = today - timedelta(days=1)
today_filename = today.strftime("%Y-%m-%d")+".csv"
yesterday_filename = 'Gonukkad_Merchants_'+yesterday.strftime("%Y-%m-%d")+".csv"
rows = mysqlconnect()
csv_file_path = new_directory+'/'+yesterday_filename

fieldnames = list(rows[0].keys())

# fieldnames = ['PK_GMBId','BusinessName','MobileNo','FK_CategoryId','FK_SubCategoryId','APIAddress','AddressId','Lat','Long',
#               'ShopNo','BuildingNo','ComplexNo','GaliOrLane','LandMark','OpenTiming','CloseTiming','Monday','Tuesday',
#               'Wednesday','Thursday','Friday','Saturday','Sunday','TakeOut','Delivery','DineIn','ShopSignage','SelfieImage',
#               'ProofImage','ManualApproval','QRstring','FK_GeofenceId','CreatedBy','CreatedDatetime','FK_PodId','FK_TeamId',
#               'FK_TeamLeadId','FK_CityManagerId','FK_CityId','FK_StateId','FK_AreaId','FK_ZoneId','Geolocation','IsApproved',
#               'ApprovedDateTime','ApprovedBy','DriveThrough','InStoreShopping','NoContactDelivery','OnlineAvailability',
#               'Description','WebsiteURL','AveragePricelevelRs','SafetyPractices','DietaryRestriction','SafetyPracticesValue',
#               'DietaryRestrictionValue','APICountryName','APIStateName','APICityName','APIPostalCode','APILocality','FSEPincode'
#     ,'IsReview','ReviewBy','ReviewDateTime','RejectComment','ReviewComment','ShopFrontHeight','ShopFrontWidth',
#               'GenericRemarks','BatchNo','BIComments','UploadedBy','Uploadeddatetime','RejectReason','ReviewReason',
#               'ActionUserName','IsAppealed','AppealedBy','AppealedDatetime','AppealRemarks','ThreeTierCategoryId',
#               'ThreeTiercategoryName','ActionAppealedBy','ActionAppealedDatetime','AuditorCategoryId','AuditorSubCategoryId',
#               'ScreenId','PinCode','Owner_Name','Owner_EmailId','IsBusinessName','IsBusinessCategory','IsBusinessSubCat',
#               'IsShopNo','IsBuildingNo','IsLandMark','IsBusinessDesc','IsGenericRemarks','IsShopSign','IsSelfie','IsProof',
#               'ImageCapture','ImageCaptureType','UserInputAddress','PK_PaymentTermId','PK_PackageId','PackageRate','QRImage',
#               'UpdatedBy','UpdatedDatetime','OTP','GoogleProfilePicture','GoogleAccessToken','GoogleLoginDateTime','RegID',
#               'OSType','LastLoginDt','CurrentAppVersion','VersionUpdateDatetime','OSVersion','Model','UniqueId','IsOTPVerified'
#     ,'OTPVerified_DateTime','IsQrString','IsImageCapture','GoogleAccountID','security_code','OutletNo','RequestStatus'
#     ,'RequestTypeId','RequestID','Changemadeby','ChangemadebyLDAP','IsGMBAPILocationVerified','GMBAPIStatus','Date',
#               'GMBLastStatusDateTime','IsOwnerName','IsOperationgHours','IsHoliday','IsHalfDay','IsOwnerEmail','GMBEditImageURL',
#               'UserWebWebSiteURL','IsSMSSent','SMSSentDatetime','Message','ReqID','ResStatus','MobileORLandLine',
#               'IsGMBAPILocationTransferred','IsRequestEditStatus','GoogleLocationID','GSTNo','IsGMBAPILocationNotAccepted',
#               'IsActive','IsNotificationSent','IsGMBAPILocationPendingInvitation','RequestEditStatusDatetime',
#               'IsPostLocationMediaStatus','PostLocationMediaStatus','IsUpdateLocationStatus','UpdateLocationStatus',
#               'IsPostLocationMediaStatusGMBEdit','PostLocationMediaStatusGMBEdit','CompanyName','BillingState_Id',
#               'BillingCity_Id','RWMCityName','RWMEmployeeId','IVRSNo']
with open(csv_file_path, mode='w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

    # Write the header row with column names
    writer.writeheader()

    # Write the data rows
    for row in rows:
        row["Geolocation"] = None
        cleaned_row = {key: convert_boolean(value) if isinstance(value, bool) else value for key, value in row.items()}
        writer.writerow(cleaned_row)

storage_client = storage.Client.from_service_account_json(
    'path_to_service_account.json')

def upload_to_bucket(blob_name, path_to_file, bucket_name):
    """ Upload data to a bucket"""

    bucket = storage_client.get_bucket(bucket_name)
    print(bucket)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(path_to_file)

    #returns a public url
    return blob.public_url

upload_to_bucket('live/Gonukkad_Merchants/'+yesterday_filename,csv_file_path,'bucket_name')

#Renaming files name inside bucket on cloud

bucket = storage_client.get_bucket('bucket_name')

folder_name = 'live/Gonukkad_Merchants/'

files = bucket.list_blobs(prefix=folder_name)
for file in files:
    if not file.name.endswith('/'):
        if not yesterday_filename in file.name:
            if '.' in file.name:
                new_name = file.name.replace('.csv','')
                print(new_name)
                bucket.rename_blob(file,new_name)

time.sleep(10)

#Data push into permanent table

# credentials = service_account.Credentials.from_service_account_file('/home/siddharth/Downloads/service_account.json')
bq_client = bigquery.Client(credentials=credentials,project=project_id)

source_table = 'gonukkad.temp_Live_Merchants'
destination_table = 'gonukkad.Live_Merchants'

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