from typing import Generator
from scraper import *
import requests
from bs4 import BeautifulSoup
from bs4 import SoupStrainer
from concurrent.futures import ProcessPoolExecutor
from cProfile import Profile
import cchardet
import json


def fetch_url(session: requests.Session, url: str, strainer: SoupStrainer) -> BeautifulSoup:
    # Send request for html content to webserver
    response = session.get(url)
    if response.status_code == 200:     # If the request was successful
        # Return html form page as bs4 soup
        return BeautifulSoup(response.text, 'lxml', parse_only=strainer)
    else:                               # Request was unsucessful, server responded with error or nothing
        raise ConnectionError('Could not connect to website')


class Crawler:
    FASS_BASE_LINK = str("https://www.fass.se/LIF")

    def retrive_medecine_links(self) -> Generator:
        ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ"
        PAGE_BASE_LINK = "https://www.fass.se/LIF/pharmaceuticallist?userType=2&page="

        only_list = SoupStrainer("li", attrs={"class": "tradeNameList"})
        session = requests.Session()

        for letter in ALPHABET:
            page_link = PAGE_BASE_LINK + letter
            soup = fetch_url(session, page_link, only_list)

            # """.tradeNameList .expandcontent > a"""
            links = soup.select(""".linkList > a""")
            names = soup.select(".linkList .innerlabel")

            for (link, name) in zip(links, names):
                base = self.FASS_BASE_LINK + link.get('href')[1:]
                yield {
                    "NPLID": base[-14:],
                    "NAME": name.get_text().strip(),
                    "bipacksedel": base + "&docType=7",
                    "produktresume": base + "&docType=6",
                    "fass_text": base + "&docType=3",
                    "bilder_och_delbarhet": base + "&docType=2000",
                    "miljöinformation": base + "&docType=78",
                    "skyddsinfo": base + "&docType=80"
                }
        session.close()

    def assert_content(self, result):
        original = {}
        with open(f"../data/products/{result[0]}.json", "r") as doc:
            original = json.load(doc)
        if original != result[1]:
            print(f"{result[0]} Failed")
            with open(f"{result[0]}.json", "w") as doc:
                json.dump(result[1], doc, indent=4, ensure_ascii=False)

        else:
            print(f"{result[0]} Successful")

    def scrape_pages(self, links: dict):
        result = {}

        only_content = SoupStrainer(
            "div", {"id": "readspeaker-article-content"})

        session = requests.Session()
        for page in links.keys():
            if page == "NPLID" or page == "NAME":
                continue
            soup = fetch_url(session, links[page], only_content)

            if soup is None:
                continue

            match page:
                case "bipacksedel":
                    result[page] = extract_product_leaflet(soup)
                case "bilder_och_delbarhet":
                    result[page] = extract_delbarhet(soup)
                case _:
                    result[page] = extract_medical_text(soup)

        result['product_name'] = {'product_name': links['NAME']}

        session.close()
        return (links['NPLID'], result)

    def crawl(self):
        with ProcessPoolExecutor() as pool:
            for result in pool.map(self.scrape_pages, self.retrive_medecine_links(), chunksize=4):
                self.assert_content(result)


if __name__ == "__main__":
    cr = Crawler()
    cr.crawl()

