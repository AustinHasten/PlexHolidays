# Saul Femm
# Initial Commit - November 16th, 2017

import getpass, urllib.request
from bs4 import BeautifulSoup
from plexapi.myplex import MyPlexAccount
from plexapi.playlist import Playlist
from plexapi.exceptions import BadRequest, NotFound

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
            except BadRequest:
                print('INVALID USERNAME/PASSWORD')
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

        # Loop until valid server name is given
        while True:
            print('Available servers:')
            for x in servers:
                print('\t', x.name)

            server_name = input('Select server: ')
            print('Connecting to server... ', end='', flush=True)
            try:
                server = account.resource(server_name).connect()
            except NotFound:
                print('INVALID SERVER NAME')
                continue
            print('Done')
            break

        return server

    def get_server_section(self, server):
        """
            Select section from Plex server.
        """
        sections = [ _ for _ in server.library.sections() if _.type == 'show' ]
        if not sections:
            print('No available sections.')
            sys.exit()

        # Loop until valid section name is given
        while True:
            print('Available sections:')
            for section in sections:
                print('\t', section.title)
            section = input('Select section: ')
            print('Getting media from section... ', end='', flush=True)
            try:
                plex_section = server.library.section(section)
            except NotFound:
                print('INVALID SECTION NAME')
                continue
            print('Done')
            break
        return plex_section

    # TODO Change this function such that it's no longer specific to TV episodes
    def get_matching_media(self, lookup):
        """
            Find matching items between a Plex library and a dictionary.
        """
        matching_media = []
        matching_shows = [ show for show in self.media if show.title in lookup ]
        for show in matching_shows:
            for episode in show.episodes():
                if episode.title.lower() in lookup[show.title]:
                    matching_media.append(episode)
        return matching_media

    def create_playlist(self, name, media):
        Playlist.create(self.server, name, media)

def imdb_search(keyword):
    """
        Search IMDb for a keyword and parse results into a dictionary.
    """
    results = dict()
    keyword = keyword.lower().replace(' ', '-')
    url = ('http://www.imdb.com/search/title?&title_type=tv_episode&view=simple&count=2000&keywords=' + keyword)

    print('Fetching IMDb results... ', end='', flush=True)
    # Loop over results 100 at a time rather than all at once to prevent timeout
    html = urllib.request.urlopen(url, timeout=60).read()
    soup = BeautifulSoup(html, 'html.parser')
    spans = soup.find_all('span', title=True)
    for span in spans:
        a = span.find_all('a')

        # Show without episode name
        if len(a) < 2:
            continue

        show_name = a[0].contents[0].strip()
        episode_name = a[1].contents[0].strip().lower()
        if show_name in results:
            results[show_name].append(episode_name)
        else:
            results[show_name] = [ episode_name ]
    print('Done')

    return results

if __name__ == "__main__":
    plex = Plex()
    imdb_results = imdb_search(input('Keyword (i.e. Holiday Name): '))
    matching_media = plex.get_matching_media(imdb_results)

    print('Matching Media: ')
    for media in matching_media:
        season = media.parentIndex.zfill(2)
        episode = str(media.index).zfill(2)
        se = ('S' + season + 'E' + episode)
        print('\t', media.grandparentTitle, '-', se, '-', media.title)
    plex.create_playlist(input('Playlist name: '), matching_media)

    print('Happy Holidays!')
