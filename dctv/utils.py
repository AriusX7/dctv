import asyncio
import html
import re
from datetime import datetime
# import functools

import aiohttp
from discord.ext.commands.errors import BadArgument


API_ROOT = "http://api.tvmaze.com/singlesearch/shows"

DCTV_SHOWS = [
    "arrow",
    "the-flash",
    "supergirl",
    "dcs-legends-of-tomorrow",
    "batwoman",
    "black-lightning",
    "stargirl",
    "superman-lois",
    "green-arrow-and-the-canaries"
]


_cleanr = re.compile("<.*?>")


def show_str(name: str):
    """Return API qualified string for the show.

    Parameters
    --------------
    name: :class:`str`
        Full/partial name of the show
    """

    name = name.replace(" ", "-")
    name = name.replace("_", "-")

    # special cases
    if name.lower() in "lot":
        return "dcs-legends-of-tomorrow"

    if name.lower() in "bl":
        return "black-lightning"

    if name.lower() in ["superman-and-lois", "superman-&-lois"]:
        return "superman-lois"

    for show in DCTV_SHOWS:
        if name.lower() in show:
            return show


def remove_html(text: str):
    """Remove HTML tags from text and convert specials to ASCII.

    Parameters
    --------------
    text: `class`:str:
        Text with HTML tags

    Returns
    ----------
    :class:`str`
        Text without HTML tags
    """

    if not text:
        return

    return re.sub(_cleanr, '', html.unescape(text))


def format_datetime(airstamp: str):
    """Format date time in MonthName Day, Year at HH:MM timezone format.

    Parameters
    --------------
    airstamp: :class:`str`
        `airstamp` string from the TVmaze API.

    Returns
    ---------
    :class:`str`
        Date time string in MonthName Day, Year at HH:MM timezone format.
    """

    dt, _ = airstamp.split("+")

    # if timezone == "00:00":
    #     timezone = ""

    dt = datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    return dt.strftime("%B %d, %Y at %H:%M UTC")


class Show:
    """A class to represent a show.

    Parameters
    --------------
    data: :class:`dict`
        TVMaze API data for the show
    """

    def __init__(self, data: dict):
        self.data = data

        self.id: int = data["id"]
        self.name: str = data["name"].replace("&", "and")
        self.url: str = data["url"]
        self.status: str = data["status"]
        self.summary: str = remove_html(data["summary"])

    async def next_ep(self, session: aiohttp.ClientSession):
        """Get ``Episode`` for the next episode of the show."""

        if self.status == "Running":
            ep_link = self.data["_links"]["nextepisode"]["href"]
            return await Episode.get(ep_link, session)

    def viewer_info(self):
        """Get information about network or webchannel."""

        network = self.data["network"]
        web = self.data["webChannel"]

        txt = ""

        if network:
            txt += f"**Network:** {network['name']}"

        if web:
            txt += f"\n**Website:** {web['name']}"

        runtime = self.data["runtime"]
        if runtime:
            txt += f"\n**Duration:** {runtime} minutes"

        return txt

    @classmethod
    async def convert(cls, ctx, argument):
        show_name = show_str(argument)

        if show_name:
            while True:
                session: aiohttp.ClientSession = ctx.cog.session
                async with session.get(API_ROOT,
                                       params={"q": show_name}) as res:
                    if res.status == 429:
                        asyncio.sleep(5)
                        continue
                    else:
                        return cls(await res.json())
        else:
            raise BadArgument(f"No DCTV show with name **{argument}** found.")


class Episode:
    """A class to represent an episode.

    Parameters
    --------------
    data: :class:`dict`
        TVMaze API data for the episode
    """

    def __init__(self, data: dict):
        self.name: str = data["name"]
        self.url: str = data["url"]
        self.season: int = data["season"]
        self.number: int = data["number"]
        self.datetime: str = format_datetime(data["airstamp"])
        self.summary: str = remove_html(data["summary"])

    @classmethod
    async def get(cls, link: str, session: aiohttp.ClientSession):
        """Get an instance of ``Episode``.

        Parameters
        --------------
        link: :class:`str`
            TVmaze episode API link
        """

        while True:
            async with session.get(link) as res:
                if res.status == 404:
                    raise EpisodeNotFoundError
                elif res.status == 429:
                    asyncio.sleep(5)
                    continue
                else:
                    return cls(await res.json())


class EpisodeNotFoundError:
    """Raised when episode is not found"""
