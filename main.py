# Saul Femm
# Initial Commit - November 16th, 2017
# TODO Allow selection of multiple sections
# TODO Allow multiple keywords
# TODO Cache series

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

    @retry()
    def get_account(self):
        """
            Sign into Plex account.
        """
        username = input("Plex Username: ")
        password = getpass.getpass()

        print('Signing into Plex... ', end='', flush=True)
        try:
            account = MyPlexAccount(username, password)
            print('Done')
        except BadRequest:
            print('Invalid Username/Password.')

        return account
    
    def get_account_server(self, account):
        """
        Select server from Plex account.
        """
        servers = [ _ for _ in account.resources() if _.product == 'Plex Media Server' ]
        if not servers:
            print('No available servers.')
            sys.exit()

        return plexapi.utils.choose('Select server index', servers, "name").connect()

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

    def __init__(self, plex_obj):
        super().__init__()
        self.plex_obj = plex_obj
        self.imdb_id = None
        self.imdb_keywords = []

    def run(self):
        self.plex_guid = self.get_plex_guid()
        self.imdb_id = self.get_imdb_id()
        self.imdb_keywords = self.get_imdb_keywords()

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

    # TODO Hard-coded indices work but are dubious
    def get_imdb_id(self):
        # Episodes must be matched with the TheTVDB agent
        if not 'tvdb' in self.plex_guid:
            return None

        split_guid = self.plex_guid.split('/')
        series_id = int(split_guid[2])
        season = int(split_guid[3])
        episode = int(split_guid[4].split('?')[0])

        series = self.get_tvdb_series(series_id)

        try:
            episode = series[season][episode]
        # TheTVDB knows of no such season/episode
        except TVDBIndexError:
            return None

        imdb_id = str(episode.IMDB_ID)
        if imdb_id.startswith('tt'):
            imdb_id = imdb_id[2:]

        return imdb_id

    @retry((RemoteDisconnected, ResponseNotReady), delay=2)
    def get_tvdb_series(self, series_id):
        return self.tvdb.get_series(series_id, 'en')

class PlexMovie2IMDb(PlexObject2IMDb):
    # TODO Hard-coded indices work but are dubious
    def get_imdb_id(self):
        # Movies must be matched with the IMDb agent
        if not 'imdb' in self.plex_guid:
            return None
        
        return self.plex_guid[28:35]

class PlexHolidays():
    def __init__(self):
        # Necessary to disable imdbpy logger to hide timeouts, which are handled
        logging.getLogger('imdbpy').disabled = True
        logging.getLogger('imdbpy.parser.http.urlopener').disabled = True
        MAX_THREADS = 10
        
        plex = Plex()
        keyword = input('Keyword (i.e. Holiday name): ').lower()
        playlist_name = input('Playlist name: ')

        print('Scanning', plex.section.title, '...')
        if plex.section.type == 'movie':
            Plex2IMDb = PlexMovie2IMDb
        else:
            Plex2IMDb = PlexEpisode2IMDb

        threads = [ Plex2IMDb(medium) for medium in plex.media ]
        batches = [ threads[i:(i+MAX_THREADS)] for i in range(0, len(threads), MAX_THREADS) ]
        with tqdm(total=len(plex.media)) as pbar:
            for batch in batches:
                [ thread.start() for thread in batch ]
                [ thread.join() for thread in batch ]
                pbar.update(MAX_THREADS)

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

if __name__ == "__main__":
    ph = PlexHolidays()
