from discord.ext import commands
from discord.ext.commands import MemberConverter, UserConverter
from oauth2client.service_account import ServiceAccountCredentials
from prettytable import PrettyTable
from collections.abc import Sequence
from time import localtime, strftime
from collections import deque
from datetime import timedelta, date

import asyncio
import pprint
import gspread
import discord
import datetime

# https://developers.google.com/sheets/api/guides/concepts
# https://docs.google.com/spreadsheets/d/1y7MaMeZb-XkrvsGVlCYdAfKKdCRJ50TdyU6Tdry6e-o/edit#gid=0
# https://docs.google.com/spreadsheets/d/19F9BQMQD-EOhl_oupPd8xXM_3ZZmUaQ0a9pwO-sksjg/edit#gid=0
# TODO: Create skeleton directing flow of application by an user wanting to rent, add, delete items.

key_file = 'secret_key.json'
scope =  ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scope)
client = gspread.authorize(creds)

class Rental(commands.Cog):

    '''
    Control commands to access the inventory on Gspread DB (Google Sheets)

    '''

    def __init__(self, bot):

        #instance variables
        self.bot = bot
        self.equipment_requests_queue = deque()
        self.active_requests_queue = deque()
        self.converter = MemberConverter()
        self.user_converter = UserConverter()

        self.registered_users = dict()

        # open registered users spreadsheet
        USERS_WORKSHEET = 2
        self.users_sheet = client.open('Inventory').get_worksheet(USERS_WORKSHEET)
        self.all_reg_users = self.users_sheet.get_all_values()

        row = 2
        for entry in self.all_reg_users[1:]:
            user_id = self.users_sheet.cell(row, 1, value_render_option='FORMULA').value
            self.registered_users[user_id] = entry[1:]
            row += 1

        self.my_user_id = "267374448720609281"

        self.initial_response = None
        self.initial_response_trimmed = None  
        self.initial_response_length = 0 

        self.pid_response = None
        self.pid_length = 0

        self.inventory_selection = None
        self.user_selection = None
        self.is_number = None
        self.is_cancelled = None
        
        self.equipment_selection = None
        self.equipment_selection_length = 0
        self.equipment_selection_trimed = None
        self.item_id = None
        self.item_quantity = 0 
        self.can_take_this_many = None
        self.avl_item_quantity =0
        self.selected_item = None

    # start user registration and rental process
    @commands.command()
    async def rent(self, ctx):

        # constants
        ID_INDEX = 0
        QUANT_INDEX = 1
        NEEDED_LENGTH = 2
        FIRST_INV = 1
        UP_ONE = 1
        ITEM_INDEX = 1
        MAX_REQUESTS = 3
        FIRST_THREE_ITEMS = 3
        FIRST_ENTRY = 0
        SECOND_LIST = 1
        LAST_LIST = -1
        ROW_INDEX = 2
        RENT_INDEX = 3
        PID_MAX_LEN = 7
        LOGISTICS_CHNL_ID = 711296973512114226
        MAX_DAYS = 2
        
        # contants for rent queue
        R_ITEM_INDEX = 0
        R_QUANT_INDEX = 1
        R_DATE_INDEX = 2
        R_FN_INDEX = 3
        R_LN_INDEX = 4
        R_PID_INDEX = 5

        # contants for spreadsheet worksheets
        EQUIP_WORKSHEET = 0
        RENTAL_WORKSHEET = 3
        FIRST_COL_INDEX = 1
        HEADER_INDEX = 0
        FN_INDEX = 0
        LN_INDEX = 1
        PID_INDEX = 2

        # get user ID to use as key for DB
        curr_user_id = float(ctx.author.id)
    
        # emoji for accept reaction
        accept_emoji = '\N{THUMBS UP SIGN}'

        # emoji for reject reaction
        reject_emoji = '\N{THUMBS DOWN SIGN}'

        # emoji for cancelations
        cancel_emoji = '\N{CROSS MARK}'

        '''
        Function to start rental process for both new and already
        registered users. The process will almost identical for both
        and only thing that will change are the initial messages.
        '''
        async def start_rental_process(message):

            # we need to ask the user to selection which inventory to explore
            inventory_message = message
            await ctx.author.send(inventory_message)

            async def extract_user_inv_selection():
                # wait for user response*
                inventory_selection = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                user_selection = inventory_selection.content

                # logical flag to check that user typed a number
                is_number = user_selection.isnumeric()
                
                # update corresponding instance variable 
                self.inventory_selection = inventory_selection
                self.user_selection = user_selection
                self.is_number = is_number
                
            await extract_user_inv_selection()
            
            # user input validation for selected inventory
            while(self.user_selection.lower() != 'cancel'):
                
                # we only want the user to put the number of corresponding inventory
                if(self.is_number):
                    if(int(self.user_selection) >= FIRST_INV and int(self.user_selection) <= FIRST_INV):
                        break
                    
                error_emoji = '\N{Black Question Mark Ornament}'
                error_message = f'Invalid inventory selection. {error_emoji}' 
                await ctx.author.send(error_message)

                # we need to try again if input is not valid
                await extract_user_inv_selection()
    
            # in case user decides to cancel request
            if(self.user_selection != 'cancel'):
                await self.inventory_selection.add_reaction(accept_emoji)

            # continue rental process otherwise
            if(self.user_selection == '1'):
                equipment_sheet = client.open('Inventory').get_worksheet(EQUIP_WORKSHEET)

                # read entire spreadsheet as a list of lists
                inventory_items = equipment_sheet.get_all_values()
                
                '''
                since we only want to display IDs and items and their quantities, only get these two to display.
                I changed the all_values from a lists of dictionaries to a list of lists for
                better manipulation of individual entries
                '''
                equipment = []

                for entry in inventory_items:
                        equipment.append(entry[:FIRST_THREE_ITEMS])

                # we need to record the first and last entries on the spreadsheet for input validation
                first_number = int(equipment[SECOND_LIST][FIRST_ENTRY])
                last_number = int(equipment[LAST_LIST][FIRST_ENTRY])

                parsed_equipment = pretty_format(equipment, HEADER_INDEX, FIRST_COL_INDEX)

                # list to log user selection
                user_selection_info = []
                
                equipment_message = (f"Here's a list of our equipment available for rent:\n\n```{parsed_equipment}``` \n"
                                    + "Please type the ID and quantity, separated by spaces, of the item(s) you wish to rent out, (e.g. 1 2) "
                                    + "for 2 ipads. Please note that you can only rent out up to **three** items at a time.")

                await ctx.author.send(equipment_message)


                async def extract_user_req_selection():

                    # We first we get the initial message from then user and extract its contents to then do validation on it
                    equipment_selection = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                    user_selection = equipment_selection.content

                    self.is_cancelled = False

                    # check for user cancellation
                    if(user_selection.lower() == 'cancel'):
                        self.user_selection = user_selection
                        return

                    # get user selection (ID and quantity)
                    equipment_selection_trimmed =  user_selection.split(" ")
                    equipment_selection_length = len(equipment_selection_trimmed)
                                    
                    # logical flag to check for numeric values
                    is_number = True

                    for entry in equipment_selection_trimmed:
                            if(entry.isnumeric() == False):
                                is_number = False

                    # logical flag for selected rental quantity
                    can_take_this_many = True
                    
                    # We are initializing variables for local scope
                    avl_item_quantity = 0
                    selected_item = None
                    item_id = 0
                    item_quantity = 0

                    if(is_number and equipment_selection_length == NEEDED_LENGTH):

                        item_id = int(equipment_selection_trimmed[ID_INDEX])
                        item_quantity = int(equipment_selection_trimmed[QUANT_INDEX])

                        if(item_id >= first_number and item_id <= last_number):

                            '''

                            Since the first row of the spread contains the keys, we need
                            to start at the following row (i.e row 2), so we add one to
                            the given ID, which represents the given row.

                            '''
                            selected_item_row = equipment_sheet.row_values(item_id + UP_ONE)

                            # get selected item
                            selected_item = selected_item_row[ITEM_INDEX] 

                            # get item's available quantity
                            avl_item_quantity = int(selected_item_row[QUANT_INDEX + UP_ONE])

                            if(item_quantity > MAX_REQUESTS or item_quantity > avl_item_quantity):
                                can_take_this_many = False
                    
                    # update corresponding instance vairables
                    self.equipment_selection = equipment_selection
                    self.user_selection = user_selection
                    self.equipment_selection_length = int(equipment_selection_length)
                    self.equipment_selection_trimed = equipment_selection_trimmed
                    self.item_id = item_id
                    self.item_quantity = int(item_quantity) 
                    self.can_take_this_many = can_take_this_many
                    self.avl_item_quantity = int(avl_item_quantity)
                    self.selected_item = selected_item
                    self.is_number = is_number
                  
                await extract_user_req_selection()

                if(self.user_selection.lower() == 'cancel'):
                    await ctx.author.send(f"You have cancelled your request. {cancel_emoji}")
                    return
                
                '''
                validate input - check that user only gave two selections, that user input is numeric, that selected quantity is valid,
                and that ID is valid
                '''
                while(self.equipment_selection_length < NEEDED_LENGTH or self.equipment_selection_length > NEEDED_LENGTH 
                        or self.is_number == False or self.can_take_this_many == False
                        or self.item_id < first_number or self.item_id > last_number):

                    error_emoji = '\N{Black Question Mark Ornament}'
                    
                    error_message = ""
                    if(self.equipment_selection_length > 2):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type only the ID and the quantity of the item you wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")
                    elif(self.equipment_selection_length < 2):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type both the ID and the quantity of the item your wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")
                    elif(self.is_number == False):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type a valid ID and quantity of the item your wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")
                    elif(self.item_id < first_number or self.item_id > last_number):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type a valid ID of the item your wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")

                    elif(self.is_number and self.equipment_selection_length == NEEDED_LENGTH and 
                        self.item_id >= first_number and self.item_id <= last_number):

                        if(self.item_quantity> MAX_REQUESTS):
                            error_message = (f'Invalid inventory selection {error_emoji} You are only allowed to rent up to **three** items at a time.')
                
                        if(self.item_quantity > self.avl_item_quantity):
                            error_message = (f'Invalid inventory selection {error_emoji} You are trying to rent out {self.item_quantity} {self.selected_item}s ' 
                                            + f'but we only have {self.avl_item_quantity} available.')
                            self.can_take_this_many = False
                            
                    await ctx.author.send(error_message)
                    await extract_user_req_selection()

                    if(self.user_selection.lower() == 'cancel'):
                        await ctx.author.send(f"You have cancelled your request. {cancel_emoji}")
                        return

                # react to correct user response
                await self.equipment_selection.add_reaction(accept_emoji)

                # for entries in all_users:
                #    if(int(entries.get('User ID')) == int(curr_user_id)):
                #        user_pid = str(entries.get('PID'))
                #        break
                
                # rentals_sheet = client.open('Inventory').get_worksheet(RENTAL_WORKSHEET)

                # cell_list = rentals_sheet.findall(user_pid)

                # log correct user selection
                user_selection_info.extend(self.equipment_selection_trimed)

                # get row values from user selection
                selected_item_row = equipment_sheet.row_values(self.item_id + UP_ONE)

                selected_item = selected_item_row[ITEM_INDEX]
                selected_quantity = int(user_selection_info[QUANT_INDEX])

                sin_or_plur = 's'
                if(selected_quantity == UP_ONE):
                    sin_or_plur = ''

                # get rental summary information
                rental_info = []

                # We need to document the rent details first                
                rental_info.append(selected_item)
                rental_info.append(selected_quantity)
                curr_time = strftime("%b %d, %Y at %I:%M %p", localtime())
                rental_info.append(curr_time)

                for key in self.registered_users:
                    if(key == curr_user_id):
                        rental_info.append(self.registered_users.get(key)[FN_INDEX])
                        rental_info.append(self.registered_users.get(key)[LN_INDEX])
                        rental_info.append(self.registered_users.get(key)[PID_INDEX])
                        break

                # log request into request queue
                self.equipment_requests_queue.append(rental_info)

                # inform the user that request has been placed and awaits confirmation
                rental_request_message = (f'Sweet!\n\nYour rental request for **{selected_quantity}** **{selected_item}{sin_or_plur}** has been placed! '
                                + 'I will notify one of our e-board members to review and accept your request. '
                                + 'I promise they will get this done in no time! '
                                + 'Once your request is accepted I will notify you so that you can go pick up your '
                                + f'rental item{sin_or_plur} at *La Villa*. Thank you for letting me help you in this quest.')
                
                await ctx.author.send(rental_request_message)

                # we need to make sure an authorizer accepts user requests
                authorizer = None

                # we need to pop queue right after insertion
                head_request = self.equipment_requests_queue.popleft()
                
                #first_line = right_justified('Requested Item:', f'**{head_request[R_ITEM_INDEX]}**')
                #second_line = right_justified('Requested Quantity:', f'**{head_request[R_QUANT_INDEX]}**')
                #third_line = right_justified('Requested On:', f'**{head_request[R_DATE_INDEX]}**')
                #fourth_line = right_justified('Requested by:', f'**{head_request[R_FN_INDEX]} {head_request[R_LN_INDEX]}**')
                #fifth_line = right_justified('Requester PID:', f'**{head_request[R_PID_INDEX]}**')

                embed = discord.Embed(title='Request Details', colour=0xB6862C)
                embed.add_field(name='Requested Item', value=f'**{head_request[R_ITEM_INDEX]}**', inline=False)
                embed.add_field(name='Requested Quantity', value=f'**{head_request[R_QUANT_INDEX]}**', inline=False)
                embed.add_field(name='Requested by', value=f'**{head_request[R_FN_INDEX]} {head_request[R_LN_INDEX]}**', inline=False)
                embed.add_field(name='Requester PID', value=f'**{head_request[R_PID_INDEX]}**', inline=False)
                embed.add_field(name='Requested On', value=f'**{head_request[R_DATE_INDEX]}**', inline=False)

                logistics_channel = self.bot.get_channel(LOGISTICS_CHNL_ID)

                rental_message = (f'Hellooo! :dog:\n\nI got a new rental request that needs your attention. '
                                 + f'You can accept this request by reacting to this message with a {accept_emoji}\n'
                                 + 'Please see the details below:\n\n')

                send_rental_message = await logistics_channel.send(rental_message, embed=embed)

                def check_emoji(reaction, user):
                    is_authorizer = False
                    for role in user.roles:
                        if role.name == 'Logistics':
                            is_authorizer = True

                    return is_authorizer and str(reaction.emoji) == accept_emoji
                    
                authorizer_reaction, authorizer = await self.bot.wait_for('reaction_add', check=check_emoji)

                # users that have reacted request message
                users = await authorizer_reaction.users(1).flatten()

                authorizer_id = None
                for user in users:
                    authorizer_id = user.id

                authorizer = await self.user_converter.convert(ctx, str(authorizer_id))

                authorizer_fn = None
                authorizer_ln = None
                # get name of rent authorizer
                for key in self.registered_users:
                    if(key == float(authorizer.id)):
                        authorizer_fn = self.registered_users.get(key)[FN_INDEX]
                        authorizer_ln = self.registered_users.get(key)[LN_INDEX]
                        rental_info.append(f'{authorizer_fn} {authorizer_ln}')
                        break

                today = date.today()

                start_date = today.strftime("%m/%d/%Y")
                start_date = datetime.datetime.strptime(start_date, "%m/%d/%Y")
                end_date = start_date + datetime.timedelta(days = MAX_DAYS)
                end_date = end_date.strftime("%b %d, %Y by 12:00 PM")
                
                confirmation_details = discord.Embed(title='Rental Details', colour=0x081E3F)
                confirmation_details.add_field(name='Item', value=f'```{head_request[R_ITEM_INDEX]}```', inline=False)
                confirmation_details.add_field(name='Quantity', value=f'```{head_request[R_QUANT_INDEX]}```', inline=False)
                confirmation_details.add_field(name='Due On', value=f'```{end_date}```', inline=False)

                rental_conf_message = (f'Hey {ctx.author.mention}!\n\nYour rental request for **{selected_quantity}** **{selected_item}{sin_or_plur}** '
                                       + f'is confirmed and your item{sin_or_plur} are ready to be picked up!\n\n'
                                       + f'Once you arrive at *La Villa*, look for **{authorizer_fn} {authorizer_ln}** to claim your item{sin_or_plur}. '
                                       + f'You will have until the date given below to pick up and use your item{sin_or_plur}. '
                                       + f'When you return your item{sin_or_plur}, please take a picture of the item{sin_or_plur} in the location where you dropped them off and '
                                       + 'send it my way! You can do this by using the "!return" command.\n\n'
                                       + 'Please see your rental details below:\n\n')
                
                await ctx.author.send(rental_conf_message, embed=confirmation_details)

                # once request has been confirmed log corresponding information onto requests section of spreadsheet
                rentals_sheet = client.open('Inventory').get_worksheet(RENTAL_WORKSHEET)

                # Make sure that request was accepted by e-board member
                if(authorizer_reaction.emoji == accept_emoji):

                    # insert new row with new rental
                    # always at the top of spreadsheet so it works as a stack
                    rentals_sheet.insert_row(rental_info, RENT_INDEX)

                    # log active request
                    self.active_requests_queue.append(head_request)

                    # only want to update corresponding cell
                    cell_to_update = equipment_sheet.find(selected_item)
                
                    # We need to udpate the corresponding values for the borrowed item on the spreadsheet
                    equipment_sheet.update_cell(cell_to_update.row, int(cell_to_update.col) + UP_ONE, int(self.avl_item_quantity) - selected_quantity)

            else:
                await ctx.author.send(f"You have cancelled your request. {cancel_emoji}")
                return

        ##############################################################################
        #                                                                            #
        #           ========= END OF START_RENTAL_PROCESS() =========                #
        #                                                                            #
        ##############################################################################

        # inform user about incoming DM
        # check if rent command was invoked from bot channel
        current_channel = str(ctx.message.channel)
        if(current_channel == 'bot-spam'):

            # inform user of incoming DM
            await ctx.send(f'Hey {ctx.author.mention}, check your DMs :eyes:')

        # if user is new
        if(curr_user_id not in self.registered_users):

            # list to log user information
            user_info = []

            # initial message to ask for user information
            initial_message = (f'Hey {ctx.author.mention}!\n\nIt seems like this is your first time requesting to rent out equipment from the UPE Makerspace. In order to rent out equipment, ' 
                    + 'I need you to provide me with your *First Name*, *Last Name*, and *PID*. ' 
                    + 'First, please type your **First Name** and **Last Name** separated by spaces, (e.g. John Doe).')

            async def extract_user_info(message):
                
                # send the initial message to the user
                await ctx.author.send(message)

                async def extract_user_response():
                    # wait for user response
                    initial_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                    initial_response_trimmed = initial_response.content.split(" ")
                    initial_response_length = len(initial_response_trimmed)

                    self.initial_response = initial_response
                    self.initial_response_trimmed = initial_response_trimmed
                    self.initial_response_length = initial_response_length

                await extract_user_response()

                # perform user response validation
                while(self.initial_response_length < NEEDED_LENGTH):
                    error_message = ('Uh-oh! I seems that either your First Name or Last Name is missing. '
                                    + 'Please make sure you include your **First Name** and **Last Name** ' 
                                    + 'in your response separated by spaces, (e.g. John Doe).')
                    
                    await ctx.author.send(error_message)
                    await extract_user_response()

                # react to correct user response
                await self.initial_response.add_reaction(accept_emoji)

                # log correct user's First Name and Last Name
                self.initial_response_trimmed = self.initial_response_trimmed[:NEEDED_LENGTH]
                user_info.extend(self.initial_response_trimmed)

                # send PID message to the user
                pid_message = "Thanks!\n\nNow, please type your **7-digit PID**, (e.g, 1231231)."
                await ctx.author.send(pid_message)

                async def extract_user_pid():
                    # wait for user response
                    pid_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                    pid_length = len(pid_response.content)
                    is_number = pid_response.content.isnumeric()

                    self.pid_response = pid_response
                    self.pid_length = pid_length
                    self.is_number = is_number
                
                await extract_user_pid()

                # perform PID validation
                while((self.pid_length < PID_MAX_LEN or self.pid_length > PID_MAX_LEN) or self.is_number == False):
                    error_message = ('Uh-oh! it seems that your PID is not valid. ' 
                                    +'Please make sure you type your **7-digit PID**, (e.g. 1231231).')

                    await ctx.author.send(error_message)
                    await extract_user_pid()

                await self.pid_response.add_reaction(accept_emoji)
                
                # log correct user's PID
                user_info.append(self.pid_response.content)

                ##############################################################################
                #                                                                            #
                #                   IF USER HAD TO DO THE STEPS ABOVE                        #
                #         ========= START RENTAL PROCESS FOR NEW USER =========              #
                #                                                                            #
                ##############################################################################

                confirmation_message = ('Awesome!\n\nNow, just to check I got everything right, can you please confirm the information below is correct?\n\n'
                                        +f'```Your First Name: {user_info[FN_INDEX]}\nYour Last Name: {user_info[LN_INDEX]}\nYour PID: {user_info[PID_INDEX]}```\n'
                                        +f'Confirm by reacting to this message with a {accept_emoji} or a {reject_emoji} to change your information.')

                send_conf_message = await ctx.author.send(confirmation_message)

                def check_emoji(reaction, user):
                    return user == ctx.author and (str(reaction.emoji) == accept_emoji or str(reaction.emoji) == reject_emoji)
                    
                confirmation_response, ctx.author = await self.bot.wait_for('reaction_add', check=check_emoji)

                if(confirmation_response.emoji == accept_emoji):
                    return True
                elif(confirmation_response.emoji == reject_emoji):
                    await send_conf_message.delete()
                    return False
                
            user_confirmation = await extract_user_info(initial_message)

            while(user_confirmation == False):
                message = "Let's do this again. Please type your **First Name** and **Last Name** separated by spaces, (e.g. John Doe)."

                user_confirmation = await extract_user_info(message)


             # insert new row with new user information and log info into dictionary
            self.registered_users[curr_user_id] = user_info
            row = [curr_user_id, user_info[FN_INDEX], user_info[LN_INDEX], user_info[PID_INDEX]]
            self.users_sheet.insert_row(row, ROW_INDEX)

            inventory_message = 'Sweet!\n\nWhich inventory would you like to check?\n\n```[1] General Equipment```\n\nPlease type the corresponding option number or "cancel"'

            await start_rental_process(inventory_message)

        ##############################################################################
        #                                                                            #
        #               IF USER HAS DONE THE STEPS ABOVE ALREADY                     #
        #   ========= START RENTAL PROCESS FOR ALREADY REGISTERED USER =========     #
        #                                                                            #
        ##############################################################################
        
        else:
            inventory_message = (f'Hi {ctx.author.mention}, Welcome Back!\n\nWhich inventory would you like to check?'+
                            '\n\n```[1] General Equipment```\n\nPlease type the corresponding option number or "cancel"')

            await start_rental_process(inventory_message)

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

# function to format spreadsheets to readable a format
def pretty_format(entries, header_index=None, column_index=None):
    table = PrettyTable() 
    table.field_names = entries[header_index]

    for entry in entries[column_index:]:
        table.add_row(entry)

    return table

# function for right text justification
def right_justified(first, second):

    def add_spacing(quantity, message):
        return (' ' * quantity) + message
        
    needed_spaces = len(first)
    max_length = 45
    second = add_spacing(max_length - needed_spaces, second)
    new_line = f'{first}{second}'
    
    return new_line

# cog setup in bot file
def setup(bot):
    bot.add_cog(Rental(bot))