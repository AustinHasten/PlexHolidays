# Austin Hasten
# Initial Commit - November 16th, 2017
import re, sys, logging, itertools
import plexapi.utils
from tqdm import tqdm
from retry import retry
from pytvdbapi import api
from multiprocessing.pool import ThreadPool
from imdb import IMDb, IMDbDataAccessError
from pytvdbapi.error import TVDBIndexError
from requests.exceptions import ConnectTimeout
from plexapi.exceptions import BadRequest, NotFound
from http.client import RemoteDisconnected, ResponseNotReady

class Plex():
    def __init__(self):
        self.account = self.get_account()
        self.server = self.get_account_server(self.account)
        self.section = self.get_server_section(self.server)
        self.media = self.get_flat_media(self.section)

    @retry(BadRequest)
    def get_account(self):
        return plexapi.utils.getMyPlexAccount()
    
    def get_account_server(self, account):
        servers = [ _ for _ in account.resources() if _.product == 'Plex Media Server' ]
        if not servers:
            print('No available servers.')
            sys.exit()
        return plexapi.utils.choose('Select server index', servers, 'name').connect()

    def get_server_section(self, server):
        sections = [ _ for _ in server.library.sections() if _.type in {'movie', 'show'} ]
        if not sections:
            print('No available sections.')
            sys.exit()
        return plexapi.utils.choose('Select section index', sections, 'title')

    def get_flat_media(self, section):
        if section.type == 'movie':
            return self.section.all()
        nested_episodes = [ show.episodes() for show in self.section.all() ]
        return list(itertools.chain.from_iterable(nested_episodes))

    def create_playlist(self, name, media):
        try:
            self.server.playlist(name).addItems(media)
        except plexapi.exceptions.NotFound:
            self.server.createPlaylist(name, media)

class PlexHolidays():
    def __init__(self):
        # Necessary to disable imdbpy logger to hide timeouts, which are handled
        logging.getLogger('imdbpy').disabled = True
        logging.getLogger('imdbpy.parser.http.urlopener').disabled = True
        self.imdbpy = IMDb()
        self.tvdb = api.TVDB('B43FF87DE395DF56')
        self.plex = Plex()
        self.keyword = input('Keyword (i.e. Holiday name): ').lower()
        self.pbar = tqdm(self.plex.media, desc=f'{self.plex.section.title}')
        self.results = ThreadPool(10).map(self.find_matches, self.plex.media)
        self.matches = [ medium for match, medium in self.results if match ]
        if not self.matches:
            print('No matching items.')
        else:
            print(len(self.matches), 'items matching', '\"' + self.keyword + '\":')
            for match in self.matches:
                print('\t', match.title, '(' + str(match.year) + ')')
            self.plex.create_playlist(input('Playlist name: '), self.matches)
            print('Playlist created/updated.')

    def find_matches(self, medium):
        try:
            if self.keyword in medium.title.lower() or self.keyword in medium.summary.lower():
                return (True, medium)
            plex_guid = self.get_plex_guid(medium)
            imdb_id = self.get_imdb_id(plex_guid)
            imdb_keywords = self.get_imdb_keywords(imdb_id)
            return ((self.keyword in imdb_keywords), medium)
        finally:
            self.pbar.update()

    @retry(ConnectTimeout, delay=1)
    def get_plex_guid(self, medium):
        return medium.guid

    def get_imdb_id(self, plex_guid):
        if 'imdb' in plex_guid:
            return re.search(r'tt(\d*)\?', plex_guid).group()
        elif 'tvdb' in plex_guid:
            return self.get_episode_id(plex_guid)
        return None

    def get_episode_id(self, plex_guid):
        regex = r'\/\/(\d*)\/(\d*)\/(\d*)'
        series_id, season, episode = map(int, re.search(regex, plex_guid).groups())
        try:
            episode = self.get_tvdb_series(series_id)[season][episode]
        except TVDBIndexError:
            return None
        imdb_id = str(episode.IMDB_ID)
        return imdb_id[2:] if imdb_id.startswith('tt') else imdb_id

    @retry((RemoteDisconnected, ResponseNotReady, AttributeError, BrokenPipeError), delay=1)
    def get_tvdb_series(self, series_id):
        return self.tvdb.get_series(series_id, 'en')

    @retry(IMDbDataAccessError, delay=1)
    def get_imdb_keywords(self, imdb_id):
        if not imdb_id:
            return []
        data = self.imdbpy.get_movie_keywords(imdb_id)['data']
        return data.get('keywords', [])

if __name__ == "__main__":
    ph = PlexHolidays()
