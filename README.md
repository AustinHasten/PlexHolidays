#Currently only works for movies due to TheTVDB moving to a subscription model for their API keys. I am looking into any workarounds or alternatives.

Automatically find holiday movies/episodes on a Plex server and add them to a playlist.
Searches the Plex title, Plex plot, and IMDb keywords for each movie/episode for a keyword.

Required modules can be installed from an elevated command prompt on Windows machines:

    py -m pip install -r requirements.txt

Or on Linux machines with:

    # python -m pip install -r requirements.txt

Tested only on movies using the Plex Movie (Legacy) and Plex Movie agents.
