# --
# File: ewsonprem_consts.py
#
# Copyright (c) Phantom Cyber Corporation, 2016-2017
#
# This unpublished material is proprietary to Phantom Cyber.
# All rights reserved. The methods and
# techniques described herein are considered trade secrets
# and/or confidential. Reproduction or distribution, in whole
# or in part, is forbidden except by express written permission
# of Phantom Cyber.
#
# --

EWSONPREM_JSON_DEVICE_URL = "url"
EWSONPREM_JSON_TEST_USER = "test_user"
EWSONPREM_JSON_SUBJECT = "subject"
EWSONPREM_JSON_FROM = "sender"
EWSONPREM_JSON_INT_MSG_ID = "internet_message_id"
EWSONPREM_JSON_EMAIL = "email"
EWSONPREM_JSON_FOLDER = "folder"
EWSONPREM_JSON_BODY = "body"
EWSONPREM_JSON_QUERY = "query"
EWSONPREM_JSON_RANGE = "range"
EWSONPREM_JSON_ID = "id"
EWSONPREM_JSON_GROUP = "group"
EWSONPREM_JSON_INGEST_EMAIL = "ingest_email"
EWS_JSON_CONTAINER_ID = "container_id"
EWS_JSON_VAULT_ID = "vault_id"

EWSONPREM_SEARCH_FINISHED_STATUS = "Finished Searching {0:.0%}"

EWS_JSON_POLL_USER = "poll_user"
EWS_JSON_USE_IMPERSONATE = "use_impersonation"
EWS_JSON_AUTH_TYPE = "auth_type"
EWS_JSON_CLIENT_ID = "client_id"
EWS_JSON_POLL_FOLDER = "poll_folder"
EWS_JSON_INGEST_MANNER = "ingest_manner"
EWS_JSON_FIRST_RUN_MAX_EMAILS = "first_run_max_emails"
EWS_JSON_POLL_MAX_CONTAINERS = "max_containers"
EWS_JSON_DONT_IMPERSONATE = "dont_impersonate"
EWS_JSON_IMPERSONATE_EMAIL = "impersonate_email"
EWS_JSON_AUTH_URL = "authority_url"
EWS_JSON_FED_PING_URL = "fed_ping_url"
EWS_JSON_FED_VERIFY_CERT = "fed_verify_server_cert"

EWSONPREM_ERR_CONNECTIVITY_TEST = "Connectivity test failed"
EWSONPREM_SUCC_CONNECTIVITY_TEST = "Connectivity test passed"
EWSONPREM_ERR_SERVER_CONNECTION = "Connection failed"
EWSONPREM_ERR_FROM_SERVER = "API failed. Status code: {code}. Message: {message}"
EWSONPREM_ERR_API_UNSUPPORTED_METHOD = "Unsupported method"
EWSONPREM_USING_BASE_URL = "Using url: {base_url}"
EWSONPREM_ERR_JSON_PARSE = "Unable to parse reply, raw string reply: '{raw_text}'"

EWSONPREM_MAX_END_OFFSET_VAL = 2147483646
EWS_O365_RESOURCE = "https://outlook.office365.com"
EWS_LOGIN_URL = "https://login.windows.net"

EWS_MODIFY_CONFIG = "Toggling the impersonation configuration on the asset might help, or login user does not have privileges to the mailbox."

EWS_INGEST_LATEST_EMAILS = "latest first"
EWS_INGEST_OLDEST_EMAILS = "oldest first"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

AUTH_TYPE_AZURE = "Azure"
AUTH_TYPE_FEDERATED = "Federated"
AUTH_TYPE_BASIC = "Basic"
