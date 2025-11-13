from datetime import datetime, timedelta

import discord
from discord import app_commands, ui
from discord.ext import commands
from discord.utils import get
import aiosqlite

from main import QUOTA_DATABASE
from main import RoleIds,ColourHexes,print_green

class quota(commands.GroupCog, group_name='quota', group_description='Manage quotas'):
    def __init__(self, bot):
        self.Bot = bot
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
                    member = interaction.guild.get_member_named(name)
                    if member is None:
                        output += f"Could not find {name} in the server\n\n"
                        continue
                    if not self.log:
                        output += f"`/quota log staff_member:{member.id} post_count:{quotaDict[name][0]} ticket_count:{quotaDict[name][1]} week_start: `\n"
                    else:
                        activity = await self.bot.is_senior(member)
                        if not activity:
                            activity = None
                        output += f"{member.mention} - " + await self.bot.log_quota(member,
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
                    member = interaction.guild.get_member_named(name)
                    if member is None:
                        output += f"Could not find {name} in the server\n\n"
                        continue
                    if not self.log:
                        output += f"`/quota log staff_member:{member.id} post_count:{quotaDict[name]} ticket_count:0 week_start: `\n"
                    else:
                        print_green(f"Would log {name} with {quotaDict[name]} posts")
                        # await self.bot.log_quota()
            if output != "":
                await interaction.followup.send(output, ephemeral=True)

    @app_commands.command(name = "parsedata", description='Parse data')
    @app_commands.checks.has_role(RoleIds.SENIOR)
    async def parse_data(self, interaction: discord.Interaction, log : bool):
        await interaction.response.send_modal(self.parse_data_modal(self.Bot, log))
        
    @app_commands.command(name = "set", description='Set a quota')
    @app_commands.checks.has_role(RoleIds.MANAGEMENT)
    async def set_quota(self, interaction: discord.Interaction, role : str, value : int):
        prev = await self.Bot.get_variable(role)
        await self.Bot.set_variable(role, value)
        
        await interaction.response.send_message(f"Changed quota for `{role}` from `{prev}` to `{value}`", ephemeral=True)

    @app_commands.command(name = "inactivity_add", description='Add a user to inactivity')
    @app_commands.checks.has_role(RoleIds.MANAGEMENT)
    async def inactivity_add(self, interaction: discord.Interaction, inspection_count : int, staff_member : discord.Member = None, role : discord.Role = None):
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            if staff_member is not None:
                await db.execute("""
                    INSERT OR IGNORE INTO Excused (StaffID, InspectionCount)
                    VALUES (?, ?)
                """, (staff_member.id, inspection_count))
            elif role is not None:
                for id in [m.id for m in role.members]:
                    await db.execute("""
                        INSERT OR IGNORE INTO Excused (StaffID, InspectionCount)
                        VALUES (?, ?)
                    """, (id, inspection_count))
            await db.commit()
            await interaction.response.send_message("Successfully added!", ephemeral=True)
        
    @app_commands.command(name = "inactivity_view", description='View all active inactivity notices.')
    @app_commands.checks.has_role(RoleIds.MANAGEMENT)
    async def inactivity_view(self, interaction: discord.Interaction):
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute('SELECT StaffID, InspectionCount FROM Excused WHERE InspectionCount > 0') as cursor:
                results = await cursor.fetchall()
        
        output = f"Total: `{len(results)}`\n\n"
        
        for row in results:
            output += f"- <@{row[0]}> - `{row[1]}`\n"
        
        await interaction.response.send_message(embed=discord.Embed(title = f"Current Inactivity Notices", description=output, colour=ColourHexes.MP_PURPLE), ephemeral=True)

    @app_commands.command(name = "inactivity_remove", description='Remove a user from inactivity')
    @app_commands.checks.has_role(RoleIds.MANAGEMENT)
    async def inactivity_remove(self, interaction: discord.Interaction, staff_member : discord.Member):
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            await db.execute('DELETE FROM Excused WHERE StaffID = ?', (staff_member.id,))
            await db.commit()
        await interaction.response.send_message("Successfully removed from inactivity!", ephemeral=True)
    

    @app_commands.command(name = "log", description='Log a quota for an individual')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week", activity="Senior Only", override_excused="Use to override excused", apply_rewards="Default: True", auto_strike="Default: True", override_existing="Default: False", dm_user="Default: True")
    async def logQuota(self, interaction: discord.Interaction, staff_member : discord.Member, post_count : int, ticket_count : int, week_start : str, activity : bool = None, override_excused : bool = False, apply_rewards : bool = True, auto_strike : bool = True, override_existing : bool = False, dm_user : bool = True):
        await interaction.response.defer(thinking=True, ephemeral=True)
        response = await self.bot.log_quota(staff_member, interaction.user, post_count, ticket_count, week_start, activity, override_excused, apply_rewards, auto_strike, override_existing, dm_user)
        await interaction.followup.send(response, ephemeral=True)
        
    @app_commands.command(name = "check_week", description='View information about a specific week')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
    async def viewWeek(self, interaction: discord.Interaction, week_start : str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted, InspectorID, TicketsCompleted
                                FROM Inspections
                                WHERE WeekStart=?
                                ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                results1 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted, InspectorID, TicketsCompleted
                                FROM SeniorInspections
                                WHERE WeekStart=?
                                ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                results2 = await cursor.fetchall()
        
        
        results = sorted(results1+results2, key=lambda x: x[1], reverse=True)
        
        output = ""
        loggedLoggers = [] # ids
        loggedStaff = [] # list of ids
        expectedStaff = [m.id for m in get(interaction.guild.roles, id = RoleIds.STAFF).members + get(interaction.guild.roles, id = RoleIds.INTERN).members]
        expectedLoggers = [m.id for m in get(interaction.guild.roles, id = RoleIds.SENIOR).members]
        
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
        
        await interaction.followup.send(embeds=[discord.Embed(title = "Results", description=f"Total Posts: `{totalPosts}`\nTotal Tickets: `{totalTickets}`\n\n**USERNAME: POSTS | TICKETS**\n{output}", colour=ColourHexes.MP_PURPLE), 
                                                discord.Embed(title = "Missing Users", description=output2, colour=ColourHexes.MP_PURPLE), 
                                                discord.Embed(title = "Missing Loggers", description=output3, colour=ColourHexes.MP_PURPLE)], ephemeral = True)

    @app_commands.command(name = "get_history", description='Get a users most recent weeks of quota history')
    async def gethistory(self, interaction: discord.Interaction, staff_member : discord.Member):
        await interaction.response.send_message(await self.Bot.get_quota_history(staff_member.id), ephemeral=True)

    
    @app_commands.command(name = "get_lifetime_history", description='Get a lifetime quota history')
    async def getlifehistory(self, interaction: discord.Interaction, staff_member : discord.Member = None, role : discord.Role = None, amount : int = 10):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if staff_member:
            rows = None
            
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute("""SELECT Pass, PostsCompleted, TicketsCompleted
                                        FROM Inspections    
                                        WHERE InspecteeID = ?
                                        """, (staff_member.id,)) as cursor:
                    rows = await cursor.fetchall()
                
            PFList = [bool(int(row[0])) for row in rows]
            passes = [PF for PF in PFList if PF]
            passRate = round(len(passes) / len(PFList) * 100, 2)
            avgPosts = sum([int(row[1]) for row in rows]) / len(rows)
            failRate = round(100 - passRate, 2)
            
            await interaction.followup.send(f"Pass: {len(passes)} | `{passRate}%`\nFail: {len(PFList) - len(passes)} | `{failRate}%`\nAverage Posts: {avgPosts}", ephemeral=True)
        elif role:
            ids = [m.id for m in role.members if await self.Bot.is_senior(m.id) == False]
            passrates = []
            for id in ids:
                async with aiosqlite.connect(QUOTA_DATABASE) as db:
                    async with db.execute("""SELECT Pass, PostsCompleted, TicketsCompleted
                                            FROM Inspections    
                                            WHERE InspecteeID = ?
                                            """, (id,)) as cursor:
                        rows = await cursor.fetchall()
                    
                PFList = [bool(int(row[0])) for row in rows]
                passes = [PF for PF in PFList if PF]
                passRate = round(len(passes) / len(PFList) * 100, 2) if PFList else 0
                avgPosts = sum([int(row[1]) for row in rows]) / len(rows) if rows else 0
                failRate = round(100 - passRate, 2)
                
                if len(rows) > amount:
                    passrates.append([id, passRate, len(PFList), avgPosts])
            
            sortedData = sorted(passrates, key=lambda x: x[1])
            
            output = ""
            embed = None
            embedList = []
            for v in sortedData:
                stringToAdd = f"<@{v[0]}>:\n- Pass: `{v[1]}`% ({v[2]})\n- Avg: {round(v[3])}\n\n"
                if len(output) + len(stringToAdd) > 2000:
                    embed = discord.Embed(
                        color = ColourHexes.MP_PURPLE,
                        description = output
                    )
                    embedList.append(embed)
                    output = ""
                output += stringToAdd
            if len(output) > 0:
                embed = discord.Embed(
                    color = ColourHexes.MP_PURPLE,
                    description = output
                )
                embedList.append(embed)
            await interaction.followup.send(embeds=embedList, ephemeral=True)
    
    @app_commands.command(name = "mvp", description='Get the mvp list for a week')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
    async def getmvp(self, interaction: discord.Interaction, week_start : str, post_threshold : int, ticket_threshold : int, form_announcement : bool = False, give_role : bool = False):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted 
                                FROM Inspections
                                WHERE WeekStart=? AND PostsCompleted > ?
                                ORDER BY PostsCompleted DESC""", (week_start, post_threshold)) as cursor:
                results1 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute("""SELECT InspecteeID, PostsCompleted 
                                FROM SeniorInspections
                                WHERE WeekStart=? AND PostsCompleted > ?
                                ORDER BY PostsCompleted DESC""", (week_start, post_threshold)) as cursor:
                results2 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute("""SELECT InspecteeID, TicketsCompleted 
                                FROM Inspections
                                WHERE WeekStart=? AND TicketsCompleted > ?
                                ORDER BY TicketsCompleted DESC""", (week_start, ticket_threshold)) as cursor:
                results3 = await cursor.fetchall()
        
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
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
            mvp_role = get(interaction.guild.roles, id=RoleIds.MVP)
            
            for user in mvp_role.members:
                await user.remove_roles(mvp_role)
            
            await get(interaction.guild.members, id = int(postresults[0][0])).add_roles(mvp_role)
            await get(interaction.guild.members, id = int(ticketresults[0][0])).add_roles(mvp_role)
        
        if form_announcement:
            await interaction.followup.send(f"```\n# <@&796462879246909532> Weekly Notice - {week_start.replace("-", "/")}\n\n{output}\n\n\nSigned,\n### :MLeader: | *deepforce123*\n```", ephemeral=True)
        else:
            await interaction.followup.send(f"```\n{output}\n```", ephemeral=True)
    
    @app_commands.command(name = "clear_logs", description='Clear all logs of a senior for a specific week')
    @app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
    @app_commands.checks.has_role(RoleIds.MANAGEMENT)
    async def clear_logs(self, interaction: discord.Interaction, week_start : str, inspector : discord.Member):
        await interaction.response.defer(thinking=True)

        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            await db.execute("DELETE FROM Inspections WHERE WeekStart=? AND InspectorID=?", (week_start, inspector.id))
            await db.commit()

        await interaction.followup.send(f"Cleared logs for <@{inspector.id}> for the week starting {week_start.replace('-', '/')}", ephemeral=True)

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
        
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
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