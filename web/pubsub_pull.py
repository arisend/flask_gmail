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
# TODO(developer)
project_id = "expanded-symbol-326820"
subscription_id = "my_sub"
#Number of seconds the subscriber should listen for messages
timeout = 86400



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


def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    print(f"Received {message}.")

    # Use `ack_with_response()` instead of `ack()` to get a future that tracks
    # the result of the acknowledge call. When exactly-once delivery is enabled
    # on the subscription, the message is guaranteed to not be delivered again
    # if the ack future succeeds.
    ack_future = message.ack_with_response()
    historyId=json.loads(message.data.decode("utf-8"))["historyId"]

    with open('stored_id.txt', 'r') as f:
        id=f.read()
        if id:
            mail_id=get_mail_id_from_the_history(id)
            list_of_saved_files=get_full_message(mail_id)
            print(list_of_saved_files)


    with open('stored_id.txt', 'w') as f:
        f.write(str(historyId))

    try:
        # Block on result of acknowledge call.
        # When `timeout` is not set, result() will block indefinitely,
        # unless an exception is encountered first.
        ack_future.result(timeout=timeout)
        print(f"Ack for message {message.message_id} successful.")
    except sub_exceptions.AcknowledgeError as e:
        print(
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


