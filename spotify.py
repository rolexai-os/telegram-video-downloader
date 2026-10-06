#!/usr/bin/env python3
"""Spotify metadata resolver.

Spotify does not expose a public raw-audio download endpoint. This module
resolves public track/album/playlist metadata; the runner then uses yt-dlp
to fetch a publicly available audio source.
"""
import base64
import json
import os
import re
import urllib.parse
import urllib.request

SPOTIFY_CLIENT_ID=os.getenv("SPOTIFY_CLIENT_ID","").strip()
SPOTIFY_CLIENT_SECRET=os.getenv("SPOTIFY_CLIENT_SECRET","").strip()
SPOTIFY_API="https://api.spotify.com/v1"
TRACK_RE=re.compile(r"open\.spotify\.com/(?:intl-[^/]+/)?track/([A-Za-z0-9]+)",re.I)
PLAYLIST_RE=re.compile(r"open\.spotify\.com/(?:intl-[^/]+/)?playlist/([A-Za-z0-9]+)",re.I)
ALBUM_RE=re.compile(r"open\.spotify\.com/(?:intl-[^/]+/)?album/([A-Za-z0-9]+)",re.I)

def is_spotify_url(url):
    try:
        p=urllib.parse.urlparse(url)
        return p.netloc.lower() in {"open.spotify.com","play.spotify.com"} and bool(TRACK_RE.search(url) or PLAYLIST_RE.search(url) or ALBUM_RE.search(url))
    except Exception:
        return False

def kind(url):
    if TRACK_RE.search(url): return "track"
    if PLAYLIST_RE.search(url): return "playlist"
    if ALBUM_RE.search(url): return "album"
    return None

def _json(url,headers=None,data=None):
    req=urllib.request.Request(url,data=data,headers=headers or {},method="POST" if data else "GET")
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def _token():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError("Spotify playlist/album support requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.")
    raw=f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    body=urllib.parse.urlencode({"grant_type":"client_credentials"}).encode()
    data=_json("https://accounts.spotify.com/api/token",{
        "Authorization":"Basic "+base64.b64encode(raw).decode(),
        "Content-Type":"application/x-www-form-urlencoded"},body)
    return data["access_token"]

def _api(path,token,params=None):
    url=SPOTIFY_API+path
    if params: url+="?"+urllib.parse.urlencode(params)
    return _json(url,{"Authorization":"Bearer "+token})

def _track(item):
    artists=item.get("artists") or []
    return {"title":item.get("name") or "Unknown","artist":", ".join(a.get("name","") for a in artists if a.get("name")),
            "album":(item.get("album") or {}).get("name",""),"url":item.get("external_urls",{}).get("spotify","")}

def track(url):
    m=TRACK_RE.search(url)
    if not m: raise RuntimeError("Invalid Spotify track URL.")
    try:
        return _track(_api("/tracks/"+m.group(1),_token()))
    except Exception:
        # Public oEmbed fallback works for individual public tracks without credentials.
        data=_json("https://open.spotify.com/oembed?url="+urllib.parse.quote(url,safe=""))
        title=data.get("title","")
        author=data.get("author_name","")
        if not title: raise RuntimeError("Could not resolve this Spotify track.")
        return {"title":title,"artist":author,"album":"","url":url}

def collection(url):
    k=kind(url)
    if k not in {"playlist","album"}: raise RuntimeError("Spotify playlist or album URL required.")
    token=_token()
    if k=="playlist":
        m=PLAYLIST_RE.search(url)
        data=_api("/playlists/"+m.group(1),token,{"fields":"name,tracks.items(track(name,artists,album,external_urls)),tracks.next,tracks.total","limit":100})
        items=[x.get("track") for x in (data.get("tracks") or {}).get("items",[]) if x.get("track")]
        return data.get("name","Spotify Playlist"),[_track(x) for x in items]
    m=ALBUM_RE.search(url)
    data=_api("/albums/"+m.group(1),token,{"limit":50})
    return data.get("name","Spotify Album"),[_track(x) for x in data.get("tracks",{}).get("items",[])]

def search_query(track_info):
    return f"ytsearch1:{track_info['artist']} - {track_info['title']}".strip(" -")
