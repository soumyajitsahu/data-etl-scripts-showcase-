#!/usr/bin/python3

import os
import pymssql
import csv
import requests
import json
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs
from google.cloud import bigquery
from google.oauth2 import service_account
from google.cloud import storage
import pandas as pd
from google.cloud import logging

load_dotenv('secrets.env')

mid_file_path = "daily_active_mid_counts_dir_token.txt"

def update_daily_active_mid_count(input_mid):
    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Check if file exists
    if os.path.exists(mid_file_path):
        # Read existing data from the file
        with open(mid_file_path, "r") as file:
            lines = file.readlines()

        # Check if the current date is already present in the file
        date_found = False
        for i, line in enumerate(lines):
            if line.startswith(current_date):
                # If the date is found, update its count
                date_found = True
                count = int(line.split(":")[1].strip()) + 1
                lines[i] = f"{current_date}: {len(input_mid)}\n"
                break

        # If the current date is not found, add it to the file with active mids count
        if not date_found:
            lines.append(f"{current_date}: {len(input_mid)}\n")

        # Write the updated data back to the file
        with open(mid_file_path, "w") as file:
            file.writelines(lines)
    else:
        # If the file doesn't exist, create it and write the current date with active mids count
        with open(mid_file_path, "w") as file:
            file.write(f"{current_date}: {len(input_mid)}\n")

# getting input mids from jiradata active merchants from google big query
project_id = 'gcp_cloud_project_id'
credentials = service_account.Credentials.from_service_account_file('path_to_service.json_directory')
bq_client = bigquery.Client(credentials=credentials,project=project_id)

source_table = 'source_table_in_cloud.csv'

sql_query = f'''
    SELECT RWM_Merchant_ID_10143
    FROM `{source_table}`
'''

# Run the query
query_job = bq_client.query(sql_query).result()

input_mid = []
for row in query_job:
    if row.RWM_Merchant_ID_10143 is not None and row.RWM_Merchant_ID_10143.isdigit():
        input_mid.append((row.RWM_Merchant_ID_10143).strip())

print("active mec count to be considered:",len(input_mid))
update_daily_active_mid_count(input_mid)
# exit()

# Convert the list to a comma-separated string
input_rwmid_str = ','.join(map(str, input_mid))


#Connecting to the datalake to fetch required records
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
        cursor.execute(f"select [PK_GMBId], [GoogleAccessToken], [GoogleAccountID], [GoogleLocationID] from azure_table where [PK_GMBId] in ({input_rwmid_str})")
        print('Query has been successfully executed')
    except Exception as e:
        print("Exception occurred")
    toCSV = cursor.fetchall()
    count = 0
    return toCSV

#writing records in csv file and save in local machine

rows = mysqlconnect()
file_name = 'token_data.csv'
token_csv_file_path = 'path_to_write_token_file/'+file_name
field_name = ['PK_GMBId','GoogleAccessToken', 'GoogleAccountID', 'GoogleLocationID']
with open(token_csv_file_path, mode='w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file,fieldnames=field_name)
    writer.writeheader()

    for row in rows:
        if row['GoogleLocationID'] is not None and row['GoogleAccessToken'] is not None:
            writer.writerow(row)


def generate_access_token(refresh_token):
    token_endpoint = 'https://accounts.google.com/o/oauth2/token'
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': os.getenv('CLIENT_ID'),
        'client_secret': os.getenv('CLIENT_SECRET')
    }

    response = requests.post(token_endpoint, data=data)
    # directory_path_oauth = os.path.join(new_directory,'oauth_json_response')
    # if not os.path.exists(directory_path_oauth):
    #     os.makedirs(directory_path_oauth)
    # json_file_path = os.path.join(directory_path_oauth, f'{row["PK_GMBId"]}_details.json')
    # with open(json_file_path, 'w', encoding='utf-8') as json_file:
    #     json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        # Assuming the response contains an access token
        access_token = response.json().get('access_token')
        return access_token
    else:
        return None


#accounts url
url1 = 'https://mybusiness.googleapis.com/v1/accounts'
#location url
base_url2 = 'https://mybusinessbusinessinformation.googleapis.com/v1/'
endpoint_2 = '?readMask=storeCode,regularHours,name,languageCode,title,phoneNumbers,categories,storefrontAddress,websiteUri,regularHours,specialHours,serviceArea,labels,adWordsLocationExtensions,latlng,openInfo,metadata,profile,relationshipData,moreHours'
#verification url
base_url3 = 'https://mybusinessverifications.googleapis.com/v1/'
endpoint_3 = 'verifications'
#get_voice_of_merchants url
base_url4 = 'https://mybusinessverifications.googleapis.com/v1/'
endpoint_4 = 'VoiceOfMerchantState'
#reviews url
base_url5 = 'https://mybusiness.googleapis.com/v4/'
endpoint_5 = 'reviews'
#media url
base_url6 = 'https://mybusiness.googleapis.com/v4/'
endpoint_6 = 'media'
#performance url
date_to_pass = (date.today()-timedelta(days=7))
base_url7 = 'https://businessprofileperformance.googleapis.com/v1/'
#automated with D-4, means dates will automatically get fetched in this
endpoint_7 = f':fetchMultiDailyMetricsTimeSeries?dailyMetrics=WEBSITE_CLICKS&dailyMetrics=CALL_CLICKS&dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_MAPS&dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_SEARCH&dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_MAPS&dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_SEARCH&dailyMetrics=BUSINESS_CONVERSATIONS&dailyMetrics=BUSINESS_DIRECTION_REQUESTS&dailyRange.start_date.year={date_to_pass.year}&dailyRange.start_date.month={date_to_pass.month}&dailyRange.start_date.day={date_to_pass.day}&dailyRange.end_date.year={date_to_pass.year}&dailyRange.end_date.month={date_to_pass.month}&dailyRange.end_date.day={date_to_pass.day}'
#Manual endpoint means we can fetch insights for particular day range, added manually
# endpoint_7 = ':fetchMultiDailyMetricsTimeSeries?dailyMetrics=WEBSITE_CLICKS&dailyMetrics=CALL_CLICKS&dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_MAPS&dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_SEARCH&dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_MAPS&dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_SEARCH&dailyMetrics=BUSINESS_CONVERSATIONS&dailyMetrics=BUSINESS_DIRECTION_REQUESTS&dailyRange.start_date.year=2023&dailyRange.start_date.month=10&dailyRange.start_date.day=01&dailyRange.end_date.year=2023&dailyRange.end_date.month=10&dailyRange.end_date.day=31'
#search keyword url
base_url8 = 'https://businessprofileperformance.googleapis.com/v1/'
endpoint_8 = 'searchkeywords/impressions/monthly?monthlyRange.start_month.year=2023&monthlyRange.start_month.month=11&monthlyRange.end_month.year=2023&monthlyRange.end_month.month=11'
#service url
base_url9 = 'https://mybusinessbusinessinformation.googleapis.com/v1/'
endpoint_9 = '?readMask=serviceItems'
#local post url
base_url10 = 'https://mybusiness.googleapis.com/v4/'
endpoint_10 = 'localPosts'

parent_dir = "/home/siddharth/Documents/GoNukkad/gmb_mec_token_api/responses"

new_directory = os.path.join(parent_dir, f'{date.today()}')

if not os.path.exists(new_directory):
    os.makedirs(new_directory)


#logic to fetch insight date from url:
query_params = parse_qs(endpoint_7)
#Extract year, month, and day
start_year = int(query_params['dailyRange.start_date.year'][0])
start_month = int(query_params['dailyRange.start_date.month'][0])
start_day = int(query_params['dailyRange.start_date.day'][0])
#Constructing date
from datetime import datetime
Insight_Date = date(start_year, start_month, start_day)

# Functions to make an API request with parameters
#function to get account details
def account_api_request(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url1, headers=headers)
    directory_path_account = os.path.join(new_directory,'account_json_response')
    if not os.path.exists(directory_path_account):
        os.makedirs(directory_path_account)
    json_file_path = os.path.join(directory_path_account, f'{row["PK_GMBId"]}_details.json')

    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        # Assuming the response contains data

        if(response.json()):
            return response.json()['accounts']
    else:
        return None

#function to get location details
def location_api_request(access_token, location_id):
    url_2 = f'{base_url2}{location_id}/{endpoint_2}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_2, headers=headers)
    directory_path_location = os.path.join(new_directory,'location_json_response')
    if not os.path.exists(directory_path_location):
        os.makedirs(directory_path_location)
    json_file_path = os.path.join(directory_path_location, f'{row["PK_GMBId"]}_details.json')
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        if(response.json()):
            return [response.json()]
    else:
        return None

#function to get verification details
def verification_api_request(access_token, location_id):
    url_3 = f'{base_url3}{location_id}/{endpoint_3}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_3, headers=headers)
    directory_path_verification = os.path.join(new_directory,'verification_json_response')
    if not os.path.exists(directory_path_verification):
        os.makedirs(directory_path_verification)
    json_file_path = os.path.join(directory_path_verification, f'{row["PK_GMBId"]}_details.json')

    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:

        if(response.json()):
            return response.json()['verifications']
    else:
        return None

#function to get voice of merchant details
def vom_api_request(access_token, location_id):
    url_4 = f'{base_url3}{location_id}/{endpoint_4}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_4, headers=headers)
    directory_path_vom = os.path.join(new_directory,'vom_json_response')
    if not os.path.exists(directory_path_vom):
        os.makedirs(directory_path_vom)
    json_file_path = os.path.join(directory_path_vom, f'{row["PK_GMBId"]}_details.json')

    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        if(response.json()):
            # file_size_bytes = os.path.getsize(json_file_path)
            return response.json()
    else:
        return None

#function to get review details
def review_api_request(access_token, account_id, location_id):
    nextPageToken = None
    url_5 = f'{base_url5}{account_id}/{location_id}/{endpoint_5}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_5, headers=headers)
    directory_path_review = os.path.join(new_directory,'review_json_response')
    if not os.path.exists(directory_path_review):
        os.makedirs(directory_path_review)
    nextPageToken = (response.json()).get('nextPageToken')
    json_file_path = os.path.join(directory_path_review, f'{row["PK_GMBId"]}_details.json')
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)
    page_count = 1
    while nextPageToken:
        params = {'pageToken' : nextPageToken}
        json_file_path_1 = os.path.join(directory_path_review, f'{row["PK_GMBId"]}_{page_count}_details.json')
        response_1 = requests.get(url_5, headers=headers, params=params)
        with open(json_file_path_1, 'w', encoding='utf-8') as json_file:
            json.dump(response_1.json(), json_file, ensure_ascii=False, indent=4)
        nextPageToken = response_1.json().get('nextPageToken')
        page_count += 1

    if response.status_code == 200:
        if(response.json()):
            return response.json()
    else:
        return None

#function to get media details
def media_api_request(access_token, account_id, location_id):
    url_6 = f'{base_url6}{account_id}/{location_id}/{endpoint_6}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_6, headers=headers)
    directory_path_media = os.path.join(new_directory,'media_json_response')
    if not os.path.exists(directory_path_media):
        os.makedirs(directory_path_media)
    json_file_path = os.path.join(directory_path_media, f'{row["PK_GMBId"]}_details.json')
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        if(response.json()):
            return response.json()
    else:
        return None

#function to get performance details
def performance_api_request(access_token, location_id):
    url_7 = f'{base_url7}{location_id}/{endpoint_7}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_7, headers=headers)

    directory_path_performance = os.path.join(new_directory,'performance_json_response')
    if not os.path.exists(directory_path_performance):
        os.makedirs(directory_path_performance)

    json_file_path = os.path.join(directory_path_performance, f'{row["PK_GMBId"]}_details.json')

    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        if(response.json()):
            return response.json()['multiDailyMetricTimeSeries']
    else:
        return None


#function to get search keyword details
def searchkeyword_api_request(access_token, location_id):
    url_8 = f'{base_url8}{location_id}/{endpoint_8}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_8, headers=headers)
    directory_path_search_keyword = os.path.join(new_directory,'searchkeyword_json_response')
    if not os.path.exists(directory_path_search_keyword):
        os.makedirs(directory_path_search_keyword)
    json_file_path = os.path.join(directory_path_search_keyword, f'{row["PK_GMBId"]}_details.json')
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        if(response.json()):
            return response.json()['searchKeywordsCounts']

#function to get service details
def service_api_request(access_token, location_id):
    url_9 = f'{base_url9}{location_id}/{endpoint_9}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_9, headers=headers)
    directory_path_service = os.path.join(new_directory,'service_json_response')
    if not os.path.exists(directory_path_service):
        os.makedirs(directory_path_service)
    json_file_path = os.path.join(directory_path_service, f'{row["PK_GMBId"]}_details.json')
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)

    if response.status_code == 200:
        if(response.json()):
            return response.json()["serviceItems"]
    else:
        return None

#function to get local posts
def localpost_api_request(access_token, account_id, location_id):
    nextPageToken = None
    url_10 = f'{base_url10}{account_id}/{location_id}/{endpoint_10}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url_10, headers=headers)
    directory_path_localpost = os.path.join(new_directory,'localpost_json_response')
    if not os.path.exists(directory_path_localpost):
        os.makedirs(directory_path_localpost)
    nextPageToken = (response.json()).get('nextPageToken')
    json_file_path = os.path.join(directory_path_localpost, f'{row["PK_GMBId"]}_details.json')
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(response.json(), json_file, ensure_ascii=False, indent=4)
    all_data = (response.json().get('localPosts', []))
    page_count = 1
    while nextPageToken:
        params = {'pageToken' : nextPageToken}
        json_file_path_1 = os.path.join(directory_path_localpost, f'{row["PK_GMBId"]}_{page_count}_details.json')
        response_1 = requests.get(url_10, headers=headers, params=params)
        with open(json_file_path_1, 'w', encoding='utf-8') as json_file:
            json.dump(response_1.json(), json_file, ensure_ascii=False, indent=4)
        nextPageToken = response_1.json().get('nextPageToken')
        page_count += 1
        all_data.extend(response_1.json().get('localPosts', []))

    if response.status_code == 200:
        if all_data:
            return all_data
        # if(response.json()):
        #     return response.json()['localPosts']
    else:
        return None

#defining function to extract address:
def extract_address(data):
    address_parts = []

    # Extract address parts, and if any part is missing, replace it with an empty string
    if "storefrontAddress" in data and "addressLines" in data["storefrontAddress"]:
        address_parts = data["storefrontAddress"]["addressLines"]

    address = ", ".join(address_parts)  # Join address parts with a comma and space

    if "storefrontAddress" in data:
        if "locality" in data["storefrontAddress"]:
            address += f", {data['storefrontAddress']['locality']}"
        if "administrativeArea" in data["storefrontAddress"]:
            address += f", {data['storefrontAddress']['administrativeArea']}"
        if "postalCode" in data["storefrontAddress"]:
            address += f" {data['storefrontAddress']['postalCode']}"

    return address if address else "Not_Found"

#creating csv file to write
insight_csv_file = f'MEC_insights_{date.today()}_{Insight_Date}.csv'
# account_csv_file = 'test_190241.csv'
directory_path = '/home/siddharth/Documents/GoNukkad/gmb_mec_token_api/insights'
insight_csv_file_path = os.path.join(directory_path,insight_csv_file)

#list of refresh Tokens

details = []

#reading file to get access token by iterating list of refresh tokens
with open(token_csv_file_path, 'r') as csvfile:

    reader = csv.DictReader(csvfile)
    # included_cols = [1]

    #iteration
    for row in reader:
        # if row['PK_GMBId'] != '192230':
        #     continue
        refresh_token = row['GoogleAccessToken']
        row['Data_Date'] = date.today()
        row['Insight_Date'] = Insight_Date
        location_id = "locations"+"/"+(row['GoogleLocationID'].strip())
        # print(location_id)
        account_id = "accounts/105586222194746834784"

        access_token = generate_access_token(refresh_token)
        # print(access_token)

        if access_token:
            # Add the access token to the data
            # print('oops! I am in loop')
            # exit()
            row['access_token'] = None
            row['account_id'] = account_id
            #location api function call
            response_data_2 = location_api_request(access_token,location_id)
            # print(response_data_2)
            # exit()
            if response_data_2:
                business_name = response_data_2[0]['title']
                # print(business_name)
                row['primary_phone'] = "Not_Found"
                if 'primaryPhone' in response_data_2[0]['phoneNumbers']:
                    primary_phone = response_data_2[0]['phoneNumbers']['primaryPhone']
                    row['primary_phone'] = primary_phone
                #additional_phone = response_data_2[0]['phoneNumbers']['additionalPhones'][0]
                row['additional_phone'] = "Not_Found"
                if 'additionalPhones' in response_data_2[0]['phoneNumbers']:
                    additional_phone = response_data_2[0]['phoneNumbers']['additionalPhones'][0]
                    row['additional_phone'] = additional_phone
                row['website_url'] = "Not_Found"
                if 'websiteUri' in response_data_2[0]:
                    website_url = response_data_2[0]['websiteUri']
                    row['website_url'] = website_url
                row['business_address'] = "Not_Found"
                # print(response_data_2_sub)
                # print(response_data_2_sub[0])

                addresses = []
                for item in response_data_2:
                    address = extract_address(item)
                    addresses.append(address)
                    row['business_address'] = addresses[0]
                    # print(row['business_address'])

                # exit()




                #store_code = response_data_2[0]['storeCode']
                row['store_code'] = "Not_Found"
                if 'storeCode' in response_data_2[0]:
                    store_code = response_data_2[0]['storeCode']
                    row['store_code'] = store_code
                row['regular_hours'] = "Not_Found"
                if 'regularHours' in response_data_2[0]:
                    daywise_hours = {}
                    for period in response_data_2[0]["regularHours"]["periods"]:
                        day = period["openDay"]
                        if "openTime" in period and "closeTime" in period:
                            open_time = period["openTime"].get("hours")
                            close_time = period["closeTime"].get("hours")
                            if open_time is not None and close_time is not None:
                                daywise_hours[day] = f"{open_time}-{close_time}"

                        row['regular_hours'] = daywise_hours
                #print(response_data_2)
                additional_categories_count = 0
                if "additionalCategories" in response_data_2[0]["categories"]:
                    for dic in response_data_2[0]["categories"]["additionalCategories"]:
                        for key, value in dic.items():
                            if key == "name":
                                additional_categories_count = additional_categories_count+1
                #print(additional_categories_count)
                row["additional_categories_count"] = additional_categories_count
                row['location_id'] = location_id
                row['business_name'] = business_name

                row['primary_category'] = "Not_Found"
                if "displayName" in response_data_2[0]["categories"]["primaryCategory"]:
                    row['primary_category'] = (response_data_2[0]["categories"]["primaryCategory"]['displayName'])

                row['review_url'] = "Not_Found"
                if "newReviewUri" in response_data_2[0]["metadata"]:
                    row['review_url'] = (response_data_2[0]["metadata"]["newReviewUri"])
                row['map_url'] = 'Not_Found'
                if 'mapsUri' in response_data_2[0]['metadata']:
                    row['map_url'] = (response_data_2[0]["metadata"]["mapsUri"])
                #verification api function call
                # response_data_3 = verification_api_request(access_token,location_id, directory_path_verification)

                #vom api function call
                response_data_4 = vom_api_request(access_token, location_id)
                #review api function call
                response_data_5 = review_api_request(access_token, account_id, location_id)
                #media api function call
                response_data_6 = media_api_request(access_token, account_id, location_id)
                #Performance api function call
                response_data_7 = performance_api_request(access_token, location_id)
                #search keyword api function call
                # response_data_8 = searchkeyword_api_request(access_token, location_id, directory_path_search_keyword)
                #service api function call
                response_data_9 = service_api_request(access_token, location_id)
                #local post api function call
                response_data_10 = localpost_api_request(access_token, account_id, location_id)

                if response_data_7:
                    metric_sum = {}

                    for data_dict in response_data_7:
                        daily_metric_time_series = data_dict.get("dailyMetricTimeSeries", [])

                        for series in daily_metric_time_series:
                            daily_metric = series.get('dailyMetric')
                            time_series = series.get('timeSeries',{})
                            dated_value = time_series.get('datedValues',[])

                            sum = 0

                            for datevalue in dated_value:
                                value = datevalue.get('value')
                                if value:
                                    try:
                                        sum += int(value)
                                    except ValueError:
                                        pass
                            metric_sum[daily_metric] = sum
                    row['phone_call_actions'] = metric_sum.get('CALL_CLICKS', 0)
                    row['website_actions'] = metric_sum.get('WEBSITE_CLICKS', 0)
                    row['directions_actions'] = metric_sum.get('BUSINESS_DIRECTION_REQUESTS', 0)
                    row['total_actions'] = (metric_sum.get('CALL_CLICKS', 0)+metric_sum.get('WEBSITE_CLICKS', 0)+metric_sum.get('BUSINESS_DIRECTION_REQUESTS', 0))
                    row['business_map_impression'] = (metric_sum.get('BUSINESS_IMPRESSIONS_DESKTOP_MAPS', 0)+metric_sum.get('BUSINESS_IMPRESSIONS_MOBILE_MAPS',0))
                    row['business_search_impression'] = (metric_sum.get('BUSINESS_IMPRESSIONS_DESKTOP_SEARCH',0)+metric_sum.get('BUSINESS_IMPRESSIONS_MOBILE_SEARCH',0))
                    row['total_impressions'] = (row['business_map_impression']+row['business_search_impression'])
                    row['business_conversations'] = metric_sum.get('BUSINESS_CONVERSATIONS',0)
                # print(response_data_5)
                # exit()
                if response_data_5:
                    row['overall_rating'] = None
                    row['total_review_count'] = None
                    if 'averageRating' in response_data_5:
                        overall_rating = response_data_5['averageRating']
                    if 'totalReviewCount' in response_data_5:
                        total_review_count = response_data_5['totalReviewCount']

                        row['overall_rating'] = round(overall_rating,1)
                        row['total_review_count'] = total_review_count
                        # print(row['overall_rating'])
                        # print(row['total_review_count'])
                # exit()
                if response_data_6:
                    if 'totalMediaItemCount' in response_data_6:
                        media_count = response_data_6['totalMediaItemCount']
                    row['media_count'] = media_count
                    row['has_cover'] = "No"
                    row['has_menu'] = "No"
                    for item in response_data_6['mediaItems']:
                        if "category" in item['locationAssociation']:
                            category = item['locationAssociation']['category']
                            if category == "COVER":
                                has_cover = "Yes"
                                row['has_cover'] = has_cover
                            elif category == "MENU":
                                has_menu = "Yes"
                                row['has_menu'] = has_menu
                if response_data_9:
                    service_count = 0
                    for item in response_data_9:
                        for key, value in item.items():
                            if key == "structuredServiceItem" or key == "freeFormServiceItem":
                                service_count += 1
                    row['service_count'] = service_count

                if response_data_10:
                    latest_offer = None
                    offer_count = 0
                    promo_count = 0
                    for item in response_data_10:
                        if item.get("topicType") == 'OFFER':
                            offer_count += 1
                            if latest_offer is None or datetime.strptime(item['createTime'], "%Y-%m-%dT%H:%M:%S.%fZ") > datetime.strptime(latest_offer['createTime'], "%Y-%m-%dT%H:%M:%S.%fZ"):
                                latest_offer = item
                        if item.get("topicType") == 'STANDARD':
                            promo_count +=1

                    if latest_offer:
                        start_date = latest_offer.get('event', {}).get('schedule', {}).get('startDate')
                        end_date = latest_offer.get('event', {}).get('schedule', {}).get('endDate')
                        update_date = latest_offer.get('updateTime')
                        row["offer_starts_at"] = date(start_date['year'], start_date['month'], start_date['day'])
                        row["offer_ends_at"] = date(end_date['year'], end_date['month'], end_date['day'])
                        row["offer_updates_at"] = (datetime.strptime(update_date, "%Y-%m-%dT%H:%M:%S.%fZ")).date()
                    row["offer_count"] = offer_count
                    row["promo_count"] = promo_count
                if response_data_4:
                    row['profile_status'] = 'Not_Found'
                    comply_with_guidelines = response_data_4.get('complyWithGuidelines', {})
                    recommendation_reason = comply_with_guidelines.get('recommendationReason', None)
                    if recommendation_reason == "BUSINESS_LOCATION_SUSPENDED":
                        row['profile_status'] = "suspended"
                        # break
                    elif recommendation_reason == "BUSINESS_LOCATION_DISABLED":
                        row['profile_status'] = 'location_disabled'
                        # break
                    elif 'waitForVoiceOfMerchant' in response_data_4:
                        row['profile_status'] = 'processing'
                        # break
                    elif response_data_4['hasVoiceOfMerchant'] and response_data_4["hasBusinessAuthority"]:
                        row['profile_status'] = 'verified'
                        # break
                    elif response_data_4.get('resolveOwnershipConflict') != None:
                        row['profile_status'] = 'duplicate'
                        # break
                    elif response_data_4.get("verify", {}).get("hasPendingVerification", True) == False:
                        row['profile_status'] = 'verification_required'
                        # break
                    else:
                        row['profile_status'] = 'unexpected_status'

                    # print(row['profile_status'])
                # exit()
            #print("response_data_2: ", response_data_2)


        else:
            print(f'Failed to generate an access token for refresh token: {refresh_token}')

        details.append(row)

        with open(insight_csv_file_path, 'w', newline='') as csvfile:
            fieldnames = ['PK_GMBId','Insight_Date','Data_Date','GoogleAccessToken','access_token','GoogleLocationID', 'GoogleAccountID','store_code','business_name', 'business_address','account_id', 'location_id', 'primary_phone', 'additional_phone', 'website_url', 'overall_rating', 'total_review_count', 'media_count', 'has_cover', 'has_menu', 'regular_hours', 'additional_categories_count', 'phone_call_actions', 'website_actions', 'directions_actions', 'total_actions', 'business_search_impression', 'business_map_impression', 'total_impressions','primary_category', 'service_count','offer_count','offer_starts_at', 'offer_ends_at','offer_updates_at', 'business_conversations', 'profile_status', 'review_url', 'map_url', 'promo_count']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for item in details:
                writer.writerow(item)

token_data_df = pd.read_csv(token_csv_file_path)
input_row_count = token_data_df.shape[0]

insight_data_df = pd.read_csv(insight_csv_file_path)
output_row_count = insight_data_df.shape[0]

def upload_to_bucket(blob_name, file_path, bucket_name):

    #enable services to access cloud storage

    if input_row_count == output_row_count:

        storage_client = storage.Client.from_service_account_json('/home/siddharth/Downloads/service_account.json')

        bucket=storage_client.get_bucket(bucket_name)
        print("destination bucket is: ", bucket)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(file_path)

        print(f'insight report has been uploaded to blob name: {blob} successfully')

        return 200

    else:
        print("sorry, insight report can't be ingested due to records mismatch. Please check input and output record counts.")

        logging_client = logging.Client.from_service_account_json('/home/siddharth/Downloads/service_account.json')
        logger = logging_client.logger('GMB-API-Data-Ingestion')
        logger.log_text('GMB API Data ingestion failed')




upload_to_bucket('GMB_API/'+insight_csv_file,insight_csv_file_path,'gonukkad')


#sending ingestion status on mail

# def send_alert(email_to, subject, body):
#     # Set up the email message
#     msg = EmailMessage()
#     msg['From'] = 'your_email@example.com'  # Sender's email address
#     msg['To'] = email_to  # Recipient's email address
#     msg['Subject'] = subject
#     msg.set_content(body)
#
#     # Connect to the SMTP server
#     with smtplib.SMTP('smtp.example.com', 587) as smtp:
#         smtp.ehlo()  # Identify yourself to the SMTP server
#         smtp.starttls()  # Enable TLS encryption
#         smtp.login('siddharth.chandel@vacobinary.in', 'xxxx')  # Login to your email account
#         smtp.send_message(msg)  # Send the email
#
# if ingestion_status != 200:
#     # Send alert email if data ingestion fails
#     email_to = 'raghvendra.mishra@vacobinary.in'
#     subject = 'Alert: GMB API Data Ingestion Failure'
#     body = 'The ETL data ingestion pipeline has failed. Data was not ingested into the cloud.'
#     send_alert(email_to, subject, body)






