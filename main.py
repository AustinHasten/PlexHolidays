# Saul Femm
# Initial Commit - November 16th, 2017
# TODO Allow selection of multiple sections
# TODO Allow multiple keywords
# TODO Cache series

import re
import sys
import time
import getpass
import logging
import threading
import plexapi.utils
from retry import retry
from tqdm import tqdm
from pytvdbapi import api
from pytvdbapi.error import TVDBIndexError
from plexapi.myplex import MyPlexAccount
from plexapi.exceptions import BadRequest
from imdb import IMDb, IMDbDataAccessError
from http.client import RemoteDisconnected, ResponseNotReady

class Plex():
    def __init__(self):
        self.account = self.get_account()
        self.server = self.get_account_server(self.account)
        self.section = self.get_server_section(self.server)
        self.media = self.get_flat_media(self.section)

    @retry(BadRequest)
    def get_account(self):
        """
            Sign into Plex account.
        """
        username = input("Plex Username: ")
        password = getpass.getpass()

        return MyPlexAccount(username, password)
    
    def get_account_server(self, account):
        """
        Select server from Plex account.
        """
        servers = [ _ for _ in account.resources() if _.product == 'Plex Media Server' ]
        if not servers:
            print('No available servers.')
            sys.exit()

        return plexapi.utils.choose('Select server index', servers, 'name').connect()

    def get_server_section(self, server):
        """
            Select section from Plex server.
        """
        sections = [ _ for _ in server.library.sections() if _.type in {'movie', 'show'} ]
        if not sections:
            print('No available sections.')
            sys.exit()

        return plexapi.utils.choose('Select section index', sections, 'title')

    def get_flat_media(self, section):
        # Movie sections are already flat
        if section.type == 'movie':
            return self.section.all()
        else:
            episodes = []
            for show in self.section.all():
                episodes += show.episodes()
            return episodes

    def create_playlist(self, name, media):
        """
            Create or update playlist with list of media.
        """
        playlist = next((p for p in self.server.playlists() if p.title == name), None)
        if playlist:
            playlist.addItems(media)
        else:
            self.server.createPlaylist(name, media)

class PlexObject2IMDb(threading.Thread):
    imdbpy = IMDb()
    thread_limiter = threading.BoundedSemaphore(10)

    def __init__(self, plex_obj):
        super().__init__()
        self.plex_obj = plex_obj
        self.imdb_id = None
        self.imdb_keywords = []

    def run(self):
        self.thread_limiter.acquire()
        try:
            self.plex_guid = self.get_plex_guid()
            self.imdb_id = self.get_imdb_id()
            self.imdb_keywords = self.get_imdb_keywords()
        finally:
            self.thread_limiter.release()

#    @retry(ConnectTimeout, delay=2)
    def get_plex_guid(self):
        return self.plex_obj.guid

    def get_imdb_id(self):
        raise NotImplementedError('This is to be overridden')

    @retry(IMDbDataAccessError, delay=2)
    def get_imdb_keywords(self):
        if not self.imdb_id:
            return []

        data = self.imdbpy.get_movie_keywords(self.imdb_id)['data']
        return data.get('keywords', [])

class PlexEpisode2IMDb(PlexObject2IMDb):
    tvdb = api.TVDB('B43FF87DE395DF56')

    def get_imdb_id(self):
        if not 'tvdb' in self.plex_guid:
            return None

        regex = r'\/\/(\d*)\/(\d*)\/(\d*)'
        series_id, season, episode = map(int, re.search(regex, self.plex_guid).groups())
        series = self.get_tvdb_series(series_id)

        try:
            episode = series[season][episode]
        except TVDBIndexError:
            return None

        imdb_id = str(episode.IMDB_ID)
        if imdb_id.startswith('tt'):
            return imdb_id[2:]
        return imdb_id

    @retry((RemoteDisconnected, ResponseNotReady, AttributeError), delay=2)
    def get_tvdb_series(self, series_id):
        return self.tvdb.get_series(series_id, 'en')

class PlexMovie2IMDb(PlexObject2IMDb):
    def get_imdb_id(self):
        if not 'imdb' in self.plex_guid:
            return None

        return re.search(r'tt(\d*)\?', self.plex_guid).group()

if __name__ == "__main__":
    # Necessary to disable imdbpy logger to hide timeouts, which are handled
    logging.getLogger('imdbpy').disabled = True
    logging.getLogger('imdbpy.parser.http.urlopener').disabled = True
    THREADS = 100
    
    plex = Plex()
    keyword = input('Keyword (i.e. Holiday name): ').lower()
    playlist_name = input('Playlist name: ')

    print('Scanning', plex.section.title, '...')
    if plex.section.type == 'movie':
        Plex2IMDb = PlexMovie2IMDb
    else:
        Plex2IMDb = PlexEpisode2IMDb

    threads = [ Plex2IMDb(medium) for medium in plex.media ]
    with tqdm(total=len(plex.media)) as pbar:
        for i in range(0, len(plex.media)+1, THREADS):
            batch = threads[i:(i+THREADS)]
            [ thread.start() for thread in batch ]
            for thread in batch:
                thread.join()
                pbar.update(1)

    keyword_matches = []
    for thread in threads:
        if keyword in thread.imdb_keywords or \
           keyword in thread.plex_obj.title.lower() or \
           keyword in thread.plex_obj.summary.lower():
            keyword_matches.append(thread.plex_obj)

    if keyword_matches:
        print(len(keyword_matches), 'items matching', '\"' + keyword + '\":')
        for match in keyword_matches:
            print('\t', match.title + ' (' + str(match.year) + ')')
        plex.create_playlist(playlist_name, keyword_matches)
        print('Playlist created.')
    else:
        print('No matching items, playlist will not be created/updated.')

    print('Happy Holidays!')
