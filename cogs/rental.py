import discord
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from prettytable import PrettyTable
from collections.abc import Sequence
import pprint

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
        self.bot = bot
        self.inventory_requests = [] #users (IDs) trying to access inventory


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

        # emoji for reaction
        emoji = '\N{THUMBS UP SIGN}'

        # emoji for cancelations
        cancel_emoji = '\N{CROSS MARK}'

        '''
        Function to start rental process for both new and already
        registered users. The process will almost identical for both
        and only thing that will change are the initial messages.
        '''
        async def start_rental_process(message):

            inventory_message = message
            send_inventory_message = await ctx.author.send(inventory_message)

            # wait for user response
            inventory_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
            user_selection = inventory_response.content
            is_number = user_selection.isnumeric()

            # user input validation for selected inventory
            while(user_selection.lower() != 'cancel'):

                if(is_number):
                    if(int(user_selection) >= 1 and int(user_selection) <= 2):
                        break

                error_emoji = '\N{Black Question Mark Ornament}'
                error_message = f'Invalid inventory selection. {error_emoji}' 
                await ctx.author.send(error_message)

                # wait for new user response
                inventory_response = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                user_selection = inventory_response.content
                is_number = user_selection.isnumeric()

            # react to correct user response
            user_selection = inventory_response.content
            if(user_selection != 'cancel'):
                await inventory_response.add_reaction(emoji)

            if(user_selection == '1'):
                sheet1 = client.open('Inventory').get_worksheet(0)
                
                # read entire spreadsheet as a list of lists
                all_values = sheet1.get_all_values()
                
                '''
                since we only want to display items and their quantities, only get these two to display
                to do this, I changed the all_values from a lists of dictionaries to a list of lists for
                better manipulation of individual entries
                '''
                equipment = []
                                
                for entry in all_values:
                        equipment.append(entry[:3])

                first_number = equipment[1][0]
                last_number = equipment[-1][0]

                parsed_equipment = pretty_format(equipment)

                # list to log user selection
                user_selection_info = []
                
                equipment_message = (f"{ctx.author.mention} here's a list of our equipment available for rent:\n```{parsed_equipment}``` \n"
                                    + "Please type the ID and quantity, separated by spaces, of the item(s) you wish to rent out, (e.g. 1 2) "
                                    + "for 2 ipads. Please note that you can only rent out up to **three** items at a time.")

                send_equipment_message = await ctx.author.send(equipment_message)
                
                #print("Requests before popping off: ", self.inventory_requests)
                #self.inventory_requests.pop(request_index)

                equipment_selection = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                user_selection = equipment_selection.content

                # check for cancellation
                if(user_selection.lower() == 'cancel'):
                    await ctx.author.send(f"You have cancelled your request. {cancel_emoji}")
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

                avl_item_quantity = None

                if(is_number and equipment_selection_length == 2 and 
                    (int(equipment_selection_trimmed[0]) >= int(first_number) 
                    and int(equipment_selection_trimmed[0]) <= int(last_number))):
                    # get row values from user selection
                    selected_item_row = sheet1.row_values(int(equipment_selection_trimmed[0]) + 1)

                    # get selected item
                    selected_item = selected_item_row[1] 

                    # get item's available quantity
                    avl_item_quantity = selected_item_row[2]

                    if(int(equipment_selection_trimmed[1]) > 3 or int(equipment_selection_trimmed[1]) > int(avl_item_quantity)):
                        can_take_this_many = False
        
                '''
                validate input - check that user only gave two selections, that user input is numeric, that selected quantity is valid,
                and that ID is valid
                '''
                while(equipment_selection_length < 2 or equipment_selection_length > 2 or is_number == False or can_take_this_many == False
                        or int(equipment_selection_trimmed[0]) < int(first_number) or int(equipment_selection_trimmed[0]) > int(last_number)):
                        
                    error_emoji = '\N{Black Question Mark Ornament}'
                    
                    error_message = ""
                    if(equipment_selection_length > 2):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type only the ID and the quantity of the item you wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")
                    elif(equipment_selection_length < 2):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type both the ID and the quantity of the item your wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")
                    elif(is_number == False):
                        error_message = (f'Invalid inventory selection {error_emoji} Please type a valid ID and quantity of the item your wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")
                    elif(int(equipment_selection_trimmed[0]) < int(first_number) or int(equipment_selection_trimmed[0]) > int(last_number)):
                        error_message = (f'Invalid inventory selection {error_emoji} Pl ease type a valid ID of the item your wish to rent out,'
                                        + "(e.g. 1 2) for 2 ipads.")

                    elif(is_number and equipment_selection_length == 2 and 
                        (int(equipment_selection_trimmed[0]) >= int(first_number) 
                        and int(equipment_selection_trimmed[0]) <= int(last_number))):

                        if(int(equipment_selection_trimmed[1]) > 3):
                            error_message = (f'Invalid inventory selection {error_emoji} You are only allowed to rent up to **three** items at a time.')
                
                        if(int(equipment_selection_trimmed[1]) > int(avl_item_quantity)):
                            error_message = (f'Invalid inventory selection {error_emoji} You are trying to rent out {equipment_selection_trimmed[1]} {selected_item}s ' 
                                            + f'but we only have {avl_item_quantity} available.')
                            can_take_this_many = False
                            
                    await ctx.author.send(error_message)

                    # wait for new user response
                    equipment_selection = await self.bot.wait_for('message', check=message_check(channel=ctx.author.dm_channel))
                    user_selection = equipment_selection.content

                    if(user_selection.lower() == 'cancel'):
                        break

                    # get user selection (ID and quantity)
                    equipment_selection_trimmed = user_selection.split(" ")
                    equipment_selection_length = len(equipment_selection_trimmed)

                    # logical flag to check for numeric values
                    is_number = True

                    for entry in equipment_selection_trimmed:
                        if(entry.isnumeric() == False):
                            is_number = False

                    # logical flag for selected rental quantity
                    can_take_this_many = True

                    if(is_number and equipment_selection_length == 2 and 
                        (int(equipment_selection_trimmed[0]) >= int(first_number) 
                        and int(equipment_selection_trimmed[0]) <= int(last_number))):
                        # get row values from user selection
                        selected_item_row = sheet1.row_values(int(equipment_selection_trimmed[0]) + 1)

                        # get selected item
                        selected_item = selected_item_row[1] 

                        # get item's available quantity
                        avl_item_quantity = selected_item_row[2]

                        if(int(equipment_selection_trimmed[1]) > 3 or int(equipment_selection_trimmed[1]) > int(avl_item_quantity)):
                            can_take_this_many = False

                # check for cancellation
                if(user_selection.lower() == 'cancel'):
                    await ctx.author.send(f"You have cancelled your request. {cancel_emoji}")
                    return

                # react to correct user response
                await equipment_selection.add_reaction(emoji)

                # log correct user selection
                user_selection_info.extend(equipment_selection_trimmed)

                # get row values from user selection
                selected_item_row = sheet1.row_values(int(equipment_selection_trimmed[0]) + 1)

                selected_item = selected_item_row[1]

                sin_or_plur = 's'
                if(int(user_selection_info[1]) == 1):
                    sin_or_plur = ''

                request_message = (f"Sweet! Your rental request for **{user_selection_info[1]}** **{selected_item}{sin_or_plur}** has been placed! "
                                + "I will notify one of our e-board members to review and accept your request. "
                                + "I promise they will get this done in no time! "
                                + "Once your request is accepted I will notify you so that you can go pick up your "
                                + "rental item at the UPE Makerspace. Thank you for letting me help you in this quest.")
                
                send_request_message = await ctx.author.send(request_message)
            
            else:
                #print("Requests before popping off: ", self.inventory_requests)
                #self.inventory_requests.pop(request_index)
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
        if(curr_user_tag not in registered_users):

            # list to log user information
            user_info = []

            # initial message to ask for user information
            initial_message = (f'Hi {ctx.author.mention}! It seems like this is your first time requesting to rent out equipment from the UPE Makerspace. In order to rent out equipment, ' 
                    + 'I need you to provide me with your *First Name*, *Last Name*, and *PID*. ' 
                    + 'First, please type your **First Name** and **Last Name** separated by spaces, (e.g. John Doe).')

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

            ##############################################################################
            #                                                                            #
            #                   IF USER HAD TO DO THE STEPS ABOVE                        #
            #         ========= START RENTAL PROCESS FOR NEW USER =========              #
            #                                                                            #
            ##############################################################################

            inventory_message = 'Sweet!\n```Which inventory would you like to check?\n\n[1] General Equipment\n\nPlease type the corresponding option number or "cancel"```'

            await start_rental_process(inventory_message)
            #print("Requests before popping off: ", self.inventory_requests)
            #self.inventory_requests.pop(request_index)

        ##############################################################################
        #                                                                            #
        #               IF USER HAS DONE THE STEPS ABOVE ALREADY                     #
        #   ========= START RENTAL PROCESS FOR ALREADY REGISTERED USER =========     #
        #                                                                            #
        ##############################################################################
        
        else:
                inventory_message = (f'Hi {ctx.author.mention}, Welcome Back!\n```Which inventory would you like to check?'+
                                '\n[1] Equipment\n\nPlease type the corresponding option number or "cancel"```')

                await start_rental_process(inventory_message)

                #print("Requests before popping off: ", self.inventory_requests)
                #self.inventory_requests.pop(request_index)

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
def pretty_format(entries):
    table = PrettyTable() 
    table.field_names = entries[0]

    for entry in entries[1:]:
        table.add_row(entry)

    return table

# cog setup in bot file
def setup(bot):
    bot.add_cog(Rental(bot))