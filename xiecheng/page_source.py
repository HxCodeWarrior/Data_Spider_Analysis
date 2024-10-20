from typing import final

import requests
from bs4 import BeautifulSoup

url = "https://you.ctrip.com/sight/qinghai100032.html"
header = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'}

source = requests.get(url, headers=header)
soup = BeautifulSoup(source.text,'html.parser')

with open("/xiecheng/analyse/tourists_list.html", 'w', encoding='utf-8') as f:
    f.write(soup.prettify())
