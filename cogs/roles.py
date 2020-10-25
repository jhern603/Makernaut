import discord
from discord.ext import commands

class Roles(commands.Cog):

    '''
    Behaviour of the bot and its sorroundings
    '''
    def __init__(self, bot):
        self.bot = bot

        #Channels
        self.BOT_LOGS_CHANNEL_ID = 746081458564890654
        self.log_channel = self.bot.get_channel(self.BOT_LOGS_CHANNEL_ID)

        #Messages
        self.RULES_ACCEPTANCE_MESSAGE_ID = 746080888571297853
        self.ROLE_ASSIGNMENT_MESSAGE_ID = 769952501386313728

        #Roles

        #Emojis
        self.emojis = {
            "RULES_ACCEPTANCE_EMOJI_NAME" :'\N{WHITE HEAVY CHECK MARK}',
            "WEB_INTEREST_EMOJI" : "<:web_dev:753272557800784024>",
            "AI_INTEREST_EMOJI" :"<:artificial_intelligence:753272557737607369>",
            "HARDWARE_INTEREST_EMOJI" : "<:robotics:753272557867761763>",
            "GAMING_INTEREST_EMOJI" : "<:partaaaay:682027649568342081>"
            }

    #Events
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        reacting_user = payload.member
        print("User " + reacting_user.name + " reacted with: " + payload.emoji.name)

        if payload.message_id == self.RULES_ACCEPTANCE_MESSAGE_ID:

            # User reacts on the appropiate message AND with the appropiate emoji
            if payload.emoji.name == self.emojis["RULES_ACCEPTANCE_EMOJI_NAME"]:
                # Sets the verified 'User' role
                verified_user_role = discord.utils.get(reacting_user.guild.roles, name="User")
                await reacting_user.add_roles(verified_user_role) 

                #Prints to console and notifies bot-log channel
                print("User " + reacting_user.name + " has read and accepted the rules!")
                await self.log_channel.send(f'{reacting_user.mention} has read and accepted the rules!')

        if payload.message_id == self.ROLE_ASSIGNMENT_MESSAGE_ID:

            if str(payload.emoji) == self.emojis["WEB_INTEREST_EMOJI"]:
                # Sets the verified 'Interested' role (placeholder)
                Placeholder_user_role = discord.utils.get(reacting_user.guild.roles, name="Interested")
                await reacting_user.add_roles(Placeholder_user_role) 

                #Prints to console and notifies bot-log channel
                print("User " + reacting_user.name + " is interested in something!")
                await self.log_channel.send(f'{reacting_user.mention} is interested in something! <a:pumpIt:439920250302103562>')

def setup(bot):
    bot.add_cog(Roles(bot)) 