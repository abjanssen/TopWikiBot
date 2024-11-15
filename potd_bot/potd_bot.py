# -*- coding: utf-8 -*-

import requests
from datetime import date, timedelta, datetime, timezone
import re 
import os
from typing import Dict, List
from bs4 import BeautifulSoup
from PIL import Image

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

#Define a function that logs into bluesky, return the access token
def bsky_login_session(handle: str, password: str) -> Dict:
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password})
    resp.raise_for_status()
    resp_data = resp.json()
    jwt = resp_data["accessJwt"]
    did = resp_data["did"]
    return(did, jwt)

#Define function to get the date in the printable form needed
def date_of_interest():
    current_day = date.today()
    year = current_day.strftime("%Y")
    month = current_day.strftime("%m")
    dayofmonth = current_day.strftime("%d")
    day_adapted = current_day.strftime("%-e")
    specified_date = datetime(int(year), int(month), int(dayofmonth))
    day_name = specified_date.strftime('%A')
    month_name = specified_date.strftime('%B')
    print_date = """{} {} {} {}""".format(day_name, day_adapted, month_name, year)
    return(print_date)

#Define the function that returns the wikipedia data needed for the post
def get_wikipedia_data():
   current_date = date.today() - timedelta(0)
   current_day = current_date.strftime("%-e")
   current_month = current_date.strftime("%m")
   current_year = current_date.strftime("%Y")
   day_isoformat = "{}-{}-{}".format(current_year, current_month, current_day)
   user_agent = {"User-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.159 Safari/537.36"}
   
   params = {
     "action": "query",
     "format": "json",
     "formatversion": "2",
     "prop": "images",
     "titles": "Template:POTD protected/" + day_isoformat
     }
   r = requests.Session().get(url = "https://en.wikipedia.org/w/api.php", params=params, headers = user_agent)
   response_data = r.json() 
   filename = response_data["query"]["pages"][0]["images"][0]["title"]
    
   params = {
    "action": "query",
    "format": "json",
    "prop": "imageinfo",
    "iiprop": "url",
    "titles": filename
    }
   r = requests.Session().get(url="https://en.wikipedia.org/w/api.php", params=params, headers = user_agent)
   response_data = r.json()
   page = next(iter(response_data["query"]["pages"].values()))
   image_info = page["imageinfo"][0]
   image_url = image_info["url"]

   image_page_url = "https://en.wikipedia.org/wiki/Template:POTD_protected/" + day_isoformat
   
   with open("feat_picture.jpg", 'w+b') as file:
    response = requests.get(image_url, stream=True, headers = user_agent)
    file.write(response.content)
    image = Image.open(file)
    width, height = image.size
    new_width = 2000
    ratio = width / height
    new_height = new_width / ratio
    resized_image = image.resize((new_width, round(new_height)))
    quality_counter = 100 
    resized_image.save("feat_picture_resized.jpg",optimize=True, quality = quality_counter)
    while os.path.getsize("feat_picture_resized.jpg") > 1000000: 
        quality_counter -= 1
        resized_image.save("feat_picture_resized.jpg", optimize=True, quality = quality_counter)
    image_path = os.getcwd() + "/feat_picture_resized.jpg"
        
    response = requests.get(image_page_url, headers = user_agent)
    soup = BeautifulSoup(response.text, 'html.parser')

    body_text = soup.body.find('div', attrs={'class':'mw-body-content'}).text
    credit_line = body_text.partition("credit")[2]
    credits = credit_line.partition("\n")[0]
    
    tot_alt_text = re.sub(r'\s+', ' ', body_text.partition("credit")[0]).strip()
    cleaned_alt_text = tot_alt_text.rsplit(' ',1)[0]
    
    img_type = tot_alt_text.rsplit(' ',1)[1].lower()
    
    alt_text = cleaned_alt_text + " Type: " + img_type + " Credits" + credits + "."

    description_text = soup.body.find('a', attrs={'class':'mw-file-description'})
    title = description_text.get("title")
#    alt_text = soup.body.find('img', attrs={'class': 'mw-file-element'})
#    alt = alt_text.get('alt')

    return(image_path, title, alt_text, credits, img_type)
    
#Define the text of the post
def text_of_message():
   date_it = date_of_interest()
   wikipedia_data = get_wikipedia_data()
   title = wikipedia_data[1]
   credits=wikipedia_data[3]
   print_message = f"""The Picture of the Day of {date_it} on @wikipedia.bsky.social is: {title}.\n\nCredit{credits}."""
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
    resp.raise_for_status()
    blob = resp.json()["blob"]
    
    post = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
        "langs": [language],}
    
    post["embed"] = {
    "$type": "app.bsky.embed.images",
    "images": [{
        "alt": alt,
        "image": blob,
    }],
    }

    if len(text) > 0:
        facets = parse_facets(post["text"])
        if facets:
            post["facets"] = facets
    
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": "Bearer " + session[1]},
        json={
            "repo": session[0],
            "collection": "app.bsky.feed.post",
            "record": post,
        },
    )
    resp.raise_for_status()

def main():
    create_post(text_of_message(), get_wikipedia_data())