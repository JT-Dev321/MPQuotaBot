database = 'quotaDB.sqlite'
import discord
from discord import ButtonStyle, app_commands, ui
from discord.ext import tasks, commands
from discord.utils import get
from discord.app_commands import AppCommandError, Group
import aiosqlite
import time
from datetime import datetime, timedelta, time
import asyncio
import re
import math
import itertools
import ast
from main import roles,has_role_f,IsManagement,IsSenior,IsIntern,get_variable,set_variable,getQuota,getSeniorTicketQuota,getSeniorQuota,getInternQuota,CheckValidDate,GetQuotaHistory,Get_Consecutive_Strikes,aclient