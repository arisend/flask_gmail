from __future__ import print_function

from __future__ import print_function

import os
import time
import requests
import os.path
import psycopg2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from datetime import datetime
from flask import Flask, request, jsonify
from pyngrok import ngrok
from flask_ngrok import run_with_ngrok
import pytz
# TODO need to create separate file with credentials of DB and ngrok token,

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'





def update_table():
    """This function connects to Google Sheets Api and retrieve all records, checks with regex for corrects ones and save them to PSQL,
    if it's finds that order was removed from GSheets it's only mark it as removed in DB for possible future use and analysis.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=r'1nmYlA6X2tncvq9XQhSqtWVqLtoLWUfSHpM-qOrnMjrg',
                                    range='Лист1!A2:D100').execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')
            return

        print(values)
    except HttpError as err:
        print(err)





SCOPES = ['https://www.googleapis.com/auth/drive.file',
         'https://www.googleapis.com/auth/drive.readonly',
         'https://www.googleapis.com/auth/drive']


def fetch_changes(saved_start_page_token,addr):
    """Retrieve the list of changes for the currently authenticated user.
        prints changed file's ID
    Args:
        saved_start_page_token : StartPageToken for the current state of the
        account.
    Returns: saved start page token.

    Load pre-authorized user credentials from the environment.
    TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # create drive api client
        service = build('drive', 'v3', credentials=creds)

        # Begin with our last saved start token for this user or the
        # current token from getStartPageToken()
        page_token = saved_start_page_token
        # pylint: disable=maybe-no-member

        while page_token is not None:
            body = {
                'id': 'ngrok_webhook123243',
                'type': "web_hook",
                'address': r''
            }

            response = service.files().watch(fileId="1nmYlA6X2tncvq9XQhSqtWVqLtoLWUfSHpM-qOrnMjrg", body=body).execute()

            print(response)
    except HttpError as error:
        print(F'An error occurred: {error}')
        saved_start_page_token = None

    return saved_start_page_token


def create_webhock(addr):
    # saved_start_page_token is the token number
    fetch_changes(saved_start_page_token=209, addr=addr)


#create_webhock()







ngrok.set_auth_token("2BIpQLR4wReSkTXEffcniRJSs7j_7ukAceYqC9ehWqBbLv16V")
http_tunnel = ngrok.connect(5000)
print('test', http_tunnel.public_url)
#
create_webhock(str(http_tunnel.public_url).replace('http','https'))


def get_timestamp():
    dt=datetime.now(pytz.timezone('US/Central'))
    return dt.strftime(("%Y-%m-%d %H:%M:%S"))


app = Flask(__name__)
app.config["BASE_URL"] = http_tunnel.public_url
run_with_ngrok(app)
@app.route('/webhook', methods=['POST','GET'])
def webhook():
    """
    This function waits for call from GoogleSheet and runs table update once received it.
    """
    if request.method=='GET':
        return '<h1>  This is a webhook listener! You should send POST request in order to trigger it.</h1>'
    if request.method == 'POST':
        print(request.headers)
        cur_date=get_timestamp()
        print("Date and time of update ====>",cur_date)
        http_status=jsonify({'status':'success'}),200
    else:
        http_status='',400
    return http_status

# if __name__ == '__main__':
#      app.run() #


request = {
  'labelIds': ['INBOX'],
  'topicName': 'projects/myproject/topics/mytopic'
}
gmail.users().watch(userId='me', body=request).execute()
