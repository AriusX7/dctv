import asyncio
import logging
import urllib.parse
from datetime import datetime
from typing import Optional

import aiohttp
import discord
from redbot.core import commands, checks
from redbot.core.commands.context import Context
from redbot.core.data_manager import bundled_data_path


from .utils import Show, Episode


log = logging.getLogger("red.dctv")

EMBED_COLOR = 0xdab159

SHOW_SUB_LINKS = {
    "Arrow": "https://www.reddit.com/r/arrow",
    "The Flash": "https://www.reddit.com/r/FlashTV",
    "Supergirl": "https://www.reddit.com/r/supergirlTV",
    "DC's Legends of Tomorrow": "https://www.reddit.com/r/LegendsOfTomorrow",
    "Black Lightning": "https://www.reddit.com/r/LegendsOfTomorrow",
    "Batwoman": "https://www.reddit.com/r/LegendsOfTomorrow",
    "Stargirl": "https://www.reddit.com/r/LegendsOfTomorrow",
    "Superman and Lois": "https://www.reddit.com/r/LegendsOfTomorrow",
    "Green Arrow and the Canaries":
        "https://www.reddit.com/r/ArrowAndTheCanaries"
}

WA_LINK = "https://www.wolframalpha.com/input/?i={}"


class DCTV(commands.Cog):

    def __init__(self, bot):
        # self.config = Config.get_conf(
        #     self, 1_310_527_007, force_registration=True)

        # self.RULES = open("./rules.md", "r").read()
        rules_fp = bundled_data_path(self) / "rules.md"
        self.RULES = rules_fp.open("r").read()

        info_fp = bundled_data_path(self) / "info.md"
        self.INFO = info_fp.open("r").read()

        roles_fp = bundled_data_path(self) / "roles.md"
        self.ROLES = roles_fp.open("r").read()

        invite_fp = bundled_data_path(self) / "invite.md"
        self.INVITE = invite_fp.open("r").read()

        self.session = aiohttp.ClientSession()
        self.bg_loop_task: Optional[asyncio.Task] = None

    def init(self):

        def done_callback(fut: asyncio.Future):

            try:
                fut.exception()
            except asyncio.CancelledError:
                pass
            except asyncio.InvalidStateError as exc:
                log.exception(
                    "We have a done callback when not done?", exc_info=exc
                )
            except Exception as exc:
                log.exception("Unexpected exception in rss: ", exc_info=exc)

    def cog_unload(self):
        # if self.bg_loop_task:
        #     self.bg_loop_task.cancel()
        asyncio.create_task(self.session.close())

    @commands.command(name="show")
    async def _show(self, ctx: Context, *, show: Show):
        """Show information about a DCTV show."""

        embed = discord.Embed(
            color=EMBED_COLOR,
            title=show.name,
            description=show.summary,
            url=SHOW_SUB_LINKS[show.name]
        )

        embed.add_field(name="Status", value=show.status, inline=False)

        if show.status == "Running":
            embed = self.ep_info(await show.next_ep(self.session), embed)

        embed.add_field(
            name="Viewing Info", value=show.viewer_info(), inline=False
        )

        embed.set_footer(text=f"Source: TVmaze API ({show.url})")

        await ctx.send(embed=embed)

    @commands.command(name="next")
    async def next_ep(self, ctx: Context, *, show: Show):
        """Show information about the next episode of the show."""

        episode = await show.next_ep(self.session)

        if not episode:
            return await ctx.send("The show is not currently running!")

        title = f"{show.name} Season {episode.season} Episode {episode.number}"

        txt = (
            f"\n**Name:** ||[{episode.name}]({episode.url})||"
            f"\n**Synopsis:** ||{episode.summary}||"
            f"\n**Airs:** {episode.datetime} ([View in your timezone]"
            f"({self.wa_time_url(episode.datetime)}))"
        )

        embed = discord.Embed(
            color=EMBED_COLOR,
            title=title,
            description=txt,
            url=SHOW_SUB_LINKS[show.name]
        )

        embed.set_footer(text=f"Source: TVmaze API")

        await ctx.send(embed=embed)

    @commands.command(name="episode", aliases=['ep'])
    async def episode_info(
        self, ctx: Context, show: Show, season: int, *, episode: int
    ):
        """Show information about a particular episode of a show."""

        url = (
            "http://api.tvmaze.com/shows/{}/"
            "episodebynumber?season={}&number={}"
        )

        episode: Episode = await Episode.get(
            url.format(show.id, season, episode), self.session
        )

        title = f"{show.name} Season {episode.season} Episode {episode.number}"

        txt = (
            f"\n**Name:** ||[{episode.name}]({episode.url})||"
            f"\n**Synopsis:** ||{episode.summary}||"
            f"\n**{self._aired_or_airs(episode.datetime)}:"
            f"** {episode.datetime} ([View in your timezone]"
            f"({self.wa_time_url(episode.datetime)}))"
        )

        embed = discord.Embed(
            color=EMBED_COLOR,
            title=title,
            description=txt,
            url=SHOW_SUB_LINKS[show.name]
        )

        embed.set_footer(text=f"Source: TVmaze API")

        await ctx.send(embed=embed)

    @commands.command(name="dctvrules")
    @checks.admin_or_permissions()
    async def send_rules(
        self, ctx: Context, channel: discord.TextChannel = None
    ):
        """Send rules in the specified channel. Defaults to current channel."""

        if not channel:
            channel = ctx.channel

        embed_img = discord.Embed(color=EMBED_COLOR)
        embed_img.set_image(url="https://i.imgur.com/Ft142SS.png")

        await channel.send(embed=embed_img)
        await channel.send(
            embed=discord.Embed(color=EMBED_COLOR, description=self.RULES)
        )

    @commands.command(name="dctvinfo")
    @checks.admin_or_permissions()
    async def send_info(
        self, ctx: Context, channel: discord.TextChannel = None
    ):
        """Send info in the specified channel. Defaults to current channel."""

        if not channel:
            channel = ctx.channel

        embed_img = discord.Embed(color=EMBED_COLOR)
        embed_img.set_image(url="https://i.imgur.com/tzl2dhs.png")

        await channel.send(embed=embed_img)
        await channel.send(
            embed=discord.Embed(
                color=EMBED_COLOR, title="Welcome!", description=self.INFO
            )
        )

    @commands.command(name="dctvroles")
    @checks.admin_or_permissions()
    async def send_roles(
        self, ctx: Context, channel: discord.TextChannel = None
    ):
        """Send roles in the specified channel. Defaults to current channel."""

        if not channel:
            channel = ctx.channel

        embed_img = discord.Embed(color=EMBED_COLOR)
        embed_img.set_image(url="https://i.imgur.com/EkzYBK8.png")

        await channel.send(embed=embed_img)
        await channel.send(
            embed=discord.Embed(color=EMBED_COLOR, description=self.ROLES)
        )

    @commands.command(name="dctvinvite")
    @checks.admin_or_permissions()
    async def send_invite(
        self, ctx: Context, channel: discord.TextChannel = None
    ):
        """Send invite in the given channel. Defaults to current channel."""

        if not channel:
            channel = ctx.channel

        embed_img = discord.Embed(color=EMBED_COLOR)
        embed_img.set_image(url="https://i.imgur.com/k4CCslx.png")

        await channel.send(embed=embed_img)
        await channel.send(self.INVITE)

    @commands.command(name="editrules")
    @checks.admin_or_permissions()
    async def edit_rules(
        self, ctx: Context, channel: discord.TextChannel, message_id: str
    ):
        """Edit the rules message."""

        message: discord.Message = await channel.fetch_message(message_id)

        await message.edit(
            embed=discord.Embed(color=EMBED_COLOR, description=self.RULES)
        )

    @commands.command(name="editinfo")
    @checks.admin_or_permissions()
    async def edit_info(
        self, ctx: Context, channel: discord.TextChannel, message_id: str
    ):
        """Edit the info message."""

        message: discord.Message = await channel.fetch_message(message_id)

        await message.edit(
            embed=discord.Embed(
                color=EMBED_COLOR, title="Welcome!", description=self.INFO
            )
        )

    @commands.command(name="editroles")
    @checks.admin_or_permissions()
    async def edit_roles(
        self, ctx: Context, channel: discord.TextChannel, message_id: str
    ):
        """Edit the roles message."""

        message: discord.Message = await channel.fetch_message(message_id)

        await message.edit(
            embed=discord.Embed(color=EMBED_COLOR, description=self.ROLES)
        )

    @commands.command(name="editinvite")
    @checks.admin_or_permissions()
    async def edit_invite(
        self, ctx: Context, channel: discord.TextChannel, message_id: str
    ):
        """Edit the invite message."""

        message: discord.Message = await channel.fetch_message(message_id)

        await message.edit(content=self.INVITE)

    def ep_info(self, episode: Episode, embed: discord.Embed):
        """Add next episode information to the embed"""

        title = (
            f"Next Episode - Season {episode.season}"
            f" Episode {episode.number}"
        )

        txt = (
            f"\n**Name:** ||[{episode.name}]({episode.url})||"
            f"\n**Synopsis:** ||{episode.summary}||"
            f"\n**Airs:** {episode.datetime} ([View in your timezone]"
            f"({self.wa_time_url(episode.datetime)}))"
        )

        embed.add_field(name=title, value=txt, inline=False)

        return embed

    def _aired_or_airs(self, air_str: str):
        dt = datetime.strptime(air_str.split('at')[0].strip(), "%B %d, %Y")

        if dt > datetime.utcnow():
            return "Airs"
        return "Aired"

    def wa_time_url(self, fmt):
        fmt = urllib.parse.quote_plus(fmt)
        return WA_LINK.format(fmt)

    __unload = cog_unload
