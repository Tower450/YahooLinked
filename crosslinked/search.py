import logging
import requests
import threading
import re
from time import sleep
from random import choice
from bs4 import BeautifulSoup
from unidecode import unidecode
from urllib.parse import urlparse
from crosslinked.logger import Log
from datetime import datetime, timedelta
from urllib3 import disable_warnings, exceptions

disable_warnings(exceptions.InsecureRequestWarning)
logging.getLogger("urllib3").setLevel(logging.WARNING)
csv = logging.getLogger('cLinked_csv')


class Timer(threading.Thread):
    def __init__(self, timeout):
        threading.Thread.__init__(self)
        self.start_time = None
        self.running = None
        self.timeout = timeout

    def run(self):
        self.running = True
        self.start_time = datetime.now()
        logging.debug("Thread Timer: Started")

        while self.running:
            if (datetime.now() - self.start_time) > timedelta(seconds=self.timeout):
                self.stop()
            sleep(0.05)

    def stop(self):
        logging.debug("Thread Timer: Stopped")
        self.running = False


class CrossLinked:
    def __init__(self, search_engine, target, timeout, conn_timeout=3, proxies=[], jitter=0):
        self.results = []
        self.url = {
            'google': 'https://www.google.com/search?q=site%3Alinkedin.com%2Fin+{}&num=100&start={}',
            'bing':   'https://www.bing.com/search?q=site%3Alinkedin.com%2Fin+{}&first={}',
            'yahoo':  'https://search.yahoo.com/search?p=site%3Alinkedin.com%2Fin+{}&b={}'
        }
 

        self.runtime = datetime.now().strftime('%m-%d-%Y %H:%M:%S')
        self.search_engine = search_engine
        self.conn_timeout = conn_timeout
        self.timeout = timeout
        self.proxies = proxies
        self.target = target
        self.jitter = jitter

    def search(self):
        search_timer = Timer(self.timeout)
        search_timer.start()

        while search_timer.running:
            try:
                url = self.url[self.search_engine].format(self.target, len(self.results))
                resp = web_request(url, self.conn_timeout, self.proxies)
                # print(resp.text)
                http_code = get_statuscode(resp)

                if http_code != 200:
                    Log.info("{:<3} {} ({})".format(len(self.results), url, http_code))
                    Log.warn('None 200 response, exiting search ({})'.format(http_code))
                    break

                self.page_parser(resp)
                Log.info("{:<3} {} ({})".format(len(self.results), url, http_code))

                sleep(self.jitter)
            except KeyboardInterrupt:
                Log.warn("Key event detected, exiting search...")
                break

        search_timer.stop()
        return self.results

    def page_parser(self, resp):
        for link in extract_links(resp):
            try:
                self.results_handler(link)
            except Exception as e:
                Log.warn('Failed Parsing: {}- {}'.format(link.get('href'), e))


    def link_parser(self, url, link):
        u = {'url': url}
        if "john" in url:
            print(link)
    
        # Safely extract text from <span> or <h3> or entire <a>
        text = link.get_text(" ", strip=True)
        u['text'] = unidecode(text)
        if "john" in url:
            print("ALLO")
            print(u['text'])
        u['title'] = self.parse_linkedin_title(u['text'])
        if "john" in url:
            print(u['title'])
        u['name'] = self.parse_linkedin_name(u['text'])

        return u
    
    def parse_linkedin_title(self, text):
        """
        Extracts job title from text like: 'John Zhang - Tesla | LinkedIn'
        """
        match = re.search(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) - (.+?) \| LinkedIn', text)
        if match:
            title = match.group(2).strip()
            return unidecode(title)
        return 'N/A'

    def parse_linkedin_name(self, text):
        """
        Extracts name from text like: 'John Zhang - Tesla | LinkedIn'
        """
        match = re.search(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) -', text)
        if match:
            name = match.group(1).strip()
            return unidecode(name).lower()
        return False
    
    #def link_parser(self, url, link):
    #    if "john" in url:
    #        print(link)
    #    u = {'url': url}
    #    u['text'] = unidecode(link.text.split("|")[0].split("...")[0])  # Capture link text before trailing chars
    #    u['title'] = self.parse_linkedin_title(u['text'])               # Extract job title
    #    u['name'] = self.parse_linkedin_name(u['text'])                 # Extract whole name
    #    return u

    #def parse_linkedin_title(self, data):
    #    try:
    #        title = data.split("-")[1].split('https:')[0]
    #        return title.split("...")[0].split("|")[0].strip()
    #    except:
    #        return 'N/A'

    #def parse_linkedin_name(self, data):
    #    try:
    #        name = data.split("-")[0].strip()
    #        return unidecode(replace_special_characters(name)).lower()
    #    except:
    #        return False

    def results_handler(self, link):
        url = str(link.get('href')).lower()
        # print(url) # SHOW FOUND URL
        # if "john" in url:
        #    print(url)
        # print(link)

        #if "linkedin.com" in  extract_subdomain(url):
        #    return False
        # elif 'linkedin.com' not in url:
        #    return False
        
        data = self.link_parser(url, link)
        self.log_results(data) if data['name'] else False


    def log_results(self, d):
        # Prevent Duplicates & non-standard responses (i.e: "<span>linkedin.com</span></a>")
        if d in self.results:
            return
        elif 'linkedin.com' in d['name']:
            return

        self.results.append(d)
        # Search results are logged to names.csv but names.txt is not generated until end to prevent duplicates
        logging.debug('name: {:25} RawTxt: {}'.format(d['name'], d['text']))
        csv.info('"{}","{}","{}","{}","{}","{}",'.format(self.runtime, self.search_engine, d['name'], d['title'], d['url'], d['text']))


def get_statuscode(resp):
    try:
        return resp.status_code
    except:
        return 0


def get_proxy(proxies):
    tmp = choice(proxies) if proxies else False
    return {"http": tmp, "https": tmp} if tmp else {}


def get_agent():
    return choice([
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0'
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 12.5; rv:104.0) Gecko/20100101 Firefox/104.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15'
    ])


def web_request(url, timeout=3, proxies=[], **kwargs):
    try:
        s = requests.Session()
        r = requests.Request('GET', url, headers={'User-Agent': get_agent()}, cookies = {'CONSENT' : 'YES'}, **kwargs)
        p = r.prepare()
        return s.send(p, timeout=timeout, verify=False, proxies=get_proxy(proxies))
    except requests.exceptions.TooManyRedirects as e:
        Log.fail('Proxy Error: {}'.format(e))
    except:
        pass
    return False


def extract_links(resp):
    links = []
    soup = BeautifulSoup(resp.content, 'lxml')
    for link in soup.findAll('a'):
        links.append(link)
    return links


def extract_subdomain(url):
    if "john" in url:
        print(urlparse(url).path) # DEBUG URL A PARSER
    # return urlparse(url).netloc # ANCIEN NOT WORKING!
    return urlparse(url).path

def replace_special_characters(text):
    replacements = {
        'ä': 'ae', 'Ä': 'Ae',
        'ö': 'oe', 'Ö': 'Oe',
        'ü': 'ue', 'Ü': 'Ue',
        'ß': 'ss',
        'œ': 'oe', 'Œ': 'Oe',
        'æ': 'ae', 'Æ': 'Ae'
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text


                                                                                                                                                         
