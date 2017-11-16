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
        # Sign into Plex account
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
        # Select server from Plex account
        # TODO Handle case where servers[] is empty
        servers = [ _ for _ in account.resources() if _.product == 'Plex Media Server' ]
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
        # Select section from Plex server
        # TODO Handle case where sections[] is empty
        sections = [ _ for _ in server.library.sections() if _.type == 'show' ]
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

    def get_matching_media(self, lookup):
        matching_media = []
        for show in self.media:
            if show.title in lookup:
                for episode in show.episodes():
                    if episode.title.lower() in lookup[show.title]:
                        matching_media.append(episode)
        return matching_media

    def create_playlist(self, name, media):
        Playlist.create(self.server, name, media)

class PlexHolidays():
    def __init__(self):
        plex = Plex()
        imdb_results = self.imdb_search(input('Keyword (i.e. Holiday Name): '))
        matching_media = plex.get_matching_media(imdb_results)

        print('Matching Media: ')
        for media in matching_media:
            print('\t', media.title)
        plex.create_playlist(input('Playlist name: '), matching_media)

        print('Happy Holidays!')

    def imdb_search(self, keyword):
        results = dict()
        keyword = keyword.lower().replace(' ', '-')
        base_url = ('http://www.imdb.com/search/title?&title_type=tv_episode&view=simple&count=100&keywords=' + keyword + '&start=')

        print('Fetching IMDb results... ', end='', flush=True)
        for i in range(1, 5000, 100):
            url = (base_url + str(i))
            html = urllib.request.urlopen(url).read()
            soup = BeautifulSoup(html, 'html.parser')
            spans = soup.find_all('span', title=True)

            if not spans:
                break

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
    PH = PlexHolidays()
