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
# Modified by idleloop (2017, 2019):
# //github.com/idleloop-github/plugin.video.hdtrailers_net
#

import json
import urllib2
from BeautifulSoup import BeautifulSoup
# //kodi.wiki/index.php?title=Add-on:Parsedom_for_xbmc_plugins
from CommonFunctions import parseDOM
import re
import xbmcaddon
import xbmcgui

SCRAP_TOPIC_IN_ADVANCE = False
if (xbmcaddon.Addon(id='plugin.video.hdtrailers_net').getSetting( 'scrap_topic_in_advance') == 'true'):
        SCRAP_TOPIC_IN_ADVANCE=True

URL_PROTO = 'https:'
MAIN_URL = URL_PROTO + '//www.hd-trailers.net/'
NEXT_IMG = URL_PROTO + '//static.hd-trailers.net/images/mobile/next.png'
PREV_IMG = URL_PROTO + '//static.hd-trailers.net/images/mobile/prev.png'
USER_AGENT = 'Kodi Add-on HD-Trailers.net v1.2.5'
number_of_plots_retrieved = 0

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
    html = __get_html(url)

    trailers = []
    clips = []
    section = trailers

    span1 = parseDOM( html, 'table', attrs={'class': 'mainTopTable'} )
    plot  = parseDOM( parseDOM( span1, 'p' ), 'span')[0]
    span2 = parseDOM( html, 'span', {'class': 'topTableImage'} ) # extract title and poster
    movie = {
        'title': parseDOM( span2, 'img', ret='title' )[0],
        'thumb': URL_PROTO + parseDOM( span2, 'img', ret='src' )[0],
        'poster':re.sub('\-resized', '', URL_PROTO + parseDOM( span2, 'img', ret='src' )[0]), # show poster
        'plot':  plot, # show plot
    }

    if SCRAP_TOPIC_IN_ADVANCE and quick:
        global number_of_plots_retrieved
        number_of_plots_retrieved += 1
        dialog = xbmcgui.Dialog()
        dialog.notification( 'hdtrailers_net',
            'retrieving plots (' + str(number_of_plots_retrieved)  + ') ...',
            xbmcgui.NOTIFICATION_INFO, int(1500) )
    if quick:
        return movie

    table = parseDOM( html, 'table', attrs={'class': 'bottomTable'} )[0]
    # unfortunately parseDOM is not able to return html entities both with AND without attributes :-(
    table = BeautifulSoup( table, convertEntities=BeautifulSoup.HTML_ENTITIES )
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
                'plot': plot, # show plot
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
    html = __get_html(url)
    global number_of_plots_retrieved
    number_of_plots_retrieved = 0
    movies = [{
        'id': parseDOM( td, 'a', ret='href' )[0].split('/')[2],
        'title': parseDOM( parseDOM( td, 'a' ), 'img', ret='alt' )[0],
        'thumb': URL_PROTO + parseDOM( parseDOM( td, 'a' ), 'img', ret='src' )[0],
        'plot': get_videos( parseDOM( td, 'a', ret='href' )[0].split('/')[2], quick=True )['plot'] if SCRAP_TOPIC_IN_ADVANCE else '' # show plot
    } for td in parseDOM( html, 'td', attrs={ 'class': 'indexTableTrailerImage' } ) if parseDOM( parseDOM( td, 'a' ), 'img' )]
    has_next_page = map(
        lambda text: 'Next' in text,
        parseDOM( html, 'a', attrs={'class': 'startLink'} )
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


def __get_html(url):
    log('__get_html opening url: %s' % url)
    headers = {'User-Agent': USER_AGENT}
    req = urllib2.Request(url, None, headers)
    try:
        html = urllib2.urlopen(req).read()
    except urllib2.HTTPError, error:
        raise NetworkError('HTTPError: %s' % error)
    log('__get_html got %d bytes' % len(html))
    return html


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
