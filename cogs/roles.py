import discord
from discord.ext import commands

class Roles(commands.Cog):

    '''
    Behaviour of the bot and its sorroundings
    '''
    def __init__(self, bot):
        self.bot = bot
        self.RULES_ACCEPTANCE_MESSAGE_ID = 746080888571297853
        self.GREETINGS_CHANNEL_ID = 746081458564890654
        self.ACCEPTANCE_EMOJI_NAME = '\N{WHITE HEAVY CHECK MARK}'
        
    #Events
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        aspiring_verified_user = payload.member
        print("Reaction added: " + payload.emoji.name + " by user: " + aspiring_verified_user.name)

        verified_user_role = discord.utils.get(aspiring_verified_user.guild.roles, name="User")
        greetings_channel = self.bot.get_channel(self.GREETINGS_CHANNEL_ID)

        if payload.message_id == self.RULES_ACCEPTANCE_MESSAGE_ID and payload.emoji.name == self.ACCEPTANCE_EMOJI_NAME:
            await aspiring_verified_user.add_roles(verified_user_role)
            # TODO: Confirm that user actually got assigned 'verified' role before sending confirmation on greetings-channel
            # await greetings_channel.send(f'{aspiring_verified_user.mention} read the rules!')
            # print(verified_user_role)
            # print(aspiring_verified_user.roles)
            # if verified_user_role in aspiring_verified_user.roles:
            print("User " + aspiring_verified_user.name + " is now verified!")
            await greetings_channel.send(f'{aspiring_verified_user.mention} is now verified!')

def setup(bot):
    bot.add_cog(Roles(bot)) 