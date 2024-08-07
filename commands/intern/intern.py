from ..imports import *

class intern(commands.GroupCog, group_name='intern'):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name = "register", description='Register interns from a role')
    async def register_from_role(self, interaction: discord.Interaction, role : discord.Role = None, id_csv : str = None):
        
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
                    
    @app_commands.command(name = "remove", description='Remove an intern')
    async def remove_intern(self, interaction: discord.Interaction, intern : discord.User, reason : str):
        
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


async def setup(bot):
    await bot.add_cog(intern(bot))