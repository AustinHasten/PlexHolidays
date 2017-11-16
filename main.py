# Saul Femm
# Initial Commit - November 16th, 2017

import getpass, urllib.request
from bs4 import BeautifulSoup
from plexapi.myplex import MyPlexAccount
from plexapi.playlist import Playlist
from plexapi.exceptions import BadRequest, NotFound

class PlexHolidays():
    def __init__(self):
        plex_server = self.get_plex_server()
        plex_shows = plex_server.library.section('TV Shows').all()
        imdb_results = self.imdb_search(input('Keyword (i.e. Holiday Name): ').lower())
        matching_eps = self.get_matching_eps(plex_shows, imdb_results)

        print('Matching Episodes: ')
        for episode in matching_eps:
            print('\t', episode.title)
        Playlist.create(plex_server, input('Playlist name: '), matching_eps)

        print('Happy Holidays!')

    def get_matching_eps(self, plex_shows, imdb_results):
        matching_eps = []
        for show in plex_shows:
            if show.title in imdb_results:
                for episode in show.episodes():
                    if episode.title in imdb_results[show.title]:
                        matching_eps.append(episode)
        return matching_eps

    def get_plex_server(self):
        # Sign into Plex account
        while True:
            username = input("Plex Username: ")
            password = getpass.getpass()

            print('Signing into Plex... ', end='', flush=True)
            try:
                account = MyPlexAccount(username, password)
            except BadRequest:
                print('Invalid username/password')
                continue
            print('Done')
            break

        # Select server from Plex account
        servers = [ _ for _ in account.resources() if _.product == 'Plex Media Server' ]
        while True:
            print('Available servers: ')
            for x in servers:
                print('\t', x.name)
            server = input('Select server: ')
            print('Connecting to server... ', end='', flush=True)
            try:
                plex = account.resource(server).connect()
            except NotFound:
                print('Invalid server name')
                continue
            print('Done')
            break
        return plex

    def imdb_search(self, keyword):
        results = dict()
        base_url = ('http://www.imdb.com/search/title?&title_type=tv_episode&view=simple&count=100&keywords=' + keyword.replace(' ', '-') + '&start=')

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
                episode_name = a[1].contents[0].strip()
                if show_name in results:
                    results[show_name].append(episode_name)
                else:
                    results[show_name] = [ episode_name ]
        print('Done')

        return results

if __name__ == "__main__":
    PH = PlexHolidays()
