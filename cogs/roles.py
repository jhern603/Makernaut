import discord
from discord.ext import commands

class Roles(commands.Cog):

    '''
    Behaviour of the bot and its sorroundings
    '''

    RULES_ACCEPTANCE_MESSAGE_ID = 745965523954565151
    GREETINGS_CHANNEL_ID = 745967282286493727
    ACCEPTANCE_EMOJI_NAME = '\N{WHITE HEAVY CHECK MARK}'
    USER_ROLE_ID = 745322343739686943

    def __init__(self, bot):
        self.bot = bot
        self.RULES_ACCEPTANCE_MESSAGE_ID = 745965523954565151
        self.GREETINGS_CHANNEL_ID = 745967282286493727
        self.ACCEPTANCE_EMOJI_NAME = '\N{WHITE HEAVY CHECK MARK}'
        
    #Events
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        aspiring_verified_user = payload.member
        print("Reaction added: " + payload.emoji.name + " by user: " + aspiring_verified_user.name)

        verified_user_role = discord.utils.get(aspiring_verified_user.guild.roles, name="User")

        if payload.message_id == self.RULES_ACCEPTANCE_MESSAGE_ID and payload.emoji.name == self.ACCEPTANCE_EMOJI_NAME:
            await aspiring_verified_user.add_roles(verified_user_role)
            print("User " + payload.emoji.name + " is now verified!")

def setup(bot):
    bot.add_cog(Roles(bot)) 