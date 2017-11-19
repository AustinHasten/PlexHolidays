# Saul Femm
# Initial Commit - November 16th, 2017

import sys
import getpass
import plexapi.utils
from tqdm import tqdm
from imdb import IMDb
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
            except BadRequest:
                print('Invalid Username/Password.')
                continue
            print('Done')
            break
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
            Flatten this object's section's media list."
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
        for playlist in self.server.playlists():
            if name == playlist.title:
                playlist.addItems(media)
                break
        else:
            Playlist.create(self.server, name, media)

class PlexHolidays():
    def __init__(self):
        self.plex = Plex()
        self.imdb = IMDb()
        keyword = input('Keyword (i.e. Holiday name): ')
        keyword_matches = []

        print('Scanning', self.plex.section.title, '...')
        for plex_medium in tqdm(self.plex.media):
            imdb_medium = self.plex2imdb(plex_medium)

            if not imdb_medium:
                continue

            keywords = self.get_keywords(imdb_medium)
            if keyword in keywords:
                keyword_matches.append(plex_medium)

        print('Titles matching\"', keyword, '\" :')
        for match in keyword_matches:
            print('\t', match.title)
        self.plex.create_playlist(input('Playlist name: '), keyword_matches)

        print('Happy Holidays!')

    def plex2imdb(self, medium):
        """
            Get the IMDbPy object for a given Plex object.
        """
        # Set appropriate search method and acceptable results based on section type
        if self.plex.section.type == 'movie':
            kinds = {'movie', 'short', 'tv movie', 'tv short'}
            search_function = self.imdb.search_movie
        else:
            kinds = {'episode'}
            search_function = self.imdb.search_episode

        # Perform IMDb search for the Plex object
        while True:
            try:
                results = [ _ for _ in search_function(medium.title) if _['kind'] in kinds ]
                break
            # Time out, try again.
            except OSError:
                print('Timed out while downloading', medium.title)
                continue

        # No IMDb results whatsoever
        if not results:
            return None
        # Plex has no year listed, return first search result
        elif not medium.year:
            return results[0]

        closest_result, closest_year = None, 9999
        for result in results:
            # This result has no year listed, ignore it.
            if not result.get('year'):
                continue

            # Exact match found
            if result['year'] == medium.year:
                return result
            # Track match with closest year in case exact match is not found
            elif (medium.year - result['year']) < closest_year:
                closest_result = result
        # No exact match found, use result with closest year
        else:
            return closest_result

    def get_keywords(self, imdb_obj):
        """
            Get the plot keywords for a given IMDbPy object.
        """
        if not imdb_obj:
            return []

        data = self.imdb.get_movie_keywords(imdb_obj.movieID)['data']
        if not 'keywords' in data:
            return []
        return data['keywords']

if __name__ == "__main__":
    PH = PlexHolidays()
