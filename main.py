import os
import time
from datetime import datetime, timedelta, time, timezone
from typing import Literal, Optional
import re
import ast
import heapq
import aiofiles

import discord
import aiosqlite
from discord import ButtonStyle, app_commands, ui
from discord.ext import tasks, commands
from discord.utils import get
from discord.app_commands import AppCommandError, Group
from dotenv import load_dotenv
load_dotenv()

GUILD_ID = 768851165671850015
QUOTA_DATABASE = 'quotaDB.sqlite'

def print_red(text):
    print(f"\033[1;31m{text}\033[0m")

def print_green(text):
    print(f"\033[1;32m{text}\033[0m")


class ColourHexes():
    RED = 0xFF0000
    DARK_RED = 0x8b0000
    ORANGE = 0xFFA500
    GREEN = 0x00FF00
    DARK_ORANGE = 0xDC582A
    MP_PURPLE = 0xA46FFF

class ChannelIds():
    QUOTA_LOGS = 1208810891626151976
    STRIKE_LOGS = 1208827574998933616
    SENIOR_QUOTA_LOGS = 1259211052164583425
    SENIOR_STRIKE_LOGS = 1259211191650222130
    SENIOR_CHAT = 1173680917374578718

class RoleIds():
    MANAGEMENT = 768851165671850022
    SENIOR = 768851165671850021
    INTERN = 1234584425547694081
    STAFF = 796462879246909532
    CANDIDATE = 768851165671850017
    MVP = 1270033237049348116

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!!", intents=discord.Intents.all(), help_command=None)

        self.synced = False

    async def remove_role_from_thread(self, thread, role):
        for m in role.members:
            await thread.remove_user(m)

    async def has_role_f(self, staff_member, role_id):
        if isinstance(staff_member, discord.Member):
            return role_id in [r.id for r in staff_member.roles]
        elif isinstance(staff_member, int):
            guild = myBot.get_guild(GUILD_ID)
            try:
                staff_member_obj = guild.get_member(staff_member)
                return role_id in [r.id for r in staff_member_obj.roles]
            except discord.NotFound:
                return False

    async def is_management(self, staff_member):
        return await self.has_role_f(staff_member, RoleIds.MANAGEMENT)

    async def is_senior(self, staff_member):
        return await self.has_role_f(staff_member, RoleIds.SENIOR)

    async def is_intern(self, staff_member):
        return await self.has_role_f(staff_member, RoleIds.INTERN) and not await self.has_role_f(staff_member, RoleIds.STAFF)

    async def log_quota(self, staff_member : discord.Member, logger : discord.Member, post_count : int, ticket_count : int, week_start : str, activity : bool = None, override_excused : bool = False, apply_rewards : bool = True, auto_strike : bool = True, override_existing : bool = False, dm_user : bool = True):
        # all wrong to do with senior quota (post count)
        print_green("Log quota being called")
        reward_excused = False
        striked = False
        Is_Senior = await myBot.is_senior(staff_member)
        
        # work out the target users quota requirement
        requirement = await myBot.get_quota()
        ticketrequirement = 0
        if Is_Senior:
            requirement = await myBot.get_senior_quota()
            ticketrequirement = await myBot.get_senior_ticket_quota()
        elif await myBot.is_intern(staff_member):
            requirement = await myBot.get_intern_quota()

        # check if inspector is a senior
        if not await myBot.is_senior(logger):
            return "Logger not senior"

        #ensure valid date
        if not await myBot.check_valid_date(week_start):
            return "Invalid date"

        # checks if theyre a senior but the activity param is empty (somethings wrong)
        if Is_Senior and activity == None:
            return "Fill in activity for seniors"

        # checks if someone is trying to record activity for a non-senior
        if not Is_Senior and activity != None:
            return "Do not put activity"

        # ensure users quota hasnt already been recorded for that week
        existing_quota = None
        if not Is_Senior:
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute('SELECT InspecteeID FROM Inspections WHERE WeekStart=? AND InspecteeID=?', (week_start,staff_member.id)) as cursor:
                    existing_quota = await cursor.fetchone()
        else:
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute('SELECT InspecteeID FROM SeniorInspections WHERE WeekStart=? AND InspecteeID=?', (week_start,staff_member.id)) as cursor:
                    existing_quota = await cursor.fetchone()
        if existing_quota is not None and not override_existing:
            return

        # Excused
        excused = False
        if not override_excused and post_count < requirement:
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute('SELECT StaffID FROM Excused WHERE InspectionCount > 0 AND StaffID = ?', (staff_member.id,)) as cursor:
                    row = await cursor.fetchone()
                if row is not None:
                    excused = True
                    await db.execute('UPDATE Excused SET InspectionCount = InspectionCount - 1 WHERE StaffID = ?', (staff_member.id,))
                    await db.execute('DELETE FROM Excused WHERE InspectionCount = 0 AND StaffID = ?', (staff_member.id,))
                    await db.commit()
        elif override_excused:
            excused = True
        
        # REWARDS
        if apply_rewards and not excused and post_count < requirement and not Is_Senior:
            async with aiosqlite.connect(QUOTA_DATABASE) as db: # get rewards
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
                                    async with aiosqlite.connect(QUOTA_DATABASE) as db:
                                        await db.execute('UPDATE Rewards SET Charges=? WHERE RecipientID=? AND Charges > 0 AND ID=? AND Type=?', (reward[3] - 1, staff_member.id, r[0], "Quota Half"))
                                        await db.commit()
                                    reward_excused = True
                                    break
                        if i == 1:
                            if "Excused" in reward[1]:
                                async with aiosqlite.connect(QUOTA_DATABASE) as db:
                                    await db.execute('UPDATE Rewards SET Charges=? WHERE RecipientID=? AND Charges > 0 AND ID=? AND Type=?', (reward[3] - 1, staff_member.id, r[0], "Quota Excused"))
                                    await db.commit()
                                reward_excused = True
                                break


        # STRIKES
        if auto_strike and not excused and not reward_excused:
            if not Is_Senior:
                if post_count < requirement:
                    striked = True
                    async with aiosqlite.connect(QUOTA_DATABASE) as db:
                        await db.execute('INSERT INTO Strikes (RecipientID, SeniorID, DateGiven) VALUES (?, ?, ?)', (staff_member.id, logger.id, week_start))
                        await db.commit()
            else:
                if post_count < requirement and not activity:
                    striked = True
                    async with aiosqlite.connect(QUOTA_DATABASE) as db:
                        await db.execute('INSERT INTO Strikes (RecipientID, SeniorID, DateGiven) VALUES (?, ?, ?)', (staff_member.id, logger.id, week_start))
                        await db.commit()


        # FINAL SQL
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute('SELECT StartDate FROM Weeks WHERE StartDate=?', (week_start,)) as cursor:
                existing_week = await cursor.fetchone()
            
            if existing_week is None:
                await db.execute('INSERT INTO Weeks (StartDate, PostRequirement, SeniorPostRequirement, InternPostRequirement) VALUES (?, ?, ?, ?)', (week_start, await myBot.get_quota(), await myBot.get_senior_quota(), await myBot.get_intern_quota()))
                await db.commit()
            
            if not Is_Senior:
                await db.execute('INSERT OR REPLACE INTO Inspections (InspecteeID, InspectorID, PostsCompleted, WeekStart, InactivityExcused, RewardExcused, Pass, TicketsCompleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                                    (staff_member.id, logger.id, post_count, week_start, int(excused), int(reward_excused), int(post_count >= requirement or int(excused) or int(reward_excused)), ticket_count))
            else:
                await db.execute('INSERT OR REPLACE INTO SeniorInspections (InspecteeID, InspectorID, PostsCompleted, Activity, WeekStart, InactivityExcused, RewardExcused, Pass, TicketsCompleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                                    (staff_member.id, logger.id, post_count, int(activity), week_start, int(excused), int(reward_excused), int(post_count >= requirement and ticket_count >= ticketrequirement and activity or excused or reward_excused), ticket_count))

            await db.commit()


        logchannel = self.get_channel(ChannelIds.QUOTA_LOGS)
        strikelogchannel = self.get_channel(ChannelIds.STRIKE_LOGS)
        if Is_Senior:
            logchannel = self.get_channel(ChannelIds.SENIOR_QUOTA_LOGS)
            strikelogchannel = self.get_channel(ChannelIds.SENIOR_STRIKE_LOGS)
        
        logmsg = ""
        print("A")
        if post_count > int(await self.get_variable("post_limit")):
            print(int(await self.get_variable("post_limit")))
            print(post_count > int(await self.get_variable("post_limit")))
            print("B")
            logmsg += f"# ⚠️ Quota Limit Exceeded ⚠️\n"
        print("C")
        logmsg += f"### {logger.mention} logged {staff_member.mention}'s quota.\n{await myBot.get_quota_history(staff_member.id, 1)}"
        logmsgsent = await logchannel.send(logmsg)
        
        finalmsg = f"Quota logged successfully."

        if override_existing:
            finalmsg += f"\nIf this user already had a quota recorded, it has been overridden!\n**Please do the following:**\n- Delete the old log in <#{ChannelIds.QUOTA_LOGS}>\n- Remove any old strikes the user may have gotten (if the old quota recorded as a fail)\n- Replenish any rewards mistakenly consumed by this action"

        if striked:
            finalmsg += "\n- The user was striked"
        if reward_excused:
            finalmsg += "\n- The user was excused by an active reward"

        # STRIKE CHECK
        strike_streak = await myBot.get_consecutive_strikes(staff_member.id)
        if strike_streak > 0:
            finalmsg += f"\n\nPlease note that this user's current consecutive strike streak is now `{strike_streak}`, any actions that need to be taken based on this information are not automated."

        if striked:
            await strikelogchannel.send(f"{staff_member.mention} [was striked]({logmsgsent.jump_url})\n\nQuota History:\n{await myBot.get_quota_history(staff_member.id)}")

        dm_msg = f"# <:MP:1173683497697808424> | Weekly Inspection Notice\n### {logger.mention} has logged your quota for the week beginning {week_start}\n- Posts: {post_count}"
        
        if Is_Senior:
            dm_msg += f"\n- Activity: {activity}"
            
        dm_msg += f"\n\nYour recent quota history:\n{await myBot.get_quota_history(staff_member.id, 5)}"
        
        if dm_user:
            await staff_member.send(dm_msg)
        
        return finalmsg

    async def csv_role(self, role : discord.Role, splitby : int = 420, pingable : bool = False, excluding : discord.Role = None, splitbygroups : int = 0, return_list : bool = False):
        if pingable:
            ids = [f"`<@{m.id}>`" for m in role.members if not excluding in m.roles]
        else:
            ids = [f"{m.id}" for m in role.members if not excluding in m.roles]
        
        output = ""
        temp = ""

        for id in ids:
            if splitbygroups == 0:
                temp += f"{id},"
                if len(temp.split(",")) > splitby:
                    output += temp[:-1]
                    output += "\n\n"
                    temp = ""
            else:
                outputs = []
                roughsize = len(ids) // splitbygroups
                for i in range(0, splitbygroups):
                    # 0-roughsize, roughsize-roughsize*2,
                    outputs.append(ids[i*roughsize : (i+1)*roughsize if i != splitbygroups - 1 else len(ids)])
                    
                    output = "\n\n".join([",".join(idlist) for idlist in outputs])
        
        if temp != "":
            output += temp[:-1]
        
        if return_list:
            return output.split("\n\n")
        return output

    async def get_variable(self, key):
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            async with db.execute('SELECT value FROM Quotas WHERE key=?', (key,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def set_variable(self, key, value):
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
            await db.execute('INSERT OR REPLACE INTO Quotas (key, value) VALUES (?, ?)', (key, value))
            await db.commit()

    async def get_quota(self, ):
        result = await self.get_variable("normal")
        return int(result) if result is not None else None

    async def get_senior_ticket_quota(self, ):
        result = await self.get_variable("senior_tickets")
        return int(result) if result is not None else None

    async def get_senior_quota(self, ):
        result = await self.get_variable("senior")
        return int(result) if result is not None else None

    async def get_intern_quota(self, ):
        result = await self.get_variable("intern")
        return int(result) if result is not None else None

    async def check_valid_date(self, date : str):
        return re.match(r"^20[0-9]{2}-([1-9]|1[0-2])-([1-9]|[12][0-9]|3[01])$", date) is not None

    async def get_quota_history(self, staff_member : int, limit : int = 20):
        
        if not await self.is_senior(staff_member):
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute("""SELECT WeekStart, Pass, PostsCompleted, InactivityExcused, RewardExcused, TicketsCompleted
                                        FROM Inspections
                                        WHERE InspecteeID = ?
                                        ORDER BY printf("%04d-%02d-%02d", 
                                        substr(WeekStart, 1, instr(WeekStart, '-') - 1), 
                                        substr(WeekStart, instr(WeekStart, '-') + 1, 2), 
                                        substr(WeekStart, -2)) DESC
                                        LIMIT ?""", (staff_member, str(limit))) as cursor:
                    rows = await cursor.fetchall()
        else:
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute("""SELECT WeekStart, Pass, PostsCompleted, InactivityExcused, RewardExcused, TicketsCompleted
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
                output += f"[0;34m{row[0]} - Reward Excused"
            elif int(row[3] == 1):
                output += f"[0;33m{row[0]} - Inactivity Excused"
            elif int(row[1]) == 1:
                output += f"[0;32m{row[0]} - Pass"
            else:
                output += f"[0;31m{row[0]} - Fail"
            output +=  f" - {row[2]} posts - {row[5]} tickets\n"
        output += "```"
        if (len(rows) == 0):
            output = "No Results"
        return output

    async def get_consecutive_strikes(self, staff_member : int): # only accurate if quota logs are fully up to date
        flat_list = []
        
        
        # as of 27-1-24, this seems to work
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
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

    async def setup_hook(self) -> None:
        await self.load_extension("commands.rewards")
        await self.load_extension("commands.quota")
        if not self.weekly_quota_reminder_before.is_running():
            self.weekly_quota_reminder_before.start()
        if not self.weekly_quota_reminder_after.is_running():
            self.weekly_quota_reminder_after.start()
        async with aiosqlite.connect(QUOTA_DATABASE) as db:
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
                                )""")
            
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
        # if not self.synced:
        #     await tree.sync(guild = discord.Object(id=guild_id))
        #     self.synced = True
        if not self.experienced_role_distribute.is_running():
            self.experienced_role_distribute.start()
        print_green(self.guilds)
        print_green(f"Logged in as {self.user}.")

    @tasks.loop(hours=1)
    async def experienced_role_distribute(self):
        print_green("Experienced Role Task")
        guild = myBot.get_guild(GUILD_ID)
        for m in guild.members:
            if m.joined_at and m.joined_at < datetime.now(timezone.utc) - timedelta(days=182) and not m.bot and not await self.has_role_f(m, 768851165671850023):
                role = get(guild.roles, id=1281614132419891200)
                await m.add_roles(role)
                if m.joined_at and m.joined_at < datetime.now(timezone.utc) - timedelta(days=365) and not m.bot and not await self.has_role_f(m, 768851165671850023):
                    role = get(guild.roles, id=1281621829936615484)
                    await m.add_roles(role)
                    if m.joined_at and m.joined_at < datetime.now(timezone.utc) - timedelta(days=365*2) and not m.bot and not await self.has_role_f(m, 768851165671850023):
                        role = get(guild.roles, id=1415810558518890577)
                        await m.add_roles(role)

    weekly_reminder_time_before = time(hour=18, tzinfo=timezone.utc)

    @tasks.loop(time=weekly_reminder_time_before)
    async def weekly_quota_reminder_before(self, force = False):
        if datetime.now(timezone.utc).weekday() == 6 or force:
            guild = myBot.get_guild(GUILD_ID)
            reminder_channel = get(guild.channels, id = ChannelIds.SENIOR_CHAT)
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute('SELECT StaffID FROM Excused WHERE InspectionCount > 0') as cursor:
                    rows = await cursor.fetchall()
            inactive_staff = [row[0] for row in rows]
            senior_list = [m for m in get(guild.roles, id = RoleIds.SENIOR).members if not await self.has_role_f(m, RoleIds.MANAGEMENT) and m.id not in inactive_staff]
            senior_count = len(senior_list)
            groups = await self.csv_role(
                get(guild.roles, id = RoleIds.STAFF),
                excluding=get(guild.roles, id = RoleIds.SENIOR),
                splitbygroups=senior_count,
                return_list=True
                )
            output = ""
            for i in range(0, senior_count):
                output += f"## Group {senior_list[i].mention}\n{groups[i]}\n\n"
            if len(groups) != senior_count:
                output += f"## Someone Else\n{groups[senior_count]}\n\n"
            await reminder_channel.send(f"# <@&768851165671850021> Inspections can be submitted now.\n\nPlease inspect these groups:\n{output}")

    weekly_reminder_time_after = time(hour=12, tzinfo=timezone.utc)

    @tasks.loop(time=weekly_reminder_time_after)
    async def weekly_quota_reminder_after(self):
        if datetime.now(timezone.utc).weekday() == 0:
            guild = myBot.get_guild(GUILD_ID)
            reminder_channel = get(guild.channels, id = ChannelIds.SENIOR_CHAT)
            dt = datetime.now() - timedelta(days=7)
            week_start = f"{dt.year}-{dt.month}-{dt.day}"
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute("""SELECT InspectorID
                                    FROM Inspections
                                    WHERE WeekStart=?
                                    ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                    results1 = await cursor.fetchall()
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                async with db.execute("""SELECT InspectorID
                                    FROM SeniorInspections
                                    WHERE WeekStart=?
                                    ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                    results2 = await cursor.fetchall()
            logged_loggers = [row[0] for row in results1] + [row[0] for row in results2]
            expected_loggers = [m.id for m in get(guild.roles, id = RoleIds.SENIOR).members]
            missing_loggers = list(set(logged_loggers).symmetric_difference(set(expected_loggers)))

            if len(missing_loggers) > 0:
                await reminder_channel.send(f"{",".join([f'<@{ml}>' for ml in missing_loggers])}\n\nQuotas should all be in by now. Last call.")

myBot = Bot()
tree = myBot.tree

@myBot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
            print(synced)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

@tree.command(guild = discord.Object(id=GUILD_ID), name = "mvp_colour", description='Choose the MVP role colour')
@app_commands.describe(hex_code="Expects 6 characters representing a colour. E.g: FF13A5")
@app_commands.checks.has_role(RoleIds.MVP)
async def mvpcolour(interaction: discord.Interaction, hex_code : str):
    await get(interaction.guild.roles, id = RoleIds.MVP).edit(colour=discord.Colour.from_str(f"0x{hex_code}"))
    await interaction.response.send_message("Success!", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "check_history", description='Check your own quota history!')
async def getownhistory(interaction: discord.Interaction):
    await interaction.response.send_message(await myBot.get_quota_history(interaction.user.id), ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "csvpingable", description='Yep')
async def csvpingable(interaction: discord.Interaction, csv_ids : str):
    output = ""
    for uid in csv_ids.split(","):
        output += f"<@{str(uid).strip()}>\n"
    await interaction.response.send_message(f"```{output}```", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "csv_role", description='Get a csv of a role')
async def csv_role_cmd(interaction: discord.Interaction, role : discord.Role, splitby : int = 420, pingable : bool = False, excluding : discord.Role = None, splitbygroups : int = 0):
    await interaction.response.send_message(await myBot.csv_role(role, splitby, pingable, excluding, splitbygroups), ephemeral=True)


@tree.command(guild = discord.Object(id=GUILD_ID), name = "sql", description='Run SQL')
async def run_sql(interaction: discord.Interaction, sql : str):
    if interaction.user.id == 378963670589505557:
        if "SELECT" == sql.split(" ")[0]:
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
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
            async with aiosqlite.connect(QUOTA_DATABASE) as db:
                await db.execute(sql)
                await db.commit()
            await interaction.response.send_message("Done!", ephemeral=True)
            return
    else:
        await interaction.response.send_message("not for you go away!", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "make_groups", description='Sorts interns into sr timezone groups')
@app_commands.checks.has_role(RoleIds.MANAGEMENT)
async def make_intern_groups(interaction: discord.Interaction, copyable : bool = False, csv_groups : bool = False):
    
    interns = []
    leaders = []
    
    candidate_role = get(interaction.guild.roles, id = RoleIds.CANDIDATE)

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
            color = ColourHexes.MP_PURPLE,
            description = output,
            title = "Intern groupings"
        )
        await interaction.response.send_message(embed=embed)
    # print(sort_interns(leaders, interns))

@tree.command(guild = discord.Object(id=GUILD_ID), name = "assign_prefix", description='Give everyone a prefix in their nickname')
@app_commands.checks.has_role(RoleIds.SENIOR)
async def assign_prefix(interaction: discord.Interaction, new_prefix : str, old_prefix : str = None):
    await interaction.response.defer(thinking=True, ephemeral=True)
    counter = 0
    for m in interaction.guild.members:
        if old_prefix is not None:
            if m.nick is not None and m.nick.startswith(old_prefix):
                new_nick = new_prefix + m.nick[len(old_prefix):]
                try:
                    await m.edit(nick=new_nick)
                    counter += 1
                except:
                    pass # missing permissions
        else:
            if m.nick is not None and not m.nick.startswith(new_prefix):
                new_nick = new_prefix + " " + m.nick
                try:
                    await m.edit(nick=new_nick)
                    counter += 1
                except:
                    pass # missing permissions
    await interaction.followup.send(f"Successfully changed {counter} nicknames", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "view_all_history", description='View everyones quota history')
@app_commands.checks.has_role(RoleIds.MANAGEMENT)
async def view_all_history(interaction: discord.Interaction, role : discord.Role, amount : int = 10):
    await interaction.response.defer(thinking=True, ephemeral=True)
    msg = ""
    counter = 0
    for uid in [m.id for m in role.members]:
        msg += f"<@{uid}>\n\n{await myBot.get_quota_history(uid, amount)}\n\n"
        counter += 1
        if counter % 3 == 0:
            await interaction.user.send(msg)
            msg = ""
    
    await interaction.followup.send(f"Sent you all {counter} quota histories!", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "role_all", description='Give everyone with a role a role')
async def role_all(interaction: discord.Interaction, has_role : discord.Role, to_give : discord.Role, excluding : str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    counter = 0
    for user_with_role in has_role.members:
        if user_with_role.id not in [int(id.strip()) for id in excluding.split(",")]:
            await user_with_role.add_roles(to_give)
            counter += 1
    await interaction.followup.send(f"Successfully roled {counter} people", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "role_all_csv", description='Give everyone in a csv a role')
async def role_all_csv(interaction: discord.Interaction, csv : str, to_give : discord.Role, excluding : str = "1,2", remove : bool = False):
    await interaction.response.defer(thinking=True, ephemeral=True)
    counter = 0
    for uid in csv.split(","):
        uid = int(uid.strip())
        if uid not in [int(id_excl.strip()) for id_excl in excluding.split(",")]:
            try:
                if remove:
                    await get(interaction.guild.members, id=uid).remove_roles(to_give)
                else:
                    await get(interaction.guild.members, id=uid).add_roles(to_give)
                counter += 1
            except:
                pass # User is not a member
    await interaction.followup.send(f"Successfully roled {counter} people", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "top_performer", description='Get the top performers')
@app_commands.checks.has_role(RoleIds.MANAGEMENT)
async def top_performer(interaction: discord.Interaction, weeks : int = 4, amount : int = 3):
    await interaction.response.defer(thinking=True, ephemeral=True)
    top_posts = None
    top_tickets = None
    async with aiosqlite.connect(QUOTA_DATABASE) as db:
        query = f"""
            WITH RankedInspections AS (
            SELECT InspecteeID, PostsCompleted, TicketsCompleted,
                ROW_NUMBER() OVER (
                    PARTITION BY InspecteeID
                    ORDER BY ID DESC
                ) AS RowNum
            FROM Inspections
            )
            SELECT InspecteeID, SUM(PostsCompleted) AS PostsCompletedSum, SUM(TicketsCompleted) AS TicketsCompletedSum
            FROM RankedInspections
            WHERE RowNum <= {weeks}
            GROUP BY InspecteeID
            ORDER BY PostsCompletedSum DESC;
            """
        async with db.execute(query) as cursor:
            results = await cursor.fetchall()
            posts = {}
            tickets = {}
            for row in results:
                if interaction.guild.get_member(int(row[0])) is None:
                    continue
                if await myBot.is_senior(int(row[0])):
                    continue
                posts[int(row[0])] = int(row[1] if row[1] is not None else 0)
                tickets[int(row[0])] = int(row[2] if row[2] is not None else 0)
            top_posts = heapq.nlargest(amount, posts.items(), key=lambda x: x[1])
            top_tickets = heapq.nlargest(amount, tickets.items(), key=lambda x: x[1])
    await interaction.followup.send(f"{top_posts}\n{top_tickets}", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "get_date", description='Get the dates of the next inspection period')
async def get_date(interaction: discord.Interaction, id_csv : str = ""):
    mondays = []
    counter = 0
    while len(mondays) < 2:
        dt = datetime.now() - timedelta(days=counter)
        counter += 1
        if dt.weekday() == 0:
            mondays.append(dt)
    output = ""
    for m in mondays:
        if len(id_csv) == 0:
            output += f"### {(datetime.now() - m).days} days ago\n"
            output += f"```/quota department:Marketplace quota_start:{m.strftime("%m/%d/%Y")} quota_end:{(m + timedelta(days=7)).strftime("%m/%d/%Y")}```\n"
        else:
            output += f"### {(datetime.now() - m).days} days ago\n"
            for i in range(0, len(id_csv.split(",")), 10):
                id_chunk = ",".join(id_csv.split(",")[i:i+10])
                output += f"```/quota department:Marketplace quota_start:{m.strftime("%m/%d/%Y")} quota_end:{(m + timedelta(days=7)).strftime("%m/%d/%Y")}"
                output += f" user_ids:{id_chunk}"
                output += "```\n"
            if len(id_csv.split(",")) > 10:
                output += "\n**More than 10 IDs, you cannot copy all of the data into the parse command**\n"
    await interaction.response.send_message(output, ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "parse_users", description='Fish out usernames from a messy string')
async def parse_users(interaction: discord.Interaction, string : str, only_mentions : bool = False):
    split_data = re.split(r"[,;:\s]+", string)
    
    output = ""
    
    for potential_user in split_data:
        potential_user = potential_user.strip()
        if potential_user.isnumeric():
            user = get(interaction.guild.members, id=int(potential_user))
        else:
            user = get(interaction.guild.members, name=potential_user)
        if user:
            if only_mentions:
                output += f"`{user.mention}`\n"
            else:
                output += f"{user.name} (`<@{user.id}>`)\n"
    await interaction.response.send_message(f"{output}", ephemeral=True)

@tree.command(guild = discord.Object(id=GUILD_ID), name = "weekly_inspection", description='Trigger the weekly inspection')
@app_commands.checks.has_role(RoleIds.MANAGEMENT)
async def trigger_weekly_inspection(interaction: discord.Interaction):
    await myBot.weekly_quota_reminder_before(force=True)
    await interaction.response.send_message("Weekly inspection reminder sent!", ephemeral=True)

class ParseDataModal(ui.Modal, title='Data parser'):
    def __init__(self):
        super().__init__()

    data = ui.TextInput(label='Data', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        split_data = self.data.value.split('\n')

        # Process the data here
        result = ""
        counter = 0
        for line in split_data:
            if '|' in line:
                username, score = line.split('|')
                username = username.strip()
                score = score.strip()
                user = get(interaction.guild.members, name=username)
                username = f"`{username}`"
                if user:
                    try:
                        await user.send(f"Your score: {score}")
                        result += f"Sent {username} a message\n"
                        counter += 1
                    except discord.Forbidden:
                        result += f"Could not DM {username}\n"
                else:
                    result += f"User {username} not found\n"
        await interaction.followup.send(f"Sent `{counter}` messages.\n\n{result}", ephemeral=True)

@tree.command(guild=discord.Object(id=GUILD_ID), name="dm_quiz_data", description="Open a modal to parse data")
async def dm_quiz_data(interaction: discord.Interaction):
    modal = ParseDataModal()
    await interaction.response.send_modal(modal)

def insert_returns(body):
    if isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(body[-1].value)
        ast.fix_missing_locations(body[-1])

    if isinstance(body[-1], ast.If):
        insert_returns(body[-1].body)
        insert_returns(body[-1].orelse)

    if isinstance(body[-1], ast.With):
        insert_returns(body[-1].body)

@tree.command(guild = discord.Object(id=GUILD_ID), name="eval", description="Eval something")
async def eval_py(interaction : discord.Interaction, cmd : str, ephemeral : bool = True):
    if interaction.user.id == 378963670589505557:
        fn_name = "_eval_expr"
        # wrap in async def body
        body = f"async def {fn_name}():\n\t{cmd}"
        parsed = ast.parse(body)
        body = parsed.body[0].body
        insert_returns(body)
        env = {
            'bot': myBot,
            'discord': discord,
            'interaction': interaction,
            'datetime' : datetime,
            '__import__': __import__
        }
        exec(compile(parsed, filename="<ast>", mode="exec"), env)
        result = str(await eval(f"{fn_name}()", env))
        if len(result) == 0:
            result = "No return value"
        await interaction.response.send_message(result, ephemeral=ephemeral)
    else:
        await interaction.response.send_message("YOU ARENT ME!!!", ephemeral=True)

@myBot.event
async def on_app_command_completion(interaction : discord.Interaction, command : app_commands.Command):
    print_red(f"{interaction.user.name} ({interaction.user.id}) Used command {command.name}")
    async with aiofiles.open("command_logs.txt", "a") as f:
        await f.write(f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | {interaction.user.name} ({interaction.user.id}) Used command {command.name}" + "\n")

@myBot.event
async def on_message(message : discord.Message):
    if message.author == myBot.user:
        return
    
    if message.author.id == 247034267601862656:
        if "chills" in message.content.lower():
            await message.channel.send("Chills bro, chills.")
@tree.error
async def on_app_command_error(interaction : discord.Interaction, error : AppCommandError):
    print_red(error)
    if isinstance(error, app_commands.MissingRole) or isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("You're missing a role!", ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"You're on cooldown for another `{int(error.retry_after)}` seconds!", ephemeral=True)
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You're missing a permission!", ephemeral=True)


if __name__ == '__main__':
    myBot.run(f"{os.getenv('token')}")
