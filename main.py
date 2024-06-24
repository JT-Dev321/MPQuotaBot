import os

import discord
from discord import ButtonStyle, app_commands, ui
from discord.ext import tasks
from discord.utils import get
from discord.app_commands import AppCommandError, Group
import aiosqlite
import time
from datetime import datetime, timedelta

import asyncio

import re

import math
import itertools
import ast

from dotenv import load_dotenv
load_dotenv()

guild_id = 768851165671850015
guild_id_l = [guild_id]

log_channel_id = 1208810891626151976
strike_log_channel_id = 1208827574998933616
management_role_id = 768851165671850022
senior_role_id = 768851165671850021
intern_role_id = 1234584425547694081
staff_role_id = 796462879246909532
candidate_role_id = 768851165671850017

database = 'quotaDB.sqlite'

redcolour = 0xFF0000
darkredcolour = 0x8b0000
orangecolour = 0xFFA500
greencolour = 0x00FF00
darkorangecolour = 0xDC582A
stafftagcolour = 0xc21808
maincolour = 0xA46FFF

def print_red(text):
    print(f"\033[1;31m{text}\033[0m")

def print_green(text):
    print(f"\033[1;32m{text}\033[0m")

class client(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        
        self.synced = False
    
    async def setup_hook(self) -> None:
        async with aiosqlite.connect(database) as db:
            
            #YYYY-MM-DD
            # changed all db architecture, will need to modify all code.
            await db.execute("""CREATE TABLE IF NOT EXISTS Weeks(
                                StartDate TEXT PRIMARY KEY, 
                                PostRequirement INTEGER,
                                SeniorPostRequirement INTEGER,
                                InternPostRequirement INTEGER
                                )""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS Inspections(
                                ID INTEGER PRIMARY KEY, 
                                InspecteeID INTEGER, 
                                InspectorID INTEGER, 
                                PostsCompleted INTEGER,
                                InactivityExcused INTEGER,
                                RewardExcused INTEGER,
                                WeekStart TEXT,
                                Pass INTEGER,
                                FOREIGN KEY(WeekStart) REFERENCES Weeks(StartDate)
                                )""") # -1 activity = doesn't apply
            
            await db.execute("""CREATE TABLE IF NOT EXISTS SeniorInspections(
                                ID INTEGER PRIMARY KEY, 
                                InspecteeID INTEGER, 
                                InspectorID INTEGER, 
                                PostsCompleted INTEGER,
                                Activity INTEGER,
                                InactivityExcused INTEGER,
                                RewardExcused INTEGER,
                                WeekStart TEXT,
                                Pass INTEGER,
                                FOREIGN KEY(WeekStart) REFERENCES Weeks(StartDate)
                                )""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS Strikes(
                                ID INTEGER PRIMARY KEY, 
                                RecipientID INTEGER, 
                                SeniorID INTEGER,
                                DateGiven TEXT
                                )""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS Rewards(
                                ID INTEGER PRIMARY KEY, 
                                RecipientID INTEGER, 
                                SeniorID INTEGER,
                                DateGiven TEXT,
                                Type TEXT,
                                Charges INTEGER
                                )""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS Interns(
                                ID INTEGER PRIMARY KEY, 
                                InternID INTEGER, 
                                DateJoined TEXT,
                                RemovalReason TEXT
                                )""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS Quotas(
                                key TEXT PRIMARY KEY,
                                value TEXT
                                )""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS Excused(
                                StaffID INTEGER PRIMARY KEY,
                                InspectionCount INTEGER
                                )""")
            
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync(guild = discord.Object(id=guild_id))
            self.synced = True
        print_green(f"Logged in as {self.user}.")
        
aclient = client()
tree = app_commands.CommandTree(aclient)

async def has_role_f(staff_member, role_id):
    if isinstance(staff_member, discord.Member):
        return role_id in [r.id for r in staff_member.roles]
    elif isinstance(staff_member, int):
        guild = aclient.get_guild(guild_id)
        try:
            staff_member_obj = await guild.fetch_member(staff_member)
            return role_id in [r.id for r in staff_member_obj.roles]
        except discord.NotFound:
            return False

async def IsManagement(staff_member):
    return await has_role_f(staff_member, management_role_id)

async def IsSenior(staff_member):
    return await has_role_f(staff_member, senior_role_id)

async def IsIntern(staff_member):
    return await has_role_f(staff_member, intern_role_id)

async def get_variable(key):
    async with aiosqlite.connect(database) as db:
        async with db.execute('SELECT value FROM Quotas WHERE key=?', (key,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def set_variable(key, value):
    async with aiosqlite.connect(database) as db:
        await db.execute('INSERT OR REPLACE INTO Quotas (key, value) VALUES (?, ?)', (key, value))
        await db.commit()

async def getCurrentQuota():
    result = await get_variable("normal")
    return int(result) if result is not None else None

async def getCurrentSeniorQuota():
    result = await get_variable("senior")
    return int(result) if result is not None else None

async def getCurrentInternQuota():
    result = await get_variable("intern")
    return int(result) if result is not None else None

async def CheckValidDate(date : str):
    return re.match(r"^20[0-9]{2}-([1-9]|1[0-2])-([1-9]|[12][0-9]|3[01])$", date) is not None

async def GetQuotaHistory(staff_member : int, limit : int = 20):
    
    if not await IsSenior(staff_member):
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT WeekStart, Pass, PostsCompleted, InactivityExcused, RewardExcused
                                    FROM Inspections
                                    WHERE InspecteeID = ?
                                    ORDER BY printf("%04d-%02d-%02d", 
                                    substr(WeekStart, 1, instr(WeekStart, '-') - 1), 
                                    substr(WeekStart, instr(WeekStart, '-') + 1, 2), 
                                    substr(WeekStart, -2)) DESC
                                    LIMIT ?""", (staff_member, str(limit))) as cursor:
                rows = await cursor.fetchall()
    else:
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT WeekStart, Pass, PostsCompleted, InactivityExcused, RewardExcused
                                    FROM SeniorInspections
                                    WHERE InspecteeID = ?
                                    ORDER BY printf("%04d-%02d-%02d", 
                                    substr(WeekStart, 1, instr(WeekStart, '-') - 1), 
                                    substr(WeekStart, instr(WeekStart, '-') + 1, 2), 
                                    substr(WeekStart, -2)) DESC
                                    LIMIT ?""", (staff_member, str(limit))) as cursor:
                rows = await cursor.fetchall()
    
    
    rows.reverse()
    
    output = "```ansi\n"
    for row in rows:
        if int(row[4]) == 1:
            output += f"[0;34m{row[0]} - Reward Excused - {row[2]} posts\n"
        elif int(row[3] == 1):
            output += f"[0;33m{row[0]} - Inactivity Excused - {row[2]} posts\n"
        elif int(row[1]) == 1:
            output += f"[0;32m{row[0]} - Pass - {row[2]} posts\n"
        else:
            output += f"[0;31m{row[0]} - Fail - {row[2]} posts\n"
    output += "```"
    if (len(rows) == 0):
        output = "No Results"
    return output
    # maybe done idk

async def Get_Consecutive_Strikes(staff_member : int): # only accurate if quota logs are fully up to date
    flat_list = []
    
    
    # as of 27-1-24, this seems to work
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT DateGiven
                                FROM Strikes
                                WHERE RecipientID = ?
                                ORDER BY printf("%04d-%02d-%02d", 
                                    substr(DateGiven, 1, instr(DateGiven, '-') - 1), 
                                    substr(DateGiven, instr(DateGiven, '-') + 1, 2), 
                                    substr(DateGiven, -2)) DESC
                                LIMIT 10""", (staff_member,)) as cursor:
            rows = await cursor.fetchall()
    
    counter = 0
    for row in rows:
        for val in row:
            flat_list.append(val)
    
    for i in range(-12,-5): # checks the last complete week's monday
        dt = datetime.now() + timedelta(days=i)
        if dt.weekday() == 0:
            last_monday = dt        
            
    for i in range(len(flat_list)):
        date = str(flat_list[i]).split("-")
        dt = datetime(int(date[0]), int(date[1]), int(date[2]))
        if i == 0 and dt.date() != last_monday.date():
            print("Not last monday")
            break
        try:
            next_date = datetime(int(flat_list[i + 1].split("-")[0]), int(flat_list[i + 1].split("-")[1]), int(flat_list[i + 1].split("-")[2]))
                
            if dt <= next_date + timedelta(days=7):
                print("Counted")
                counter += 1
                if i == len(flat_list) - 2 and len(flat_list) != 1:
                    counter += 1
            else:
                break
        except IndexError:
            print("Except")
            break
        
    return counter

rewardGroup = Group(name = "reward", description= "Handle rewards", guild_ids=guild_id_l)


@rewardGroup.command(name = "distribute", description='Distribute rewards based on the previous 4 inspections.')
@app_commands.checks.has_role(management_role_id)
async def distribute_rewards(interaction: discord.Interaction, week_start : str, just_show : bool = False):
    ids_to_check = [m.id for m in get(interaction.guild.roles, id = staff_role_id).members]
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    async with aiosqlite.connect(database) as db:
        query = """
            SELECT InspecteeID, SUM(PostsCompleted) AS PostsCompletedSum
            FROM (
                SELECT InspecteeID, PostsCompleted,
                       ROW_NUMBER() OVER (PARTITION BY InspecteeID ORDER BY WeekStart DESC) AS RowNum
                FROM Inspections
            ) sub
            WHERE RowNum <= 4
            GROUP BY InspecteeID
            ORDER BY PostsCompletedSum;
        """
        async with db.execute(query) as cursor:
            results = await cursor.fetchall()
            
            if not just_show:
                counter = 0
                for row in results:
                    UserId = row[0]
                    print(f"Checking {UserId}")
                    if not await IsSenior(UserId) and interaction.guild.get_member(UserId) is not None:
                        print(f"{UserId} is not a senior")
                        PostSum = row[1]
                        MemberObj = interaction.guild.get_member(UserId)
                        
                        messageStart = f"You have been given a reward for completing `{PostSum}` posts over the last 4 inspections."
                        messageEnd = f"These rewards are only applied if you would have otherwise failed a given inspection week, and expire after 4 weeks."
                        
                        rewarded = []
                        
                        if PostSum >= 900:
                            # await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Excused", 2))
                            # await db.commit()
                            # await MemberObj.send(messageStart + "\n\n- You will be excused for 2 of the next 4 inspections\n\n" + messageEnd)
                            counter += 1
                            rewarded.append(f"<@{UserId}>")
                        elif PostSum >= 600:
                            # await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Excused", 1))
                            # await db.commit()
                            # await MemberObj.send(messageStart + "\n\n- You will be excused for 1 of the next 4 inspections\n\n" + messageEnd)
                            counter += 1
                            rewarded.append(f"<@{UserId}>")
                        elif PostSum >= 450:
                            # await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Half", 2))
                            # await db.commit()
                            # await MemberObj.send(messageStart + "\n\n- Your post requirement will be halved for 2 of the next 4 inspections\n\n" + messageEnd)
                            counter += 1
                            rewarded.append(f"<@{UserId}>")
                        elif PostSum >= 300:
                            # await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Half", 1))
                            # await db.commit()
                            # await MemberObj.send(messageStart + "\n\n- Your post requirement will be halved for 1 of the next 4 inspections\n\n" + messageEnd)
                            counter += 1
                            rewarded.append(f"<@{UserId}>")
                await interaction.followup.send(f"Done! - Given {counter} rewards to: {', '.join(rewarded)}", ephemeral=True)
            else:
                output = ""
                for row in results:
                    output += f"<@{row[0]}> - {row[1]}\n"
                await interaction.followup.send(output, ephemeral=True)

@rewardGroup.command(name = "check_staff", description='Check a staff members rewards')
async def checkRewards(interaction: discord.Interaction, staff_member : discord.Member):
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    async with aiosqlite.connect(database) as db:
        async with db.execute('SELECT Type, DateGiven, Charges, SeniorID FROM Rewards WHERE RecipientID=?', (staff_member.id,)) as cursor:
            results = await cursor.fetchall()   
    
    if len(results) == 0:
        await interaction.followup.send("User has no rewards", ephemeral=True)
    
    valid_rewards = []
    
    for r in results:
        date = str(r[1]).split("-")
        dt = datetime(int(date[0]), int(date[1]), int(date[2]))
        if dt > datetime.now() - timedelta(days=29):
            valid_rewards.append(r)
    
    message = ""
    
    for r in valid_rewards:
        message += f"{r[0]}\n- Given by: <@{r[3]}>\n- Date: {r[1]}\n- Charges Remaining: {r[2]}\n\n"
    
    await interaction.followup.send(message, ephemeral=True)
            
@rewardGroup.command(name = "give", description='Give a reward')
@app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week",charges="Number of weeks this reward is useable for")
async def giveReward(interaction: discord.Interaction, staff_member : discord.Member, week_start : str, reward_type : str, charges : int):
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    if not await CheckValidDate(week_start):
        await interaction.followup.send("Please enter a valid date", ephemeral=True)
        return
    
    async with aiosqlite.connect(database) as db:
        await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (staff_member.id, interaction.user.id, week_start, reward_type, charges))
        await db.commit()
    
    await interaction.followup.send("Success!", ephemeral=True)

@giveReward.autocomplete('reward_type')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    choicelist = [
    app_commands.Choice(name = 'Quota Half', value = "Quota Half"),
    app_commands.Choice(name = 'Quota Excused', value = "Quota Excused"),
    ]
    return choicelist

tree.add_command(rewardGroup)

class parse_data_modal(ui.Modal, title = 'Data parser'):

    def __init__(self):
        super().__init__()

    data = ui.TextInput(label = 'Data', style = discord.TextStyle.paragraph, required = True)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        splitData = self.data.value.split('\n')
        
        quotaDict = {}
        
        for i in range(0, len(splitData), 6):
            quotaDict.update({f"{splitData[i]}" : int(splitData[i+4].split(': ')[1])})
        
        output = ""
        
        for name in quotaDict:
            output += f"`/quota log staff_member:{name} post_count:{quotaDict[name]} week_start: `\n"
        
        await interaction.response.send_message(output, ephemeral=True)

quotaGroup = Group(name = "quota", description = "Handle quotas", guild_ids=guild_id_l)

@quotaGroup.command(name = "parsedata", description='Parse data')
async def parseData(interaction: discord.Interaction):
    await interaction.response.send_modal(parse_data_modal())
    
@quotaGroup.command(name = "set", description='Set a quota')
@app_commands.checks.has_role(management_role_id)
async def set_quota(interaction: discord.Interaction, role : str, value : int):
    prev = await get_variable(role)
    await set_variable(role, value)
    
    await interaction.response.send_message(f"Changed quota for `{role}` from `{prev}` to `{value}`", ephemeral=True)

@quotaGroup.command(name = "inactivity_add", description='Add a user to inactivity')
@app_commands.checks.has_role(management_role_id)
async def inactivity_add(interaction: discord.Interaction, staff_member : discord.Member, inspection_count : int):
    async with aiosqlite.connect(database) as db:
        await db.execute('INSERT OR REPLACE INTO Excused (StaffID, InspectionCount) VALUES (?, ?)', (staff_member.id, inspection_count))
        await db.commit()
        await interaction.response.send_message("Successfully added user!", ephemeral=True)
    
@quotaGroup.command(name = "inactivity_view", description='View all active inactivity notices.')
@app_commands.checks.has_role(management_role_id)
async def inactivity_view(interaction: discord.Interaction):
    async with aiosqlite.connect(database) as db:
        async with db.execute('SELECT StaffID, InspectionCount FROM Excused WHERE InspectionCount > 0') as cursor:
            results = await cursor.fetchall()
    
    output = f"Total: `{len(results)}`\n\n"
    
    for row in results:
        output += f"- <@{row[0]}> - `{row[1]}`\n"
    
    await interaction.response.send_message(embed=discord.Embed(title = f"Current Inactivity Notices", description=output, colour=maincolour), ephemeral=True)
    
@quotaGroup.command(name = "log", description='Log a quota for an individual')
@app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week", activity="Senior Only", override_excused="Use to override excused", apply_rewards="Default: True", auto_strike="Default: True", override_existing="Default: False", dm_user="Default: True")
async def logQuota(interaction: discord.Interaction, staff_member : discord.Member, post_count : int, week_start : str, activity : bool = None, override_excused : bool = False, apply_rewards : bool = True, auto_strike : bool = True, override_existing : bool = False, dm_user : bool = True):
    await interaction.response.defer(thinking=True, ephemeral=True)
    # all wrong to do with senior quota (post count)
    reward_excused = False
    striked = False
    Is_Senior = await IsSenior(staff_member)
    
    # work out the target users quota requirement
    requirement = 0
    if Is_Senior:
        requirement = await getCurrentSeniorQuota()
    elif await IsIntern(staff_member):
        requirement = await getCurrentInternQuota()
    else:
        requirement = await getCurrentQuota()

    # check if inspector is a senior
    if not await IsSenior(interaction.user):
        await interaction.followup.send("Only seniors can do this >:(", ephemeral=True)
        return

    #ensure valid date
    if not await CheckValidDate(week_start):
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
    if apply_rewards and not excused and post_count < requirement:
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
            await db.execute('INSERT INTO Weeks (StartDate, PostRequirement, SeniorPostRequirement, InternPostRequirement) VALUES (?, ?, ?, ?)', (week_start, await getCurrentQuota(), await getCurrentSeniorQuota(), await getCurrentInternQuota()))
            await db.commit()
        
        if not Is_Senior:
            await db.execute('INSERT OR REPLACE INTO Inspections (InspecteeID, InspectorID, PostsCompleted, WeekStart, InactivityExcused, RewardExcused, Pass) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                                (staff_member.id, interaction.user.id, post_count, week_start, int(excused), int(reward_excused), int(post_count >= requirement or int(excused) or int(reward_excused))))
        else:
            await db.execute('INSERT OR REPLACE INTO SeniorInspections (InspecteeID, InspectorID, PostsCompleted, Activity, WeekStart, InactivityExcused, RewardExcused, Pass) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                                (staff_member.id, interaction.user.id, post_count, int(activity), week_start, int(excused), int(reward_excused), int(post_count >= requirement and activity or excused or reward_excused)))

        await db.commit()


    logchannel = get(interaction.guild.channels, id=log_channel_id)
    strikelogchannel = get(interaction.guild.channels, id=strike_log_channel_id)
    
    logmsg = f"### {interaction.user.mention} logged {staff_member.mention}'s quota.\n- Posts: {post_count}\n- Activity: {activity}"
    if reward_excused:
        logmsg += f"\n- A reward was consumed to excuse this user"
    logmsgsent = await logchannel.send(logmsg)
    
    finalmsg = f"Done! - Quota for {staff_member.mention} has been logged successfully."

    if override_existing:
        finalmsg += f"\nIf this user already had a quota recorded, it has been overridden!\n**Please do the following:**\n- Delete the old log in <#{log_channel_id}>\n- Remove any old strikes the user may have gotten (if the old quota recorded as a fail)\n- Replenish any rewards mistakenly consumed by this action"

    if striked:
        finalmsg += "\n- The user was striked"
    if reward_excused:
        finalmsg += "\n- The user was excused by an active reward"

    # STRIKE CHECK
    strike_streak = await Get_Consecutive_Strikes(staff_member.id)
    if strike_streak > 0:
        finalmsg += f"\n\nPlease note that this user's current consecutive strike streak is now `{strike_streak}`, any actions that need to be taken based on this information are not automated."

    if striked:
        await strikelogchannel.send(f"{staff_member.mention} [was striked]({logmsgsent.jump_url})\n\nQuota History:\n{await GetQuotaHistory(staff_member.id)}")

    dm_msg = f"# <:MP:1173683497697808424> | Weekly Inspection Notice\n### {interaction.user.mention} has logged your quota for the week beginning {week_start}\n- Posts: {post_count}"
    
    if Is_Senior:
        dm_msg += f"\n- Activity: {activity}"
        
    dm_msg += f"\n\nYour recent quota history:\n{await GetQuotaHistory(staff_member.id, 5)}"
    
    if dm_user:
        await staff_member.send(dm_msg)
    
    await interaction.followup.send(finalmsg)
    
@quotaGroup.command(name = "check_week", description='View information about a specific week')
@app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
async def viewWeek(interaction: discord.Interaction, week_start : str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, PostsCompleted, InspectorID
                            FROM Inspections
                            WHERE WeekStart=?
                            ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
            results1 = await cursor.fetchall()
    
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, PostsCompleted 
                            FROM SeniorInspections
                            WHERE WeekStart=?
                            ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
            results2 = await cursor.fetchall()
    
    
    results = sorted(results1+results2, key=lambda x: x[1], reverse=True)
    
    output = ""
    loggedLoggers = [] # ids
    loggedStaff = [] # list of ids
    expectedStaff = [m.id for m in get(interaction.guild.roles, id = staff_role_id).members + get(interaction.guild.roles, id = intern_role_id).members]
    expectedLoggers = [m.id for m in get(interaction.guild.roles, id = senior_role_id).members]
    
    for i in range(0, len(results)):
        loggedLoggers.append(results[i][2])
        output += f"- <@{results[i][0]}> - {results[i][1]}\n"
        loggedStaff.append(results[i][0])
    
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
    
    await interaction.followup.send(embeds=[discord.Embed(title = "Results", description=output, colour=maincolour), 
                                            discord.Embed(title = "Missing Users", description=output2, colour=maincolour), 
                                            discord.Embed(title = "Missing Loggers", description=output3, colour=maincolour)], ephemeral = True)

@quotaGroup.command(name = "get_history", description='Get a users most recent weeks of quota history')
async def gethistory(interaction: discord.Interaction, staff_member : discord.Member):
    await interaction.response.send_message(await GetQuotaHistory(staff_member.id), ephemeral=True)

@quotaGroup.command(name = "mvp", description='Get the mvp list for a week')
@app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
async def getmvp(interaction: discord.Interaction, week_start : str, threshold : int):
    await interaction.response.defer(thinking=True)
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, PostsCompleted 
                            FROM Inspections
                            WHERE WeekStart=? AND PostsCompleted > ?
                            ORDER BY PostsCompleted DESC""", (week_start, threshold)) as cursor:
            results1 = await cursor.fetchall()
    
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, PostsCompleted 
                            FROM SeniorInspections
                            WHERE WeekStart=? AND PostsCompleted > ?
                            ORDER BY PostsCompleted DESC""", (week_start, threshold)) as cursor:
            results2 = await cursor.fetchall()
    
    
    results = sorted(results1+results2, key=lambda x: x[1], reverse=True)
    
    output = "```\n"
    
    
    for i in range(0, len(results)):
        if i == 0:
            output += f"## :CH_Diamond_Shiny: - <@{results[i][0]}> - {results[i][1]} posts"
        else:
            output += f"\n### :Crown2Silver: - <@{results[i][0]}> - {results[i][1]} posts"
            
    output += "\n```"
    
    await interaction.followup.send(output)
    

tree.add_command(quotaGroup)


internGroup = Group(name = "intern", description = "Handle intern", guild_ids=guild_id_l)

@internGroup.command(name = "register", description='Register interns from a role')
async def register_from_role(interaction: discord.Interaction, role : discord.Role = None, id_csv : str = None):
    
    if (role == None and id_csv == None) or (role != None and id_csv != None):
        await interaction.response.send_message("Choose one source to get them from!", ephemeral=True)
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("SELECT InternID FROM Interns") as cursor:
            existing_interns = list(itertools.chain.from_iterable(await cursor.fetchall()))
    
    counter = 0
    for id in map(int, [m.id for m in role.members] if role != None else id_csv.split(",")):
        if id not in existing_interns:
            async with aiosqlite.connect(database) as db:
                await db.execute("INSERT INTO Interns (InternID, DateJoined) VALUES (?, ?)", (id, datetime.now().strftime('%Y-%m-%d')))
                await db.commit()
                counter += 1
                
    await interaction.response.send_message(f"Enrolled {counter} people", ephemeral=True)
                
@internGroup.command(name = "remove", description='Remove an intern')
async def remove_intern(interaction: discord.Interaction, intern : discord.User, reason : str):
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("SELECT InternID FROM Interns") as cursor:
            existing_interns = list(itertools.chain.from_iterable(await cursor.fetchall()))
            
    if intern.id in existing_interns:
        async with aiosqlite.connect(database) as db:
            await db.execute("UPDATE Interns SET RemovalReason = ? WHERE InternID = ?", (reason, intern.id))
            await db.commit()
    else:
        await interaction.response.send_message("Not in DB", ephemeral=True)
    
    await interaction.response.send_message("Dont forget to kick them!", ephemeral=True)

tree.add_command(internGroup)


@tree.command(guild = discord.Object(id=guild_id), name = "check_history", description='Check your own quota history!')
async def getownhistory(interaction: discord.Interaction):
    await interaction.response.send_message(await GetQuotaHistory(interaction.user.id), ephemeral=True)


@tree.command(guild = discord.Object(id=guild_id), name = "csv_role", description='Get a csv of a role')
async def csv_role(interaction: discord.Interaction, role : discord.Role, splitby : int = -1):
    if splitby == -1:
        await interaction.response.send_message(",".join([str(m.id) for m in role.members]), ephemeral=True)
    elif splitby > 5:
        ids = [str(m.id) for m in role.members]
        
        output = ""
        temp = ""

        for id in ids:
            temp += f"{id},"
            if len(temp.split(",")) > splitby:
                output += temp
                output += "\n\n"
                temp = ""
        
        if temp != "":
            output += temp
            
        await interaction.response.send_message(output, ephemeral=True)  

@tree.command(guild = discord.Object(id=guild_id), name = "sql", description='Run SQL')
async def run_sql(interaction: discord.Interaction, sql : str):
    if interaction.user.id == 378963670589505557:
        if "SELECT" in sql:
            async with aiosqlite.connect(database) as db:
                async with db.execute(sql) as cursor:
                    rows = await cursor.fetchall()
                    output = ""
                    for row in rows:
                        output += str(row) + "\n"
                    if len(rows) > 0:
                        await interaction.response.send_message(output, ephemeral=True)
                    else:
                        await interaction.response.send_message("Fetch result was none", ephemeral=True)
            return
        else:
            async with aiosqlite.connect(database) as db:
                await db.execute(sql)
                await db.commit()
            await interaction.response.send_message("Done!", ephemeral=True)
            return
    else:
        await interaction.response.send_message("not for you go away!", ephemeral=True)

@tree.command(guild = discord.Object(id=guild_id), name = "make_groups", description='Sorts interns into sr timezone groups')
@app_commands.checks.has_role(management_role_id)
async def make_intern_groups(interaction: discord.Interaction, copyable : bool = False, csv_groups : bool = False):
    
    interns = []
    leaders = []
    
    candidate_role = get(interaction.guild.roles, id = candidate_role_id)

    for m in candidate_role.members:
        if m.nick != None:
            if " | " in m.nick:

                nickname_split = m.nick.split(" | ")
                timezone_nickname = nickname_split[1]
                timezone_number = ""

                if "+" in timezone_nickname:
                    timezone_number = timezone_nickname.split("+")[1]
                elif "-" in timezone_nickname:
                    timezone_number = timezone_nickname.split("-")[1]

                if timezone_number == "5:30":
                    timezone_number = 5.5
                
                float(timezone_number)

                inter_array = [str(m.id), timezone_number]
                interns.append(inter_array)

    coach_role = get(interaction.guild.roles, id = 1229906177203372065)

    for m in coach_role.members:
        if m.nick != None:
            if " | " in m.nick:
                nickname_split = m.nick.split(" | ")
                timezone_nickname = nickname_split[1]
                timezone_number = ""

                if "+" in timezone_nickname:
                    timezone_number = timezone_nickname.split("+")[1]
                elif "-" in timezone_nickname:
                    timezone_number = timezone_nickname.split("-")[1]

                if timezone_number == "5:30":
                    timezone_number = 5.5
                
                float(timezone_number)

                leader_array = [str(m.id), timezone_number, []]
                leaders.append(leader_array)
    
    # print(leaders, interns)

    # ahmood. | GMT+3
        
    #eaders = [["dav", 1, []], ["red", 10 , []], ["knight", 5.3, []], ["deep", 0, []], ["picture", -6, []]]
    #interns = [["Wezza", 3], ["lillyx", 0], ["ahmood", 3], ["6b", 1], ["Kmdq", 0], ["abluety", -4], ["Helix", 2], ["Synthe", -5], ["Keegan", -5], ["cap", -4], 
            #["ZizzleWizard", -4], ["Bored", -5], ["Pocopotato", -7], ["carisoul", -7], ["okcrystal", +2], ["invanthegreat01", -4], ["jinxisfly", -5], ["Maximoose.7", -6],  
            #["Rafael" , 1], ["Yoshi", 1], ["Potata" , 5.30], ["nzl" , 5.30], ["qvjk" , 8], ["FrostChain" , 8], ["Abdiel" , 8], ["Mamba" , -6], ["knnni" , -5]]

    sorted_pairs = []

    def sort_interns(leaders: list, interns: list):
        leader_count = 0
        amount_of_interns = len(interns)
        sorted_pairs = {}  # Initialize as empty dictionary

        # removes any possible empty lists
        leaders = [i for i in leaders if i != []]
        interns = [j for j in interns if j != []]

        while len(interns) > 0:
            if len(leaders) == leader_count:
                leader_count = 0

            leader_now = leaders[leader_count]
            best_intern_tz_dif = 100
            best_intern = None  # Initialize as None

            C = 25  # --12 + 12 + 1 (-gmt-12 + gmt+12 + 1)

            for intern in interns:
                distance_1 = int(leader_now[1]) - int(intern[1])
                distance_2 = int(intern[1]) - int(leader_now[1])

                D_1 = distance_1 if distance_1 >= 0 else distance_1 + C
                D_2 = distance_2 if distance_2 >= 0 else distance_2 + C

                actual_distance = min(D_1, D_2)

                if actual_distance < best_intern_tz_dif:
                    best_intern_tz_dif = actual_distance
                    best_intern = intern
                        
                    if actual_distance == 0:
                        break

            if best_intern:  # Check that best_intern is not None
                if leader_now[0] not in sorted_pairs:
                    sorted_pairs[leader_now[0]] = []
                sorted_pairs[leader_now[0]].append(best_intern)

                interns.remove(best_intern)

            leader_count += 1

        return sorted_pairs

    sp = sort_interns(leaders, interns)
    output = ""
    for p in sp.keys():
        output += f"<@{p}>**'s Group:**\n"
        for p2 in sp[p]:
            output += f"> <@{p2[0]}>\n"
        output += "\n\n"
    if copyable:
        await interaction.response.send_message(f"```\n{output}```")
    if csv_groups:
        output = ""
        for p in sp.keys():
            output += f"<@{p}>: "
            for p2 in sp[p]:
                output += f"{p2[0]},"
            output += "\n\n"
        await interaction.response.send_message(output)
    else:
        embed = discord.Embed(
            color = maincolour,
            description = output,
            title = "Intern groupings"
        )
        await interaction.response.send_message(embed=embed)
    # print(sort_interns(leaders, interns))

@tree.command(guild = discord.Object(id=guild_id), name = "view_all_history", description='View everyones quota history')
@app_commands.checks.has_role(management_role_id)
async def view_all_history(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    msg = ""
    counter = 0
    for id in [m.id for m in get(interaction.guild.roles, id = staff_role_id).members]:
        msg += f"<@{id}>\n\n{await GetQuotaHistory(id)}\n\n"
        counter += 1
        if counter % 3 == 0:
            await interaction.user.send(msg)
            msg = ""
    
    await interaction.followup.send(f"Sent you all {counter} quota histories!", ephemeral=True)

def parse_timezone(name):
    timezone = name.split(" | GMT")[1]
    return int(timezone)

@logQuota.autocomplete('week_start')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    choicelist = []   
    
    for i in range(-9,0):
        dt = datetime.now() + timedelta(days=i)
        if dt.weekday() == 0:
            choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
    
    return choicelist

@set_quota.autocomplete('role')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    choicelist = [app_commands.Choice(name = 'intern', value = 'intern'),
                  app_commands.Choice(name = 'normal', value = 'normal'),
                  app_commands.Choice(name = 'senior', value = 'senior')]
    
    return choicelist

@viewWeek.autocomplete('week_start')
@giveReward.autocomplete('week_start')
@distribute_rewards.autocomplete('week_start')
@getmvp.autocomplete('week_start')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    choicelist = []   
    
    for i in range(-61,1):
        dt = datetime.now() + timedelta(days=i)
        if dt.weekday() == 0:
            choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
    
    return choicelist

def insert_returns(body):
    if isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(body[-1].value)
        ast.fix_missing_locations(body[-1])

    if isinstance(body[-1], ast.If):
        insert_returns(body[-1].body)
        insert_returns(body[-1].orelse)

    if isinstance(body[-1], ast.With):
        insert_returns(body[-1].body)

@tree.command(guild = discord.Object(id=guild_id), name="eval", description="Eval something")
async def eval_py(interaction : discord.Interaction, cmd : str, ephemeral : bool = True):
    if interaction.user.id == 378963670589505557:
        fn_name = "_eval_expr"
        
        # wrap in async def body
        body = f"async def {fn_name}():\n\t{cmd}"
        
        parsed = ast.parse(body)
        body = parsed.body[0].body

        insert_returns(body)

        env = {
            'bot': aclient,
            'discord': discord,
            'interaction': interaction,
            '__import__': __import__
        }
        exec(compile(parsed, filename="<ast>", mode="exec"), env)

        result = (await eval(f"{fn_name}()", env))
        if len(result) == 0:
            result = "No return value"
        await interaction.response.send_message(result, ephemeral=ephemeral)
    else:
        await interaction.response.send_message("YOU ARENT ME!!!", ephemeral=True)

@aclient.event
async def on_app_command_completion(interaction : discord.Interaction, command : app_commands.Command):
    print_red(f"{interaction.user.name} ({interaction.user.id}) Used command {command.name}")

@tree.error
async def on_app_command_error(interaction : discord.Interaction, error : AppCommandError):
    print_red(error)
    if isinstance(error, app_commands.MissingRole) or isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("You're missing a role!", ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"You're on cooldown for another `{int(error.retry_after)}` seconds!", ephemeral=True)
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You're missing a permission!", ephemeral=True)

aclient.run(f"{os.getenv('token')}")
