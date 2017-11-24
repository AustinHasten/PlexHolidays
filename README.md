Automatically find holiday movies/episodes on a Plex server and add them to a playlist.
Searches the Plex title, Plex plot, and IMDb keywords for each movie/episode for a keyword.

Currently, specials are ignored. The progressbar is also herky-jerky due to complications with multithreading.

On my machine/library/network, shows took an average of <30s each and movies took an average of <2s each.

Required Python3 modules: plexapi, imdbpy, imdbpie, tqdm
