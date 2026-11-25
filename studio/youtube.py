"""YouTube upload through the official YouTube Data API v3.

The user's own Google Cloud OAuth client ("Desktop app") and the sign-in token are kept in
%LOCALAPPDATA%\\HighlightStudio\\youtube\\ (never in the repo). Nothing is uploaded unless the
user presses Upload in the app."""
import json
import shutil
import threading
from datetime import datetime
from pathlib import Path

from common import DATA

YT_DIR = DATA / "youtube"
YT_DIR.mkdir(parents=True, exist_ok=True)
CLIENT = YT_DIR / "client_secret.json"
TOKEN = YT_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
GAMING = "20"
_lock = threading.Lock()
_channel = None  # cached {"id", "title"}


class YTError(Exception):
    """An error with a message meant for the user."""


def _friendly(e):
    """Turn Google API errors into plain messages."""
    text = str(e)
    try:
        from googleapiclient.errors import HttpError
        if isinstance(e, HttpError):
            data = json.loads(e.content.decode("utf-8", "replace"))
            err = data.get("error", {})
            reasons = {x.get("reason") for x in err.get("errors", [])}
            if reasons & {"quotaExceeded", "rateLimitExceeded", "uploadLimitExceeded"}:
                return "YouTube's daily upload limit for this app is reached. Try again tomorrow."
            if "youtubeSignupRequired" in reasons:
                return "This Google account doesn't have a YouTube channel yet. Create one on youtube.com first."
            if e.resp.status in (401, 403) and ("insufficient" in text.lower() or "authError" in reasons):
                return "YouTube refused the sign-in. Sign in again in Settings → YouTube."
            if "accessNotConfigured" in reasons or "SERVICE_DISABLED" in text:
                return "The YouTube Data API isn't enabled in your Google Cloud project (setup step 2)."
            return err.get("message") or text
    except Exception:
        pass
    if "invalid_grant" in text or "Token has been expired or revoked" in text:
        return "The YouTube sign-in expired or was revoked. Sign in again in Settings → YouTube."
    return text


def set_client(path):
    """Copy the downloaded OAuth client file into the app's folder after checking it."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise YTError("That file isn't a Google OAuth client file (JSON).")
    if "installed" not in data:
        kind = next(iter(data), "unknown")
        raise YTError(f"This client is of type '{kind}'. Create an OAuth client ID of type 'Desktop app' (setup step 4).")
    shutil.copyfile(path, CLIENT)
    sign_out()
    return True


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not TOKEN.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                if "invalid_grant" in str(e):  # expired (Testing mode: after 7 days) or revoked: start clean
                    sign_out()
                    raise YTError("The YouTube sign-in expired (Google does this weekly for apps in Testing). Sign in again.")
                raise YTError(_friendly(e))
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
        else:
            return None
    return creds


def _service():
    from googleapiclient.discovery import build
    c = _creds()
    if not c:
        raise YTError("Not signed in to YouTube. Sign in in Settings → YouTube.")
    return build("youtube", "v3", credentials=c, cache_discovery=False)


def sign_in():
    """Opens the normal Google sign-in in the browser; returns the channel."""
    global _channel
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not CLIENT.exists():
        raise YTError("Choose your OAuth client file first (setup step 5).")
    with _lock:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300,
                                      authorization_prompt_message="",
                                      success_message="Signed in. You can close this tab and go back to Highlight Studio.")
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
        _channel = None
    return status()


def sign_out():
    global _channel
    TOKEN.unlink(missing_ok=True)
    _channel = None


def status():
    """{client, signed_in, channel{id,title}, error}"""
    global _channel
    out = {"client": CLIENT.exists(), "signed_in": False, "channel": None, "error": ""}
    if not out["client"] or not TOKEN.exists():
        return out
    try:
        if _channel is None:
            r = _service().channels().list(part="snippet", mine=True).execute()
            items = r.get("items") or []
            if not items:
                out["error"] = "This Google account doesn't have a YouTube channel yet."
                return out
            _channel = {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}
        out.update(signed_in=True, channel=_channel)
    except YTError as e:
        out["error"] = str(e)
    except Exception as e:
        out["error"] = _friendly(e)
    return out


def upload(path, meta, progress, cancelled):
    """Resumable upload. meta: title, description, tags[], privacy, publish_at (ISO UTC or ''),
    made_for_kids, notify. progress(fraction) is called per chunk; cancelled() is checked between chunks.
    Returns {id, url, studio, privacy_requested, privacy}."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    yt = _service()
    privacy = meta.get("privacy", "private")
    status_ = {"privacyStatus": "private" if meta.get("publish_at") else privacy,
               "selfDeclaredMadeForKids": bool(meta.get("made_for_kids"))}
    if meta.get("publish_at"):
        status_["publishAt"] = meta["publish_at"]
    body = {"snippet": {"title": meta["title"][:100], "description": meta.get("description", "")[:5000],
                        "tags": meta.get("tags") or [], "categoryId": GAMING},
            "status": status_}
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media,
                             notifySubscribers=bool(meta.get("notify", True)))
    resp, retries = None, 0
    while resp is None:
        if cancelled():
            raise YTError("Cancelled")
        try:
            st, resp = req.next_chunk()
            retries = 0
            if st:
                progress(st.progress())
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                continue
            raise YTError(_friendly(e))
        except (ConnectionError, TimeoutError, OSError) as e:
            if retries < 5:
                retries += 1
                continue
            raise YTError(f"The connection dropped during the upload ({type(e).__name__}).")
    progress(1.0)
    vid = resp["id"]
    applied = (resp.get("status") or {}).get("privacyStatus", status_["privacyStatus"])
    return {"id": vid, "url": f"https://youtu.be/{vid}", "studio": f"https://studio.youtube.com/video/{vid}/edit",
            "privacy_requested": "scheduled" if meta.get("publish_at") else privacy, "privacy": applied,
            "publish_at": meta.get("publish_at") or None, "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "title": body["snippet"]["title"]}
