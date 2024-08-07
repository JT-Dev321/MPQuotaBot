from commands.imports import *

class rewards(commands.GroupCog, group_name='reward'):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.checks.has_role(roles.management_role_id)
    async def distribute_rewards(interaction: discord.Interaction, week_start : str, just_show : bool = False):
        ids_to_check = [m.id for m in get(interaction.guild.roles, id = roles.staff_role_id).members]
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        async with aiosqlite.connect(database) as db:
            query = """
                SELECT InspecteeID, SUM(PostsCompleted) AS PostsCompletedSum
                FROM (
                    SELECT InspecteeID, PostsCompleted,
                        ROW_NUMBER() OVER (
                            PARTITION BY InspecteeID 
                            ORDER BY 
                                CAST(SUBSTR(WeekStart, 1, INSTR(WeekStart, '-') - 1) AS INT) DESC,
                                CAST(SUBSTR(WeekStart, INSTR(WeekStart, '-') + 1, INSTR(SUBSTR(WeekStart, INSTR(WeekStart, '-') + 1), '-') - 1) AS INT) DESC,
                                CAST(SUBSTR(WeekStart, INSTR(SUBSTR(WeekStart, INSTR(WeekStart, '-') + 1), '-') + INSTR(WeekStart, '-') + 1) AS INT) DESC
                        ) AS RowNum
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
                    rewarded = []
                    for row in results:
                        UserId = row[0]
                        print(f"Checking {UserId}")
                        if not await IsSenior(UserId) and interaction.guild.get_member(UserId) is not None:
                            print(f"{UserId} is not a senior")
                            PostSum = row[1]
                            MemberObj = interaction.guild.get_member(UserId)
                            
                            messageStart = f"You have been given a reward for completing `{PostSum}` posts over the last 4 inspections."
                            messageEnd = f"These rewards are only applied if you would have otherwise failed a given inspection week, and expire after 4 weeks."
                            
                            if PostSum >= 900:
                                await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Excused", 2))
                                await db.commit()
                                await MemberObj.send(messageStart + "\n\n- You will be excused for 2 of the next 4 inspections\n\n" + messageEnd)
                                counter += 1
                                rewarded.append(f"<@{UserId}>")
                            elif PostSum >= 600:
                                await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Excused", 1))
                                await db.commit()
                                await MemberObj.send(messageStart + "\n\n- You will be excused for 1 of the next 4 inspections\n\n" + messageEnd)
                                counter += 1
                                rewarded.append(f"<@{UserId}>")
                            elif PostSum >= 450:
                                await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Half", 2))
                                await db.commit()
                                await MemberObj.send(messageStart + "\n\n- Your post requirement will be halved for 2 of the next 4 inspections\n\n" + messageEnd)
                                counter += 1
                                rewarded.append(f"<@{UserId}>")
                            elif PostSum >= 300:
                                await db.execute('INSERT INTO Rewards (RecipientID, SeniorID, DateGiven, Type, Charges) VALUES (?, ?, ?, ?, ?)', (UserId, interaction.user.id, week_start, "Quota Half", 1))
                                await db.commit()
                                await MemberObj.send(messageStart + "\n\n- Your post requirement will be halved for 1 of the next 4 inspections\n\n" + messageEnd)
                                counter += 1
                                rewarded.append(f"<@{UserId}>")
                    await interaction.followup.send(f"Done! - Given {counter} rewards to: {', '.join(rewarded)}", ephemeral=True)
                elif just_show:
                    UserId = 0
                    output = ""
                    for row in results:
                        UserId = int(row[0])
                        if not await IsSenior(UserId) and interaction.guild.get_member(UserId) is not None:
                            output += f"<@{row[0]}> - {row[1]}\n"
                    await interaction.followup.send(output, ephemeral=True)

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
    
    @giveReward.autocomplete('week_start')
    @distribute_rewards.autocomplete('week_start')
    async def autocomplete_callback(interaction: discord.Interaction, current: str):
        choicelist = []   
        
        for i in range(-61,1):
            dt = datetime.now() + timedelta(days=i)
            if dt.weekday() == 0:
                choicelist.append(app_commands.Choice(name = f'{dt.year}-{dt.month}-{dt.day}', value = f'{dt.year}-{dt.month}-{dt.day}'))
        
        return choicelist


async def setup(bot):
    # finally, adding the cog to the bot
    await bot.add_cog(rewards(bot))