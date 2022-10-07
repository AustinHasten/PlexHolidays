# Austin Hasten
# Initial Commit - November 16th, 2017
import sys, logging
import plexapi.utils
from tqdm import tqdm
from retry import retry
from multiprocessing.pool import ThreadPool
from imdb import IMDb, IMDbDataAccessError
from requests.exceptions import ConnectTimeout
from plexapi.exceptions import BadRequest, NotFound
from http.client import RemoteDisconnected, ResponseNotReady

class Plex():
    def __init__(self):
        self.account = self.get_account()
        self.server = self.get_account_server(self.account)
        self.section = self.get_server_section(self.server)
        self.media = self.section.all()

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
        sections = [ _ for _ in server.library.sections() if _.type == 'movie' and _.agent == 'tv.plex.agents.movie' ]
        if not sections:
            print('No available sections.')
            sys.exit()
        return plexapi.utils.choose('Select section index', sections, 'title')

    def create_playlist(self, name, media):
        try:
            self.server.playlist(name).addItems(media)
        except plexapi.exceptions.NotFound:
            self.server.createPlaylist(title=name, items=media)

class PlexHolidays():
    def __init__(self):
        # Necessary to disable imdbpy logger to hide timeouts, which are handled
        logging.getLogger('imdbpy').disabled = True
        logging.getLogger('imdbpy.parser.http.urlopener').disabled = True

        self.imdbpy = IMDb()
        self.plex = Plex()

        self.keyword = input('Keyword (i.e. Holiday name): ').lower()
        with tqdm(self.plex.media, desc=self.plex.section.title) as self.pbar:
            self.matches = [_ for _ in ThreadPool(6).map(self.find_matches, self.plex.media) if _]
        if not self.matches:
            print('No matching items.')
        else:
            print(f'{len(self.matches)} items matching "{self.keyword}":')
            for match in self.matches:
                print(f'\t{match.title} ({match.year})')
            self.plex.create_playlist(input('Playlist name: '), self.matches)
            print('Playlist created/updated.')

    def find_matches(self, medium):
        try:
            if (
                self.keyword in medium.title.lower() 
                or self.keyword in medium.summary.lower()
                or self.keyword in self.get_imdb_keywords(medium)
            ):
                return medium
        except Exception as e:
            self.pbar.write(f'UNHANDLED EXCEPTION WHILE CHECKING {medium.title}. PLEASE REPORT -', e)
        finally:
            self.pbar.update()

    @retry(ConnectTimeout, delay=2, tries=3)
    @retry(IMDbDataAccessError, delay=2, tries=3)
    def get_imdb_keywords(self, medium):
        try:
            imdb_id = next((_.id[9:] for _ in medium.guids if _.id.startswith('imdb')), '')
            if not imdb_id:
                return []
            return self.imdbpy.get_movie_keywords(imdb_id)['data'].get('keywords', [])
        except (ConnectTimeout, IMDbDataAccessError) as e:
            self.pbar.write(f'Error getting keywords for {medium.title}:  "{e.args[0]["original exception"]}"')
            return []

if __name__ == "__main__":
    ph = PlexHolidays()
