#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import MySQLdb
import time
import numpy
import logging
import re
import sys  
import json
import ssl
import os

reload(sys)  
sys.setdefaultencoding('utf8')  

# state of tag_info
FINISHED = 1
UNFINISHED = 0
# tag page related
PAGE_ADD = 20
PAGE_END = 980
# max times to get same one url
MAX_TRY_TIMES = 20
# sleep time after disconnecting router
DISCON_SLEEP_TIME = 15
# some headers
HEADERSES=[{'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.89 Safari/537.36'},\
{'User-Agent':'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'},\
{'User-Agent':'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11'},\
{'User-Agent': 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)'}]
# set log format
logging.basicConfig(level=logging.INFO,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='doubanspider.log',
                filemode='w')
# send important info to stderr as well 
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def get_html(url, headers): 
    headers['Referer'] = url
    r = requests.get(url, headers = headers)
    if r.status_code != requests.codes.ok :
        logging.warning("requests error for url:%s, code:%d" % (url, r.status_code))
    if r.status_code == requests.codes.forbidden:
        logging.warning("requests is forbidden(403) for url:%s, need regain ip." % (url))
        r.raise_for_status()
    return r.content

# load tag info from db
def get_tags(conn):
    cur = conn.cursor()
    cur.execute("select `id`, `name`, `page`, `is_end` from `tag_info`")
    tag_list = []
    for row in cur.fetchall():
        # load unfinished tag only
        if row[3] == UNFINISHED:
            tag_list.append({'id':row[0], 'name':row[1].encode('utf-8'), 'page':row[2], 'is_end':row[3]})
    cur.close()
    return tag_list

def do_spider(conn, tag_list):
    for tag_info in tag_list:
        fetch_books(conn, tag_info)
    logging.info('all books in tags is fetched!')

def fetch_books(conn, tag_info):
    logging.info("start fetching books in tag:%s" % tag_info['name'])
    cur = conn.cursor()
    fetch_count = 0
    time.sleep(numpy.random.rand()*2)

    while tag_info['is_end'] == UNFINISHED:
        url = 'https://book.douban.com/tag/' + tag_info['name'] + '?start=' + str(tag_info['page']) + '&type=T'
        headers = HEADERSES[fetch_count % len(HEADERSES)]

        for times in xrange(1, MAX_TRY_TIMES):
            try:
                content = get_html(url, headers)
                soup = BeautifulSoup(content, 'lxml')
                ul = soup.body.find('ul', attrs = {'class':'subject-list'})
                li_list = ul.find_all('li')
                break
            except requests.exceptions.HTTPError, e:
                raise requests.exceptions.HTTPError, e
            except Exception, e:
                logging.warning("requests exception for tag:%s,page:%d,url:%s,exception:%s,trytimes:%d" % (tag_info['name'], tag_info['page'], url, e, times))
                headers = HEADERSES[(fetch_count + 1) % len(HEADERSES)]
                time.sleep(numpy.random.rand() * 3)

        # get all book info of this page
        book_info_list = []
        for li in li_list:
            # get book url
            time.sleep(numpy.random.rand())
            div = li.find('div', attrs = {'class':'info'})
            book_url = div.a['href']
            for times in xrange(1, MAX_TRY_TIMES):
                try:
                    book_content = get_html(book_url, headers)
                    soup = BeautifulSoup(book_content, 'lxml')
                    bkif = fetch_book_info(book_url, soup)
                    book_info_list.append(bkif)
                    break
                except requests.exceptions.HTTPError, e:
                    raise requests.exceptions.HTTPError, e
                except Exception, e:
                    logging.warning("requests exception for url:%s,exception:%s,try times:%d" % (book_url, e, times))
                    time.sleep(numpy.random.rand() * 2)

        # update tag_info and save book_infos to db
        # logging.info("book_info_list:%s" % book_info_list)
        logging.info("finish tag:%s, page:%d" %(tag_info['name'], tag_info['page']))
        # page is end
        if li_list == []:
            tag_info['is_end'] = FINISHED
            save_tag(cur, tag_info)
        else:
            save_tag_book(cur, tag_info, book_info_list)
        fetch_count += 1
    logging.info("finish fetching books in tag:%s" % tag_info['name'])  
    cur.close()

def save_tag(cur, tag_info):
    cur.execute("UPDATE `tag_info` SET `page` = %d, `is_end` = %s WHERE `id` = %d" %(tag_info['page'], tag_info['is_end'], tag_info['id']))
    conn.commit()

def save_tag_book(cur, tag_info, book_info_list):
    if tag_info['page'] >= PAGE_END:
        tag_info['is_end'] = FINISHED
    else:
        tag_info['page'] += PAGE_ADD
    books_sql = make_sql(book_info_list)
    cur.execute(books_sql)
    cur.execute("UPDATE `tag_info` SET `page` = %d, `is_end` = %s WHERE `id` = %d" %(tag_info['page'], tag_info['is_end'], tag_info['id']))
    conn.commit()

def make_sql(book_info_list):
    str_list = []
    for book_info in book_info_list:
        string = "(%s,'%s','%s','%s','%s','%s',%s,'%s',%s,%s)" %(book_info['id'], book_info['book_name'], book_info['author'], book_info['publisher'], book_info['translator'], book_info['publish_date'], book_info['page_num'], book_info['isbn'], book_info['score'], book_info['rating_num'])
        str_list.append(string)
    strings = ','.join(str_list)
    sql = "REPLACE INTO `book_info`(`id`, `book_name`, `author`, `publisher`, `translator`, `publish_date`, `page_num`, `isbn`, `score`, `rating_num`) VALUES %s" % strings
    # logging.info("sql:%s" % sql)
    return sql

# strip special characters
def strip_blank(string):
    new_string = string.replace("'","")
    new_string = "".join(new_string.split())
    return new_string

def fetch_book_info(book_url, soup):
    book_info = {'id':0, 'book_name':'NULL', 'author':'NULL', 'publisher':'NULL', 
        'translator':'NULL', 'publish_date':'NULL', 'page_num':0, 'isbn':'NULL',
        'score':0.0, 'rating_num':0}
    body = soup.body
    # get book_name
    wrapper = body.find('div', attrs = {'id':'wrapper'})
    book_name = wrapper.h1.span.string
    book_name = unicode(book_name).encode('utf-8')
    book_name = strip_blank(book_name)
    book_info['book_name'] = book_name
    #print "book_name:",book_name,type(book_name)

    # get other info
    info = body.find('div', attrs = {'id':'info'})
    text = str(info)
    # get book id
    id_pattern = re.compile(r"\d+")
    id_match = re.search(id_pattern, book_url)
    if id_match :
        book_info['id'] = int(id_match.group())
        #print "id:",int(id_match.group())
    # get author 
    au_pattern = re.compile(r"作者:?</span>.*?<a.*?>(.*?)</a>", re.S)
    au_match = re.search(au_pattern, text)
    if au_match:
        # strip \n and \s
        author = strip_blank(au_match.group(1))
        #print "author:",author, type(author)
        book_info['author'] = author
    # get publisher
    pu_pattern = re.compile(r"出版社:</span>(.*?)<br/>")
    pu_match = re.search(pu_pattern, text)
    if pu_match:
        publisher = strip_blank(pu_match.group(1))
        #print "publisher:",publisher, type(publisher)
        book_info['publisher'] = publisher
    # get translator
    tr_pattern = re.compile(r"译者:?</span>.*?<a.*?>(.*?)</a>", re.S)
    tr_match = re.search(tr_pattern, text)
    if tr_match:
        translator = strip_blank(tr_match.group(1))
        #print "translator:",translator, type(translator)
        book_info['translator'] = translator
    # get publish_date
    date_pattern = re.compile(r"出版年:</span>(.*?)<br/>")
    data_match = re.search(date_pattern, text)
    if data_match:
        publish_date = strip_blank(data_match.group(1))
        #print "publish_date:",publish_date, type(publish_date)
        book_info['publish_date'] = publish_date
    # get page_num
    num_pattern = re.compile(r"页数:?</span>.*?(\d+).*?<br/?>", re.S)
    num_match = re.search(num_pattern, text)
    if num_match:
        #print "page_num:",int(num_match.group(1))
        book_info['page_num'] = int(num_match.group(1))
    # get isbn
    isbn_pattern = re.compile(r"ISBN:</span>.*?(\d+)<br/>")
    isbn_match = re.search(isbn_pattern, text)
    if isbn_match:
        #print "isbn:",isbn_match.group(1), type(isbn_match.group(1))
        book_info['isbn'] = isbn_match.group(1)
    # get score
    score_ele = body.find('strong', attrs = {'class':'ll rating_num '})

    if score_ele != None:
        try:
            score = float(score_ele.string)
            #print score,type(score)
            book_info['score'] = score
        except ValueError:
            pass
    # get rating num
    rt_num_ele = body.find('a', attrs = {'class':'rating_people'})
    if rt_num_ele != None and rt_num_ele.span != None:
        rt_num = int(rt_num_ele.span.string)
        #print rt_num
        book_info['rating_num'] = rt_num    
    #print book_info
    return book_info

def disconnect_router():
    ssl._create_default_https_context = ssl._create_unverified_context
    data = {
        "method":"do",
        "login":{"password":"your_password_after_encrypt"}
    }
    headers = {
        'Host':'192.168.0.1',
        'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.89 Safari/537.36',
        'Accept':'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding':'gzip, deflate',
        'Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7,zh-TW;q=0.6',
        'Connection':'keep-alive',
        'Content-Length':'50',
        'Content-Type':'application/json; charset=UTF-8',
        'Origin':'http://192.168.0.1',
        'Referer':'http://192.168.0.1/',
        'X-Requested-With':'XMLHttpRequest'
    }
    url = "http://192.168.0.1/"
    html = requests.post(url,json=data,headers=headers,verify = False)
    stok = json.loads(html.text)["stok"]
    full_url = "http://192.168.0.1/stok="+ stok +"/ds"
    Disconnect = {"network":{"change_wan_status":{"proto":"pppoe","operate":"disconnect"}},"method":"do"}
    disconn_route = requests.post(url=full_url, json=Disconnect).json()
    logging.info("disconnecting router...sleep for %s s" % DISCON_SLEEP_TIME)
    time.sleep(DISCON_SLEEP_TIME)
    while 1:
        ping_code = os.system('ping www.baidu.com -c 2')
        if ping_code:
            logging.info("cannot connect to internet yet, sleep for %s s" % DISCON_SLEEP_TIME)
            time.sleep(DISCON_SLEEP_TIME)
        else:
            break


if __name__=='__main__':
    conn= MySQLdb.connect(host='localhost',port = 3306,user='root',passwd='123456',db ='test',charset='utf8')
    tag_list = get_tags(conn)
    while 1:
        try:
            do_spider(conn, tag_list)
            break
        except requests.exceptions.HTTPError, e:
            logging.info("HTTPError,e:%s,need regain ip" % e)
            disconnect_router()
            tag_list = filter(lambda tag: tag['is_end'] ==  UNFINISHED, tag_list)
    conn.close()
