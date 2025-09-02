
import requests
from datetime import date, timedelta, datetime, timezone
import re 
import os
from typing import Dict, List
from bs4 import BeautifulSoup
from PIL import Image
from zoneinfo import ZoneInfo

#Defien global variables for easy use
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
    today = date.today()
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
    language = "en"
    year, month, day = date_of_interest()[1:4]

    req_url = "https://{}.wikipedia.org/api/rest_v1/feed/featured/{}/{}/{}".format(language, year, month, day)
    resp = requests.get(req_url, headers = USER_AGENT)
    resp_data = resp.json()
    
    today_feat_article = resp_data["tfa"]

    title = today_feat_article["normalizedtitle"]
    url = today_feat_article["content_urls"]["desktop"]["page"]
    text = today_feat_article["extract"].split(".")
    title_url = today_feat_article["title"]
    
    page_info_req_url = "https://{}.wikipedia.org/w/api.php?action=query&prop=pageimages&format=json&piprop=original&titles={}".format(language, title_url)
    page_info_resp = requests.get(page_info_req_url, headers = USER_AGENT)
    page_info_resp_data = page_info_resp.json()
    number_dict = page_info_resp_data["query"]["pages"]
    number = list(number_dict.keys())[0]
    
    if ('original' in page_info_resp_data['query']['pages'][number]):
        page_picture_url = page_info_resp_data["query"]["pages"][number]["original"]["source"]
    else:
        page_picture_url = None
    
    return(title,url,page_picture_url,text)

#Define the text of the post
def text_of_message():
   date_it = date_of_interest()[0]
   character_limit=300
   wikipedia_data = get_wikipedia_data()
   title = wikipedia_data[0]
   text = wikipedia_data[3]
   print_message = f"""The Featured Article of {date_it} on @wikipedia.org is: {title}.\n\n"""
   
   for i in range(len(text)):
       addition = text[i]
       if len(print_message + addition + ".") < character_limit:
           print_message = print_message + addition + "."
       else:
           break

   return(print_message)

def fix_url_format(url):
   match = re.search(r'en\.wikipedia\.org\/.*', url)
   if match:
       extracted_part = match.group(0)
       url = "https://" + extracted_part
   return(url)
    
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

#Define function to parse uris and return list of bluesky objects
def parse_uri(uri: str) -> Dict:
    if uri.startswith("at://"):
        repo, collection, rkey = uri.split("/")[2:5]
        return {"repo": repo, "collection": collection, "rkey": rkey}
    elif uri.startswith("https://bsky.app/"):
        repo, collection, rkey = uri.split("/")[4:7]
        if collection == "post":
            collection = "app.bsky.feed.post"
        elif collection == "lists":
            collection = "app.bsky.graph.list"
        elif collection == "feed":
            collection = "app.bsky.feed.generator"
        return {"repo": repo, "collection": collection, "rkey": rkey}
    else:
        raise Exception("unhandled URI format: " + uri)
        
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

#Define the function to fetch the embeded URL card for the top page
def fetch_embed_url_card() -> Dict:
    accessJWT = bsky_login_session(BLUESKY_HANDLE,BLUESKY_PASSWORD)[1]
    wikipedia_url = get_wikipedia_data()[1]
    url = fix_url_format(wikipedia_url)
    image_mimetype = "image/png"
    max_size = 1_000_000
    
    card = {
        "uri": url,
        "title": "",
        "description": "",
    }

    resp = requests.get(url, headers = USER_AGENT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("meta", property="og:title")
    description_tag = soup.find("meta", property="og:description")
    image_tag = soup.find("meta", property="og:image")
    
    if title_tag:
        card["title"] = title_tag["content"]
    
    if description_tag:
        card["description"] = description_tag["content"]

    if image_tag:
        img_url = image_tag["content"]
        if "://" not in img_url:
            img_url = url + img_url
        resp = requests.get(img_url,headers = USER_AGENT)
        resp.raise_for_status()

        blob_resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
            headers={
                "Content-Type": image_mimetype,
                "Authorization": "Bearer " + accessJWT,
            },
            data=resp.content,
        )
        if blob_resp.json()["blob"]["size"] < max_size:
            blob_resp.raise_for_status()
            card["thumb"] = blob_resp.json()["blob"]
        
        else:
            with open("feat_picture.jpg", 'w+b') as file:
                response = requests.get(image_tag["content"], stream=True, headers = USER_AGENT)
                file.write(response.content)
                image = Image.open(file)
                if image.mode in ("RGBA", "P"):  # P is paletted PNG
                    image = image.convert("RGB")
                width, height = image.size
                new_width = 2000
                ratio = width / height
                new_height = new_width / ratio
                resized_image = image.resize((new_width, round(new_height)))
                quality_counter = 100 
                resized_image.save("feat_picture_resized.jpg",optimize=True, quality = quality_counter)
                while os.path.getsize("feat_picture_resized.jpg") > max_size: 
                    quality_counter -= 1
                    resized_image.save("feat_picture_resized.jpg", optimize=True, quality = quality_counter)
                with open("feat_picture_resized.jpg", 'rb') as file:
                    img_bytes= file.read()
                    blob_resp = requests.post(
                        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
                        headers={
                            "Content-Type": image_mimetype,
                            "Authorization": "Bearer " + accessJWT,
                            },
                        data=img_bytes,
                        )
                card["thumb"] = blob_resp.json()["blob"]
                    
    return {
        "$type": "app.bsky.embed.external",
        "external": card,
        "aspectRatio:": {"width": 4510, "height":2927}
        }


def create_post(text: str):
    did, accessJWT = bsky_login_session(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    time = datetime.now(ZoneInfo("Europe/Zurich")).isoformat()
    facets = parse_facets(text)
    embed_url_card = fetch_embed_url_card()
    language = "en-US"
    
    post = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": time,
        "langs": [language],
        "facets": facets,
        "embed": embed_url_card
        }
    
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": "Bearer " + accessJWT},
        json={
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": post
        },
    )
    resp.raise_for_status()

def main():
    create_post(text_of_message())