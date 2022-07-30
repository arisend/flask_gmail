import socket

socket.setdefaulttimeout(4000)
import json
import os.path
import time
from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.cloud.pubsub_v1.subscriber import exceptions as sub_exceptions
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from base64 import urlsafe_b64decode
import requests
import json
import os
from requests.exceptions import HTTPError
import PyPDF2
import boto3
import mimetypes
import datetime
import logging

logging.basicConfig(filename='std.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logger=logging.getLogger()
logger.setLevel(logging.DEBUG)
# TODO(developer)
project_id = "cloud-sub-pub"
subscription_id = "my_sub_pull"
folder_name = r'/root/flask_gmail-mail/web/files'
mock_url = r'https://cd485f9b-bd8f-4db3-81e4-f63abe212a59.mock.pstmn.io/company/company_id'
# Number of seconds the subscriber should listen for messages
timeout = 600


def build_gmail_api_connection():
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/pubsub']
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('/root/flask_gmail-mail/web/token.json'):
        creds = Credentials.from_authorized_user_file('/root/flask_gmail-mail/web/token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '/root/flask_gmail-mail/web/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('/root/flask_gmail-mail/web/token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Call the Gmail API
        g_mail = build('gmail', 'v1', credentials=creds)
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')

    return g_mail


g_mail = build_gmail_api_connection()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/flask_gmail-mail/web/service_credentials.json"

subscriber = pubsub_v1.SubscriberClient()
# The `subscription_path` method creates a fully qualified identifier
# in the form `projects/{project_id}/subscriptions/{subscription_id}`
subscription_path = subscriber.subscription_path(project_id, subscription_id)


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


def get_mail_id_from_the_history(last_id):
    logger.debug(f"{str(last_id)}- last_id")
    results = g_mail.users().history().list(userId='me', startHistoryId=last_id, labelId="UNREAD",
                                            historyTypes=["messageAdded"]).execute()
    #print(last_id, results)
    time.sleep(2)
    return results['history'][-1]['messages'][-1]["id"]


def get_full_message(message_id, save_to_folder=folder_name):
    results = g_mail.users().messages().get(userId='me', id=message_id, format='full').execute()
    #print(results)
    payload = results['payload']
    headers = payload.get("headers")
    parts = payload.get("parts")

    set_of_files = parse_parts(g_mail, parts, save_to_folder, results)
    has_subject = False
    email_title, email_from, email_date=None,None,None
    if headers:
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name.lower() == 'from':
                # we print the From address
                logger.debug(f"From:{value}")
                email_from=value
            if name.lower() == "to":
                # we print the To address
                logger.debug(f"To:{value}")
            if name.lower() == "subject":
                # make our boolean True, the email has "subject"
                has_subject = True
                logger.debug(f"Subject:{value}")
                email_title=value
            if name.lower() == "date":
                # we print the date when the message was sent
                logger.debug(f"Date:{value}")
                email_date=datetime.datetime.strptime(value, '%a, %d %b %Y %H:%M:%S %z')  # for ref. Fri, 29 Jul 2022 18:14:45 +0300
    return set_of_files,email_title, email_from, email_date


def parse_parts(service, parts, folder_name, message):
    """
    Utility function that parses the content of an email partition
    """
    set_of_files = set()
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
                # set_of_files.add(filepath)
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
                            logger.debug(f"Saving the file: {filename}, size: {get_size_format(file_size)}")
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


def retrieve_company_id(email):
    params = {'email': email}
    try:
        response = requests.get(mock_url, params=params)
        # If the response was successful, no Exception will be raised
    except HTTPError as http_err:
        logger.error(f'HTTP error occurred: {http_err}')
    except Exception as err:
        logger.error(f'Other error occurred: {err}')
    else:
        try:
            key = response.json()['company']['id']
            return key
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err}')
        except Exception as err:
            logger.error(f'Other error occurred: {err}')

def upload_file_and_send_post_notification(path_to_file, key, email_title,email_from,email_date):
    file_name = os.path.basename(path_to_file)
    file_extension =os.path.splitext(file_name)[-1]
    logger.debug(f"file - {file_name}")
    if file_extension in ['.jpg','.png','.pdf']:
        obj=None
        mimetype=None
        #try:
            #try with boto3, does it handle all formats of files?
        s3 = boto3.resource('s3')
        bucket = s3.Bucket('lendica-pod')
        obj = bucket.Object(f"{key}/invoice/{file_name}")
        mimetype, _ = mimetypes.guess_type(path_to_file)
        logger.debug(f"mimetype {mimetype}")
        if mimetype is None:
            logger.error('failed to guess mimetype or file removed')
            return 
        elif mimetype=="application/pdf":
            with open(path_to_file, "rb") as f:
                qty_of_pages = str(PyPDF2.PdfFileReader(f).numPages)
                response = requests.post('https://micro-awsmanager.herokuapp.com/s3/upload-fileobj', files={
                    'file_obj': f,
                    'json': (None, json.dumps({
                        'object_key': f"{key}/invoice/{file_name}",
                        'bucket_name': 'lendica-pod',
                        'extra_args': {"ContentType": mimetype, "Metadata": {"numpages": qty_of_pages}}
                    }), 'application/json'),
                })
                logger.debug(f"{str(response.status_code)} - s3 response status code")
                logger.debug(response.text)
        else:
            with open(path_to_file, "rb") as f:
                response = requests.post('https://micro-awsmanager.herokuapp.com/s3/upload-fileobj', files={
                    'file_obj': f,
                    'json': (None, json.dumps({
                        'object_key': f"{key}/invoice/{file_name}",
                        'bucket_name': 'lendica-pod',
                        'extra_args': {"ContentType": mimetype, "Metadata": {"numpages": 1}}
                    }), 'application/json'),
                })
                logger.debug(f"{str(response.status_code)} - s3 response status code")
                logger.debug(response.text)

        response = requests.post('https://webhook.site/05f454b8-bd9a-4485-beb6-d46b26d29039', data={
            'company_id': key,
            'object_key': f"{key}/invoice/{file_name}",
            'email_subject': email_title ,
            'email_from': email_from,
            'email_date': email_date.strftime("%Y-%m-%dT%H:%M:%S%z")  # for ref. 2022-07-14T13:15:03-08:00'
        })
        os.remove(path_to_file)
        logger.debug(f"{str(response.status_code)} - webhook response status code")
        return
        # except HTTPError as http_err:
        #     print(f'HTTP error occurred: {http_err}')
        # except Exception as err:
        #     print(f'Other error occurred: {err}')
    else:
        os.remove(path_to_file)
    

def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    print(f"Received {message}.")

    # Use `ack_with_response()` instead of `ack()` to get a future that tracks
    # the result of the acknowledge call. When exactly-once delivery is enabled
    # on the subscription, the message is guaranteed to not be delivered again
    # if the ack future succeeds.

    email = json.loads(message.data.decode("utf-8"))["emailAddress"]
    historyId = json.loads(message.data.decode("utf-8"))["historyId"]
    if "add" in email:
        with open('/root/flask_gmail-mail/web/stored_id.txt', 'r') as f:
            storage_dict = json.loads(f.read())
        if email in storage_dict:
            logger.debug(f"{email} - email, {str(historyId)}, - history_id")
            mail_id=None
            try:
                mail_id = get_mail_id_from_the_history(storage_dict[email])
                logger.debug(f"{mail_id}, - mail_id")
            except:
                http_status = '', 400
                return http_status
            if mail_id:
                    list_of_saved_files=None
                    try:
                        list_of_saved_files,email_title, email_from, email_date = get_full_message(mail_id)
                    except:
                        http_status = '', 400
                        return http_status 
                    if list_of_saved_files:
                        key=retrieve_company_id(email)
                        logger.debug(f"key - {key}")
                        for file in list_of_saved_files:
                            response=upload_file_and_send_post_notification(file, key, email_title,email_from,email_date)   

        with open('/root/flask_gmail-mail/web/stored_id.txt', 'w') as f:
            storage_dict[email] = historyId
            json.dump(storage_dict, f)

    ack_future = message.ack_with_response()
    try:
        # Block on result of acknowledge call.
        # When `timeout` is not set, result() will block indefinitely,
        # unless an exception is encountered first.
        ack_future.result(timeout=timeout)
        logger.debug(f"Ack for message {message.message_id} successful.")
    except sub_exceptions.AcknowledgeError as e:
        logger.error(
            f"Ack for message {message.message_id} failed with error: {e.error_code}"
        )


streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
print(f"Listening for messages on {subscription_path}..\n")

# Wrap subscriber in a 'with' block to automatically call close() when done.
with subscriber:
    try:
        # When `timeout` is not set, result() will block indefinitely,
        # unless an exception is encountered first.
        streaming_pull_future.result(timeout=timeout)
    except TimeoutError:
        streaming_pull_future.cancel()  # Trigger the shutdown.
        streaming_pull_future.result()  # Block until the shutdown is complete.
