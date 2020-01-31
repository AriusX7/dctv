from .dctv import DCTV


async def setup(bot):
    cog = DCTV(bot)
    cog.init()
    bot.add_cog(cog)
