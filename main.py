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

from dotenv import load_dotenv
load_dotenv()

guild_id = 768851165671850015
guild_id_l = [guild_id]

senior_role_id = 768851165671850021

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
                                SeniorPostRequirement INTEGER
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
            
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync(guild = discord.Object(id=guild_id))
            self.synced = True
        print_green(f"Logged in as {self.user}.")
        
aclient = client()
tree = app_commands.CommandTree(aclient)

async def IsSenior(staff_member):
    if isinstance(staff_member, discord.Member):
        return senior_role_id in [r.id for r in staff_member.roles]
    elif isinstance(staff_member, int):
        staff_member = get(client.get_guild(guild_id).members, id = staff_member)
        return senior_role_id in [r.id for r in staff_member.roles]

async def getCurrentQuota():
    return int(open("currentquota.txt", "r").readline().split("|")[0])
async def getCurrentSeniorQuota():
    return int(open("currentquota.txt", "r").readline().split("|")[1])

async def CheckValidDate(date : str):
    return re.match(r"^20[0-9]{2}-([1-9]|1[0-2])-([1-9]|[12][0-9]|3[01])$", date) is not None

async def GetQuotaHistory(staff_member : int):
    
    if not IsSenior(staff_member):
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT WeekStart, Pass, PostsCompleted
                                    FROM Inspections
                                    WHERE InspecteeID = ?
                                    ORDER BY printf("%04d-%02d-%02d", 
                                    substr(WeekStart, 1, instr(WeekStart, '-') - 1), 
                                    substr(WeekStart, instr(WeekStart, '-') + 1, 2), 
                                    substr(WeekStart, -2)) DESC
                                    LIMIT 20""", (staff_member,)) as cursor:
                rows = await cursor.fetchall()
    else:
        async with aiosqlite.connect(database) as db:
            async with db.execute("""SELECT WeekStart, Pass, PostsCompleted
                                    FROM SeniorInspections
                                    WHERE InspecteeID = ?
                                    ORDER BY printf("%04d-%02d-%02d", 
                                    substr(WeekStart, 1, instr(WeekStart, '-') - 1), 
                                    substr(WeekStart, instr(WeekStart, '-') + 1, 2), 
                                    substr(WeekStart, -2)) DESC
                                    LIMIT 20""", (staff_member,)) as cursor:
                rows = await cursor.fetchall()

    output = "```diff\n"
    for row in rows:
        if bool(int(row[1])):
            output += f"+ {row[0]} - `Pass` - `{row[2]} posts\n"
        else:
            output += f"- {row[0]} - `Fail` - `{row[2]} posts\n"
    output += "```"
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

quotaGroup = Group(name = "quota", description = "Handle quotas", guild_ids=guild_id_l)

@quotaGroup.command(name = "log", description='Log a quota for an individual')
@app_commands.checks.has_role(senior_role_id)
@app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week", activity="False = Fail | True = Pass | Blank = N/A", excused="Use if user is excused DUE TO AN INACTIVITY NOTICE", apply_rewards="Leave Alone", auto_strike="Leave Alone")
async def logQuota(interaction: discord.Interaction, staff_member : discord.Member, post_count : int, week_start : str, activity : bool = None, excused : bool = False, apply_rewards : bool = True, auto_strike : bool = True):
    await interaction.response.defer(thinking=True, ephemeral=True)
    # all wrong to do with senior quota (post count)
    reward_excused = False
    striked = False
    Is_Senior = await IsSenior(staff_member)

    # work out the target users quota requirement
    requirement = 0
    if not Is_Senior:
        requirement = await getCurrentQuota()
    else:
        requirement = await getCurrentSeniorQuota()

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
    if existing_quota != None:
        await interaction.followup.send(f"This user already has a quota recorded for this week (`{week_start}`)", ephemeral=True)
        return

    # REWARDS
    if apply_rewards and not excused:
        async with aiosqlite.connect(database) as db: # get rewards
            async with db.execute('SELECT ID, Type, DateGiven, Charges FROM Rewards WHERE RecipientID=? AND Charges > 0', (staff_member.id,)) as cursor:
                results = await cursor.fetchall()
        
        valid_rewards = []
        
        for r in results:
            date = str(r[2]).split("-")
            dt = datetime(int(date[0]), int(date[1]), int(date[2]))
            if dt > datetime.now() - timedelta(days=29):
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
            if post_count < requirement and activity:
                striked = True
                async with aiosqlite.connect(database) as db:
                    await db.execute('INSERT INTO Strikes (RecipientID, SeniorID, DateGiven) VALUES (?, ?, ?)', (staff_member.id, interaction.user.id, week_start))
                    await db.commit()


    # FINAL SQL
    async with aiosqlite.connect(database) as db:
        async with db.execute('SELECT StartDate FROM Weeks WHERE StartDate=?', (week_start,)) as cursor:
            existing_week = await cursor.fetchone()
        
        if existing_week is None:
            await db.execute('INSERT INTO Weeks (StartDate, PostRequirement, SeniorPostRequirement) VALUES (?, ?, ?)', (week_start, await getCurrentQuota(), await getCurrentSeniorQuota()))
            await db.commit()
        
        if not Is_Senior:
            await db.execute('INSERT INTO Inspections (InspecteeID, InspectorID, PostsCompleted, WeekStart, InactivityExcused, RewardExcused, Pass) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                                                                    (staff_member.id, interaction.user.id, post_count, week_start, int(excused), int(reward_excused), int(post_count >= requirement or int(excused) or int(reward_excused))))
        else:
            await db.execute('INSERT INTO SeniorInspections (InspecteeID, InspectorID, PostsCompleted, Activity, WeekStart, InactivityExcused, RewardExcused, Pass) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                                                                    (staff_member.id, interaction.user.id, post_count, int(activity), week_start, int(excused), int(reward_excused), int(post_count >= requirement and activity or excused or reward_excused)))
        await db.commit()


    finalmsg = f"Done! - Quota for {staff_member.mention} has been logged successfully."

    if striked:
        finalmsg += "\n- The user was striked"
    if reward_excused:
        finalmsg += "\n- The user was excused by an active reward"

    # STRIKE CHECK
    strike_streak = await Get_Consecutive_Strikes(staff_member.id)
    if strike_streak > 0:
        finalmsg += f"\n\nPlease note that this user's current consecutive strike streak is now `{strike_streak}`, any actions that need to be taken based on this information are not automated."

    await interaction.followup.send(finalmsg)
    
@quotaGroup.command(name = "check_week", description='View information about a specific week')
@app_commands.describe(week_start="Format: YYYY-MM-DD | Must use Monday of week")
async def viewWeek(interaction: discord.Interaction, week_start : str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    if not await CheckValidDate(week_start):
        await interaction.followup.send("Please enter a valid date", ephemeral=True)
        return

    dict = {}
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, InspectorID, PostsCompleted, Activity
                                FROM Inspections, Weeks 
                                WHERE StartDate=? AND Startdate=WeekStart""", (week_start,)) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    inspectee = int(row[0])
                    inspector = int(row[1])
                    posts = int(row[2])
                    activity = int(row[3])
                    
                    if not inspector in dict.keys():
                        dict.update({inspector : []})
                    
                    dict[inspector].append([inspectee, [posts, activity]])
    
    body = ""
    print(dict)
    for key in dict:
        body += f"<@{key}>"
        print(dict[key])
        for s in dict[key]:
            body += f"\n- <@{s[0]}> | {s[1][0]}{'' if s[1][1] == -1 else ' | ' + str(bool(s[1][1]))}"
        body += "\n\n"
    
    embed = discord.Embed(title=f"Inspection Week Starting {week_start}", description=body, color=maincolour)
    
    await interaction.followup.send(embed=embed)

@quotaGroup.command(name = "get_history", description='Get a users most recent weeks of quota history')
async def eightweek(interaction: discord.Interaction, staff_member : discord.Member):
    await interaction.response.send_message(await GetQuotaHistory(staff_member.id), ephemeral=True)

@quotaGroup.command(name = "mvp", description='Get the mvp list for a week')
async def getmvp(interaction: discord.Interaction, week_start : str):
    await interaction.response.defer(thinking=True)
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, PostsCompleted 
                            FROM Inspections
                            WHERE WeekStart=? AND PostsCompleted > 99
                            ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
            results1 = await cursor.fetchall()
    
    
    async with aiosqlite.connect(database) as db:
        async with db.execute("""SELECT InspecteeID, PostsCompleted 
                            FROM SeniorInspections
                            WHERE WeekStart=? AND PostsCompleted > 99
                            ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
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

@tree.command(guild = discord.Object(id=guild_id), name = "checkstrikestreak", description='Check your current strike streak')
async def checkstreak(interaction: discord.Interaction):
    await interaction.response.send_message(f"Your current strike streak is `{await Get_Consecutive_Strikes(interaction.user.id)}`", ephemeral=True)

@tree.command(guild = discord.Object(id=guild_id), name = "sql", description='Run SQL')
async def run_sql(interaction: discord.Interaction, sql : str):
    if interaction.user.id == 378963670589505557:
        if "SELECT" in sql:
            async with aiosqlite.connect(database) as db:
                async with db.execute(sql) as cursor:
                    rows = await cursor.fetchall()
                    if rows != None:
                        await interaction.response.send_message(str(rows), ephemeral=True)
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
        await interaction.response.send_message("not for you", ephemeral=True)


@logQuota.autocomplete('week_start')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    choicelist = []   
    
    for i in range(-9,0):
        dt = datetime.now() + timedelta(days=i)
        if dt.weekday() == 0:
            choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
    
    return choicelist

@viewWeek.autocomplete('week_start')
@giveReward.autocomplete('week_start')
@getmvp.autocomplete('week_start')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    choicelist = []   
    
    for i in range(-62,0):
        dt = datetime.now() + timedelta(days=i)
        if dt.weekday() == 0:
            choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
    
    return choicelist


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