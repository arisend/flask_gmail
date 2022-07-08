from flask import Flask, request, jsonify
from pyngrok import ngrok
from flask_ngrok import run_with_ngrok
from datetime import datetime
import pytz
import socket
socket.setdefaulttimeout(4000)
import json
import os.path
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from base64 import urlsafe_b64decode
import base64



def build_gmail_api_connection():
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/spreadsheets']
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
        # Call the Gmail API
        g_mail = build('gmail', 'v1', credentials=creds)
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')

    return g_mail
g_mail=build_gmail_api_connection()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="service_credentials.json"
ngrok.set_auth_token("")
http_tunnel = ngrok.connect(5000)
print('test', http_tunnel.public_url)
#
def get_timestamp():
    dt=datetime.now(pytz.timezone('US/Central'))
    return dt.strftime(("%Y-%m-%d %H:%M:%S"))


def get_mail_id_from_the_history(last_id):
    print(last_id)
    results = g_mail.users().history().list(userId='me',startHistoryId=last_id,  labelId="UNREAD", historyTypes=["messageAdded"]).execute()
    print(last_id,results)
    time.sleep(2)
    return results['history'][-1]['messages'][-1]["id"]
def get_full_message(message_id):
    results=g_mail.users().messages().get(userId='me', id=message_id, format='full').execute()
    print(results)
    payload = results['payload']
    headers = payload.get("headers")
    parts = payload.get("parts")
    folder_name = r''
    set_of_files = parse_parts(g_mail, parts, folder_name, results)
    has_subject = False
    if headers:
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name.lower() == 'from':
                # we print the From address
                print("From:", value)
            if name.lower() == "to":
                # we print the To address
                print("To:", value)
            if name.lower() == "subject":
                # make our boolean True, the email has "subject"
                has_subject = True
                print("Subject:", value)
            if name.lower() == "date":
                # we print the date when the message was sent
                print("Date:", value)
    return set_of_files
def parse_parts(service, parts, folder_name, message):
    """
    Utility function that parses the content of an email partition
    """
    set_of_files=set()
    if parts:
        for part in parts:
            filename = part.get("filename")
            mimeType = part.get("mimeType")
            body = part.get("body")
            data = body.get("data")
            file_size = body.get("size")
            part_headers = part.get("headers")
            if part.get("parts"):
                # recursively call this function when we see that a part
                # has parts inside
                parse_parts(service, part.get("parts"), folder_name, message)
            if mimeType == "text/plain":
                # if the email part is text plain
                if data:
                    text = urlsafe_b64decode(data).decode()
                    print(text)
            elif mimeType == "text/html":
                pass
                # !! IF YOU NEED TO SAVE HTML BODY OF EMAIL, YOU CAN UNCOMMENT THIS BLOCK OF CODE >>>>
                # if the email part is an HTML content
                # save the HTML file and optionally open it in the browser
                # if not filename:
                #     filename = "index.html"
                # filepath = os.path.join(folder_name, filename)
                # print("Saving HTML to", filepath)
                # with open(filepath, "wb") as f:
                #     f.write(urlsafe_b64decode(data))
                #set_of_files.add(filepath)
                #                                                                                <<<<<

            else:
                # attachment other than a plain text or HTML
                for part_header in part_headers:
                    part_header_name = part_header.get("name")
                    part_header_value = part_header.get("value")
                    if part_header_name == "Content-Disposition":
                        if "attachment" in part_header_value:
                            # we get the attachment ID
                            # and make another request to get the attachment itself
                            print("Saving the file:", filename, "size:", get_size_format(file_size))
                            attachment_id = body.get("attachmentId")
                            attachment = service.users().messages() \
                                        .attachments().get(id=attachment_id, userId='me', messageId=message['id']).execute()
                            data = attachment.get("data")
                            filepath = os.path.join(folder_name, filename)
                            set_of_files.add(filepath)
                            if data:
                                with open(filepath, "wb") as f:
                                    f.write(urlsafe_b64decode(data))
    return set_of_files
# utility functions
def get_size_format(b, factor=1024, suffix="B"):
    """
    Scale bytes to its proper byte format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"
def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

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
        # print(dir(request))
        # print(request.data)
        # print(request.query_string)
        # print(request.files)
        text=json.loads(request.data.decode("utf-8"))['message']['data']
        historyId=json.loads(base64.b64decode(text).decode())['historyId']
        print(historyId)
        with open('stored_id.txt', 'r') as f:
            id = f.read()
            if id:
                try:
                    mail_id = get_mail_id_from_the_history(id)
                    list_of_saved_files = get_full_message(mail_id)
                    print(list_of_saved_files)
                except:
                    http_status = '', 400
                    return http_status


        cur_date=get_timestamp()
        print("Date and time of update ====>",cur_date)
        http_status=jsonify({'status':'success'}),200
        with open('stored_id.txt', 'w') as f:
            f.write(str(historyId))
    else:
        http_status='',400
    return http_status
