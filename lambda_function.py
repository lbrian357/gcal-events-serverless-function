from google.oauth2 import service_account
from googleapiclient.discovery import build

from datetime import datetime, timedelta
import json
import os
import base64


def invite_user_to_event(attendee_name, attendee_email, is_joining_newsletter, gcal_meid):
    GCAL_MEID_DECODED_STR = base64.b64decode(gcal_meid + '=' * (-len(gcal_meid) % 4)).decode('UTF-8')
    GCAL_EVENT_ID = GCAL_MEID_DECODED_STR.split(' ')[0]
    GCAL_ID_EMAIL = GCAL_MEID_DECODED_STR.split(' ')[1]
    GCAL_ID = "get-id-from-google-calendar-settings"
    SCOPES = ['https://www.googleapis.com/auth/calendar',
              'https://www.googleapis.com/auth/drive']

    SERVICE_ACCOUNT_FILE = os.environ['LAMBDA_TASK_ROOT'] + '/service-account.json'
    #### local testing
    #### from pathlib import Path
    #### path = Path(__file__).parent.absolute()
    #### SERVICE_ACCOUNT_FILE = str(path) + "/service-account.json"
    #### /local testing

    # Init credentials
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE,
                                                                        scopes=SCOPES)
    delegated_credentials = credentials.with_subject(GCAL_ID_EMAIL)


    # Init calendar service and add an attendee
    cal_service = build('calendar', 'v3', credentials=delegated_credentials)

    this_event = cal_service.events().get(calendarId=GCAL_ID,
                                         eventId=GCAL_EVENT_ID,).execute()

    this_event['sendUpdates'] = "all"

    try:
        this_event['attendees'].append({"email": attendee_email,
                                       "displayName": attendee_name})
    except KeyError:
        this_event['attendees'] = [{"email": attendee_email,
                                   "displayName": attendee_name}]

    updated_event = cal_service.events().update(calendarId=GCAL_ID,
                                                eventId=GCAL_EVENT_ID,
                                                body=this_event).execute()


    # Init google drive service and add attendee to proper sheet
    drive_service = build('drive', 'v3', credentials=delegated_credentials)
    sheet_service = build('sheets', 'v4', credentials=delegated_credentials)

    EVENTS_ATTENDEES_GD_FOLDER_ID = "get-folder-id-from-google-drive"

    files = []
    page_token = None
    while True:
        response = drive_service.files().list(q="'" + EVENTS_ATTENDEES_GD_FOLDER_ID + "' in parents",
                                              spaces='drive',
                                              fields='nextPageToken, '
                                              'files(id, name)',
                                              pageToken=page_token).execute()
        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # find the id of the gsheet in question
    this_event_attendee_gsheet = next((file for file in files if GCAL_EVENT_ID in file['name']), None)

    if this_event_attendee_gsheet:
        # if that gsheet does exist: append row to it
        gsheet_id = this_event_attendee_gsheet["id"]
        range_ = 'Sheet1!A1:E1'
        value_input_option = 'RAW'  # Stores as raw strings only
        insert_data_option = 'INSERT_ROWS'

        value_range_body = {
            "majorDimension": "ROWS",
            "values": [
                [attendee_name, attendee_email, is_joining_newsletter, datetime.utcnow().timestamp()],
            ],
        }

        sheet_append_request = sheet_service.spreadsheets().values().append(spreadsheetId=gsheet_id,
                                                               range=range_,
                                                               valueInputOption=value_input_option,
                                                               insertDataOption=insert_data_option,
                                                               body=value_range_body)
        sheet_append_request = sheet_append_request.execute()

    else:
        # if that gsheet doesn't exist: create it with a unique identifier (ie. GCAL_EVENT_ID)
        body = {
            "name": this_event['summary'].replace(" ", "_") + "_ATTENDEES_WAIVERS_" + GCAL_EVENT_ID,
            "parents": [EVENTS_ATTENDEES_GD_FOLDER_ID],
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        res = drive_service.files().create(body=body, supportsAllDrives=True, fields='id').execute()

        # Append first row to the newly created sheet
        gsheet_id = res.get("id")
        range_ = 'Sheet1!A1:E1'
        value_input_option = 'RAW'  # Stores as raw strings only
        insert_data_option = 'INSERT_ROWS'

        value_range_body = {
            "majorDimension": "ROWS",
            "values": [
                ["Name", "Email", "Joining Newsletter", "UTC Timestamp"],
                [attendee_name, attendee_email, is_joining_newsletter, datetime.utcnow().timestamp()],
            ],
        }

        sheet_append_request = sheet_service.spreadsheets().values().append(spreadsheetId=gsheet_id,
                                                                            range=range_,
                                                                            valueInputOption=value_input_option,
                                                                            insertDataOption=insert_data_option,
                                                                            body=value_range_body)
        sheet_append_request = sheet_append_request.execute()

def lambda_handler(event, context):
    attendee_name = event.get('queryStringParameters', {}).get('name')
    attendee_email = event.get('queryStringParameters', {}).get('email')
    is_joining_newsletter = event.get('queryStringParameters', {}).get('is_joining_newsletter')
    gcal_meid = event.get('queryStringParameters', {}).get('gcal_meid')

    try:
        if not attendee_name:
            raise TypeError('name param must exist')
        if not attendee_email:
            raise TypeError('email param must exist')
        if not is_joining_newsletter:
            raise TypeError('is_joining_newsletter param must exist')
        if not gcal_meid:
            raise TypeError('gcal_meid param must exist')

        invite_user_to_event(attendee_name, attendee_email, is_joining_newsletter, gcal_meid)
        print(attendee_email + ' is successfully invited to the event.')
        return {
            'headers': {
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,PUT'
            },
            'statusCode': 200,
            'body': json.dumps(attendee_email + ' is successfully invited to the event.')
        }
    except Exception as e:
        print(e)
        return {
            'headers': {
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,PUT'
            },
            'statusCode': 400,
            'body': json.dumps('Unable to invite to event at this time: ' + str(e))
        }
