#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#     Copyright (C) 2012 Tristan Fischer (sphere@dersphere.de)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import json
import urllib2
from BeautifulSoup import BeautifulSoup
import re
import xbmcaddon

SCRAP_TOPIC_IN_ADVANCE = False
if (xbmcaddon.Addon(id='plugin.video.hdtrailers_net').getSetting( 'scrap_topic_in_advance') == 'true'):
        SCRAP_TOPIC_IN_ADVANCE=True

URL_PROTO = 'https:'
MAIN_URL = URL_PROTO + '//www.hd-trailers.net/'
NEXT_IMG = URL_PROTO + '//static.hd-trailers.net/images/mobile/next.png'
PREV_IMG = URL_PROTO + '//static.hd-trailers.net/images/mobile/prev.png'
USER_AGENT = 'Kodi Add-on HD-Trailers.net v1.2.4'

SOURCES = (
    'apple.com',
    'yahoo-redir',
    'yahoo.com',
    'youtube.com',
    'moviefone.com',
    'ign.com',
    'hd-trailers.net',
    'aol.com'
)


class NetworkError(Exception):
    pass


def get_latest(page=1):
    url = MAIN_URL + 'page/%d/' % int(page)
    return _get_movies(url)


def get_most_watched():
    url = MAIN_URL + 'most-watched/'
    return _get_movies(url)


def get_top_ten():
    url = MAIN_URL + 'top-movies/'
    return _get_movies(url)


def get_opening_this_week():
    url = MAIN_URL + 'opening-this-week/'
    return _get_movies(url)


def get_coming_soon():
    url = MAIN_URL + 'coming-soon/'
    return _get_movies(url)


def get_by_initial(initial='0'):
    url = MAIN_URL + 'poster-library/%s/' % initial
    return _get_movies(url)


def get_initials():
    return list('0ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def get_videos(movie_id, quick=False):
    url = MAIN_URL + 'movie/%s' % movie_id
    tree = __get_tree(url)

    trailers = []
    clips = []
    section = trailers

    span1= tree.find('table', {'class': 'mainTopTable'})
    span2= tree.find('span', {'class': 'topTableImage'}) # extract title and poster
    movie = {
        'title': span2.img['title'],
        'thumb': URL_PROTO + span2.img['src'],
        'poster':re.sub('\-resized', '', URL_PROTO + span2.img['src']), # show poster
        'plot':  span1.p.span.text, # show plot
    }

    if quick:
        return movie

    table = tree.find('table', {'class': 'bottomTable'})
    for tr in table.findAll('tr'):
        if tr.find('td', text='Trailers'):
            section = trailers
            continue
        elif tr.find('td', text='Clips'):
            section = clips
            continue
        elif tr.get('itemprop'):
            res_tds = tr.findAll('td', {'class': 'bottomTableResolution'})
            resolutions = {}
            for td in res_tds:
                if td.a:
                    resolutions[td.a.string] = td.a['href']
            if not resolutions:
                log('No resolutions found: %s' % movie_id)
                continue
            try:
                source = __detect_source(resolutions.values()[0])
            except NotImplementedError, video_url:
                log('Skipping: %s - %s' % (movie_id, video_url))
                continue
            log(str(tr.contents[3]))
            section.append({
                'title': tr.contents[3].span.string,
                'date': __format_date(tr.contents[1].string),
                'source': source,
                'plot': span1.p.span.text, # show plot
                'resolutions': resolutions
            })
    return movie, trailers, clips


def get_yahoo_url(vid, res):
    data_url = (
        "http://video.query.yahoo.com/v1/public/yql?"
        "q=SELECT+*+FROM+yahoo.media.video.streams+WHERE+id='%(video_id)s'+"
        "AND+format='mp4'+AND+protocol='http'+"
        "AND+plrs='sdwpWXbKKUIgNzVhXSce__'+AND+"
        "region='US'&env=prod&format=json"
    )
    data = __get_json(data_url % {'video_id': vid})
    media = data.get('query', {}).get('results', {}).get('mediaObj', [])
    for stream in media[0].get('streams'):
        if int(stream.get('height')) == int(res):
            return stream['host'] + stream['path']
    raise NotImplementedError


def _get_movies(url):
    tree = __get_tree(url)
    movies = [{
        'id': td.a['href'].split('/')[2],
        'title': td.a.img['alt'],
        'thumb': URL_PROTO + td.a.img['src'],
        'plot': get_videos( td.a['href'].split('/')[2], quick=True )['plot'] if SCRAP_TOPIC_IN_ADVANCE else '' # show plot
    } for td in tree.findAll('td', 'indexTableTrailerImage') if td.a.img]
    has_next_page = tree.find(
        'a',
        attrs={'class': 'startLink'},
        text=lambda text: 'Next' in text
    ) is not None
    return movies, has_next_page


def __detect_source(url):
    for source in SOURCES:
        if source in url:
            return source
    raise NotImplementedError(url)


def __format_date(date_str):
    y, m, d = date_str.split('-')
    return '%s.%s.%s' % (d, m, y)


def __get_tree(url):
    log('__get_tree opening url: %s' % url)
    headers = {'User-Agent': USER_AGENT}
    req = urllib2.Request(url, None, headers)
    try:
        html = urllib2.urlopen(req).read()
    except urllib2.HTTPError, error:
        raise NetworkError('HTTPError: %s' % error)
    log('__get_tree got %d bytes' % len(html))
    tree = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES)
    return tree


def __get_json(url):
    log('__get_json opening url: %s' % url)
    headers = {'User-Agent': USER_AGENT}
    req = urllib2.Request(url, None, headers)
    try:
        response = urllib2.urlopen(req).read()
    except urllib2.HTTPError, error:
        raise NetworkError('HTTPError: %s' % error)
    return json.loads(response)


def log(msg):
    print(u'%s scraper: %s' % (USER_AGENT, msg))
