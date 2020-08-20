import discord
from discord.ext import commands

class BotContext(commands.Cog):

    '''
    Behaviour of the bot and its sorroundings
    '''
    def __init__(self, bot):
        self.bot = bot
        self.MOD_ROLE_ID = 743537238071181472
        self.BOT_FRIENDLY_CHANNELS = [746081458564890654, 745044635604484217]


    #Events
    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        Allows bot to reply to social messages 
        '''
        # we do not want the bot to reply to itself
        author = message.author
        content = message.content
        channel = message.channel

        if channel.id in self.BOT_FRIENDLY_CHANNELS:
        
            if author.id == self.bot.user.id:
                return

            if (('hello' in content) or ('hi' in content)) and "makernaut" in content.lower():
                try:
                    print('Inside Bot Context: ' + message.content)
                    emoji = '\N{WHITE HEAVY CHECK MARK}'
                    await message.add_reaction(emoji)
                    await message.channel.send('Hello {0.author.mention}'.format(message))
                except discord.HTTPException:
                    # sometimes errors occur during this, for example
                    # maybe you dont have permission to do that
                    # we dont mind, so we can just ignore them
                    pass   
            if 'good bot' in content:
                try:
                    emoji = '\N{SPARKLING HEART}'
                    await message.add_reaction(emoji)
                    await message.channel.send('Aww, thanks {0.author.mention}. Good human!'.format(message))

                except discord.HTTPException:
                    # sometimes errors occur during this, for example
                    # maybe you dont have permission to do that
                    # we dont mind, so we can just ignore them
                    pass 
            if 'bad bot' in content:
                try: 
                    await message.channel.send('https://tenor.com/view/pedro-monkey-puppet-meme-awkward-gif-15268759')
                except discord.HTTPException:
                    # sometimes errors occur during this, for example
                    # maybe you dont have permission to do that
                    # we dont mind, so we can just ignore them
                    pass 

    @commands.command()
    async def purge(self, ctx, num_messages):
        '''
        Bot will delete number of messages specified (excluding the command) 
        '''
        user_roles = ctx.author.roles
        mod_role = ctx.guild.get_role(self.MOD_ROLE_ID)

        if mod_role not in user_roles:
            await ctx.send(
                f'{ctx.author.mention} this command is only usable by moderator.')
        else:
            await ctx.channel.purge(limit=int(num_messages) + 1)
            await ctx.channel.send('Woof, woof! Wiped!'.format(ctx))

    @commands.command()
    async def copy(self, ctx, id):
        '''
        Bot will send a copy of a specified message (by ID) 
        '''
        user_roles = ctx.author.roles
        mod_role = ctx.guild.get_role(self.MOD_ROLE_ID)

        if mod_role not in user_roles:
            await ctx.send(f'{ctx.author.mention} this command is only usable by moderator.')
        else:
            message = await ctx.channel.fetch_message(id)
            await ctx.send(message.content)

def setup(bot):
    bot.add_cog(BotContext(bot)) 
    