import discord
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from prettytable import PrettyTable
from collections.abc import Sequence
import pprint

# https://developers.google.com/sheets/api/guides/concepts
# https://docs.google.com/spreadsheets/d/1y7MaMeZb-XkrvsGVlCYdAfKKdCRJ50TdyU6Tdry6e-o/edit#gid=0
# TODO: Create skeleton directing flow of application by an user wanting to rent, add, delete items.

key_file = 'secret_key.json'
scope =  ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scope)
client = gspread.authorize(creds)

class Storage(commands.Cog):

    '''
    Control commands to access the inventory on Gspread DB (Google Sheets)
    '''

    def __init__(self, bot):
        self.bot = bot
        self.inventory_requests = [] #users (IDs) trying to access inventory

    #Events
    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        Allows bot to reply to messages (additional to commands).
        Follow up on Inventory Request.
        '''
        author = message.author
        content = message.content
        channel = message.channel
        #print("Message detected! Properties are: ", author, content, channel)
        #print("Requests at start of detection: ", self.inventory_requests)
        if author.id != self.bot.user.id:
            pass

        request_index = 0        
        for user_with_request in self.inventory_requests: #traversing through list of authors that have made inv. requests
 
            if user_with_request  == author.id: 

                if content == '1':
                    sheet1 = client.open('Inventory').get_worksheet(0)
                    equipment = sheet1.get_all_records()
                    #print(equipment)
                    parsed_equipment = pretty_format(equipment)
                    await channel.send(f"{author.mention} here's a list of our equipment:\n```{parsed_equipment}```")
                    #print("Requests before popping off: ", self.inventory_requests)
                    self.inventory_requests.pop(request_index)
                elif content == '2':
                    sheet2 = client.open('Inventory').get_worksheet(1)
                    snacks = sheet2.get_all_records()
                    #print(snacks)
                    parsed_snacks = pretty_format(snacks)
                    await channel.send(f"{author.mention} here's a list of our snacks:\n```{parsed_snacks}```")
                    #print("Requests before popping off: ", self.inventory_requests)
                    self.inventory_requests.pop(request_index)
                elif content == 'cancel':
                    emoji = '\N{CROSS MARK}'
                    #print("Requests before popping off: ", self.inventory_requests)
                    self.inventory_requests.pop(request_index)
                    await channel.send(f"**{author.name}**, request cancelled. {emoji}")
                else:
                    emoji = '\N{Black Question Mark Ornament}'
                    await channel.send(f'Invalid inventory selection. {emoji}')                        
                

            request_index += 1

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        '''
        TODO: Allow e-board member to react in order to grant permission.
        '''
        print("Reaction by: " + str(user) + " & Target user is: " + str(self.target_user))
        if str(self.target_user) == str(user): 
            if reaction == 1:
                sheet1 = client.open('Inventory').get_worksheet(0)
                equipment = sheet1.get_all_records()
                print(equipment)
                await self.ctx.send(equipment)
            elif reaction == 2:
                sheet2 = client.open('Inventory').get_worksheet(1)
                snacks = sheet2.get_all_records()
                print(snacks)
                await self.ctx.send(snacks)
            else:
                await self.ctx.send('Invalid Inventory')
            
    #Commands
    @commands.command()
    async def inventory(self, ctx, arg=0):
        '''
        Calls for an inventory. If no argument is provided, bot will listen for next messages coming from user.
        '''
        if arg == 1:
            sheet1 = client.open('Inventory').get_worksheet(0)
            equipment = sheet1.get_all_records() #TODO: FIX format
            #print(equipment)
            parsed_equipment = pretty_format(equipment)
            await ctx.send(f"{ctx.author.mention} here's a list of our equipment:\n```{parsed_equipment}```")
        elif arg == 2:
            sheet2 = client.open('Inventory').get_worksheet(1)
            snacks = sheet2.get_all_records() #TODO: FIX format
            #print(snacks)
            parsed_snacks = pretty_format(snacks)
            await ctx.send(f"{ctx.author.mention} here's a list of our snacks:\n```{parsed_snacks}```")
        else:
            await ctx.send(f'Hey {ctx.author.mention}\n```Which inventory would you like to check?\n[1] Equipment\n[2] Snacks\n\nType the corresponding option number or "cancel"```')
            self.inventory_requests.append(ctx.author.id)


    # start user registration and rental process
    @commands.command()
    async def rent(self, ctx):

        # open registered users spreadsheet
        users_sheet = client.open('Registered Users').get_worksheet(0)

        # get discord tags
        registered_users = users_sheet.col_values(1)

        # convert to set for constant time contains checks operations - O(1)
        registered_users = set(registered_users)

        # get username as a string so it can be logged
        curr_user = str(ctx.author)

        # get user tag 
        curr_user_tag = curr_user[-4:]

        # always add at top of sheet so it works like a stack
        index = 2

        # inform user about incoming DM
        await ctx.send(f'Hey {ctx.author.mention}, take a look at your DMs :eyes:')

        # if user is new
        if(curr_user_tag not in registered_users):

            # list to log user information
            user_info = []

            # emoji for reaction
            emoji = '\N{THUMBS UP SIGN}'

            # initial message to ask for user information
            initial_message = (f'Hi {ctx.author.mention}! It seems like this is your first time requesting to rent out equipment from the UPE Makerspace. In order to rent out equipment, ' 
                    + 'I need you to provide me with your *First Name*, *Last Name*, and *PID*. ' 
                    + 'First, please enter your **First Name** and **Last Name** separated by spaces, (e.g. John Doe).')

            # send the initial message to the user
            send_initial_message = await ctx.author.send(initial_message)

            # wait for user response
            initial_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
            initial_response_trimmed =  initial_response.content.split(" ")
            initial_response_length = len(initial_response_trimmed)

            # perform user response validation
            while(initial_response_length < 2):
                error_message = ('Uh-oh! I seems that either your First Name or Last Name is missing. '
                                + 'Please make sure you include your **First Name** and **Last Name** ' 
                                + 'in your response separated by spaces, (e.g. John Doe).')
                await ctx.author.send(error_message)
        
                # wait for new user response
                initial_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                initial_response_trimmed = initial_response.content.split(" ")
                initial_response_length = len(initial_response_trimmed)
            
            # react to correct user response
            await initial_response.add_reaction(emoji)

            # log correct user's First Name and Last Name
            initial_response_trimmed = initial_response_trimmed[:2]
            user_info.extend(initial_response_trimmed)

            # send PID message to the user
            pid_message = "Thanks! Now please enter your **7-digit PID**, (e.g, 1231231)."
            send_pid_message = await ctx.author.send(pid_message)

            # wait for user response
            pid_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
            pid_length = len(pid_response.content)
            is_number = pid_response.content.isnumeric()

            while((pid_length < 7 or pid_length > 7) or is_number == False):
                error_message = ('Uh-oh! it seems that your PID is not valid. ' 
                                +'Please make sure you enter your **7-digit PID**, (e.g. 1231231).')
                await ctx.author.send(error_message)

                # wait for new user response
                pid_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                pid_length = len(pid_response.content)
                is_number = pid_response.content.isnumeric()

            # react to correct user response
            await pid_response.add_reaction(emoji)
            
            # log correct user's PID
            user_info.append(pid_response.content)

            # insert new row with new user information
            row = [curr_user_tag, user_info[0], user_info[1], user_info[2]]
            users_sheet.insert_row(row, index)

            inventory_message = 'Sweet!\n```Which inventory would you like to check?\n[1] Equipment\n[2] Snacks\n\nType the corresponding option number or "cancel"```'
            send_inventory_message = await ctx.author.send(inventory_message)

            # display list of available items
            #sendItemsMessage = await ctx.author.send(items_message)
            ###############-PROCEEED TO TAKE ITEM REQUEST-###################
        # if user has done the above already
        else:
            inventory_message = f'Hi {ctx.author.mention}, Welcome Back!\n```Which inventory would you like to check?\n[1] Equipment\n[2] Snacks\n\nType the corresponding option number or "cancel"```'
            send_inventory_message = await ctx.author.send(inventory_message)

        # display list of available items
        #sendItemsMessage = await ctx.author.send(items_message)
        
# auxiliary function for the message_check function to make a string sequence of the given parameter
def make_sequence(seq):
    if seq is None:
        return ()
    if isinstance(seq, Sequence) and not isinstance(seq, str):
        return seq
    else:
        return (seq,)

# function to make logical checks when receiving DMs
def message_check(channel=None, author=None, content=None, ignore_bot=True, lower=True):
    channel = make_sequence(channel)
    author = make_sequence(author)
    content = make_sequence(content)
    if lower:
        content = tuple(c.lower() for c in content)
    # check that the sender of DM is the same as the receiver of the original DM from bot
    def check(message):
        if ignore_bot and message.author.bot:
            return False
        if channel and message.channel not in channel:
            return False
        if author and message.author not in author:
            return False
        actual_content = message.content.lower() if lower else message.content
        if content and actual_content not in content:
            return False
        return True
    return check

# function to format spreadsheets to readable formats
def pretty_format(entries):
    table = PrettyTable() 
    table.field_names = entries[0].keys()

    for entry in entries:
        table.add_row(entry.values())

    return table

# cog setup in bot file
def setup(bot):
    bot.add_cog(Storage(bot))
