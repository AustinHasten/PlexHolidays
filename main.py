# Saul Femm
# Initial Commit - November 16th, 2017

import sys
import getpass
import logging
import threading
import plexapi.utils
from imdb import IMDb, IMDbDataAccessError
from plexapi.myplex import MyPlexAccount
from plexapi.playlist import Playlist
from plexapi.exceptions import BadRequest

class Plex():
    def __init__(self):
        self.account = self.get_account()
        self.server = self.get_account_server(self.account)
        self.section = self.get_server_section(self.server)
        self.media = self.get_flat_media()

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

    def get_flat_media(self):
        """
            Flatten this object's section's media list.
        """
        # Movie sections are already flat
        if self.section.type == 'movie':
            return self.section.all()
        # TV sections are not
        else:
            flattened = []
            for show in self.section.all():
                for episode in show.episodes():
                    flattened.append(episode)
            return flattened

    def create_playlist(self, name, media):
        """
            Create or update playlist with list of media.
        """
        # TODO Handle this
        if not media:
            return
        playlist = next((p for p in self.server.playlists() if p.title == name), None)
        if playlist:
                playlist.addItems(media)
        else:
            Playlist.create(self.server, name, media)

class Plex2IMDb(threading.Thread):
    # Class variables
    imdb = IMDb()

    # TODO Find out how to get the section_type from the plex_obj
    def __init__(self, plex_obj, section_type):
        super().__init__()
        self.setDaemon(True)
        self.plex_obj = plex_obj
        self.section_type = section_type
        self.imdb_obj = None
        self.keywords = []

    def run(self):
        self.imdb_obj = self.plex2imdb(self.plex_obj, self.section_type)
        self.keywords = self.get_keywords(self.imdb_obj)

    def plex2imdb(self, plex_obj, section_type):
        """
            Get the IMDbPy object for a given Plex object.
        """
        # Set appropriate search method and acceptable results based on section type
        if section_type == 'movie':
            kinds = {'movie', 'short', 'tv movie', 'tv short'}
            search_function = self.imdb.search_movie
        else:
            kinds = {'episode'}
            search_function = self.imdb.search_episode

        # Perform IMDb search for the Plex object
        while True:
            try:
                results = [ _ for _ in search_function(plex_obj.title) if _['kind'] in kinds ]
                break
            except IMDbDataAccessError:
                pass

        # No IMDb results whatsoever
        if not results:
            return None
        # Plex has no year listed, return first search result
        elif not plex_obj.year:
            return results[0]

        closest_result = next((_ for _ in results if _.get('year')))
        closest_year = (plex_obj.year - closest_result['year'])
        for result in results:
            # This result has no year listed, ignore it.
            if not result.get('year'):
                continue

            # Exact match found
            if result['year'] == plex_obj.year:
                return result
            # Track match with closest year in case exact match is not found
            elif (plex_obj.year - result['year']) < closest_year:
                closest_result = result
                closest_year = (plex_obj.year - result['year'])
        # No exact match found, use result with closest year
        else:
            return closest_result

    def get_keywords(self, imdb_obj):
        """
            Get the plot keywords for a given IMDbPy object.
        """
        if not imdb_obj:
            return []

        while True:
            try:
                data = self.imdb.get_movie_keywords(imdb_obj.movieID)['data']
                break
            except IMDbDataAccessError:
                pass
                
        if not 'keywords' in data:
            return []
        return data['keywords']

if __name__ == "__main__":
    # Necessary to disable imdbpy logger to hide timeouts, which are handled
    logging.getLogger('imdbpy').disabled = True

    plex = Plex()
    keyword = input('Keyword (i.e. Holiday name): ').lower()
    playlist_name = input('Playlist name: ')

    print('Scanning', plex.section.title, '...')
    thread_list = []
    for plex_obj in plex.media:
        t = Plex2IMDb(plex_obj, plex.section.type)
        thread_list.append(t)
    for i in range(0, len(thread_list), 10):
        for t in thread_list[i:(i+10)]:
            t.start()
        for t in thread_list[i:(i+10)]:
            t.join()

    keyword_matches = []
    for thread in thread_list:
        if keyword in thread.keywords or \
           keyword in thread.plex_obj.summary.lower():
            keyword_matches.append(thread.plex_obj)

    if keyword_matches:
        print('Items matching keyword:')
        for match in keyword_matches:
            print('\t', match.title)
        plex.create_playlist(playlist_name, keyword_matches)
        print('Playlist created.')
    else:
        print('No matching items, playlist will not be created/updated.')

    print('Happy Holidays!')
