database = 'quotaDB.sqlite'
import discord
from discord import ButtonStyle, app_commands, ui
from discord.ext import tasks, commands
from discord.utils import get
from discord.app_commands import AppCommandError, Group
import aiosqlite
import time
from datetime import datetime, timedelta, time
from typing import Literal, Optional
import asyncio
import re
import math
import itertools
import ast
from main import role_ids,channel_ids,colours