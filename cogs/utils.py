import discord
from discord.ext import commands
from discord.ext.commands import TextChannelConverter
from ext.utility import load_json
from urllib.parse import quote as uriquote
from mtranslate import translate
from ext import embedtobox
from PIL import Image
import traceback
import aiohttp
import asyncio
import time
import re
import random
import typing
import io

class Utility:
    def __init__(self, bot):
        self.bot = bot
        self.lang_conv = load_json('data/langs.json')
    
    @commands.command()
    async def translate(self, ctx, language, *, text):
        """translates the string into a given language
        __**Parameters**__
        • language - the language to translate to
        • text - the text to be translated
        """
        await ctx.send(translate(text, language))
        
    @commands.command()
    @commands.has_permissions(manage_emojis = True)
    async def addemoji(self, ctx, emoji_name, emoji_link = '', *roles : discord.Role):
        """Add an emoji to a server
        __**Parameters**__
        • emoji_name – The emoji name. Must be at least 2 characters
        • emoji_link – The url or attachment of an image to turn into an emoji
        • roles – A list of Roles that can use this emoji (case sensitive). Leave empty to make it available to everyone
        """
        if ctx.message.attachments:
            emoji_link = ctx.message.attachments[0].url
            async with ctx.session.get(emoji_link) as resp:
                image = await resp.read()
        elif emoji_link:
            async with ctx.session.get(emoji_link) as resp:
                image = await resp.read()
        created_emoji = await ctx.guild.create_custom_emoji(name = emoji_name, image = image, roles = [r for r in roles if roles is not None])
        await ctx.send(f"Emoji {created_emoji} created!")
     
    @commands.command()
    async def delemoji(self, ctx, name: str):
        "Deletes an emoji"
        emoji = discord.utils.get(ctx.guild.emojis, name = name)
        await emoji.delete()
        await ctx.send(content = f"Deleted emoji : {name}", delete_after = 2)
        
    @commands.command()
    async def editemoji(self, ctx, emoji_name, new_name):
        emoji = discord.utils.get(ctx.guild.emojis, name = emoji_name)
        await emoji.edit(name = new_name)
        await ctx.send(content = f"Edited emoji {emoji_name} to {new_name}")
    
    @commands.command(name='logout')
    async def _logout(self, ctx):
        '''
        restart the bot
        '''
        await ctx.send('`Selfbot Logging out`')
        await self.bot.logout()

    @commands.command(name='help', hidden = 'True')
    async def new_help_command(self, ctx, *commands : str):
        """get help cmds"""
        destination = ctx.message.author if self.bot.pm_help else ctx.message.channel

        def repl(obj):
            return self.bot._mentions_transforms.get(obj.group(0), '')

        # help by itself just lists our own commands.
        if len(commands) == 0:
            pages = await self.bot.formatter.format_help_for(ctx, self.bot)
        elif len(commands) == 1:
            # try to see if it is a cog name
            name = self.bot._mention_pattern.sub(repl, commands[0])
            command = None
            if name in self.bot.cogs:
                command = self.bot.cogs[name]
            else:
                command = self.bot.all_commands.get(name)
                if command is None:
                    await destination.send(self.bot.command_not_found.format(name))
                    return

            pages = await self.bot.formatter.format_help_for(ctx, command)
        else:
            name = self.bot._mention_pattern.sub(repl, commands[0])
            command = self.bot.all_commands.get(name)
            if command is None:
                await destination.send(self.bot.command_not_found.format(name))
                return

            for key in commands[1:]:
                try:
                    key = self.bot._mention_pattern.sub(repl, key)
                    command = command.all_commands.get(key)
                    if command is None:
                        await destination.send(self.bot.command_not_found.format(key))
                        return
                except AttributeError:
                    await destination.send(self.bot.command_has_no_subcommands.format(command, key))
                    return

            pages = await self.bot.formatter.format_help_for(ctx, command)

        if self.bot.pm_help is None:
            characters = sum(map(lambda l: len(l), pages))
            # modify destination based on length of pages.
            if characters > 1000:
                destination = ctx.message.author

        color = await ctx.get_dominant_color(ctx.author.avatar_url)

        for embed in pages:
            embed.color = color
            try:
                await ctx.send(embed=embed)
            except discord.HTTPException:
                em_list = await embedtobox.etb(embed)
                for page in em_list:
                    await ctx.send(page)
      
    @commands.command()
    async def nick(self, ctx, user : discord.Member, *, nickname : str = None):
        await user.edit(nick = nickname)
        await ctx.send("Changed {user.name}'s nickname to {nickname}")
    
    @commands.command()
    async def cpres(self, ctx, status : str, Type:str = "playing", *, message:str = None):
        '''Sets a custom presence, the Type argument can be "playing", "streaming", "listeningto" or "watching"
        status can be "online", "dnd", "idle", "invisible"
        Example : (prefix)cpres idle watching a movie'''
        types = {"playing" : "Playing", "streaming" : "Streaming", "listeningto" : "Listening to", "watching" : "Watching"}
        stats = {"online" : discord.Status.online, "dnd" : discord.Status.dnd, "idle" : discord.Status.idle, "invisible" : discord.Status.invisible}
        em = discord.Embed(color=0x6ed457, title="Presence")
        if message is None:
            await self.bot.change_presence(status=discord.Status.online, activity= message, afk = True)
        else:
            if Type == "playing":
                await self.bot.change_presence(status=stats[status], activity=discord.Game(name=message), afk = True)
            elif Type == "streaming":
                await self.bot.change_presence(status=stats[status], activity=discord.Streaming(name=message, url=f'https://twitch.tv/{message}'), afk = True)
            elif Type == "listeningto":
                await self.bot.change_presence(status=stats[status], activity=discord.Activity(type=discord.ActivityType.listening, name=message), afk = True)
            elif Type == "watching":
                await self.bot.change_presence(status=stats[status], activity=discord.Activity(type=discord.ActivityType.watching, name=message), afk = True)
            em.description = f"Presence : {types[Type]} {message}"
            if ctx.author.guild_permissions.embed_links:
                await ctx.send(embed = em)
            else:
                await ctx.send(f"Presence : {types[Type]} {message}")      

    @commands.command()
    async def clear(self, ctx, *, serverid = "all"):
        '''Marks messages from selected servers or emote servers as read'''
        if serverid != None:
            if serverid == 'all':
                for guild in self.bot.guilds:
                    await guild.ack()
                await ctx.send('Cleared all unread messages')
                return
            try:
                serverid = int(serverid)
            except:
                await ctx.send('Invalid Server ID')
                return
            server = discord.utils.get(self.bot.guilds, id=int(serverid))
            if server == None:
                await ctx.send('Invalid Server ID')
                return
            await server.ack()
            await ctx.send(f'All messages marked read in {server.name}!')
            return
        for guild in self.bot.guilds:
            if guild.id in emotes_servers:
                await guild.ack()
        await ctx.send('All messages marked read in emote servers!')

    @commands.command()
    async def choose(self, ctx, *, choices: commands.clean_content):
        '''choose! use , in between'''
        choices = choices.split(',')
        if len(choices) < 2:
            return await ctx.send('Not enough choices to pick from.')
        choices[0] = ' ' + choices[0]
        await ctx.send(str(random.choice(choices))[1:])
        
    @commands.command()
    async def picsu(self, ctx, user : discord.Member = None, size : typing.Optional[int] = 512, format = None):
        """gets the Display Picture of a user
        __**Parameters**__
        • user – Tag of the user to fetch his avatar
        • size – The size of the image to display
        • format – The format to attempt to convert the avatar to. If the format is None, then it is automatically detected
        """
        await ctx.message.delete()
        mem = user or ctx.author
        if format is None and ctx.author.is_avatar_animated() != True:
            format = "png" 
        avatar = mem.avatar_url_as(format = format if format is not "gif" else None, size = size)
        await ctx.send(avatar)

def setup(bot):
    bot.add_cog(Utility(bot))
