import hashlib
from fastapi import FastAPI, HTTPException
from starlette.responses import RedirectResponse
from deta import Deta
from fastapi.middleware.cors import CORSMiddleware
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from collections import OrderedDict

class SECScraper:
    def __init__(self, user_agent):
        self.user_agent = user_agent

    def get_root(self):
        r = requests.get('https://www.sec.gov/cgi-bin/srch-edgar?text=items%3D1.05&output=atom',
                         headers={'User-Agent': self.user_agent})
        return ET.fromstring(r.text)

    def get_links(self, entry):
        unique_links = OrderedDict()
        for link in entry.iter('{http://www.w3.org/2005/Atom}link'):
            url = "https://www.sec.gov" + link.attrib['href']
            r = requests.get(url, headers={'User-Agent': self.user_agent})
            soup = BeautifulSoup(r.text, 'html.parser')
            table = soup.find('table', {'class': 'tableFile'})

            if table:
                trs = table.find_all('tr')
                for tr in trs:
                    tds = tr.find_all('td')
                    for td in tds:
                        if "8-K" in td.text:
                            links = tr.find_all('a')
                            link = links[0].get('href')
                            link = link.replace('/ix?doc=', '')
                            link = "https://www.sec.gov" + link
                            unique_links[link] = None
        return unique_links

    def get_title(self, entry):
        for title in entry.iter('{http://www.w3.org/2005/Atom}title'):
            title = title.text
            title = title.replace('8-K/A - ', '')
            title = title.replace('8-K - ', '')

        return title.title()

    def get_date(self, entry):
        for date in entry.iter('{http://www.w3.org/2005/Atom}updated'):
            date = date.text
        return date

    def extract_description(self, url):
        start = "Material Cybersecurity Incidents"
        ends = ["Forward-Looking Statements",  "Forward-looking statements.","Item\\"]
        response = requests.get(url, headers={'User-Agent': self.user_agent})

        if response.status_code != 200:
            return "Failed to retrieve the webpage."

        soup = BeautifulSoup(response.content, 'html.parser')

        paragraphs = soup.find_all('p')
        if not paragraphs:
            paragraphs = soup.find_all('span')

        text = ' '.join(p.get_text() for p in paragraphs)

        for end in ends:
            if start in text and end in text:
                description = text.split(start)[1].split(end)[0]
                if description:
                    return description
                else:
                    description = "No description found."
                    return description
        description = "No description found."
        return description

    def find_breach(self):
        root = self.get_root()
        for entry in root.iter('{http://www.w3.org/2005/Atom}entry'):
            unique_links = self.get_links(entry)
            for link in unique_links:
                extracted_link = link
                description = self.extract_description(link)
            title = self.get_title(entry)
            date = self.get_date(entry)
            db = deta.Base("SEC")
            db.put({"title": title, "date": date, "link": extracted_link, "description": description},key=extracted_link)

        return True

def hash_word(word):
    return hashlib.sha256(word.encode()).hexdigest()


r = requests.get("https://storage.duplexes.lol/hashed.txt")


def check_mc(word):
    hashed_word = hash_word(word.lower())
    lines = r.text.split("\n")
    for line in lines:
        if hashed_word == line.strip():
            return True
    return False

deta = Deta()
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_agent = 'Hobby Project - Elliott hey@duplexes.lol'

@app.exception_handler(requests.exceptions.RequestException)
async def http_exception_handler(request, exc):
    return {"error": "An error occurred while making a request to an external service."}

@app.get("/")
async def root():
    return RedirectResponse(url='https://duplexes.lol')

@app.get("/api/v1/reports")
async def sites():
    db = deta.Base("sites")
    sites = db.fetch()
    return sites


@app.post("/api/v1/mc")
async def checkmc(username: str):
    return {"mc": check_mc(username)}


@app.get("/api/v1/sec/check")
async def sites():
    scraper = SECScraper(user_agent)
    scraper.find_breach()
    return {"success": True}

@app.get("/api/v1/sec")
async def sites():
    db = deta.Base("SEC")
    fetch_response = db.fetch()
    fetch_response_list = list(fetch_response)
    if fetch_response_list:
        formatted_response = {item['title']: {'date': item['date'], 'description': item['description'], 'link': item['link']} for item in fetch_response_list[0]}
        return formatted_response
    else:
        return {"message": "No data found"}