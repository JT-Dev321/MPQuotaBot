from ..imports import *

        
class quota(commands.GroupCog, group_name='quota', group_description='Manage quotas'):
    def __init__(self, bot):
        self.bot = bot
    class parse_data_modal(ui.Modal, title = 'Data parser'):
        def __init__(self, bot, log : bool):
            super().__init__()
            self.log = log
            self.bot = bot

        data = ui.TextInput(label = 'Data', style = discord.TextStyle.paragraph, required = True)
        
        async def on_submit(self, interaction: discord.Interaction) -> None:
            await interaction.response.defer(thinking=True, ephemeral=True)
            splitData = self.data.value.split('\n')
            print_green("Hi")
            quotaDict = {}
            
            if "Marketplace Tickets:" in str(self.data.value):
                for i in range(0, len(splitData), 7):
                    quotaDict.update({f"{splitData[i]}" : [int(splitData[i+4].split(': ')[1]), int(splitData[i+5].split(': ')[1])]})
                
                output = ""
                
                monday = ""
                for i in range(-9,0):
                    dt = datetime.now() + timedelta(days=i)
                    if dt.weekday() == 0:
                        monday = f'{dt.year}-{dt.month}-{dt.day}'
                        break
                    
                for name in quotaDict:
                    if not self.log:
                        output += f"`/quota log staff_member:{interaction.guild.get_member_named(name).id} post_count:{quotaDict[name][0]} ticket_count:{quotaDict[name][1]} week_start: `\n"
                    else:
                        #print_green(f"Would log {name} with {quotaDict[name][0]} posts and {quotaDict[name][1]} tickets")
# async def logQuota(self, staff_member : discord.Member, logger : discord.Member, post_count : int, ticket_count : int, week_start : str, activity : bool = None, override_excused : bool = False, apply_rewards : bool = True, auto_strike : bool = True, override_existing : bool = False, dm_user : bool = True):
                        
                        
                            
                        activity = await self.bot.IsSenior(interaction.guild.get_member_named(name))
                        if activity == False:
                            activity = None
                        output += f"{interaction.guild.get_member_named(name).mention} - " + await self.bot.logQuota(interaction.guild.get_member_named(name),
                                                interaction.user,
                                                quotaDict[name][0],
                                                quotaDict[name][1],
                                                monday,
                                                activity) + "\n\n"
            else:
                for i in range(0, len(splitData), 6):
                    quotaDict.update({f"{splitData[i]}" : int(splitData[i+4].split(': ')[1])})
            
                output = ""
                
                for name in quotaDict:
                    if not self.log:
                        output += f"`/quota log staff_member:{interaction.guild.get_member_named(name).id} post_count:{quotaDict[name]} ticket_count:0 week_start: `\n"
                    else:
                        print_green(f"Would log {name} with {quotaDict[name]} posts")
                        # await self.bot.logQuota()
            if output != "":
                await interaction.followup.send(output, ephemeral=True)
    
    @app_commands.command(name = "get_date", description='Get the dates of the next inspection period')
    async def get_date(self, interaction: discord.Interaction):
        mondays = []
        for i in range(-9,0):
            dt = datetime.now() + timedelta(days=i)
            if dt.weekday() == 0:
                mondays.append(f"{dt.month}/{dt.day}/{dt.year}|{abs(i)}")
            
        output = ""
        for m in mondays:
            date = str(m).split("|")[0]
            i = str(m).split("|")[1]
            output += f"`{date}` was `{i}` days ago\n"
        
        await interaction.response.send_message(f"{output}", ephemeral=True)

    @app_commands.command(name = "parsedata", description='Parse data')
    async def parseData(self, interaction: discord.Interaction, log : bool):
        await interaction.response.send_modal(self.parse_data_modal(self.bot, log))
        
    @app_commands.command(name = "set", description='Set a quota')
    @app_commands.checks.has_role(role_ids.management)
    async def set_quota(self, interaction: discord.Interaction, role : str, value : int):
        prev = await self.bot.get_variable(role)
        await self.bot.set_variable(role, value)
        
        await interaction.response.send_message(f"Changed quota for `{role}` from `{prev}` to `{value}`", ephemeral=True)

    @app_commands.command(name = "inactivity_add", description='Add a user to inactivity')
    @app_commands.checks.has_role(role_ids.management)
    async def inactivity_add(self, interaction: discord.Interaction, inspection_count : int, staff_member : discord.Member = None, role : discord.Role = None):
        async with aiosqlite.connect(database) as db:
            if staff_member is not None:
                await db.execute('INSERT OR REPLACE INTO Excused (StaffID, InspectionCount) VALUES (?, ?)', (staff_member.id, inspection_count))
            elif role is not None:
                for id in [i.id for i in role.members]:
                    await db.execute('INSERT OR REPLACE INTO Excused (StaffID, InspectionCount) VALUES (?, ?)', (id, inspection_count))
            await db.commit()
            await interaction.response.send_message("Successfully added!", ephemeral=True)
        
    @app_commands.command(name = "inactivity_view", description='View all active inactivity notices.')
    @app_commands.checks.has_role(role_ids.management)
    async def inactivity_view(self, interaction: discord.Interaction):
        async with aiosqlite.connect(database) as db:
            async with db.execute('SELECT StaffID, InspectionCount FROM Excused WHERE InspectionCount > 0') as cursor:
                results = await cursor.fetchall()
        
        output = f"Total: `{len(results)}`\n\n"
        
        for row in results:
            output += f"- <@{row[0]}> - `{row[1]}`\n"
        
        await interaction.response.send_message(embed=discord.Embed(title = f"Current Inactivity Notices", description=output, colour=colours.mp_purple), ephemeral=True)
        
    @app_commands.command(name = "log", description='Log a quota for an individual')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week", activity="Senior Only", override_excused="Use to override excused", apply_rewards="Default: True", auto_strike="Default: True", override_existing="Default: False", dm_user="Default: True")
    async def logQuota(self, interaction: discord.Interaction, staff_member : discord.Member, post_count : int, ticket_count : int, week_start : str, activity : bool = None, override_excused : bool = False, apply_rewards : bool = True, auto_strike : bool = True, override_existing : bool = False, dm_user : bool = True):
        await interaction.response.defer(thinking=True, ephemeral=True)
        # all wrong to do with senior quota (post count)
        reward_excused = False
        striked = False
        Is_Senior = await self.bot.IsSenior(staff_member)
        
        # work out the target users quota requirement
        requirement = 0
        ticketrequirement = 0
        if Is_Senior:
            requirement = await self.bot.getSeniorQuota()
            ticketrequirement = await self.bot.getSeniorTicketQuota()
        elif await self.bot.IsIntern(staff_member):
            requirement = await self.bot.getInternQuota()
        else:
            requirement = await self.bot.getQuota()

        # check if inspector is a senior
        if not await self.bot.IsSenior(interaction.user):
            await interaction.followup.send("Only seniors can do this >:(", ephemeral=True)
            return

        #ensure valid date
        if not await self.bot.CheckValidDate(week_start):
            await interaction.followup.send("Please enter a valid date", ephemeral=True)
            return

        # checks if theyre a senior but the activity param is empty (somethings wrong)
        if Is_Senior and activity == None: 
            await interaction.followup.send("The user you are logging is a senior - You need to fill in the activity parameter", ephemeral=True)
            return

        # checks if someone is trying to record activity for a non-senior
        if not Is_Senior and activity != None:
            await interaction.followup.send("Do not log activity for a non-senior!", ephemeral=True)
            return

        # ensure users quota hasnt already been recorded for that week
        existing_quota = None
        if not Is_Senior:
            async with aiosqlite.connect(database) as db:
                async with db.execute('SELECT InspecteeID FROM Inspections WHERE WeekStart=? AND InspecteeID=?', (week_start,staff_member.id)) as cursor:
                    existing_quota = await cursor.fetchone()
        else:
            async with aiosqlite.connect(database) as db:
                async with db.execute('SELECT InspecteeID FROM SeniorInspections WHERE WeekStart=? AND InspecteeID=?', (week_start,staff_member.id)) as cursor:
                    existing_quota = await cursor.fetchone()
        if existing_quota != None and not override_existing:
            await interaction.followup.send(f"This user already has a quota recorded for this week (`{week_start}`)", ephemeral=True)
            return

        # Excused
        excused = False
        if not override_excused and post_count < requirement:
            async with aiosqlite.connect(database) as db:
                async with db.execute('SELECT StaffID FROM Excused WHERE InspectionCount > 0 AND StaffID = ?', (staff_member.id,)) as cursor:
                    row = await cursor.fetchone()
                if row is not None:
                    excused = True
                    await db.execute('UPDATE Excused SET InspectionCount = InspectionCount - 1 WHERE StaffID = ?', (staff_member.id,))
                    await db.commit()
        elif override_excused:
            excused = True
        
        # REWARDS
        if apply_rewards and not excused and post_count < requirement and not Is_Senior:
            async with aiosqlite.connect(database) as db: # get rewards
                async with db.execute('SELECT ID, Type, DateGiven, Charges FROM Rewards WHERE RecipientID=? AND Charges > 0', (staff_member.id,)) as cursor:
                    results = await cursor.fetchall()
            
            valid_rewards = []
            
            for r in results:
                date = str(r[2]).split("-")
                dt = datetime(int(date[0]), int(date[1]), int(date[2]))
                if dt > datetime.now() - timedelta(days=31):
                    valid_rewards.append(r)
            
            if len(valid_rewards) > 0: # consume reward if applicable
                for i in range(2):
                    for reward in valid_rewards:
                        # 2 ifs so if half doesnt make them pass and they have an excused, then the excused will activate
                        if i == 0: # check all the halfs first (less valuable)
                            if "Half" in reward[1]:
                                if post_count >= (requirement * 0.5):
                                    async with aiosqlite.connect(database) as db:
                                        await db.execute('UPDATE Rewards SET Charges=? WHERE RecipientID=? AND Charges > 0 AND ID=? AND Type=?', (reward[3] - 1, staff_member.id, r[0], "Quota Half"))
                                        await db.commit()
                                    reward_excused = True
                                    break
                        if i == 1:
                            if "Excused" in reward[1]:
                                async with aiosqlite.connect(database) as db:
                                    await db.execute('UPDATE Rewards SET Charges=? WHERE RecipientID=? AND Charges > 0 AND ID=? AND Type=?', (reward[3] - 1, staff_member.id, r[0], "Quota Excused"))
                                    await db.commit()
                                reward_excused = True
                                break


        # STRIKES
        if auto_strike and not excused and not reward_excused:
            if not Is_Senior:
                if post_count < requirement:
                    striked = True
                    async with aiosqlite.connect(database) as db:
                        await db.execute('INSERT INTO Strikes (RecipientID, SeniorID, DateGiven) VALUES (?, ?, ?)', (staff_member.id, interaction.user.id, week_start))
                        await db.commit()
            else:
                if post_count < requirement and not activity:
                    striked = True
                    async with aiosqlite.connect(database) as db:
                        await db.execute('INSERT INTO Strikes (RecipientID, SeniorID, DateGiven) VALUES (?, ?, ?)', (staff_member.id, interaction.user.id, week_start))
                        await db.commit()


        # FINAL SQL
        async with aiosqlite.connect(database) as db:
            async with db.execute('SELECT StartDate FROM Weeks WHERE StartDate=?', (week_start,)) as cursor:
                existing_week = await cursor.fetchone()
            
            if existing_week is None:
                await db.execute('INSERT INTO Weeks (StartDate, PostRequirement, SeniorPostRequirement, InternPostRequirement) VALUES (?, ?, ?, ?)', (week_start, await self.bot.getQuota(), await self.bot.getSeniorQuota(), await self.bot.getInternQuota()))
                await db.commit()
            
            if not Is_Senior:
                await db.execute('INSERT OR REPLACE INTO Inspections (InspecteeID, InspectorID, PostsCompleted, WeekStart, InactivityExcused, RewardExcused, Pass, TicketsCompleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                                    (staff_member.id, interaction.user.id, post_count, week_start, int(excused), int(reward_excused), int(post_count >= requirement or int(excused) or int(reward_excused)), ticket_count))
            else:
                await db.execute('INSERT OR REPLACE INTO SeniorInspections (InspecteeID, InspectorID, PostsCompleted, Activity, WeekStart, InactivityExcused, RewardExcused, Pass, TicketsCompleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                                    (staff_member.id, interaction.user.id, post_count, int(activity), week_start, int(excused), int(reward_excused), int(post_count >= requirement and ticket_count >= ticketrequirement and activity or excused or reward_excused), ticket_count))

            await db.commit()


        logchannel = get(interaction.guild.channels, id=channel_ids.quota_logs)
        strikelogchannel = get(interaction.guild.channels, id=channel_ids.strike_logs)
        if Is_Senior:
            logchannel = get(interaction.guild.channels, id=channel_ids.senior_quota_logs)
            strikelogchannel = get(interaction.guild.channels, id=channel_ids.senior_strike_logs)
        
        logmsg = f"### {interaction.user.mention} logged {staff_member.mention}'s quota.\n{await self.bot.GetQuotaHistory(staff_member.id, 1)}"
        logmsgsent = await logchannel.send(logmsg)
        
        finalmsg = f"Done! - Quota for {staff_member.mention} has been logged successfully."

        if override_existing:
            finalmsg += f"\nIf this user already had a quota recorded, it has been overridden!\n**Please do the following:**\n- Delete the old log in <#{channel_ids.quota_logs}>\n- Remove any old strikes the user may have gotten (if the old quota recorded as a fail)\n- Replenish any rewards mistakenly consumed by this action"

        if striked:
            finalmsg += "\n- The user was striked"
        if reward_excused:
            finalmsg += "\n- The user was excused by an active reward"

        # STRIKE CHECK
        strike_streak = await self.bot.Get_Consecutive_Strikes(staff_member.id)
        if strike_streak > 0:
            finalmsg += f"\n\nPlease note that this user's current consecutive strike streak is now `{strike_streak}`, any actions that need to be taken based on this information are not automated."

        if striked:
            await strikelogchannel.send(f"{staff_member.mention} [was striked]({logmsgsent.jump_url})\n\nQuota History:\n{await self.bot.GetQuotaHistory(staff_member.id)}")

        dm_msg = f"# <:MP:1173683497697808424> | Weekly Inspection Notice\n### {interaction.user.mention} has logged your quota for the week beginning {week_start}\n- Posts: {post_count}"
        
        if Is_Senior:
            dm_msg += f"\n- Activity: {activity}"
            
        dm_msg += f"\n\nYour recent quota history:\n{await self.bot.GetQuotaHistory(staff_member.id, 5)}"
        
        if dm_user:
            await staff_member.send(dm_msg)
        
        await interaction.followup.send(finalmsg)
        
    @app_commands.command(name = "check_week", description='View information about a specific week')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
    async def viewWeek(self, interaction: discord.Interaction, week_start : str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted, InspectorID, TicketsCompleted
                                FROM Inspections
                                WHERE WeekStart=?
                                ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                results1 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted, InspectorID, TicketsCompleted
                                FROM SeniorInspections
                                WHERE WeekStart=?
                                ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                results2 = await cursor.fetchall()
        
        
        results = sorted(results1+results2, key=lambda x: x[1], reverse=True)
        
        output = ""
        loggedLoggers = [] # ids
        loggedStaff = [] # list of ids
        expectedStaff = [m.id for m in get(interaction.guild.roles, id = role_ids.staff).members + get(interaction.guild.roles, id = role_ids.intern).members]
        expectedLoggers = [m.id for m in get(interaction.guild.roles, id = role_ids.senior).members]
        
        totalPosts = 0
        totalTickets = 0
        for i in range(0, len(results)):
            postsCompleted = results[i][1] if results[i][1] is not None else 0
            ticketsCompleted = results[i][3] if results[i][3] is not None else 0
            inspectorID = results[i][2]
            inspecteeID = results[i][0]
            
            totalPosts += postsCompleted
            totalTickets += ticketsCompleted
            
            loggedLoggers.append(inspectorID)
            loggedStaff.append(inspecteeID)
            
            output += f"- <@{inspecteeID}>: `{postsCompleted}` | `{ticketsCompleted}`\n"
        
        missingLoggers = list(set(loggedLoggers).symmetric_difference(set(expectedLoggers)))
        missingstaff = list(set(loggedStaff).symmetric_difference(set(expectedStaff)))
        
        output2 = ""
        if len(missingstaff) > 0:
            for id in missingstaff:
                output2 += f"<@{id}>, "
        else:
            output2 = "Nobody missing!"
        
        output3 = ""
        if len(missingLoggers) > 0:
            for id in missingLoggers:
                output3 += f"<@{id}>, "
        else:
            output3 = "Nobody missing!"
        
        await interaction.followup.send(embeds=[discord.Embed(title = "Results", description=f"Total Posts: `{totalPosts}`\nTotal Tickets: `{totalTickets}`\n\n**USERNAME: POSTS | TICKETS**\n{output}", colour=colours.mp_purple), 
                                                discord.Embed(title = "Missing Users", description=output2, colour=colours.mp_purple), 
                                                discord.Embed(title = "Missing Loggers", description=output3, colour=colours.mp_purple)], ephemeral = True)

    @app_commands.command(name = "get_history", description='Get a users most recent weeks of quota history')
    async def gethistory(self, interaction: discord.Interaction, staff_member : discord.Member):
        await interaction.response.send_message(await self.bot.GetQuotaHistory(staff_member.id), ephemeral=True)

    @app_commands.command(name = "mvp", description='Get the mvp list for a week')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
    async def getmvp(self, interaction: discord.Interaction, week_start : str, post_threshold : int, ticket_threshold : int, form_announcement : bool = False, give_role : bool = False):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted 
                                FROM Inspections
                                WHERE WeekStart=? AND PostsCompleted > ?
                                ORDER BY PostsCompleted DESC""", (week_start, post_threshold)) as cursor:
                results1 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted 
                                FROM SeniorInspections
                                WHERE WeekStart=? AND PostsCompleted > ?
                                ORDER BY PostsCompleted DESC""", (week_start, post_threshold)) as cursor:
                results2 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT InspecteeID, TicketsCompleted 
                                FROM Inspections
                                WHERE WeekStart=? AND TicketsCompleted > ?
                                ORDER BY TicketsCompleted DESC""", (week_start, ticket_threshold)) as cursor:
                results3 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT InspecteeID, TicketsCompleted 
                                FROM SeniorInspections
                                WHERE WeekStart=? AND TicketsCompleted > ?
                                ORDER BY TicketsCompleted DESC""", (week_start, ticket_threshold)) as cursor:
                results4 = await cursor.fetchall()
        
        postresults = sorted(results1+results2, key=lambda x: x[1], reverse=True)
        ticketresults = sorted(results3+results4, key=lambda x: x[1], reverse=True)
        
        output = ""
        
        for i in range(0, len(postresults)):
            if i == 0:
                output += f"## :CH_Diamond_Shiny: - <@{postresults[i][0]}> - {postresults[i][1]} posts\n"
            else:
                output += f"\n### :Crown2Silver: - <@{postresults[i][0]}> - {postresults[i][1]} posts"
        
        for i in range(0, len(ticketresults)):
            if i == 0:
                output += f"\n\n## :CH_Diamond_Shiny: - <@{ticketresults[i][0]}> - {ticketresults[i][1]} tickets\n"
            else:
                output += f"\n### :Crown2Silver: - <@{ticketresults[i][0]}> - {ticketresults[i][1]} tickets"
        
        if give_role:
            mvp_role = get(interaction.guild.roles, id=role_ids.mvp)
            
            for user in mvp_role.members:
                await user.remove_roles(mvp_role)
            
            await get(interaction.guild.members, id = int(postresults[0][0])).add_roles(mvp_role)
            await get(interaction.guild.members, id = int(ticketresults[0][0])).add_roles(mvp_role)
        
        if form_announcement:
            await interaction.followup.send(f"```\n# <@&796462879246909532> Weekly Notice - {week_start.replace("-", "/")}\n\n{output}\n\n\nSigned,\n### :MLeader: | *deepforce123*\n```", ephemeral=True)
        else:
            await interaction.followup.send(f"```\n{output}\n```", ephemeral=True)
            
    @logQuota.autocomplete('week_start')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str):
        choicelist = []   
        
        for i in range(-9,0):
            dt = datetime.now() + timedelta(days=i)
            if dt.weekday() == 0:
                choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
        
        return choicelist
    
    @set_quota.autocomplete('role')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str):
        choicelist = []
        
        async with aiosqlite.connect(database) as db:
            async with await db.execute("SELECT key, value FROM Quotas") as cursor:
                results = await cursor.fetchall()
        
        for r in results:
            choicelist.append(app_commands.Choice(name=f"{r[0]} ({r[1]})", value=r[0]))
            
        return choicelist
    
    @viewWeek.autocomplete('week_start')
    @getmvp.autocomplete('week_start')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str):
        choicelist = []   
        
        for i in range(-61,1):
            dt = datetime.now() + timedelta(days=i)
            if dt.weekday() == 0:
                choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
        
        return choicelist

async def setup(bot):
    await bot.add_cog(quota(bot))