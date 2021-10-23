import util.trackmania_username.retrieving as ret
import util.trackmania_username.storing as stor
import discord
from discord.ext import commands

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import util.logging.convert_logging as convert_logging
from util.guild_ids import guild_ids
from util.logging.usage import record_usage, finish_usage
import util.discord.easy_embed as ezembed

log = convert_logging.get_logging()

class UsernameSlash(commands.Cog):
    def __init__(self, client):
        self.client = client
        
    @commands.slash_command(guild_ids=guild_ids, name='storeusername', description='Stores Username in JSON File for Future Use and Speed')
    @commands.before_invoke(record_usage)
    @commands.after_invoke(finish_usage)
    async def _store_username(self, ctx: commands.Context, username: str):
        log.debug(f"Checking Username")
        if not stor.check_valid_trackmania_username(username):
            log.debug(f"Username not found")
            embed=ezembed.create_embed(title=':negative_squared_cross_mark: Username not Found or does not exist.', color=discord.Colour.red())
            await ctx.respond(embed=embed)
            return None
        log.debug(f"User Exists, Continuing")

        log.debug(f"Storing {username} for {ctx.author.name}. ID: {ctx.author.id}")
        stor.store_trackmania_username(ctx.author.id, username)
        log.debug(f"Stored Username for {ctx.author.name}")

        log.debug(f"Sending Success Message")
        embed=ezembed.create_embed(title=':white_check_mark: Successfully Stored Username', color=discord.Color.green())
        await ctx.respond(embed=embed)
        log.debug(f"Sent Success Message")
        
    @commands.slash_command(guild_ids=guild_ids, name='checkusername', description='Checks if your username is in the file')
    @commands.before_invoke(record_usage)
    @commands.after_invoke(finish_usage)
    async def _check_username(self, ctx: commands.Context):
        if ret.check_discord_id_in_file(str(ctx.author.id)):
            log.debug(f"Username in json file")
            embed=ezembed.create_embed(title=":white_check_mark: Your Username Exists", color=discord.Colour.green())
            await ctx.respond(embed=embed)
        else:
            log.debug(f"Username not in json file")
            embed = ezembed.create_embed(
                title=":negative_squared_cross_mark: Your Username does not Exist", color=discord.Colour.red()
            )
            await ctx.respond(embed=embed)

    @commands.slash_command(guild_ids=guild_ids, name='removeusername', description='Removes your username from the file if present')
    @commands.before_invoke(record_usage)
    @commands.after_invoke(finish_usage)
    async def _remove_username(self, ctx: commands.Context):
        if not ret.check_discord_id_in_file(str(ctx.author.id)):
            log.debug(f"User does not exist in file")
            embed = ezembed.create_embed(
                title=":negative_squared_cross_mark: User does not exist", color=discord.Colour.red()
            )
            await ctx.respond(embed=embed)
            return

        log.debug(f"Removing Trackmania Username")
        stor.remove_trackmania_username(ctx.author.id)
        log.debug(f"Removed Trackmania Username")
        embed = ezembed.create_embed(title=":white_check_mark: Successfully Removed Your Username from the File.", color=discord.Colour.green())
        await ctx.respond(embed=embed)

def setup(client):
    client.add_cog(UsernameSlash(client))