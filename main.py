import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import traceback
import os

# KEEP ALIVE

app = Flask(__name__)

@app.route("/")
def home():
    return "Royal Economy Online"

def run_web():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

def keep_alive():

    t = Thread(
        target=run_web
    )

    t.start()

# BOT

intents = discord.Intents.default()

intents.message_content = True
intents.members = True

class RoyalBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix=".",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):

        print("Loading Cogs...")

        if os.path.exists("./cogs"):

            for file in os.listdir("./cogs"):

                if file.endswith(".py"):

                    try:

                        await self.load_extension(
                            f"cogs.{file[:-3]}"
                        )

                        print(
                            f"Loaded {file}"
                        )

                    except Exception:

                        print(
                            f"FAILED TO LOAD: {file}"
                        )

                        traceback.print_exc()

bot = RoyalBot()

# EVENTS

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user}"
    )


# ─────────────────────────
# ERROR HANDLER
# ─────────────────────────

@bot.event
async def on_command_error(ctx, error):

    print("\n========== COMMAND ERROR ==========")

    traceback.print_exception(
        type(error),
        error,
        error.__traceback__
    )

    print("===================================\n")

    try:

        await ctx.send(
            f"❌ Error: {error}"
        )

    except:

        pass


# ─────────────────────────
# DISCONNECT LOGS
# ─────────────────────────

@bot.event
async def on_disconnect():

    print("⚠ Bot disconnected from Discord.")


@bot.event
async def on_resumed():

    print("✅ Bot reconnected to Discord.")


# START BOT

if __name__ == "__main__":

    keep_alive()

    token = os.getenv("TOKEN")

    bot.run(
        token,
        reconnect=True
        )
