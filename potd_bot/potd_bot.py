# -*- coding: utf-8 -*-

import requests
from datetime import date, timedelta, datetime, timezone
import re 
import os
from typing import Dict, List
from bs4 import BeautifulSoup
from PIL import Image
import ffmpeg
import ffprobe

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")
USER_AGENT = {"User-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"}

#Define a function that logs into bluesky, return the access token
def bsky_login_session(handle: str, password: str) -> Dict:
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password})
    resp.raise_for_status()
    resp_data = resp.json()
    return(resp_data["did"], resp_data["accessJwt"])

#Define function to get the date in the printable form needed
def date_of_interest():
    today = date.today() - timedelta(21)
    year = today.strftime("%Y")
    month = today.strftime("%m")
    day = today.strftime("%d")
    day_nonzero = today.strftime("%-e")
    
    specified_date = datetime(int(year), int(month), int(day))
    
    day_name = specified_date.strftime('%A')
    month_name = specified_date.strftime('%B')
    
    print_date = """{} {} {} {}""".format(day_name, day_nonzero, month_name, year)
    
    return(print_date, year, month, day)

#Define the function that returns the wikipedia data needed for the post
def get_wikipedia_data():
   file_type_movie = False
   movie_cut = False
   current_year, current_month, current_day = date_of_interest()[1:4]
   day_isoformat = "{}-{}-{}".format(current_year, current_month, current_day)
   
   params = {
     "action": "query",
     "format": "json",
     "formatversion": "2",
     "prop": "images",
     "titles": "Template:POTD protected/" + day_isoformat
     }
   resp = requests.Session().get(url = "https://en.wikipedia.org/w/api.php", params=params, headers = USER_AGENT)
   resp_data = resp.json() 
   filename = resp_data["query"]["pages"][0]["images"][0]["title"]
    
   params = {
    "action": "query",
    "format": "json",
    "prop": "imageinfo",
    "iiprop": "url",
    "titles": filename
    }
   resp = requests.Session().get(url = "https://en.wikipedia.org/w/api.php", params=params, headers = USER_AGENT)
   resp_data = resp.json()
   page = next(iter(resp_data["query"]["pages"].values()))
   image_info = page["imageinfo"][0]
   image_url = image_info["url"]
   image_page_url = "https://en.wikipedia.org/wiki/Template:POTD_protected/" + day_isoformat
   
   if image_url.lower().endswith(".jpg"):
       with open("feat_picture.jpg", 'w+b') as file:
        response = requests.get(image_url, stream=True, headers = USER_AGENT)
        file.write(response.content)
        image = Image.open(file)
        width, height = image.size
        new_width = 2000
        ratio = width / height
        new_height = new_width / ratio
        resized_image = image.resize((new_width, round(new_height)))
        quality_counter = 100 
        resized_image.save("feat_picture_resized.jpg",optimize=True, quality = quality_counter)
        while os.path.getsize("feat_picture_resized.jpg") > 1_000_000: 
            quality_counter -= 1
            resized_image.save("feat_picture_resized.jpg", optimize=True, quality = quality_counter)
        final_path = os.getcwd() + "/feat_picture_resized.jpg"
        response = requests.get(image_page_url, headers = USER_AGENT)
        soup = BeautifulSoup(response.text, 'html.parser')
        body_text = soup.body.find('div', attrs={'class':'mw-body-content'}).text
        credit_line = body_text.partition("credit")[2]
        credits = credit_line.partition("\n")[0]
        tot_alt_text = re.sub(r'\s+', ' ', body_text.partition("credit")[0]).strip()
        cleaned_alt_text = tot_alt_text.rsplit(' ',1)[0]
        img_type = tot_alt_text.rsplit(' ',1)[1].lower()
        alt_text = cleaned_alt_text + " Type: " + img_type + ". Credits" + credits + "."
        description_text = soup.body.find('a', attrs={'class':'mw-file-description'})
        title = description_text.get("title")
        
   elif image_url.lower().endswith(".webm"):
        file_type_movie = True
        print("VIDEO")
        with open("feat_video.webm", 'w+b') as file:
            response = requests.get(image_url, stream=True, headers = USER_AGENT)
            file.write(response.content)
        probe = ffmpeg.probe("feat_video.webm")
        duration_seconds = float(probe['format']['duration'])
        print("original duration",duration_seconds)
        print("original file size", os.path.getsize("feat_video.webm"))
        if duration_seconds > 179:
            movie_cut = True
            input_file = ffmpeg.input("feat_video.webm", ss="00:00:00", to="00:00:10")
            output_file = ffmpeg.output(input_file, "feat_video_adapt.webm", acodec='copy',vcodec='copy')
            output_file.run(overwrite_output=True)
            probe = ffmpeg.probe("feat_video_adapt.webm")
            duration_seconds = float(probe['format']['duration'])
            print("new duration", duration_seconds)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            print(audio_stream)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            print(audio_stream)
            os.replace("feat_video_adapt.webm", "feat_video.webm")
        
        print("New file size", os.path.getsize("feat_video.webm"))
        
        if os.path.getsize("feat_video.webm") > 100_000_000: 
            probe = ffmpeg.probe("feat_video.webm")
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            if width > 720: 
                input_file = ffmpeg.input("feat_video.webm")
                ffmpeg.input("feat_video.webm").filter("scale", 720, -1).output("feat_video_adapt.webm").run()
                os.replace("feat_video_adapt.webm", "feat_video.webm")
        else:
            print("Resolution adaptation not needed")
                
        if os.path.getsize("feat_video.webm") > 100_000_000: 
            probe = ffmpeg.probe("feat_video.webm")
            audio_bitrate = float(next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)['bit_rate'])
            print(audio_bitrate)
            if audio_bitrate > 128_000:
                input = ffmpeg.input("feat_video.webm")
                ffmpeg.output(input, "feat_video_adapt.webm", **{'c:v': 'libvpx-vp9', 'c:a': 'libopus', 'b:a': 128_000}).overwrite_output().run()
                os.replace("feat_video_adapt.webm", "feat_video.webm")
        else:
            print("video bitrate adaptation not needed")
        
        if os.path.getsize("feat_video.webm") > 100_000_000: 
            probe = ffmpeg.probe("feat_video.webm")
            video_bitrate = float(next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)['bit_rate'])
            print(video_bitrate)
            if video_bitrate > 2_500_000:
                input = ffmpeg.input("feat_video.webm")
                ffmpeg.output(input, "feat_video_adapt.webm", **{'c:v': 'libvpx-vp9', 'c:a': 'libopus', 'b:v': 2_500_000}).overwrite_output().run()
                os.replace("feat_video_adapt.webm", "feat_video.webm")
        else:
            print("aaudio bitrate adaptation not needed")
                
        final_path = os.getcwd() + "/feat_video.webm"
        response = requests.get(image_page_url, headers = USER_AGENT)
        soup = BeautifulSoup(response.text, 'html.parser')
        body_text = soup.body.find('div', attrs={'class':'mw-body-content'}).text
        credit_line = body_text.partition("credit")[2]
        credits = credit_line.partition("\n")[0]
        tot_alt_text = re.sub(r'\s+', ' ', body_text.partition("credit")[0]).strip()
        cleaned_alt_text = tot_alt_text.rsplit(' ',1)[0]
        img_type = tot_alt_text.rsplit(' ',1)[1].lower()
        alt_text = cleaned_alt_text + " Type: " + img_type + ". Credits" + credits + "."
        title_data = soup.select_one("td p")
        title = title_data.find_all("a")[0].get_text()
        
   else:
        pass        

   return(final_path, title, alt_text, credits, img_type, file_type_movie, movie_cut, image_url)
    
#Define the text of the post
def text_of_message():
   date_it = date_of_interest()[0]
   wikipedia_data = get_wikipedia_data()
   title = wikipedia_data[1]
   credits = wikipedia_data[3]
   movie_cut = wikipedia_data[6]
   image_url = wikipedia_data[7]
   if not movie_cut:
       print_message = f"""The Picture of the Day of {date_it} on @wikipedia.org is: {title}.\n\nCredits{credits}."""
   elif movie_cut:
       print_message = f"""The Picture of the Day of {date_it} on @wikipedia.org is: {title}.\n\nCredits{credits}.\n\nThis movie has been cut from the original due to Bluesky media limits, view the original on {image_url}."""
   return(print_message)

#Define function to parse mentions in the message text into facets
def parse_mentions(text: str) -> List[Dict]:
    spans = []
    mention_regex = rb"[$|\W](@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(mention_regex, text_bytes):
        spans.append(
            {
                "start": m.start(1),
                "end": m.end(1),
                "handle": m.group(1)[1:].decode("UTF-8"),
            }
        )
    return spans

#Define function to turn facets into bluesky objects text and return list of bluesky objects
def parse_facets(text: str) -> List[Dict]:
    facets = []
    for m in parse_mentions(text):
        resp = requests.get(
            "https://bsky.social/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": m["handle"]},)
        if resp.status_code == 400:
            continue
        did = resp.json()["did"]
        facets.append(
            {
                "index": {
                    "byteStart": m["start"],
                    "byteEnd": m["end"],
                },
                "features": [{"$type": "app.bsky.richtext.facet#mention", "did": did}],
            }
        )
    for u in parse_urls(text):
        facets.append(
            {
                "index": {
                    "byteStart": u["start"],
                    "byteEnd": u["end"],
                },
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#link",
                        "uri": u["url"],
                    }
                ],
            }
        )
    return facets

#Define function to parse URLs in the message text into facets
def parse_urls(text: str) -> List[Dict]:
    spans = []
    url_regex = rb"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(url_regex, text_bytes):
        spans.append(
            {
                "start": m.start(1),
                "end": m.end(1),
                "url": m.group(1).decode("UTF-8"),
            }
        )
    return spans

def create_post(text: str, wikipedia_data):
    image_path = wikipedia_data[0]
    alt = wikipedia_data[2]
    file_type_movie = wikipedia_data[5]
    session = bsky_login_session(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    language = "en-US"
    
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        headers={
            "Content-Type": "image/jpg",
            "Authorization": "Bearer " + session[1],
        },
        data=img_bytes,
        )
    print(1)    
    resp.raise_for_status()
    blob = resp.json()["blob"]
    print(2)
    post = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
        "langs": [language],}
    print(3)
    if not file_type_movie:
        post["embed"] = {
        "$type": "app.bsky.embed.images",
        "images": [{
            "alt": alt,
            "image": blob,
        }],
        }
    print(4)
    if file_type_movie:
        post["embed"] = {
            "type": "app.bsky.embed.video",
            "video": blob,
            "aspectRatio": 1412 / 1080,
            }
    print(5)

    if len(text) > 0:
        facets = parse_facets(post["text"])
        if facets:
            post["facets"] = facets
    print(6)

    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": "Bearer " + session[1]},
        json={
            "repo": session[0],
            "collection": "app.bsky.feed.post",
            "record": post,
        },
    )
    print(7)
    resp.raise_for_status()
    print(8)

def main():
    create_post(text_of_message(), get_wikipedia_data())