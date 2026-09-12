from discord.ext import commands, tasks
import discord
import aiohttp
import asyncio
import re
import datetime
import io
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────────────────────────
# IMPORTS — uses the same MongoDB economy as the rest of the bot
# ─────────────────────────────────────────────────────────────────
from utils.economy import get_cash, add_cash, remove_cash, format_cash, parse_amount
from utils.pokemon_db import db

# ─────────────────────────────────────────────────────────────────
# MARKET SAFEGUARDS
# ─────────────────────────────────────────────────────────────────
# .give has a daily cap so players can't just hand cash to an alt
# account. Without a floor/fee here, .pokemon sell/buy was a free
# workaround: list a Pokémon for 1 NGR and "buy" it from an alt to
# move any amount of money instantly. A minimum price plus a burned
# market fee (same idea as .donate's 50% cut) closes that loophole
# while keeping real trades between real players unaffected.
MARKET_MIN_PRICE = 25_000
MARKET_FEE_PCT = 0.05  # 5% burned on every sale, not paid to anyone

def gif_url(name: str) -> str:
    clean = name.lower().replace(" ", "").replace(".", "").replace("'", "")
    return f"https://play.pokemonshowdown.com/sprites/xyani/{clean}.gif"

# ─────────────────────────────────────────────────────────────────
# PILLOW / IMAGE HELPERS
# ─────────────────────────────────────────────────────────────────

async def fetch_image(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    """Fetches an image from a URL and returns a PIL Image."""
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        pass
    return None

def get_font(size: int):
    """Attempts to load a clean TTF font, falls back to default if unavailable."""
    for font_name in ["arial.ttf", "Ubuntu-R.ttf", "seguiemj.ttf", "tahoma.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except IOError:
            continue
    return ImageFont.load_default()

async def generate_market_page(listings: list, page_num: int, total_pages: int) -> io.BytesIO:
    """Generates a Pillow image grid for the Pokemart listings."""
    # Discord dark theme colors
    bg_color = (43, 45, 49, 255)       
    card_color = (30, 31, 34, 255)      
    text_color = (255, 255, 255, 255)
    sub_text_color = (181, 186, 193, 255)
    accent_color = (88, 101, 242, 255)  # Discord Blurple for top card borders
    price_color = (241, 196, 15, 255)   # Gold/Yellow for price
    
    # Fonts
    font_large = get_font(22)
    font_med = get_font(18)
    font_small = get_font(14)
    font_xs = get_font(12)

    # Grid config
    cols, rows = 3, 3
    card_w, card_h = 200, 260
    pad_x, pad_y = 20, 20
    
    # Canvas setup
    width = (card_w * cols) + (pad_x * (cols + 1))
    height = (card_h * rows) + (pad_y * (rows + 1)) + 40 # Extra 40px for bottom pagination text
    
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Async fetch all sprites concurrently
    async with aiohttp.ClientSession() as session:
        tasks = []
        for item in listings:
            dex_id = item.get("pokedex_id", 0)
            url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{dex_id}.png"
            tasks.append(fetch_image(session, url))
        sprites = await asyncio.gather(*tasks)

    # Draw each card
    for i, listing in enumerate(listings):
        col = i % cols
        row = i // cols
        
        x = pad_x + col * (card_w + pad_x)
        y = pad_y + row * (card_h + pad_y)
        
        # 1. Base Rounded Card
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=15, fill=card_color)
        
        # 2. Top Accent Line
        draw.rounded_rectangle([x, y, x + card_w, y + 6], radius=15, fill=accent_color)
        draw.rectangle([x, y + 3, x + card_w, y + 6], fill=accent_color) # Flatten bottom
        
        # 3. Sprite Paste
        sprite_img = sprites[i]
        if sprite_img:
            # Resize nicely
            sprite_img = sprite_img.resize((120, 120), Image.Resampling.LANCZOS)
            # Center sprite horizontally
            img.paste(sprite_img, (x + (card_w - 120)//2, y + 20), sprite_img)
        
        # 4. Text: Display Name
        display_name = listing.get("display", "Unknown")
        name_bbox = draw.textbbox((0, 0), display_name, font=font_large)
        name_w = name_bbox[2] - name_bbox[0]
        draw.text((x + (card_w - name_w)//2, y + 145), display_name, fill=text_color, font=font_large)
        
        # 5. Text: Dex ID
        dex_text = f"#{listing.get('pokedex_id', 0):03}"
        dex_bbox = draw.textbbox((0, 0), dex_text, font=font_small)
        dex_w = dex_bbox[2] - dex_bbox[0]
        draw.text((x + (card_w - dex_w)//2, y + 175), dex_text, fill=sub_text_color, font=font_small)
        
        # 6. Text: Price
        price_text = format_cash(listing.get("price", 0))
        price_bbox = draw.textbbox((0, 0), price_text, font=font_med)
        price_w = price_bbox[2] - price_bbox[0]
        draw.text((x + (card_w - price_w)//2, y + 200), price_text, fill=price_color, font=font_med)
        
        # 7. Text: Seller Name
        seller_name = listing.get("seller_name", "Unknown")
        seller_text = f"Seller: {seller_name}"
        seller_bbox = draw.textbbox((0, 0), seller_text, font=font_xs)
        seller_w = seller_bbox[2] - seller_bbox[0]
        draw.text((x + (card_w - seller_w)//2, y + 230), seller_text, fill=sub_text_color, font=font_xs)

    # Draw Bottom Footer Text
    footer_text = f"Page {page_num} of {total_pages} | Sorted by Listed Date | .pokemon buy @seller <name> to trade"
    draw.text((pad_x, height - 30), footer_text, fill=sub_text_color, font=font_small)
    
    # Save to IO buffer
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ─────────────────────────────────────────────────────────────────
# DISCORD UI VIEW FOR PAGINATION
# ─────────────────────────────────────────────────────────────────

class MarketPaginationView(discord.ui.View):
    def __init__(self, listings: list, guild: discord.Guild):
        super().__init__(timeout=180) # 3 minute timeout
        self.listings = listings
        self.guild = guild
        self.per_page = 9 # 3x3 grid
        self.pages = [listings[i:i + self.per_page] for i in range(0, len(listings), self.per_page)]
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        # Disable/enable previous button
        self.prev_button.disabled = (self.current_page == 0)
        # Disable/enable next button
        self.next_button.disabled = (self.current_page == len(self.pages) - 1)
        # Update center indicator label
        self.page_indicator.label = f"{self.current_page + 1} / {len(self.pages)}"

    async def get_current_ui(self) -> tuple[discord.Embed, discord.File]:
        page_items = self.pages[self.current_page]
        
        # Resolve seller names dynamically to avoid storing them in DB
        for item in page_items:
            if "seller_name" not in item:
                seller_id = int(item["seller_id"])
                seller = self.guild.get_member(seller_id)
                item["seller_name"] = seller.display_name if seller else f"User {str(seller_id)[-4:]}"
                
        # Generate Pillow Image
        image_buf = await generate_market_page(page_items, self.current_page + 1, len(self.pages))
        file = discord.File(image_buf, filename="pokemart.png")
        
        # Build Embed container
        embed = discord.Embed(
            title="🏪 Global Pokémon Market",
            description=f"There are **{len(self.listings)}** Pokémon currently listed for sale.",
            color=0x2B2D31
        )
        embed.set_image(url="attachment://pokemart.png")
        
        return embed, file

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.defer()
        embed, file = await self.get_current_ui()
        await interaction.message.edit(embed=embed, attachments=[file], view=self)

    @discord.ui.button(style=discord.ButtonStyle.secondary, disabled=True, custom_id="indicator")
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass # Purely visual indicator

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.defer()
        embed, file = await self.get_current_ui()
        await interaction.message.edit(embed=embed, attachments=[file], view=self)


# ─────────────────────────────────────────────────────────────────
# SHARED HELPERS  (imported by pokemon_battle.py)
# ─────────────────────────────────────────────────────────────────

def get_team(user_id: str) -> list[str]:
    if db is None: return []
    doc = db.pokemon_teams.find_one({"user_id": user_id})
    if not doc:
        return []
    return doc.get("team", [])

def owns_pokemon(user_id: str, name: str) -> bool:
    if db is None: return False
    doc = db.pokemon_collection.find_one({"user_id": user_id, "name": name.lower()})
    return doc is not None

def get_pokemon_moves(user_id: str, name: str) -> list[str]:
    """Return the saved moveset for a specific Pokémon."""
    if db is None: return []
    doc = db.pokemon_collection.find_one({"user_id": user_id, "name": name.lower()})
    if not doc:
        return []
    return doc.get("moves", [])

async def fetch_pokemon_data(name: str, user_id: str = None) -> dict | None:
    """
    Full Pokémon data from PokéAPI.
    If user_id given, uses their saved moveset (falls back to learnset).
    """
    async with aiohttp.ClientSession() as s:
        async with s.get(f"https://pokeapi.co/api/v2/pokemon/{name.lower()}") as r:
            if r.status != 200:
                return None
            data = await r.json()

    stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
    types = [t["type"]["name"] for t in data["types"]]

    saved_moves = get_pokemon_moves(user_id, name) if user_id else []

    if saved_moves:
        moves = []
        async with aiohttp.ClientSession() as s:
            for mslug in saved_moves:
                async with s.get(f"https://pokeapi.co/api/v2/move/{mslug}") as r:
                    if r.status != 200:
                        continue
                    mdata = await r.json()
                    moves.append({
                        "name":     mdata["name"],
                        "display":  mdata["name"].replace("-", " ").title(),
                        "power":    mdata.get("power") or 0,
                        "type":     mdata["type"]["name"],
                        "category": mdata["damage_class"]["name"],
                    })
    else:
        all_moves = [m["move"]["name"] for m in data["moves"]][:20]
        moves = []
        async with aiohttp.ClientSession() as s:
            for mslug in all_moves:
                if len(moves) >= 4:
                    break
                async with s.get(f"https://pokeapi.co/api/v2/move/{mslug}") as r:
                    if r.status != 200:
                        continue
                    mdata = await r.json()
                    if mdata.get("power") and mdata["power"] >= 40:
                        moves.append({
                            "name":     mdata["name"],
                            "display":  mdata["name"].replace("-", " ").title(),
                            "power":    mdata.get("power") or 40,
                            "type":     mdata["type"]["name"],
                            "category": mdata["damage_class"]["name"],
                        })
        while len(moves) < 4:
            moves.append({"name": "tackle", "display": "Tackle",
                          "power": 40, "type": "normal", "category": "physical"})

    sprite = (
        data["sprites"]["other"]["official-artwork"]["front_default"]
        or data["sprites"]["front_default"]
    )

    return {
        "id":      data["id"],
        "name":    data["name"],
        "display": data["name"].title(),
        "stats":   stats,
        "types":   types,
        "moves":   moves,
        "sprite":  sprite,
        "gif":     gif_url(data["name"]),
    }


# ─────────────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────────────

class PokemonTeam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cleanup_market.start() # Start the background task

    def cog_unload(self):
        self.cleanup_market.cancel() # Stop the task if the cog is reloaded/unloaded

    # ─────────────────────────────────────────────────────────────
    # BACKGROUND TASK: Auto-remove listings older than 2 days
    # ─────────────────────────────────────────────────────────────
    @tasks.loop(hours=1) # Checks every 1 hour
    async def cleanup_market(self):
        """Removes market listings older than 48 hours."""
        if db is None: 
            return
            
        # Calculate the exact time 2 days ago
        cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(days=2)
        
        # Delete all listings where 'listed_at' is older than the cutoff time
        result = db.pokemon_market.delete_many({"listed_at": {"$lt": cutoff_time}})
        
        if result.deleted_count > 0:
            print(f"[Market Cleanup] Removed {result.deleted_count} expired listings.")

    @cleanup_market.before_loop # <--- Added the missing @ decorator here
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    # ─────────────────────────────────────────────────────────────
    # .team — view / set active team
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="team")
    async def team(self, ctx, *, args: str = None):
        uid = str(ctx.author.id)

        # View team
        if args is None:
            slots = get_team(uid)
            if not slots:
                await ctx.send(embed=discord.Embed(
                    title="⚔️ Your Team",
                    description=(
                        "You don't have a team yet!\n\n"
                        "**Set one with:**\n"
                        "`.team Charizard, Blastoise, Snorlax`"
                    ),
                    color=0xED4245,
                ))
                return

            embed = discord.Embed(
                title=f"⚔️ {ctx.author.display_name}'s Team",
                color=0x5865F2,
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            for i, name in enumerate(slots, 1):
                doc = db.pokemon_collection.find_one({"user_id": uid, "name": name})
                
                moves_txt = "No moves set"
                if doc and doc.get("moves"):
                    m = [move.replace("-", " ").title() for move in doc["moves"]]
                    if m:
                        moves_txt = " • ".join(m)
                        
                embed.add_field(
                    name=f"`{i}.` {name.title()}",
                    value=f"[🎞]({gif_url(name)})  {moves_txt}",
                    inline=False,
                )
            embed.set_footer(text="Use .battle @user <amount> to fight!")
            await ctx.send(embed=embed)
            return

        # Set team
        names = [n.strip().lower() for n in args.split(",") if n.strip()]
        if not 1 <= len(names) <= 6:
            await ctx.send(embed=discord.Embed(
                description="List 1–6 Pokémon separated by commas.\n`.team Charizard, Blastoise, Snorlax`",
                color=0xED4245,
            ))
            return

        not_owned = [n for n in names if not owns_pokemon(uid, n)]
        if not_owned:
            await ctx.send(embed=discord.Embed(
                description=f"❌ You don't own: **{', '.join(n.title() for n in not_owned)}**",
                color=0xED4245,
            ))
            return

        # Update in MongoDB
        db.pokemon_teams.update_one(
            {"user_id": uid},
            {"$set": {"team": names}},
            upsert=True
        )

        embed = discord.Embed(
            title="✅ Team Updated!",
            description="\n".join(f"`{i+1}.` {n.title()}" for i, n in enumerate(names)),
            color=0x57F287,
        )
        embed.set_footer(text="Use .battle @user <amount> to challenge someone!")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────────────────────
    # .pokemon sell <name> <price>
    # List a Pokémon on the market for other players to buy
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="pokemon")
    async def pokemon_cmd(self, ctx, action: str = None, *, args: str = None):
        """
        .pokemon sell <name> <price>   — list a Pokémon for sale
        .pokemon buy @seller <name>    — buy from the market
        """
        if action is None:
            embed = discord.Embed(
                title="🎮 Pokémon Commands",
                description=(
                    "`.pokemon sell <name> <price>` — list a Pokémon for sale\n"
                    "`.pokemon buy @seller <name>` — buy a Pokémon from the market\n"
                    "`.pokemons` — view your Pokémon collection\n"
                    "`.pokemart` — browse the Pokémon market\n"
                    "`.team` — view / set your battle team"
                ),
                color=0x5865F2,
            )
            await ctx.send(embed=embed)
            return

        action = action.lower()

        # ── SELL ──────────────────────────────────────────────────
        if action == "sell":
            if args is None:
                await ctx.send(embed=discord.Embed(
                    description="❌ Usage: `.pokemon sell <name> <price>`\nExample: `.pokemon sell Excadrill 400k`",
                    color=0xED4245,
                ))
                return

            parts = args.rsplit(" ", 1)
            if len(parts) < 2:
                await ctx.send(embed=discord.Embed(
                    description="❌ Usage: `.pokemon sell <name> <price>`\nExample: `.pokemon sell Excadrill 400k`",
                    color=0xED4245,
                ))
                return

            poke_name_raw, price_raw = parts[0].strip(), parts[1].strip()
            poke_name = poke_name_raw.lower()
            price = parse_amount(price_raw)

            if price is None or price <= 0:
                await ctx.send(embed=discord.Embed(
                    description="❌ Invalid price. Use a number like `400k`, `1m`, or `50000`.",
                    color=0xED4245,
                ))
                return

            if price < MARKET_MIN_PRICE:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ Minimum listing price is **{format_cash(MARKET_MIN_PRICE)}**.",
                    color=0xED4245,
                ))
                return

            uid = str(ctx.author.id)

            if not owns_pokemon(uid, poke_name):
                await ctx.send(embed=discord.Embed(
                    description=f"❌ You don't own a **{poke_name_raw.title()}**!",
                    color=0xED4245,
                ))
                return

            existing = db.pokemon_market.find_one({"seller_id": uid, "name": poke_name})

            if existing:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ You already have **{poke_name_raw.title()}** listed in the market!\nRemove the old listing first (contact an admin).",
                    color=0xED4245,
                ))
                return

            prow = db.pokemon_collection.find_one({"user_id": uid, "name": poke_name})

            if not prow:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ Couldn't find **{poke_name_raw.title()}** in your collection.",
                    color=0xED4245,
                ))
                return

            display = prow.get("display", poke_name.title())
            pokedex_id = prow.get("pokedex_id", 0)

            db.pokemon_market.insert_one({
                "seller_id": uid,
                "name": poke_name,
                "display": display,
                "pokedex_id": pokedex_id,
                "price": price,
                "listed_at": datetime.datetime.utcnow()
            })

            embed = discord.Embed(
                title="🏪 Pokémon Listed!",
                description=(
                    f"**{display}** has been listed in the market!\n\n"
                    f"💰 Price: **{format_cash(price)}**\n"
                    f"🎞 [View GIF]({gif_url(poke_name)})\n\n"
                    f"Players can buy it with:\n"
                    f"`.pokemon buy {ctx.author.mention} {display}`"
                ),
                color=0x57F287,
            )
            embed.set_thumbnail(url=gif_url(poke_name))
            embed.set_footer(text=f"Pokédex #{pokedex_id}")
            await ctx.send(embed=embed)

        # ── BUY ───────────────────────────────────────────────────
        elif action == "buy":
            if args is None or not ctx.message.mentions:
                await ctx.send(embed=discord.Embed(
                    description="❌ Usage: `.pokemon buy @seller <name>`\nExample: `.pokemon buy @Alice Excadrill`",
                    color=0xED4245,
                ))
                return

            seller = ctx.message.mentions[0]

            poke_name_raw = re.sub(r"<@!?\d+>", "", args).strip()
            if not poke_name_raw:
                await ctx.send(embed=discord.Embed(
                    description="❌ Usage: `.pokemon buy @seller <name>`\nExample: `.pokemon buy @Alice Excadrill`",
                    color=0xED4245,
                ))
                return

            poke_name = poke_name_raw.lower()
            buyer_id = str(ctx.author.id)
            seller_id = str(seller.id)

            if buyer_id == seller_id:
                await ctx.send(embed=discord.Embed(
                    description="❌ You can't buy your own Pokémon!",
                    color=0xED4245,
                ))
                return

            listing = db.pokemon_market.find_one({"seller_id": seller_id, "name": poke_name})

            if not listing:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ **{seller.display_name}** doesn't have a **{poke_name_raw.title()}** listed for sale!",
                    color=0xED4245,
                ))
                return

            price = listing["price"]
            display = listing["display"]
            pokedex_id = listing["pokedex_id"]

            if owns_pokemon(buyer_id, poke_name):
                await ctx.send(embed=discord.Embed(
                    description=f"❌ You already own a **{display}**! Each trainer can only have one of each species.",
                    color=0xED4245,
                ))
                return

            buyer_cash = get_cash(buyer_id)
            if buyer_cash < price:
                await ctx.send(embed=discord.Embed(
                    description=(
                        f"❌ You don't have enough money!\n\n"
                        f"💰 Price: **{format_cash(price)}**\n"
                        f"👛 Your balance: **{format_cash(buyer_cash)}**\n"
                        f"💸 You need: **{format_cash(price - buyer_cash)}** more"
                    ),
                    color=0xED4245,
                ))
                return

            # ── Execute the trade ──────────────────────────────────
            fee = int(price * MARKET_FEE_PCT)
            seller_receives = price - fee

            remove_cash(buyer_id, price)
            add_cash(seller_id, seller_receives)
            
            seller_poke = db.pokemon_collection.find_one({"user_id": seller_id, "name": poke_name})
            moves = seller_poke.get("moves", []) if seller_poke else []

            db.pokemon_collection.insert_one({
                "user_id": buyer_id,
                "name": poke_name,
                "display": display,
                "pokedex_id": pokedex_id,
                "moves": moves
            })
            
            db.pokemon_collection.delete_one({"user_id": seller_id, "name": poke_name})
            db.pokemon_market.delete_one({"seller_id": seller_id, "name": poke_name})
            
            seller_team_doc = db.pokemon_teams.find_one({"user_id": seller_id})
            if seller_team_doc:
                current_team = seller_team_doc.get("team", [])
                new_team = [p for p in current_team if p.lower() != poke_name]
                db.pokemon_teams.update_one(
                    {"user_id": seller_id},
                    {"$set": {"team": new_team}}
                )

            embed = discord.Embed(
                title=f"✅ Trade Complete! {display} has a new trainer!",
                description=(
                    f"**{ctx.author.display_name}** bought **{display}** from **{seller.display_name}**!\n\n"
                    f"💰 Amount paid: **{format_cash(price)}**\n"
                    f"🎞 [View GIF]({gif_url(poke_name)})\n\n"
                    f"**{display}** has been added to your collection!\n"
                    f"Use `.team` to add it to your battle team."
                ),
                color=0x57F287,
            )
            embed.set_thumbnail(url=gif_url(poke_name))
            embed.set_footer(text=f"Pokédex #{pokedex_id}")
            await ctx.send(embed=embed)

            try:
                seller_embed = discord.Embed(
                    title="💰 Your Pokémon was sold!",
                    description=(
                        f"**{display}** was purchased by **{ctx.author.display_name}**!\n\n"
                        f"💰 You received: **{format_cash(seller_receives)}**\n"
                        f"🏪 Market fee (5%): **{format_cash(fee)}**"
                    ),
                    color=0x57F287,
                )
                await seller.send(embed=seller_embed)
            except Exception:
                pass

        else:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Unknown action `{action}`.\nUse `.pokemon sell` or `.pokemon buy`.",
                color=0xED4245,
            ))

    # ─────────────────────────────────────────────────────────────
    # .pokemart — browse all Pokémon listed for sale (REWRITTEN UI)
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="pokemart")
    async def pokemart(self, ctx):
        """Browse all Pokémon currently listed for sale in a visual grid."""
        listings = list(db.pokemon_market.find().sort("listed_at", -1))

        if not listings:
            await ctx.send(embed=discord.Embed(
                title="🏪 Pokémon Market",
                description=(
                    "The market is empty right now!\n\n"
                    "List your Pokémon with:\n"
                    "`.pokemon sell <name> <price>`"
                ),
                color=0xFFA500,
            ))
            return

        # Send a temporary loading message since image generation + fetching can take a moment
        loading_msg = await ctx.send(embed=discord.Embed(
            description="⏳ **Loading the PokéMart... Fetching sprites!**",
            color=0x5865F2
        ))

        # Instantiate View and get first page UI
        view = MarketPaginationView(listings, ctx.guild)
        embed, file = await view.get_current_ui()

        # Delete loading message and send final beautiful interactive UI
        await loading_msg.delete()
        await ctx.send(embed=embed, file=file, view=view)


    # ─────────────────────────────────────────────────────────────
    # .pokecheck @user — view someone's listed Pokémon in market
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="pokecheck")
    async def pokecheck(self, ctx, member: discord.Member = None):
        """See what a specific trainer has listed in the market."""
        target = member or ctx.author
        listings = list(db.pokemon_market.find({"seller_id": str(target.id)}).sort("listed_at", -1))

        if not listings:
            await ctx.send(embed=discord.Embed(
                description=f"**{target.display_name}** has no Pokémon listed for sale.",
                color=0xED4245,
            ))
            return

        embed = discord.Embed(
            title=f"🏪 {target.display_name}'s Listings",
            color=0xF1C40F,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        for listing in listings:
            embed.add_field(
                name=f"🎴 {listing['display']} — {format_cash(listing['price'])}",
                value=(
                    f"[🎞 View GIF]({gif_url(listing['name'])})\n"
                    f"📖 Pokédex #{listing['pokedex_id']:03}\n"
                    f"Buy: `.pokemon buy {target.mention} {listing['display']}`"
                ),
                inline=True,
            )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PokemonTeam(bot))
