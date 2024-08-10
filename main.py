import os
import discord
from discord import ButtonStyle, app_commands, ui
from discord.ext import tasks, commands
from discord.utils import get
from discord.app_commands import AppCommandError, Group
import aiosqlite
import time
from datetime import datetime, timedelta, time
import asyncio
from typing import Literal, Optional
import re
import math
import itertools
import ast
from dotenv import load_dotenv

load_dotenv()

guild_id = 768851165671850015

database = 'quotaDB.sqlite'

def print_red(text):
    print(f"\033[1;31m{text}\033[0m")

def print_green(text):
    print(f"\033[1;32m{text}\033[0m")


class colours():
    red = 0xFF0000
    darkred = 0x8b0000
    orange = 0xFFA500
    green = 0x00FF00
    darkorange = 0xDC582A
    mp_purple = 0xA46FFF

class channel_ids():
    quota_logs = 1208810891626151976
    strike_logs = 1208827574998933616
    senior_quota_logs = 1259211052164583425
    senior_strike_logs = 1259211191650222130

class role_ids():
    management = 768851165671850022
    senior = 768851165671850021
    intern = 1234584425547694081
    staff = 796462879246909532
    candidate = 768851165671850017
    mvp = 1270033237049348116

class bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!!", intents=discord.Intents.all(), help_command=None)
        
        self.synced = False
    
    async def has_role_f(self, staff_member, role_id):
        if isinstance(staff_member, discord.Member):
            return role_id in [r.id for r in staff_member.roles]
        elif isinstance(staff_member, int):
            print(guild_id)
            print(len(aclient.guilds))
            guild = aclient.get_guild(guild_id)
            print(guild)
            try:
                staff_member_obj = guild.get_member(staff_member)
                return role_id in [r.id for r in staff_member_obj.roles]
            except discord.NotFound:
                return False

    async def IsManagement(self, staff_member):
        return await self.has_role_f(staff_member, role_ids.management)

    async def IsSenior(self, staff_member):
        return await self.has_role_f(staff_member, role_ids.senior)

    async def IsIntern(self, staff_member):
        return await self.has_role_f(staff_member, role_ids.intern)

    async def get_variable(self, key):
        async with aiosqlite.connect(database) as db:
            async with db.execute('SELECT value FROM Quotas WHERE key=?', (key,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def set_variable(self, key, value):
        async with aiosqlite.connect(database) as db:
            await db.execute('INSERT OR REPLACE INTO Quotas (key, value) VALUES (?, ?)', (key, value))
            await db.commit()

    async def getQuota(self, ):
        result = await self.get_variable("normal")
        return int(result) if result is not None else None

    async def getSeniorTicketQuota(self, ):
        result = await self.get_variable("senior_tickets")
        return int(result) if result is not None else None

    async def getSeniorQuota(self, ):
        result = await self.get_variable("senior")
        return int(result) if result is not None else None

    async def getInternQuota(self, ):
        result = await self.get_variable("intern")
        return int(result) if result is not None else None

    async def CheckValidDate(self, date : str):
        return re.match(r"^20[0-9]{2}-([1-9]|1[0-2])-([1-9]|[12][0-9]|3[01])$", date) is not None

    async def GetQuotaHistory(self, staff_member : int, limit : int = 20):
        
        if not await self.IsSenior(staff_member):
            async with aiosqlite.connect(database) as db:
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
            async with aiosqlite.connect(database) as db:
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
                output += f"[0;34m{row[0]} - Reward Excused - {row[2]} posts\n"
            elif int(row[3] == 1):
                output += f"[0;33m{row[0]} - Inactivity Excused - {row[2]} posts\n"
            elif int(row[1]) == 1:
                output += f"[0;32m{row[0]} - Pass - {row[2]} posts - {row[5]} tickets\n"
            else:
                output += f"[0;31m{row[0]} - Fail - {row[2]} posts - {row[5]} tickets\n"
        output += "```"
        if (len(rows) == 0):
            output = "No Results"
        return output
        # maybe done idk

    async def Get_Consecutive_Strikes(self, staff_member : int): # only accurate if quota logs are fully up to date
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
    
    async def setup_hook(self) -> None:
        
        await self.load_extension("commands.rewards.rewards")
        await self.load_extension("commands.quota.quota")
        # await self.load_extension("commands.intern.intern")
        
        if not self.weekly_quota_reminder.is_running():
            self.weekly_quota_reminder.start()
        
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
        print_green(self.guilds)
        print_green(f"Logged in as {self.user}.")
    
    weekly_reminder_time = time(hour=12)

    @tasks.loop(time=weekly_reminder_time)
    async def weekly_quota_reminder(self):
        if datetime.now().weekday() == 0:
            guild = aclient.get_guild(guild_id)
            reminder_channel = get(guild.channels, id = 1173680917374578718)
            
            dt = datetime.now() - timedelta(days=7)
            week_start = f"{dt.year}-{dt.month}-{dt.day}"
            
            async with aiosqlite.connect(database) as db:
                async with db.execute("""SELECT InspectorID
                                    FROM Inspections
                                    WHERE WeekStart=?
                                    ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                    results1 = await cursor.fetchall()
            
            
            async with aiosqlite.connect(database) as db:
                async with db.execute("""SELECT InspectorID 
                                    FROM SeniorInspections
                                    WHERE WeekStart=?
                                    ORDER BY PostsCompleted DESC""", (week_start,)) as cursor:
                    results2 = await cursor.fetchall()
            
            
            loggedLoggers = [row[0] for row in results1] + [row[0] for row in results2]

            expectedLoggers = [m.id for m in get(guild.roles, id = role_ids.senior).members]
            
            missingLoggers = list(set(loggedLoggers).symmetric_difference(set(expectedLoggers)))
            
            if len(missingLoggers) > 0:
                await reminder_channel.send(f"{",".join([f'<@{ml}>' for ml in missingLoggers])}\n\nQuotas should all be in by now. Last call.")
                

    
        
aclient = bot()
tree = aclient.tree

@aclient.command()
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

@tree.command(guild = discord.Object(id=guild_id), name = "mvp_colour", description='Choose the MVP role colour')
@app_commands.describe(hex_code="Expects 6 characters representing a colour. E.g: FF13A5")
@app_commands.checks.has_role(role_ids.mvp)
async def mvpcolour(interaction: discord.Interaction, hex_code : str):
    await get(interaction.guild.roles, id = role_ids.mvp).edit(colour=discord.Colour.from_str(f"0x{hex_code}"))
    
    await interaction.response.send_message("Success!", ephemeral=True)

@tree.command(guild = discord.Object(id=guild_id), name = "check_history", description='Check your own quota history!')
async def getownhistory(interaction: discord.Interaction):
    await interaction.response.send_message(await aclient.GetQuotaHistory(interaction.user.id), ephemeral=True)

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
        if "SELECT" == sql.split(" ")[0]:
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
            async with aiosqlite.connect(database).cursor() as cursor:
                await cursor.execute(sql)
                affectedNo = cursor.rowcount
                await cursor.commit()
            await interaction.response.send_message(f"Done! - Change impacted `{affectedNo}` rows", ephemeral=True)
            return
    else:
        await interaction.response.send_message("not for you go away!", ephemeral=True)

@tree.command(guild = discord.Object(id=guild_id), name = "make_groups", description='Sorts interns into sr timezone groups')
@app_commands.checks.has_role(role_ids.management)
async def make_intern_groups(interaction: discord.Interaction, copyable : bool = False, csv_groups : bool = False):
    
    interns = []
    leaders = []
    
    candidate_role = get(interaction.guild.roles, id = role_ids.candidate)

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
            color = colours.mp_purple,
            description = output,
            title = "Intern groupings"
        )
        await interaction.response.send_message(embed=embed)
    # print(sort_interns(leaders, interns))

@tree.command(guild = discord.Object(id=guild_id), name = "view_all_history", description='View everyones quota history')
@app_commands.checks.has_role(role_ids.management)
async def view_all_history(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    msg = ""
    counter = 0
    for id in [m.id for m in get(interaction.guild.roles, id = role_ids.staff).members]:
        msg += f"<@{id}>\n\n{await aclient.GetQuotaHistory(id, 10)}\n\n"
        counter += 1
        if counter % 3 == 0:
            await interaction.user.send(msg)
            msg = ""
    
    await interaction.followup.send(f"Sent you all {counter} quota histories!", ephemeral=True)

@tree.command(guild = discord.Object(id=guild_id), name = "get_date", description='Get the dates of the next inspection period')
async def get_date(interaction: discord.Interaction):
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

def parse_timezone(name):
    timezone = name.split(" | GMT")[1]
    return int(timezone)

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


if __name__ == '__main__':
    aclient.run(f"{os.getenv('token')}")
