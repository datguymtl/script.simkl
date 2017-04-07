#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import xbmc
import interface
import utils
from datetime import datetime
from utils import getstr, getSetting
import json
__addon__ = interface.__addon__
def getstr(strid): return interface.getstr(strid)

class Engine:
  def __init__(self, api, player):
    self.api = api
    self.player = player
    player.engine = self
    player.api    = api

  #Note 4 myself: Maybe you should handle movies and series completly different
  #I mean: Two different functions, two different "databases", etc.
  def synclibrary(self, mode="full"):
    simkl_old_f = utils.get_old_file("simkl")
    kodi_old_f = utils.get_old_file("kodi")
    kodi_current = {
    "movies": self.get_movies(), "episodes": self.get_episodes(), 
    "lastcheck": datetime.today().strftime(utils.SIMKL_TIME_FORMAT)}
    #Don't update if library hasn't changed
    simkl_current = self.api.get_all_items()

    def open_file(filename, current):
      if not os.path.exists(filename):
      #if True:
        with open(filename, "w") as f:
          f.write(json.dumps(current, indent=2))
        return current
      else:
        with open(filename, "r") as f:
          old = json.loads(f.read())
        with open(filename, "w") as f:
          f.write(json.dumps(current, indent=2))
        return old

    kodi_old = open_file(kodi_old_f, kodi_current)
    simkl_old = open_file(simkl_old_f, simkl_current)

    self.syncmovies(simkl_old["movies"], simkl_current["movies"], kodi_old["movies"], kodi_current["movies"], kodi_old["lastcheck"])

    # simkl_removed = self.diff(utils.simkl2kodi(simkl_current),utils.simkl2kodi(simkl_old))
    # simkl_added = self.diff(utils.simkl2kodi(simkl_old), utils.simkl2kodi(simkl_current))
    # kodi_removed = self.diff(kodi_current, kodi_old)
    # kodi_added = self.diff(kodi_old, kodi_current)
    # diff_kodi_simkl = self.diff(kodi_current, utils.simkl2kodi(simkl_current))
    # diff_simkl_kodi = self.diff(utils.simkl2kodi(simkl_current), kodi_current)

  def syncmovies(self, simkl_old, simkl_current, kodi_old, kodi_current, kodi_lastcheck):
    simkl_lastcheck = utils.simkl_time_to_kodi(self.api.get_last_activity()["movies"]["completed"])
    xbmc.log("Simkl: Lastcheck movies %s" % simkl_lastcheck)

    simkl_added = self.diff(utils.simkl2kodi(simkl_old), utils.simkl2kodi(simkl_current))
    simkl_removed = self.diff(utils.simkl2kodi(simkl_current), utils.simkl2kodi(simkl_old))
    # U iterate through this, not through the WHOLE library
    in_both = self.intersect(kodi_current, utils.simkl2kodi(simkl_current))
    for movie in in_both:
      xbmc.log("Movie: %s" % movie)

    for movie in simkl_added:
      xbmc.log("Added %s" % movie)
    for movie in simkl_removed:
      xbmc.log("Removed %s" % movie)

  @staticmethod
  def diff(A, B):
    """ 
      Returns the difference between A and B. About data return: B > A
    """
    A_movies = set([x["imdbnumber"] for x in A])
    B_movies = set([x["imdbnumber"] for x in B])
    diff = list(B_movies - A_movies)
    return [movie_B for movie_B in B if movie_B["imdbnumber"] in diff]

  @staticmethod
  def intersect(A, B):
    """ Returns the intersection between A and B. About data return: B > A """
    A_movies = set([x["imdbnumber"] for x in A])
    B_movies = set([x["imdbnumber"] for x in B])
    inter = A_movies & B_movies
    return [movie_B for movie_B in B if movie_B["imdbnumber"] in inter]

  @staticmethod
  def get_movies():
    movies_list = []
    movies = json.loads(xbmc.executeJSONRPC(json.dumps({
          "jsonrpc": "2.0",
          "method": "VideoLibrary.GetMovies",
          "params": {
            "limits": {
              "start": 0,
              "end": 0
            },
            "properties": [
              "playcount",
              "imdbnumber",
              "file",
              "lastplayed",
              "year"
            ],
            "sort": {
              "order": "ascending",
              "method": "playcount",
              #"ignorearticle": True
            }
          },
          "id": "libMovies"
      })))["result"]["movies"]
    for movie in movies:
      if movie["playcount"] > 0:
        movies_list.append(movie)
    return movies_list

  @staticmethod
  def get_episodes():
    shows_library = json.loads(xbmc.executeJSONRPC(json.dumps({
      "jsonrpc": "2.0",
      "method": "VideoLibrary.GetTVShows",
      "params": {
        "limits": {"start": 0, "end": 0},
        "properties": ["imdbnumber", "title", "watchedepisodes", "year"],
        "sort": {"order": "ascending", "method": "season"}
      },
      "id": "libMovies"
    })))
    if shows_library["result"]["limits"]["total"] == 0: return None
    list_tvshows = []
    for tvshow in shows_library["result"]["tvshows"]:
      list_episodes = []
      episodes = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetEpisodes",
        "params": {
          "limits": {"start": 0, "end": 0},
          "properties": ["playcount", "season", "episode", "lastplayed", "tvshowid"],
          "sort": {"order": "ascending", "method": "playcount"},
          #"season": season["season"],
          "tvshowid": tvshow["tvshowid"]
        },
        "id": tvshow["tvshowid"]
      })))

      if episodes["result"]["limits"]["end"] > 0:
        for episode in episodes["result"]["episodes"]:
          if episode["playcount"] > 0: list_episodes.append(episode)
      if len(list_episodes) > 0:
        list_tvshows.append({
          "title":tvshow["title"],
          "year":tvshow["year"],
          "imdbnumber":tvshow["imdbnumber"],
          "episodes":list_episodes})

    return list_tvshows

class Player(xbmc.Player):
  """ Replaces the Kodi player class """
  def __init__(self):
    xbmc.Player.__init__(self)

  @staticmethod
  def getMediaType():
    """ Returns the MediaType of the file currently playing """
    if xbmc.getCondVisibility('Container.Content(tvshows)'):
      return "show"
    elif xbmc.getCondVisibility('Container.Content(seasons)'):
      return "season"
    elif xbmc.getCondVisibility('Container.Content(episodes)'):
      return "episode"
    elif xbmc.getCondVisibility('Container.Content(movies)'):
      return "movie"
    else:
      return None

  def onPlayBackStarted(self):
    """ Activated at start """
    #self.onPlayBackStopped()
    pass
  def onPlayBackSeek(self, *args):
    """ Activated on seek """
    self.onPlayBackStopped()
  def onPlayBackResumed(self):
    """ Activated on resume """
    self.onPlayBackStopped()
  def onPlayBackEnded(self):
    """ Activated at end """
    xbmc.log("Simkl: ONPLAYBACKENDED")
    self.onPlayBackStopped()

  def onPlayBackStopped(self):
    ''' Gets the info needed to pass to the api '''
    self.api.check_connection()
    try:
      item = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "method": "Player.GetItem",
        "params": {
          "properties": ["showtitle", "title", "season", "episode", "file", "tvshowid", "imdbnumber", "year" ],
          "playerid": 1},
        "id": "VideoGetItem"})))["result"]["item"]
      if item["tvshowid"] != -1:
        item["imdbnumber"] = json.loads(xbmc.executeJSONRPC(json.dumps({
          "jsonrpc": "2.0", "method":"VideoLibrary.GetTVShowDetails",
          "params":{"tvshowid":item["tvshowid"], "properties":["imdbnumber"]},
          "id":1
          })))["result"]["tvshowdetails"]["imdbnumber"]
      xbmc.log("Simkl: Full: {0}".format(item))

      percentage = min(99, 100 * self.getTime() / self.getTotalTime())
      pctconfig  = int(self.addon.getSetting("scr-pct"))

      if percentage > pctconfig:
        bubble = __addon__.getSetting("bubble")
        r = self.api.watched(item, self.getTotalTime())

        if bubble=="true" and r:
          if item["label"] == os.path.basename(item["file"]):
          #if True: #For testing purposes
            xbmc.log("Simkl: Label and file are the same")
            lstw = self.api.lastwatched
            if lstw["type"] == "episode":
              item["showtitle"] = lstw["show"]["title"]
              item["season"] = lstw["episode"]["season"]
              item["episode"] = lstw["episode"]["episode"]
            elif lstw["type"] == "movie":
              item["title"] = "".join([lstw["movie"]["title"], " (", str(lstw["movie"]["year"]), ")"])
            media = lstw["type"]

          txt = item["label"]
          title = ""
          if item["type"] == "movie":
            txt = "".join([item["title"], " (", str(item["year"]), ")"])
          elif item["type"] == "episode":
            txt = item["showtitle"]
            title = "- S{:02}E{:02}".format(item["season"], item["episode"])
          xbmc.log("Simkl: " + "; ".join([item["type"], txt, title]))
          interface.notify(getstr(32028).format(title), title=txt)
          r = 0

    except RuntimeError:
      pass
    except ZeroDivisionError:
      self.onPlayBackStopped()
