# File: process_email.py
#
# Copyright (c) 2016-2021 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
import email
import tempfile
from collections import OrderedDict
import os
import re
from bs4 import BeautifulSoup
import phantom.app as phantom
import phantom.utils as ph_utils
import phantom.rules as phantom_rules
import mimetypes
import socket
from email.header import decode_header
import shutil
import hashlib
import json
from bs4 import UnicodeDammit
from builtins import str
import magic
from requests.structures import CaseInsensitiveDict
from copy import deepcopy
from urllib.parse import urlparse
from ewsonprem_consts import *


FILE_EXTENSIONS = {
    '.vmsn': ['os memory dump', 'vm snapshot file'],
    '.vmss': ['os memory dump', 'vm suspend file'],
    '.js': ['javascript'],
    '.doc': ['doc'],
    '.docx': ['doc'],
    '.xls': ['xls'],
    '.xlsx': ['xls'],
}

MAGIC_FORMATS = [
    (re.compile('^PE.* Windows'), ['pe file', 'hash']),
    (re.compile('^MS-DOS executable'), ['pe file', 'hash']),
    (re.compile('^PDF '), ['pdf']),
    (re.compile('^MDMP crash'), ['process dump']),
    (re.compile('^Macromedia Flash'), ['flash']),
]

EWS_DEFAULT_ARTIFACT_COUNT = 100
EWS_DEFAULT_CONTAINER_COUNT = 100
HASH_FIXED_PHANTOM_VERSION = "2.0.201"

OFFICE365_APP_ID = "a73f6d32-c9d5-4fec-b024-43876700daa6"
EXCHANGE_ONPREM_APP_ID = "badc5252-4a82-4a6d-bc53-d1e503857124"
IMAP_APP_ID = "9f2e9f72-b0e5-45d6-92a7-09ef820476c1"

PROC_EMAIL_JSON_FILES = "files"
PROC_EMAIL_JSON_BODIES = "bodies"
PROC_EMAIL_JSON_DATE = "date"
PROC_EMAIL_JSON_FROM = "from"
PROC_EMAIL_JSON_SUBJECT = "subject"
PROC_EMAIL_JSON_TO = "to"
PROC_EMAIL_JSON_START_TIME = "start_time"
PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS = "extract_attachments"
PROC_EMAIL_JSON_EXTRACT_BODY = "add_body_to_header_artifacts"
PROC_EMAIL_JSON_EXTRACT_URLS = "extract_urls"
PROC_EMAIL_JSON_EXTRACT_IPS = "extract_ips"
PROC_EMAIL_JSON_EXTRACT_DOMAINS = "extract_domains"
PROC_EMAIL_JSON_EXTRACT_EMAIL_ADDRESSES = "extract_email_addresses"
PROC_EMAIL_JSON_EXTRACT_HASHES = "extract_hashes"
PROC_EMAIL_JSON_IPS = "ips"
PROC_EMAIL_JSON_HASHES = "hashes"
PROC_EMAIL_JSON_URLS = "urls"
PROC_EMAIL_JSON_DOMAINS = "domains"
PROC_EMAIL_JSON_EMAIL_ADDRESSES = "email_adresses"
PROC_EMAIL_JSON_MSG_ID = "message_id"
PROC_EMAIL_JSON_EMAIL_HEADERS = "email_headers"
PROC_EMAIL_CONTENT_TYPE_MESSAGE = "message/rfc822"

URI_REGEX = r"[Hh][Tt][Tt][Pp][Ss]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMAIL_REGEX = r"\b[A-Z0-9._%+-]+@+[A-Z0-9.-]+\.[A-Z]{2,}\b"
EMAIL_REGEX2 = r'".*"@[A-Z0-9.-]+\.[A-Z]{2,}\b'
HASH_REGEX = r"\b[0-9a-fA-F]{32}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{64}\b"
IP_REGEX = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
IPV6_REGEX = r'\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|'
IPV6_REGEX += r'(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))'
IPV6_REGEX += r'|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d))'
IPV6_REGEX += r'{3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
IPV6_REGEX += r'(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:'
IPV6_REGEX += r'((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}'
IPV6_REGEX += r'(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)'
IPV6_REGEX += r'(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:'
IPV6_REGEX += r'((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|'
IPV6_REGEX += r'((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*'


uri_regexc = re.compile(URI_REGEX)
email_regexc = re.compile(EMAIL_REGEX, re.IGNORECASE)
email_regexc2 = re.compile(EMAIL_REGEX2, re.IGNORECASE)
hash_regexc = re.compile(HASH_REGEX)
ip_regexc = re.compile(IP_REGEX)
ipv6_regexc = re.compile(IPV6_REGEX)


class ProcessEmail(object):

    def __init__(self):

        self._base_connector = None
        self._config = dict()
        self._email_id_contains = list()
        self._container = dict()
        self._artifacts = list()
        self._attachments = list()
        self._headers_from_ews = list()
        self._attachments_from_ews = list()
        self._parsed_mail = None
        self._guid_to_hash = dict()
        self._tmp_dirs = list()

    def _get_file_contains(self, file_path):

        contains = []
        ext = os.path.splitext(file_path)[1]
        contains.extend(FILE_EXTENSIONS.get(ext, []))
        magic_str = magic.from_file(file_path)
        for regex, cur_contains in MAGIC_FORMATS:
            if regex.match(magic_str):
                contains.extend(cur_contains)

        return contains

    def _is_ip(self, input_ip):

        if (ph_utils.is_ip(input_ip)):
            return True

        if (self.is_ipv6(input_ip)):
            return True

        return False

    def is_ipv6(self, input_ip):

        try:
            socket.inet_pton(socket.AF_INET6, input_ip)
        except:  # not a valid v6 address
            return False

        return True

    def _debug_print(self, *args):

        if (self._base_connector) and (hasattr(self._base_connector, 'debug_print')):
            self._base_connector.debug_print(*args)

        return

    def _clean_url(self, url):

        url = url.strip('>),.]\r\n')

        # Check before splicing, find returns -1 if not found
        # _and_ you will end up splicing on -1 (incorrectly)
        if ('<' in url):
            url = url[:url.find('<')]

        if ('>' in url):
            url = url[:url.find('>')]

        url = url.rstrip('>),.]\r\n')

        return url.strip()

    def _extract_urls_domains(self, file_data, urls, domains, parent_id=None):

        if ((not self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS]) and (not self._config[PROC_EMAIL_JSON_EXTRACT_URLS])):
            return

        # try to load the email
        try:
            soup = BeautifulSoup(file_data, "html.parser")
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            err = "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)
            self._debug_print("Error occurred while extracting domains of the URLs. {0}".format(err))
            return

        uris = []
        # get all tags that have hrefs
        links = soup.find_all(href=True)
        if (links):
            # it's html, so get all the urls
            uris = [x['href'] for x in links if (not x['href'].startswith('mailto:'))]
            # work on the text part of the link, they might be http links different from the href
            # and were either missed by the uri_regexc while parsing text or there was no text counterpart
            # in the email
            uri_text = [self._clean_url(x.get_text()) for x in links]
            if (uri_text):
                uri_text = [x for x in uri_text if x.startswith('http')]
                if (uri_text):
                    uris.extend(uri_text)
        else:
            # Parse it as a text file
            uris = re.findall(uri_regexc, file_data)
            if (uris):
                uris = [self._clean_url(x) for x in uris]

        if (self._config[PROC_EMAIL_JSON_EXTRACT_URLS]):
            # add the uris to the urls
            unique_uris = set(uris)
            unique_uris = list(unique_uris)
            for uri in unique_uris:
                uri_dict = {'requestURL': uri, 'parentInternetMessageId': parent_id}
                urls.append(uri_dict)

        if (self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS]):
            for uri in uris:
                domain = phantom.get_host_from_url(uri)
                if (domain) and (not self._is_ip(domain)):
                    domains.append({'destinationDnsDomain': domain, 'parentInternetMessageId': parent_id})
            # work on any mailto urls if present
            if (links):
                mailtos = [x['href'] for x in links if (x['href'].startswith('mailto:'))]
                for curr_email in mailtos:
                    domain = curr_email[curr_email.find('@') + 1:]
                    if (domain) and (not self._is_ip(domain)):
                        if ('?' in domain):
                            domain = domain[:domain.find('?')]
                        domains.append({'destinationDnsDomain': domain, 'parentInternetMessageId': parent_id})

        return

    def _get_ips(self, file_data, ips, parent_id=None):

        # First extract what looks like an IP from the file, this is a faster operation
        ips_in_mail = re.findall(ip_regexc, file_data)
        ip6_in_mail = re.findall(ipv6_regexc, file_data)

        if (ip6_in_mail):
            for ip6_tuple in ip6_in_mail:
                ip6s = [x for x in ip6_tuple if x]
                ips_in_mail.extend(ip6s)

        # Now validate them
        if (ips_in_mail):
            ips_in_mail = set(ips_in_mail)
            # match it with a slower and difficult regex.
            # TODO: Fix this with a one step approach.
            ips_in_mail = [x for x in ips_in_mail if self._is_ip(x)]
            if (ips_in_mail):
                unique_ips = set(ips_in_mail)
                for ip in unique_ips:
                    ips.append({'sourceAddress': ip, 'parentInternetMessageId': parent_id})

    def _handle_body(self, body, parsed_mail, body_index, email_id):

        local_file_path = body['file_path']
        charset = body.get('charset')
        parent_id = None

        # parent_id = parsed_mail['email_headers'][body_index]['cef'].get('parentInternetMessageId')
        if 'True' in local_file_path:
            for item in parsed_mail['email_headers']:
                parent_id = item['cef'].get('parentInternetMessageId')
                if parent_id:
                    break

        ips = parsed_mail[PROC_EMAIL_JSON_IPS]
        hashes = parsed_mail[PROC_EMAIL_JSON_HASHES]
        urls = parsed_mail[PROC_EMAIL_JSON_URLS]
        domains = parsed_mail[PROC_EMAIL_JSON_DOMAINS]
        email_addresses = parsed_mail[PROC_EMAIL_JSON_EMAIL_ADDRESSES]

        file_data = None
        with open(local_file_path, 'r') as f:
            file_data = f.read()

        if ((file_data is None) or (len(file_data) == 0)):
            return phantom.APP_ERROR

        self._parse_email_headers_as_inline(file_data, parsed_mail, charset, email_id)

        if (self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS] or self._config[PROC_EMAIL_JSON_EXTRACT_EMAIL_ADDRESSES]):
            emails = []
            emails.extend(re.findall(email_regexc, file_data))
            emails.extend(re.findall(email_regexc2, file_data))

            for curr_email in emails:

                if self._config[PROC_EMAIL_JSON_EXTRACT_EMAIL_ADDRESSES]:
                    email_addresses.append({'emailAddress': curr_email, 'parentInternetMessageId': parent_id})

                if self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS]:
                    domain = curr_email[curr_email.rfind('@') + 1:]
                    if (domain) and (not ph_utils.is_ip(domain)):
                        domains.append({'destinationDnsDomain': domain, 'parentInternetMessageId': parent_id})

        self._extract_urls_domains(file_data, urls, domains, parent_id)

        if (self._config[PROC_EMAIL_JSON_EXTRACT_IPS]):
            self._get_ips(file_data, ips, parent_id)

        if (self._config[PROC_EMAIL_JSON_EXTRACT_HASHES]):
            hashs_in_mail = re.findall(hash_regexc, file_data)
            if (hashs_in_mail):
                unique_hashes = set(hashs_in_mail)
                for hash in unique_hashes:
                    hashes.append({'fileHash': hash, 'parentInternetMessageId': parent_id})

        return phantom.APP_SUCCESS

    def _add_artifacts(self, input_set, artifact_name, start_index, artifacts):

        added_artifacts = 0
        for item in input_set:
            # ignore empty entries
            if (not item):
                continue

            if artifact_name == 'URL Artifact':

                try:
                    url_to_parse = item.get('requestURL', '')
                    parsed_url = urlparse(url_to_parse)
                except Exception as e:
                    phantom.debug('An exception occurred when parsing the URL {0}: {1}'.format(url_to_parse, e))

                if not parsed_url.netloc:
                    continue

            artifact = {}
            artifact['source_data_identifier'] = start_index + added_artifacts
            artifact['cef'] = item
            artifact['name'] = artifact_name
            self._debug_print('Artifact:', artifact)
            artifacts.append(artifact)
            added_artifacts += 1

        return added_artifacts

    def _parse_email_headers_as_inline(self, file_data, parsed_mail, charset, email_id):

        # remove the 'Forwarded Message' from the email text and parse it
        if self._base_connector._python_version == 2:
            p = re.compile(r'.*Forwarded Message.*\r\n(.*)', re.IGNORECASE)
        else:
            p = re.compile(r'.*Forwarded Message.*\n(.*)', re.IGNORECASE)
        email_text = p.sub(r'\1', file_data.strip()[:500])
        mail = email.message_from_string(email_text)

        # Get the array
        # email_headers = parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS]

        self._parse_email_headers(parsed_mail, mail, charset, add_email_id=email_id)

        # email_headers.append(mail.items())

        return phantom.APP_SUCCESS

    def _add_email_header_artifacts(self, email_header_artifacts, start_index, artifacts):

        added_artifacts = 0
        for artifact in email_header_artifacts:

            artifact['source_data_identifier'] = start_index + added_artifacts
            artifacts.append(artifact)
            added_artifacts += 1

        return added_artifacts

    def _create_artifacts(self, parsed_mail):

        self._debug_print("Parsed mail: ", parsed_mail)

        # get all the artifact data in their own list objects
        ips = [dict(t) for t in set([tuple(d.items()) for d in parsed_mail[PROC_EMAIL_JSON_IPS]])]
        hashes = [dict(t) for t in set([tuple(d.items()) for d in parsed_mail[PROC_EMAIL_JSON_HASHES]])]
        urls = [dict(t) for t in set([tuple(d.items()) for d in parsed_mail[PROC_EMAIL_JSON_URLS]])]
        domains = [dict(t) for t in set([tuple(d.items()) for d in parsed_mail[PROC_EMAIL_JSON_DOMAINS]])]
        email_addresses = [dict(t) for t in set([tuple(d.items()) for d in parsed_mail[PROC_EMAIL_JSON_EMAIL_ADDRESSES]])]
        email_headers = parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS]

        # set the default artifact dict

        artifact_id = 0

        # add artifacts
        added_artifacts = self._add_artifacts(ips, 'IP Artifact', artifact_id, self._artifacts)
        artifact_id += added_artifacts

        added_artifacts = self._add_artifacts(hashes, 'Hash Artifact', artifact_id, self._artifacts)
        artifact_id += added_artifacts

        added_artifacts = self._add_artifacts(urls, 'URL Artifact', artifact_id, self._artifacts)
        artifact_id += added_artifacts

        # domains = [x.decode('idna') for x in domains]

        added_artifacts = self._add_artifacts(domains, 'Domain Artifact', artifact_id, self._artifacts)
        artifact_id += added_artifacts

        added_artifacts = self._add_artifacts(email_addresses, 'Email Address Artifact', artifact_id, self._artifacts)
        artifact_id += added_artifacts

        added_artifacts = self._add_email_header_artifacts(email_headers, artifact_id, self._artifacts)
        email_headers = email_headers
        artifact_id += added_artifacts

        return phantom.APP_SUCCESS

    def _decode_uni_string(self, input_str, def_name):

        # try to find all the decoded strings, we could have multiple decoded strings
        # or a single decoded string between two normal strings separated by \r\n
        # YEAH...it could get that messy
        encoded_strings = re.findall(r'=\?.*\?=', input_str, re.I)

        # return input_str as is, no need to do any conversion
        if (not encoded_strings):
            return input_str

        # get the decoded strings
        try:
            decoded_strings = [decode_header(x)[0] for x in encoded_strings]
            decoded_strings = [{'value': x[0], 'encoding': x[1]} for x in decoded_strings]
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            err = "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)
            self._debug_print("Decoding: {0}. {1}".format(encoded_strings, err))
            return def_name

        # convert to dict for safe access, if it's an empty list, the dict will be empty
        decoded_strings = dict(enumerate(decoded_strings))

        new_str = ''
        new_str_create_count = 0
        for i, encoded_string in enumerate(encoded_strings):

            decoded_string = decoded_strings.get(i)

            if (not decoded_string):
                # nothing to replace with
                continue

            value = decoded_string.get('value')
            encoding = decoded_string.get('encoding')

            if (not encoding or not value):
                # nothing to replace with
                continue

            try:
                # Some non-ascii characters were causing decoding issue with
                # the UnicodeDammit and working correctly with the decode function.
                # keeping previous logic in the except block incase of failure.
                value = value.decode(encoding)
                new_str += value
                new_str_create_count += 1
            except:
                try:
                    if (encoding != 'utf-8'):
                        value = str(value, encoding)
                except:
                    pass

                try:
                    # commenting the existing approach due to a new approach being deployed below
                    # substitute the encoded string with the decoded one
                    # input_str = input_str.replace(encoded_string, value)

                    # make new string insted of replacing in the input string because issue find in PAPP-9531
                    if value:
                        new_str += UnicodeDammit(value).unicode_markup
                        new_str_create_count += 1
                except:
                    pass

        # replace input string with new string because issue find in PAPP-9531
        if new_str and new_str_create_count == len(encoded_strings):
            self._debug_print("Creating a new string entirely from the encoded_strings and assigning into input_str")
            input_str = new_str

        return input_str

    def _get_container_name(self, parsed_mail, email_id):

        # Create the default name
        def_cont_name = "Email ID: {0}".format(email_id)

        # get the subject from the parsed mail
        subject = parsed_mail.get(PROC_EMAIL_JSON_SUBJECT)

        # if no subject then return the default
        if (not subject):
            return def_cont_name

        return self._decode_uni_string(subject, def_cont_name)

    def _handle_if_body(self, content_disp, content_id, content_type, part, bodies, file_path):

        process_as_body = False

        # if content disposition is None then assume that it is
        if (content_disp is None):
            process_as_body = True
        # if content disposition is inline
        elif (content_disp.lower().strip() == 'inline'):
            if ('text/html' in content_type) or ('text/plain' in content_type):
                process_as_body = True

        if (not process_as_body):
            return (phantom.APP_SUCCESS, True)

        part_payload = part.get_payload(decode=True)

        if (not part_payload):
            return (phantom.APP_SUCCESS, False)

        with open(file_path, 'wb') as f:
            f.write(part_payload)

        bodies.append({'file_path': file_path, 'charset': part.get_content_charset()})

        return (phantom.APP_SUCCESS, False)

    def remove_child_info(self, file_path):
        if file_path.endswith('_True'):
            return file_path.rstrip('_True')
        else:
            return file_path.rstrip('_False')

    def _handle_attachment(self, part, file_name, file_path):

        files = self._parsed_mail[PROC_EMAIL_JSON_FILES]

        if (not self._config[PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS]):
            return phantom.APP_SUCCESS

        part_base64_encoded = part.get_payload()

        headers = self._get_email_headers_from_part(part)

        attach_meta_info = dict()

        if (headers):
            attach_meta_info = {'headers': dict(headers)}

        for curr_attach in self._attachments_from_ews:

            if (curr_attach.get('should_ignore', False)):
                continue

            try:
                attach_content = curr_attach['content']
            except:
                continue

            if (attach_content.strip().replace('\r\n', '') == part_base64_encoded.strip().replace('\r\n', '')):
                attach_meta_info.update(dict(curr_attach))
                del attach_meta_info['content']
                curr_attach['should_ignore'] = True

        part_payload = part.get_payload(decode=True)
        if (not part_payload):
            return phantom.APP_SUCCESS
        try:
            with open(file_path, 'wb') as f:
                f.write(part_payload)
        except IOError as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            try:
                if "File name too long" in error_msg:
                    new_file_name = "ph_long_file_name_temp"
                    file_path = \
                        "{}{}".format(self.remove_child_info(file_path).rstrip(file_name.replace('<',
                                      '').replace('>', '').replace(' ', '')), new_file_name)
                    self._base_connector.debug_print("Original \
                                                      filename: {}".format(self._base_connector._handle_py_ver_compat_for_input_str(file_name)))
                    self._base_connector.debug_print("Modified filename: {}".format(new_file_name))
                    with open(file_path, 'wb') as long_file:
                        long_file.write(part_payload)
                else:
                    self._base_connector.debug_print("Error occurred while adding file to Vault. Error Details: {}".format(error_msg))
                    return
            except Exception as e:
                error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
                self._base_connector.debug_print("Error occurred while adding file to Vault. Error Details: {}".format(error_msg))
                return
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            self._base_connector.debug_print("Error occurred while adding file to Vault. Error Details: {}".format(error_msg))
            return

        file_hash = hashlib.sha1(part_payload).hexdigest()
        files.append({'file_name': file_name, 'file_path': file_path, 'file_hash': file_hash, 'meta_info': attach_meta_info})

    def _handle_part(self, part, part_index, tmp_dir, extract_attach, parsed_mail, child=False):

        bodies = parsed_mail[PROC_EMAIL_JSON_BODIES]

        # get the file_name
        file_name = part.get_filename()
        content_disp = part.get('Content-Disposition')
        content_type = part.get('Content-Type')
        content_id = part.get('Content-ID')

        if (file_name is None):
            # init name and extension to default values
            name = "part_{0}_{1}".format(part_index, child)
            extension = ".{0}".format(part_index)

            # Try to create an extension from the content type if possible
            if (content_type is not None):
                extension = mimetypes.guess_extension(re.sub(';.*', '', content_type))

            # Try to create a name from the content id if possible
            if (content_id is not None):
                name = content_id

            file_name = "{0}{1}".format(name, extension)
        else:
            file_name = self._decode_uni_string(file_name, file_name)

        # Remove any chars that we don't want in the name
        file_path = "{0}/{1}_{2}_{3}".format(tmp_dir, part_index, file_name.replace('<', '').replace('>', '').replace(' ', ''), child)

        self._debug_print("file_path: {0}".format(file_path))

        # is the part representing the body of the email
        status, process_further = self._handle_if_body(content_disp, content_id, content_type, part, bodies, file_path)

        if (not process_further):
            return phantom.APP_SUCCESS

        # is this another email as an attachment
        if ((content_type is not None) and (content_type.find(PROC_EMAIL_CONTENT_TYPE_MESSAGE) != -1)):
            return phantom.APP_SUCCESS

        # This is an attachment and it's not an email
        self._handle_attachment(part, file_name, file_path)

        return phantom.APP_SUCCESS

    def _update_headers(self, headers):

        # compare the various values of the passed header (param: headers)
        # to the header that the class got self._headers_from_ews
        if (not self._headers_from_ews):
            return phantom.APP_SUCCESS

        if (not headers):
            return phantom.APP_SUCCESS

        headers_ci = CaseInsensitiveDict(headers)

        for curr_header_lower in self._headers_from_ews:
            if (headers_ci.get('message-id', 'default_value1').strip() == curr_header_lower.get('message-id', 'default_value2').strip()):
                # the headers match with the one that we got from the ews API, so update it
                headers.update(curr_header_lower)

        return phantom.APP_SUCCESS

    def _get_email_headers_from_part(self, part, charset=None):

        email_headers = list(part.items())

        # TODO: the next 2 ifs can be condensed to use 'or'
        if (not charset):
            charset = part.get_content_charset()

        if (not charset):
            charset = 'utf8'

        if (not email_headers):
            return {}

        # Convert the header tuple into a dictionary
        headers = CaseInsensitiveDict()
        try:
            [headers.update({x[0]: self._base_connector._get_string(x[1], charset)}) for x in email_headers]
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            err = "Error occurred while converting the header tuple into a dictionary"
            self._base_connector.debug_print("{}. {}. {}".format(err, error_code, error_msg))

        # Convert "Cc" and "Bcc" fields to uppercase
        # when the unify_cef_fields asset configuration parameter is set to True
        if self._base_connector and self._base_connector._unify_cef_fields:
            if headers.get("CC"):
                headers["CC"] = headers.get("CC")
            if headers.get("BCC"):
                headers["BCC"] = headers.get("BCC")

        # Handle received seperately
        try:
            received_headers = list()
            received_headers = [self._base_connector._get_string(x[1], charset) for x in email_headers if x[0].lower() == 'received']
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            err = "Error occurred while handling the received header tuple separately"
            self._base_connector.debug_print("{}. {}. {}".format(err, error_code, error_msg))

        if (received_headers):
            headers['Received'] = received_headers

        # handle the subject string, if required add a new key
        subject = headers.get('Subject')
        if (subject):
            if isinstance(subject, str):
                headers['decodedSubject'] = self._decode_uni_string(subject, subject)

        return headers

    def _parse_email_headers(self, parsed_mail, part, charset=None, add_email_id=None):

        email_header_artifacts = parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS]

        headers = self._get_email_headers_from_part(part, charset)

        if (not headers):
            return 0

        # Parse email keys first
        cef_artifact = {}
        cef_types = {}

        if (headers.get('From')):
            emails = headers['From']
            if (emails):
                cef_artifact.update({'fromEmail': emails})

        if (headers.get('To')):
            emails = headers['To']
            if (emails):
                cef_artifact.update({'toEmail': emails})

        # if the header did not contain any email addresses then ignore this artifact
        message_id = headers.get('message-id')
        if ((not cef_artifact) and (message_id is None)):
            return 0

        cef_types.update({'fromEmail': ['email'], 'toEmail': ['email']})

        if (headers):
            self._update_headers(headers)
            cef_artifact['emailHeaders'] = dict(headers)

        for curr_key in list(cef_artifact['emailHeaders'].keys()):
            if curr_key.lower().startswith('body'):
                curr_value = cef_artifact['emailHeaders'].pop(curr_key)
                if (self._config.get(PROC_EMAIL_JSON_EXTRACT_BODY, False)):
                    cef_artifact.update({curr_key: curr_value})
            elif (curr_key == 'parentInternetMessageId'):
                curr_value = cef_artifact['emailHeaders'].pop(curr_key)
                cef_artifact.update({curr_key: curr_value})
            elif (curr_key == 'parentGuid'):
                curr_value = cef_artifact['emailHeaders'].pop(curr_key)
                cef_artifact.update({curr_key: curr_value})
            elif (curr_key == 'emailGuid'):
                curr_value = cef_artifact['emailHeaders'].pop(curr_key)
                cef_artifact.update({curr_key: curr_value})

        # Adding the email id as a cef artifact crashes the UI when trying to show the action dialog box
        # so not adding this right now. All the other code to process the emailId is there, but the refraining
        # from adding the emailId
        # add_email_id = False
        if (add_email_id):
            cef_artifact['emailId'] = add_email_id
            if (self._email_id_contains):
                cef_types.update({'emailId': self._email_id_contains})

        artifact = {}
        artifact['name'] = 'Email Artifact'
        artifact['severity'] = self._base_connector.get_config().get('container_severity', 'medium')
        artifact['cef'] = cef_artifact
        artifact['cef_types'] = cef_types
        email_header_artifacts.append(artifact)

        return len(email_header_artifacts)

    def _handle_mail_object(self, mail, email_id, rfc822_email, tmp_dir, start_time_epoch):

        self._parsed_mail = OrderedDict()

        # Create a tmp directory for this email, will extract all files here
        tmp_dir = tmp_dir
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        extract_attach = self._config[PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS]

        charset = mail.get_content_charset()

        if (not charset):
            charset = 'utf8'

        # Extract fields and place it in a dictionary
        self._parsed_mail[PROC_EMAIL_JSON_SUBJECT] = mail.get('Subject', '')
        self._parsed_mail[PROC_EMAIL_JSON_FROM] = mail.get('From', '')
        self._parsed_mail[PROC_EMAIL_JSON_TO] = mail.get('To', '')
        self._parsed_mail[PROC_EMAIL_JSON_DATE] = mail.get('Date', '')
        self._parsed_mail[PROC_EMAIL_JSON_MSG_ID] = mail.get('Message-ID', '')
        self._parsed_mail[PROC_EMAIL_JSON_FILES] = files = []
        self._parsed_mail[PROC_EMAIL_JSON_BODIES] = bodies = []
        self._parsed_mail[PROC_EMAIL_JSON_START_TIME] = start_time_epoch
        self._parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS] = []

        file_hash = hashlib.sha1(rfc822_email.encode()).hexdigest()
        extension = '.eml'
        file_name = self._parsed_mail[PROC_EMAIL_JSON_SUBJECT]
        file_name = "{0}{1}".format(self._base_connector._decode_uni_string(file_name, file_name), extension)
        file_path = "{0}/{1}".format(tmp_dir, file_name)
        try:
            with open(file_path, 'wb') as f:
                f.write(rfc822_email.encode())
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            try:
                new_file_name = "ph_temp_email_file.eml"
                file_path = "{0}/{1}".format(tmp_dir, new_file_name)
                self._base_connector.debug_print("Original filename: {}".format(file_name))
                self._base_connector.debug_print("Modified filename: {}".format(new_file_name))
                with open(file_path, 'wb') as uncompressed_file:
                    uncompressed_file.write(rfc822_email.encode())
            except Exception as e:
                error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
                self._base_connector.debug_print("Error occurred while adding file to Vault. Error Details: {}".format(error_msg))
                return
        files.append({'file_name': file_name, 'file_path': file_path, 'file_hash': file_hash})

        # parse the parts of the email
        if (mail.is_multipart()):
            child = False
            message_id = None
            ret_val = None
            for i, part in enumerate(mail.walk()):
                add_email_id = None
                if (i == 0):
                    add_email_id = email_id

                self._parse_email_headers(self._parsed_mail, part, add_email_id=add_email_id)
                if message_id is None and part.get('Message-ID'):
                    message_id = part.get('Message-ID')
                    child = False
                elif message_id and part.get('Message-ID'):
                    child = True

                # parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS].append(part.items())

                if (part.is_multipart()):
                    self._debug_print("Skipping part because it is multipart")
                    continue

                self._debug_print("part: {0}".format(part.__dict__))
                self._debug_print("part type", type(part))

                try:
                    ret_val = self._handle_part(part, i, tmp_dir, extract_attach, self._parsed_mail, child)
                except Exception as e:
                    self._debug_print("ErrorExp in _handle_part # {0}".format(i), e)
                    continue

                if (phantom.is_fail(ret_val)):
                    continue

        else:
            print('else')
            self._parse_email_headers(self._parsed_mail, mail, add_email_id=email_id)
            # parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS].append(mail.items())
            file_path = "{0}/part_1.text".format(tmp_dir)
            with open(file_path, 'wb') as f:
                f.write(mail.get_payload(decode=True))
            bodies.append({'file_path': file_path, 'charset': mail.get_content_charset()})

        # get the container name
        container_name = self._get_container_name(self._parsed_mail, email_id)

        if (container_name is None):
            return phantom.APP_ERROR

        # Add the container
        # first save the container, to do that copy things from parsed_mail to a new object
        container_data = dict(self._parsed_mail)

        # delete the header info, we dont make it a part of the container json
        del(container_data[PROC_EMAIL_JSON_EMAIL_HEADERS])
        self._container['source_data_identifier'] = email_id
        self._container['name'] = container_name
        self._container['data'] = {'raw_email': rfc822_email}
        self._container['severity'] = self._base_connector.get_config().get('container_severity', 'medium')

        # Create the sets before handling the bodies If both the bodies add the same ip
        # only one artifact should be created

        # Changing to a list due to add parent identifier in each artifact
        self._parsed_mail[PROC_EMAIL_JSON_IPS] = list()
        self._parsed_mail[PROC_EMAIL_JSON_HASHES] = list()
        self._parsed_mail[PROC_EMAIL_JSON_URLS] = list()
        self._parsed_mail[PROC_EMAIL_JSON_DOMAINS] = list()
        self._parsed_mail[PROC_EMAIL_JSON_EMAIL_ADDRESSES] = list()

        # For bodies
        for i, body in enumerate(bodies):
            if (not body):
                continue

            try:
                self._handle_body(body, self._parsed_mail, i, email_id)
            except Exception as e:
                error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
                err = "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)
                self._debug_print("Error occurred in _handle_body # {0}. {1}".format(i, err))
                continue

        # Files
        self._attachments.extend(files)

        self._create_artifacts(self._parsed_mail)

        return phantom.APP_SUCCESS

    def _set_email_id_contains(self, email_id):

        if (not self._base_connector):
            return

        email_id = str(email_id)

        if ((self._base_connector.get_app_id() == EXCHANGE_ONPREM_APP_ID) and (email_id.endswith('='))):
            self._email_id_contains = [ "exchange email id" ]
        elif ((self._base_connector.get_app_id() == OFFICE365_APP_ID) and (email_id.endswith('='))):
            self._email_id_contains = [ "office 365 email id" ]
        elif (self._base_connector.get_app_id() == IMAP_APP_ID) and (email_id.isdigit()):
            self._email_id_contains = [ "imap email id" ]
        elif (ph_utils.is_sha1(email_id)):
            self._email_id_contains = [ "vault id" ]

        return

    def _int_process_email(self, rfc822_email, email_id, start_time_epoch):

        mail = email.message_from_string(rfc822_email)

        ret_val = phantom.APP_SUCCESS

        tmp_dir = tempfile.mkdtemp(prefix='ph_email_ewsonprem')
        self._tmp_dirs.append(tmp_dir)

        try:
            ret_val = self._handle_mail_object(mail, email_id, rfc822_email, tmp_dir, start_time_epoch)
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            err = "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)
            message = "Error occurred in _handle_mail_object. {0}".format(err)
            self._debug_print(message)
            return (phantom.APP_ERROR, message, [])

        results = [{'container': self._container, 'artifacts': self._artifacts, 'files': self._attachments, 'temp_directory': tmp_dir}]

        return (ret_val, "Email Parsed", results)

    def process_email(self, base_connector, rfc822_email, email_id, config, epoch, container_id=None, email_headers=None, attachments_data=None):

        self._base_connector = base_connector
        self._config = config

        if (email_headers):
            for curr_header in email_headers:
                self._headers_from_ews.append(CaseInsensitiveDict(curr_header))

        if (config[PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS]) and (attachments_data is not None):
            self._attachments_from_ews = attachments_data

        try:
            self._set_email_id_contains(email_id)
        except:
            pass

        ret_val, message, results = self._int_process_email(rfc822_email, email_id, epoch)

        data = results[0].get('files', [])
        if (data):
            for file_info in data:
                con_des = file_info.get('meta_info', {}).get('headers', {}).get('Content-Description')
                if isinstance(con_des, str):
                    file_info['meta_info']['headers']['decodedContentDescription'] = self._decode_uni_string(con_des, con_des)

                con_type = file_info.get('meta_info', {}).get('headers', {}).get('Content-Type', '')
                con_type_uni = re.findall(r'=\?.*\?=', con_type)
                for value in range(len(con_type_uni)):
                    if isinstance(con_type_uni[value], str):
                        con_type_decode = self._decode_uni_string(con_type_uni[value], con_type_uni[value])
                        if 'decodedContentType' in file_info['meta_info']['headers']:
                            decoded_type = file_info['meta_info']['headers']['decodedContentType'].replace(con_type_uni[value], con_type_decode)
                            file_info['meta_info']['headers']['decodedContentType'] = decoded_type
                        else:
                            file_info['meta_info']['headers']['decodedContentType'] = con_type.replace(con_type_uni[value], con_type_decode)

                con_disp = file_info.get('meta_info', {}).get('headers', {}).get('Content-Disposition', '')
                con_disp_uni = re.findall(r'=\?.*\?=', con_disp)
                for value in range(len(con_disp_uni)):
                    if isinstance(con_disp_uni[value], str):
                        con_disp_decode = self._decode_uni_string(con_disp_uni[value], con_disp_uni[value])
                        if 'decodedContentDisposition' in file_info['meta_info']['headers']:
                            decoded_disposition = file_info['meta_info']['headers']['decodedContentDisposition'].replace(con_disp_uni[value],
                                                                                                                         con_disp_decode)
                            file_info['meta_info']['headers']['decodedContentDisposition'] = decoded_disposition
                        else:
                            file_info['meta_info']['headers']['decodedContentDisposition'] = con_disp.replace(con_disp_uni[value],
                                                                                                              con_disp_decode)

        if (not ret_val):
            self._del_tmp_dirs()
            return (phantom.APP_ERROR, message)

        try:
            self._parse_results(results, container_id)
        except Exception:
            self._del_tmp_dirs()
            raise

        return (phantom.APP_SUCCESS, "Email Processed")

    def _handle_save_ingested(self, artifacts, container, container_id, files):
        # One of either container or container_id will be set to None
        using_dummy = False
        duplicate_container = False

        if container_id:
            # We are adding artifacts to an existing container
            using_dummy = True
            container = {
                'name': 'Dummy Container',
                'dummy': True,
                'id': container_id
            }

        if (hasattr(self._base_connector, '_preprocess_container')):
            container = self._base_connector._preprocess_container(container)

        if not using_dummy:
            ret_val, message, container_id = self._base_connector.save_container(container)
            self._base_connector.debug_print(
                "save_container (without artifacts) returns, value: {0}, reason: {1}, id: {2}".format(
                    ret_val,
                    message,
                    container_id
                )
            )
            duplicate_container = (message == "Duplicate container found")

        if duplicate_container and (not self._base_connector.is_poll_now() and self._base_connector.get_action_identifier() != "get_email"):
            self._base_connector._dup_emails += 1

        if not using_dummy:
            if (phantom.is_fail(ret_val)):
                message = "Failed to save ingested container, error msg: {0}".format(message)
                self._base_connector.debug_print(message)
                return

        if (not container_id):
            message = "save_container did not return a container_id"
            self._base_connector.debug_print(message)
            return

        if duplicate_container and (not self._base_connector.is_poll_now()) and self._config.get(EWS_JSON_INGEST_TIME, "") == "created time":
            message = "Skipping the process of save_artifacts because when \
                       the created_time is selected, new artifacts should not be ingested for duplicate container"
            self._base_connector.debug_print(message)
            return

        vault_artifacts = list()
        for i, curr_file in enumerate(files):

            file_name = self._decode_uni_string(curr_file.get('file_name'), curr_file.get('file_name'))

            try:
                success, message, vault_info = phantom_rules.vault_info(vault_id=curr_file['file_hash'], container_id=container_id)
            except:
                continue

            if "file_hash" in curr_file and vault_info:
                self._base_connector.debug_print("File {0} already attached to container {1}. Skipping.".format(file_name, container_id))
                continue

            local_file_path = curr_file['file_path']

            contains = self._get_file_contains(local_file_path)

            # lets move the data into the vault
            vault_attach_dict = {}

            if (not file_name):
                file_name = os.path.basename(local_file_path)

            self._base_connector.debug_print("Vault file name: {0}".format(self._base_connector._handle_py_ver_compat_for_input_str(file_name)))

            vault_attach_dict[phantom.APP_JSON_ACTION_NAME] = self._base_connector.get_action_name()
            vault_attach_dict[phantom.APP_JSON_APP_RUN_ID] = self._base_connector.get_app_run_id()

            file_name = self._decode_uni_string(file_name, file_name)

            try:
                success, message, vault_id = phantom_rules.vault_add(file_location=local_file_path,
                                                                     container=container_id,
                                                                     file_name=file_name,
                                                                     metadata=vault_attach_dict)
            except Exception as e:
                error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
                err = "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)
                self._base_connector.debug_print(phantom.APP_ERR_FILE_ADD_TO_VAULT.format(err))
                continue

            if not success:
                self._base_connector.debug_print("Failed to add file to Vault: {0}".format(json.dumps(message)))
                continue

            # add the vault id artifact to the container
            cef_artifact = curr_file.get('meta_info', {})
            if (file_name):
                cef_artifact.update({'fileName': file_name})

            if vault_id:
                cef_artifact.update({'vaultId': vault_id,
                    'cs6': vault_id,
                    'cs6Label': 'Vault ID'})

                # now get the rest of the hashes and add them to the cef artifact
                self._add_vault_hashes_to_dictionary(cef_artifact, vault_id, container_id)

            if (not cef_artifact):
                continue

            artifact = {}
            artifact['name'] = 'Vault Artifact'
            # set the artifact severity as configured in the asset, otherwise the artifact will get the default 'medium' severity
            # The container picks up the severity of any artifact that is higher than it's own
            artifact['severity'] = self._base_connector.get_config().get('container_severity', 'medium')
            artifact['cef'] = cef_artifact

            if (contains):
                artifact['cef_types'] = {'vaultId': contains, 'cs6': contains}
            self._set_sdi(artifact)

            if ('parentGuid' in cef_artifact):
                parent_guid = cef_artifact.pop('parentGuid')
                cef_artifact['parentSourceDataIdentifier'] = self._guid_to_hash.get(parent_guid)
                self._debug_print("The value of parentSourceDataIdentifier in cef_artifact of is: {}".format(
                    cef_artifact.get('parentSourceDataIdentifier')))

            vault_artifacts.append(artifact)

        if vault_artifacts:
            artifacts.extend(vault_artifacts)

        container['artifacts'] = artifacts
        if (hasattr(self._base_connector, '_preprocess_container')):
            container = self._base_connector._preprocess_container(container)

        artifacts_list = container['artifacts']

        for artifact in artifacts_list:
            artifact['container_id'] = container_id
            artifact['run_automation'] = False

        if duplicate_container:
            artifacts[-1]['run_automation'] = self._config.get('automation_on_duplicate', True)
        else:
            artifacts[-1]['run_automation'] = True

        ret_val, message, ids = self._base_connector.save_artifacts(artifacts_list)
        self._base_connector.debug_print(
            "save_artifacts returns, value: {0}, reason: {1}".format(
                ret_val,
                message
            )
        )

        if (phantom.is_fail(ret_val)):
            message = "Failed to save ingested artifacts, error msg: {0}".format(message)
            self._base_connector.debug_print(message)

        return

    def _parse_results(self, results, container_id=None):

        param = self._base_connector.get_current_param()

        container_count = EWS_DEFAULT_CONTAINER_COUNT
        # artifact_count = EWS_DEFAULT_ARTIFACT_COUNT

        if (param):
            container_count = param.get(phantom.APP_JSON_CONTAINER_COUNT, EWS_DEFAULT_CONTAINER_COUNT)
            # artifact_count = param.get(phantom.APP_JSON_ARTIFACT_COUNT, EWS_DEFAULT_ARTIFACT_COUNT)

        results = results[:container_count]

        for result in results:

            if (container_id is None):

                container = result.get('container')

                if (not container):
                    continue

            else:
                container = None

            # run a loop to first set the sdi which will create the hash
            artifacts = result.get('artifacts', [])
            for j, artifact in enumerate(artifacts):

                if (not artifact):
                    continue

                self._set_sdi(artifact)

            if (not artifacts):
                continue

            for j, artifact in enumerate(artifacts):

                if (not artifact):
                    continue

                cef_artifact = artifact.get('cef')
                if ('parentGuid' in cef_artifact):
                    parent_guid = cef_artifact.pop('parentGuid')
                    if (parent_guid in self._guid_to_hash):
                        cef_artifact['parentSourceDataIdentifier'] = self._guid_to_hash[parent_guid]
                if ('emailGuid' in cef_artifact):
                    # cef_artifact['emailGuid'] = self._guid_to_hash[cef_artifact['emailGuid']]
                    del cef_artifact['emailGuid']

            self._handle_save_ingested(artifacts, container, container_id, result.get('files'))

        # delete any temp directories that were created by the email parsing function
        [shutil.rmtree(x['temp_directory'], ignore_errors=True) for x in results if x.get('temp_directory')]

        return self._base_connector.set_status(phantom.APP_SUCCESS)

    def _add_vault_hashes_to_dictionary(self, cef_artifact, vault_id, container_id):

        try:
            success, message, vault_info = phantom_rules.vault_info(vault_id=vault_id, container_id=container_id)
        except:
            return phantom.APP_ERROR, "Could not retrieve vault file"

        if (not vault_info):
            return (phantom.APP_ERROR, "Vault ID not found")

        # The return value is a list, each item represents an item in the vault
        # matching the vault id, the info that we are looking for (the hashes)
        # will be the same for every entry, so just access the first one
        try:
            metadata = vault_info[0].get('metadata')
        except:
            return (phantom.APP_ERROR, "Failed to get vault item metadata")

        try:
            cef_artifact['fileHashSha256'] = metadata['sha256']
        except:
            pass

        try:
            cef_artifact['fileHashMd5'] = metadata['md5']
        except:
            pass

        try:
            cef_artifact['fileHashSha1'] = metadata['sha1']
        except:
            pass

        return (phantom.APP_SUCCESS, "Mapped hash values")

    def _set_sdi(self, input_dict):

        if ('source_data_identifier' in input_dict):
            del input_dict['source_data_identifier']

        input_dict_hash = input_dict

        cef = input_dict.get('cef')

        curr_email_guid = None

        if (cef is not None):
            if (('parentGuid' in cef) or ('emailGuid' in cef)):
                # make a copy since the dictionary will have to be different
                input_dict_hash = deepcopy(input_dict)
                cef = input_dict_hash['cef']
                if ('parentGuid' in cef):
                    del cef['parentGuid']
                curr_email_guid = cef.get('emailGuid')
                if (curr_email_guid is not None):
                    del cef['emailGuid']

        input_dict['source_data_identifier'] = self._create_dict_hash(input_dict_hash)

        if (curr_email_guid):
            self._guid_to_hash[curr_email_guid] = input_dict['source_data_identifier']

        return phantom.APP_SUCCESS

    def _create_dict_hash(self, input_dict):

        input_dict_str = None

        if (not input_dict):
            return None

        try:
            input_dict_str = json.dumps(input_dict, sort_keys=True)
        except Exception as e:
            error_code, error_msg = self._base_connector._get_error_message_from_exception(e)
            err = "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)
            self._base_connector.debug_print('Error occurred in _create_dict_hash. {0}'.format(err))
            return None

        return hashlib.md5(UnicodeDammit(input_dict_str).unicode_markup.encode('utf-8')).hexdigest()

    def _del_tmp_dirs(self):
        """Remove any tmp_dirs that were created."""
        for tmp_dir in self._tmp_dirs:
            shutil.rmtree(tmp_dir, ignore_errors=True)
