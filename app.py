#!/usr/bin/env python3
"""
Free Fire Ban Checker Bot
Main application file
Developer: Digamber Raj
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands
from flask import Flask, request, jsonify

from utils import (
    get_player_status,
    build_embed_response,
    load_translations,
    get_guild_count,
    validate_player_id,
    BANNED_EMOJI,
    NOT_BANNED_EMOJI,
    save_config,
    load_config,
    is_allowed_channel
)

# ============================================================================
# Configuration
# ============================================================================

# Discord bot token from environment variable
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

# Bot prefix
COMMAND_PREFIX = "!"

# API endpoint for ban checking
BAN_CHECK_API = "http://raw.thug4ff.com/check_ban/check_ban/"

# Default language
DEFAULT_LANG = "en"

# Config file path
CONFIG_FILE = "bot_config.json"

# ============================================================================
# Flask web server for keep-alive
# ============================================================================

web_app = Flask(__name__)

@web_app.route('/')
def home():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "online",
        "service": "FreeFire Ban Checker",
        "developer": "Digamber Raj",
        "timestamp": datetime.utcnow().isoformat()
    })

@web_app.route('/health')
def health_check():
    """Simple health endpoint for uptime monitoring"""
    return "OK", 200

def run_flask():
    """Run Flask in a separate thread"""
    web_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ============================================================================
# Discord Bot Setup
# ============================================================================

# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=None
)

# Store user language preferences
user_languages: Dict[int, str] = {}

# Store channel restrictions
# Structure: {guild_id: allowed_channel_id}
allowed_channels: Dict[int, int] = {}

# Load translations once
translations = load_translations()

# ============================================================================
# Configuration Management
# ============================================================================

def load_bot_config():
    """Load bot configuration from file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('allowed_channels', {})
    except Exception as e:
        print(f"Error loading config: {e}")
    return {}

def save_bot_config():
    """Save bot configuration to file"""
    try:
        config = {
            'allowed_channels': allowed_channels,
            'updated_at': datetime.utcnow().isoformat()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

# ============================================================================
# Permission Checks
# ============================================================================

def check_admin_permission(ctx):
    """Check if user has admin permissions"""
    if ctx.author.guild_permissions.administrator:
        return True
    
    # Check for specific roles if needed
    for role in ctx.author.roles:
        if role.permissions.manage_guild or role.permissions.manage_channels:
            return True
    
    return False

# ============================================================================
# Bot Events
# ============================================================================

@bot.event
async def on_ready():
    """Called when the bot is ready and connected"""
    print(f"✅ Bot is online as {bot.user.name}")
    print(f"✅ Connected to {len(bot.guilds)} servers")
    print(f"✅ Developer: Digamber Raj")
    
    # Load saved configuration
    global allowed_channels
    saved_channels = load_bot_config()
    allowed_channels.update(saved_channels)
    print(f"✅ Loaded {len(allowed_channels)} channel restrictions")
    
    # Set bot status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="!ID <player_id>"
    )
    await bot.change_presence(activity=activity)

@bot.event
async def on_guild_join(guild):
    """When bot joins a new server"""
    print(f"➕ Joined new server: {guild.name} (ID: {guild.id})")
    
    # Send welcome message to system channel or first text channel
    try:
        channel = guild.system_channel
        if channel and channel.permissions_for(guild.me).send_messages:
            welcome_embed = discord.Embed(
                title="Free Fire Ban Checker",
                description=(
                    "Thanks for adding me to your server!\n\n"
                    "**Available Commands:**\n"
                    "`!ID <player_id>` - Check ban status\n"
                    "`!setchannel` - Set restricted channel (Admin only)\n"
                    "`!lang en/fr` - Set your language\n"
                    "`!guilds` - Show server count\n"
                    "`!helpchannel` - Show current channel restriction\n"
                ),
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
            welcome_embed.set_footer(text="Developer: Digamber Raj")
            await channel.send(embed=welcome_embed)
    except Exception as e:
        print(f"Couldn't send welcome message: {e}")

@bot.event
async def on_guild_remove(guild):
    """When bot is removed from a server"""
    print(f"➖ Removed from server: {guild.name} (ID: {guild.id})")
    
    # Clean up channel restriction for this guild
    if guild.id in allowed_channels:
        del allowed_channels[guild.id]
        save_bot_config()

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        # Silently ignore unknown commands
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        lang = user_languages.get(ctx.author.id, DEFAULT_LANG)
        msg = translations[lang]['errors']['missing_id']
        await ctx.send(f"❌ {msg}")
    elif isinstance(error, commands.CheckFailure):
        # Permission error for setchannel
        await ctx.send("❌ You need **Administrator** permissions to use this command.")
    else:
        # Log other errors but don't spam the channel
        print(f"Command error: {error}")

# ============================================================================
# Channel Restriction Check
# ============================================================================

def check_channel_restriction():
    """Decorator to check if command is allowed in current channel"""
    async def predicate(ctx):
        # Always allow commands in DMs
        if isinstance(ctx.channel, discord.DMChannel):
            return True
        
        guild_id = ctx.guild.id
        
        # If no restriction set for this guild, allow everywhere
        if guild_id not in allowed_channels:
            return True
        
        # Check if current channel is the allowed one
        if ctx.channel.id == allowed_channels[guild_id]:
            return True
        
        # If not, send error message
        allowed_channel = ctx.guild.get_channel(allowed_channels[guild_id])
        if allowed_channel:
            await ctx.send(
                f"⚠️ This bot is restricted to <#{allowed_channels[guild_id]}> only. "
                f"Please use commands there."
            )
        else:
            await ctx.send(
                "⚠️ This bot is restricted to a specific channel. "
                "Please ask an admin to use `!setchannel` to set a new channel."
            )
        return False
    
    return commands.check(predicate)

# ============================================================================
# Bot Commands
# ============================================================================

@bot.command(name='ID')
@check_channel_restriction()
async def check_ban(ctx, player_id: str):
    """
    Check if a Free Fire player ID is banned
    Usage: !ID <player_id>
    """
    # Get user's language preference
    user_id = ctx.author.id
    lang = user_languages.get(user_id, DEFAULT_LANG)
    
    # Validate player ID
    if not validate_player_id(player_id):
        error_msg = translations[lang]['errors']['invalid_id']
        await ctx.send(f"⚠️ {error_msg}")
        return
    
    # Show typing indicator
    async with ctx.typing():
        try:
            # Fetch ban status from API
            status_data = await get_player_status(player_id, BAN_CHECK_API)
            
            if not status_data:
                error_msg = translations[lang]['errors']['api_error']
                await ctx.send(f"🔧 {error_msg}")
                return
            
            # Create embed response
            embed = build_embed_response(status_data, lang, translations)
            
            # Determine which GIF to send
            is_banned = status_data.get('banned', False)
            gif_filename = "banned.gif" if is_banned else "notbanned.gif"
            gif_path = f"assets/{gif_filename}"
            
            # Check if GIF file exists
            if os.path.exists(gif_path):
                # Send GIF file
                gif_file = discord.File(gif_path, filename=gif_filename)
                # Send both embed and GIF
                await ctx.send(file=gif_file, embed=embed)
            else:
                # Fallback: send just the embed
                print(f"Warning: GIF file not found at {gif_path}")
                await ctx.send(embed=embed)
                
        except Exception as e:
            print(f"Error checking ban status: {e}")
            error_msg = translations[lang]['errors']['unexpected']
            await ctx.send(f"💥 {error_msg}")

@bot.command(name='lang')
@check_channel_restriction()
async def set_language(ctx, language: str):
    """
    Set your preferred language (en/fr)
    Usage: !lang en  OR  !lang fr
    """
    lang = language.lower().strip()
    
    if lang not in ['en', 'fr']:
        await ctx.send("⚠️ Available languages: `en` (English) or `fr` (French)")
        return
    
    # Store user preference
    user_languages[ctx.author.id] = lang
    
    # Get confirmation message in selected language
    confirmation = translations[lang]['language_set']
    await ctx.send(f"✅ {confirmation}")

@bot.command(name='guilds')
@check_channel_restriction()
async def server_count(ctx):
    """
    Display the number of servers this bot is in
    Usage: !guilds
    """
    count = get_guild_count(bot)
    
    # Get user's language for response
    user_id = ctx.author.id
    lang = user_languages.get(user_id, DEFAULT_LANG)
    
    # Create response
    embed = discord.Embed(
        title=translations[lang]['guilds']['title'],
        description=translations[lang]['guilds']['description'].format(count=count),
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    embed.set_footer(text=f"Developer: Digamber Raj")
    
    await ctx.send(embed=embed)

@bot.command(name='setchannel')
@commands.has_permissions(administrator=True)
async def set_restricted_channel(ctx):
    """
    Set the channel where bot commands will work (Admin only)
    Usage: !setchannel
    """
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id
    
    # Set this channel as the allowed one
    allowed_channels[guild_id] = channel_id
    
    # Save configuration
    save_bot_config()
    
    # Send confirmation
    embed = discord.Embed(
        title="✅ Channel Restriction Set",
        description=(
            f"Bot commands are now restricted to this channel only.\n"
            f"**Channel:** <#{channel_id}>\n\n"
            f"To remove restriction, use `!removechannel` (Admin only)."
        ),
        color=0x00FF00,
        timestamp=datetime.utcnow()
    )
    
    embed.set_footer(text="Developer: Digamber Raj")
    await ctx.send(embed=embed)

@bot.command(name='removechannel')
@commands.has_permissions(administrator=True)
async def remove_channel_restriction(ctx):
    """
    Remove channel restriction (Admin only)
    Usage: !removechannel
    """
    guild_id = ctx.guild.id
    
    if guild_id in allowed_channels:
        del allowed_channels[guild_id]
        save_bot_config()
        
        embed = discord.Embed(
            title="✅ Channel Restriction Removed",
            description=(
                "Channel restriction has been removed.\n"
                "Bot commands will now work in all channels."
            ),
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        
        embed.set_footer(text="Developer: Digamber Raj")
        await ctx.send(embed=embed)
    else:
        await ctx.send("ℹ️ No channel restriction was set for this server.")

@bot.command(name='helpchannel')
async def show_channel_info(ctx):
    """
    Show current channel restriction info
    Usage: !helpchannel
    """
    guild_id = ctx.guild.id
    
    if guild_id in allowed_channels:
        channel_id = allowed_channels[guild_id]
        channel = ctx.guild.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="📌 Channel Restriction Info",
                description=(
                    f"Bot commands are restricted to: <#{channel_id}>\n"
                    f"**Channel Name:** {channel.name}\n"
                    f"**Category:** {channel.category.name if channel.category else 'None'}\n\n"
                    f"Only administrators can change this setting using `!setchannel`."
                ),
                color=0xFFA500,
                timestamp=datetime.utcnow()
            )
        else:
            embed = discord.Embed(
                title="⚠️ Channel Restriction Info",
                description=(
                    f"A restriction is set for channel ID: `{channel_id}`\n"
                    f"But this channel no longer exists in the server.\n\n"
                    f"Please use `!setchannel` in a new channel to update."
                ),
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
    else:
        embed = discord.Embed(
            title="ℹ️ Channel Restriction Info",
            description=(
                "No channel restriction is set for this server.\n"
                "Bot commands work in all channels.\n\n"
                "To restrict to a specific channel, use `!setchannel` (Admin only)."
            ),
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
    
    embed.set_footer(text="Developer: Digamber Raj")
    await ctx.send(embed=embed)

@bot.command(name='botinfo')
async def bot_information(ctx):
    """
    Show bot information and commands
    Usage: !botinfo
    """
    embed = discord.Embed(
        title="🤖 Free Fire Ban Checker Bot",
        description=(
            "A Discord bot to check Free Fire player ban status\n\n"
            "**Main Commands:**\n"
            "• `!ID <player_id>` - Check if player is banned\n"
            "• `!lang en/fr` - Set your language\n"
            "• `!guilds` - Show server count\n"
            "• `!botinfo` - Show this info\n\n"
            "**Admin Commands:**\n"
            "• `!setchannel` - Restrict bot to current channel\n"
            "• `!removechannel` - Remove channel restriction\n"
            "• `!helpchannel` - Show current restriction\n"
        ),
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="Developer",
        value="Digamber Raj",
        inline=True
    )
    
    embed.add_field(
        name="Prefix",
        value="`!`",
        inline=True
    )
    
    embed.add_field(
        name="Support",
        value="Contact server admin for help",
        inline=True
    )
    
    embed.set_footer(text="Free Fire Ban Checker Bot")
    await ctx.send(embed=embed)

# ============================================================================
# Startup Logic
# ============================================================================

async def start_bot():
    """Start the Discord bot"""
    # Start Flask server in background for keep-alive
    import threading
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask keep-alive server started on port 8080")
    
    # Start Discord bot
    await bot.start(BOT_TOKEN)

def main():
    """Main entry point"""
    # Run the bot
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()