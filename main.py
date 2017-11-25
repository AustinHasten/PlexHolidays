# Saul Femm
# Initial Commit - November 16th, 2017
# TODO Allow selection of multiple sections
# TODO Allow multiple keywords

import sys
import time
import getpass
import logging
import threading
import plexapi.utils
from tqdm import tqdm
from imdbpie import Imdb
from requests.exceptions import HTTPError
from plexapi.myplex import MyPlexAccount
from plexapi.exceptions import BadRequest
from imdb import IMDb, IMDbDataAccessError

class Plex():
    def __init__(self):
        self.account = self.get_account()
        self.server = self.get_account_server(self.account)
        self.section = self.get_server_section(self.server)
        self.media = self.section.all()

    def get_account(self):
        """
            Sign into Plex account.
        """
        while True:
            username = input("Plex Username: ")
            password = getpass.getpass()

            print('Signing into Plex... ', end='', flush=True)
            try:
                account = MyPlexAccount(username, password)
                print('Done')
                break
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
    imdbpie = Imdb()

    def __init__(self, plex_obj):
        super().__init__()
        self.plex_obj = plex_obj
        self.imdb_id = None
        self.imdb_keywords = []

    def run(self):
        self.imdb_id = self.get_imdb_id()
        self.imdb_keywords = self.get_imdb_keywords()

    def get_imdb_id(self):
        raise NotImplementedError('This is to be overridden')

    def get_imdb_keywords(self):
        if not self.imdb_id:
            return []

        # Remove 'tt' from beginning of imdb_id for imdbpy
        if len(self.imdb_id) == 9:
            self.imdb_id = self.imdb_id[2:]

        while True:
            try:
                data = self.imdbpy.get_movie_keywords(self.imdb_id)['data']
                return data.get('keywords', [])
            except IMDbDataAccessError:
                time.sleep(2)

class PlexEpisode2IMDb(PlexObject2IMDb):
    cached_episodes = []

    @classmethod
    def cache_show(self, show):
        """
            Cache episodes of show so we don't have to fetch them repeatedly.
        """
        results = [ _ for _ in self.imdbpie.search_for_title(show.title) if _.get('year') ]

        # No search results for this show at all.
        if not results:
            return

        if show.year:
            best_match = min(results, key=lambda e: abs(int(e['year']) - show.year))
        else:
            best_match = results[0]

        self.cached_episodes = self.imdbpie.get_episodes(best_match['imdb_id'])

    def get_imdb_id(self):
        # The case when there were no IMDb results for this episode's show
        if not self.cached_episodes:
            return None

        # TODO Handle specials rather than ignoring them
        if int(self.plex_obj.parentIndex) == 0 or self.plex_obj.index == 0:
            return None

        # TODO Calculate episode's offset instead of comparing with every episode
        for episode in self.cached_episodes:
            if int(self.plex_obj.parentIndex) == episode.season and \
                self.plex_obj.index == episode.episode:
                return episode.imdb_id

        # IMDb knows of no such episode. It could be that the user has an erroneous episode
        # in their library, or it could be that IMDb and TheTVDB have different season/episode order
        return None

class PlexMovie2IMDb(PlexObject2IMDb):
    def get_imdb_id(self):
        results = [ _ for _ in self.imdbpie.search_for_title(self.plex_obj.title) if _.get('year') ]

        # The case when there were no IMDb results for this movie
        if not results:
            return None

        if not self.plex_obj.year:
            return results[0]['imdb_id']

        best_match = min(results, key=lambda m: abs(int(m['year']) - self.plex_obj.year))
        return best_match['imdb_id']

class PlexHolidays():
    def __init__(self):
        # Necessary to disable imdbpy logger to hide timeouts, which are handled
        logging.getLogger('imdbpy').disabled = True
        
        self.plex = Plex()
        self.keyword = input('Keyword (i.e. Holiday name): ').lower()
        self.keyword_matches = []
        playlist_name = input('Playlist name: ')

        print('Scanning', self.plex.section.title, '...')
        if self.plex.section.type == 'movie':
            self.match_movies()
        else:
            self.match_episodes()

        if self.keyword_matches:
            print('Items matching keyword:')
            for match in self.keyword_matches:
                print('\t', match.title + ' (' + str(match.year) + ')')
            self.plex.create_playlist(playlist_name, self.keyword_matches)
            print('Playlist created.')
        else:
            print('No matching items, playlist will not be created/updated.')

        print('Happy Holidays!')

    def match_movies(self):
        thread_list = [ PlexMovie2IMDb(movie) for movie in self.plex.media ]
        [ thread.start() for thread in thread_list ]
        [ thread.join() for thread in tqdm(thread_list) ]

        for thread in thread_list:
            if self.keyword in thread.imdb_keywords or \
               self.keyword in thread.plex_obj.title.lower() or \
               self.keyword in thread.plex_obj.summary.lower():
                self.keyword_matches.append(thread.plex_obj)

    def match_episodes(self):
        for show in tqdm(self.plex.media):
            PlexEpisode2IMDb.cache_show(show)

            thread_list = [ PlexEpisode2IMDb(episode) for episode in show.episodes() ]
            [ thread.start() for thread in thread_list ]
            [ thread.join() for thread in thread_list ]

            for thread in thread_list:
                if self.keyword in thread.imdb_keywords or \
                   self.keyword in thread.plex_obj.title.lower() or \
                   self.keyword in thread.plex_obj.summary.lower():
                    self.keyword_matches.append(thread.plex_obj)

            del thread_list

if __name__ == "__main__":
    ph = PlexHolidays()
