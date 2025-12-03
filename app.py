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
import sys
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
    save_bot_config,
    load_bot_config
)

# ============================================================================
# Configuration
# ============================================================================

# Discord bot token from environment variable
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ ERROR: DISCORD_BOT_TOKEN environment variable is not set!")
    print("\n🔧 How to fix:")
    print("1. On Render.com:")
    print("   - Go to your project dashboard")
    print("   - Click on 'Environment'")
    print("   - Add environment variable:")
    print("     Key: DISCORD_BOT_TOKEN")
    print("     Value: Your Discord bot token")
    print("\n2. Locally:")
    print("   export DISCORD_BOT_TOKEN='your_token_here'")
    print("   or create .env file with DISCORD_BOT_TOKEN=your_token_here")
    print("\n3. Get bot token from:")
    print("   https://discord.com/developers/applications")
    print("   → Select your bot → Bot → Copy Token")
    
    # Don't crash immediately, wait a bit for Render to set env vars
    print("\n⚠️ Waiting 10 seconds in case environment variable loads late...")
    import time
    time.sleep(10)
    
    # Try again
    BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if not BOT_TOKEN:
        print("\n❌ Still no token found. Please set DISCORD_BOT_TOKEN.")
        print("💡 For testing, you can use placeholder token but bot won't connect.")
        BOT_TOKEN = "PLACEHOLDER_TOKEN_NO_CONNECTION"
        print(f"Using placeholder: {BOT_TOKEN}")
        print("Bot will start but won't connect to Discord. Set real token to fix.")

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
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Bot is running"
    })

@web_app.route('/health')
def health_check():
    """Simple health endpoint for uptime monitoring"""
    return "OK", 200

@web_app.route('/setup')
def setup_guide():
    """Setup guide endpoint"""
    return """
    <h1>Free Fire Ban Checker Bot Setup</h1>
    <p><strong>Developer:</strong> Digamber Raj</p>
    
    <h2>Setup Steps:</h2>
    <ol>
        <li>Get bot token from <a href="https://discord.com/developers/applications">Discord Developer Portal</a></li>
        <li>Set environment variable: <code>DISCORD_BOT_TOKEN=your_token_here</code></li>
        <li>Restart the application</li>
        <li>Invite bot to your server</li>
    </ol>
    
    <h2>Environment Variable Help:</h2>
    <p><strong>On Render.com:</strong></p>
    <ul>
        <li>Go to your project → Environment</li>
        <li>Add new environment variable</li>
        <li>Key: DISCORD_BOT_TOKEN</li>
        <li>Value: Your bot token</li>
        <li>Click "Save Changes"</li>
        <li>Redeploy if needed</li>
    </ul>
    
    <p><strong>Command to check if variable is set:</strong></p>
    <pre>echo $DISCORD_BOT_TOKEN</pre>
    """

def run_flask():
    """Run Flask in a separate thread"""
    try:
        port = int(os.environ.get("PORT", 8080))
        web_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"Flask error: {e}")

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

def load_allowed_channels():
    """Load allowed channels from config file"""
    global allowed_channels
    try:
        config = load_bot_config()
        if 'allowed_channels' in config:
            allowed_channels = config['allowed_channels']
            print(f"📁 Loaded {len(allowed_channels)} channel restrictions from config")
    except Exception as e:
        print(f"⚠️ Error loading config: {e}")
        allowed_channels = {}

def save_allowed_channels():
    """Save allowed channels to config file"""
    try:
        config = {
            'allowed_channels': allowed_channels,
            'updated_at': datetime.utcnow().isoformat(),
            'developer': 'Digamber Raj'
        }
        save_bot_config(config)
        print(f"💾 Saved {len(allowed_channels)} channel restrictions")
    except Exception as e:
        print(f"⚠️ Error saving config: {e}")

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
# Channel Restriction Check
# ============================================================================

def check_channel_restriction():
    """Decorator to check if command is allowed in current channel"""
    async def predicate(ctx):
        # Always allow commands in DMs
        if isinstance(ctx.channel, discord.DMChannel):
            return True
        
        # If no guild (shouldn't happen)
        if not ctx.guild:
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
# Bot Events
# ============================================================================

@bot.event
async def on_ready():
    """Called when the bot is ready and connected"""
    print(f"✅ Bot is online as {bot.user.name}")
    print(f"✅ Connected to {len(bot.guilds)} servers")
    print(f"✅ Developer: Digamber Raj")
    print(f"✅ Prefix: {COMMAND_PREFIX}")
    
    # Load saved configuration
    load_allowed_channels()
    
    # Set bot status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="!ID <player_id>"
    )
    try:
        await bot.change_presence(activity=activity)
    except:
        pass

@bot.event
async def on_guild_join(guild):
    """When bot joins a new server"""
    print(f"➕ Joined new server: {guild.name} (ID: {guild.id})")
    
    # Send welcome message to system channel or first text channel
    try:
        channel = guild.system_channel
        if not channel or not channel.permissions_for(guild.me).send_messages:
            # Try to find first text channel with send permissions
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
        
        if channel and channel.permissions_for(guild.me).send_messages:
            welcome_embed = discord.Embed(
                title="🤖 Free Fire Ban Checker",
                description=(
                    "Thanks for adding me to your server!\n\n"
                    "**Main Commands:**\n"
                    "`!ID <player_id>` - Check ban status\n"
                    "`!lang en/fr` - Set your language\n"
                    "`!guilds` - Show server count\n"
                    "`!botinfo` - Show all commands\n\n"
                    "**Admin Commands:**\n"
                    "`!setchannel` - Restrict bot to this channel\n"
                    "`!removechannel` - Remove restriction\n"
                    "`!helpchannel` - Show current restriction\n"
                ),
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
            welcome_embed.set_footer(text="Developer: Digamber Raj")
            await channel.send(embed=welcome_embed)
    except Exception as e:
        print(f"⚠️ Couldn't send welcome message: {e}")

@bot.event
async def on_guild_remove(guild):
    """When bot is removed from a server"""
    print(f"➖ Removed from server: {guild.name} (ID: {guild.id})")
    
    # Clean up channel restriction for this guild
    if guild.id in allowed_channels:
        del allowed_channels[guild.id]
        save_allowed_channels()

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        lang = user_languages.get(ctx.author.id, DEFAULT_LANG)
        msg = translations[lang]['errors']['missing_id']
        await ctx.send(f"❌ {msg}")
    elif isinstance(error, commands.CheckFailure):
        # Check if it's channel restriction error
        if "predicate" in str(error):
            return  # Already handled by decorator
        # Permission error for setchannel
        await ctx.send("❌ You need **Administrator** permissions to use this command.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ I don't have permission to do that. Please check my role permissions.")
    else:
        print(f"⚠️ Command error: {type(error).__name__}: {error}")

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
                await ctx.send(embed=embed)
                
        except Exception as e:
            print(f"Error checking ban status: {e}")
            error_msg = translations[lang]['errors']['unexpected']
            await ctx.send(f"💥 {error_msg}")

@bot.command(name='lang')
@check_channel_restriction()
async def set_language(ctx, language: str = None):
    """
    Set your preferred language (en/fr)
    Usage: !lang en  OR  !lang fr
    """
    if language is None:
        current_lang = user_languages.get(ctx.author.id, DEFAULT_LANG)
        await ctx.send(f"ℹ️ Your current language is: **{current_lang}**\n"
                      f"Use `!lang en` or `!lang fr` to change.")
        return
    
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
    save_allowed_channels()
    
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
        save_allowed_channels()
        
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

@bot.command(name='ping')
async def ping_command(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)  # Convert to ms
    await ctx.send(f"🏓 Pong! Latency: **{latency}ms**")

# ============================================================================
# Startup Logic
# ============================================================================

async def start_bot():
    """Start the Discord bot"""
    print("🚀 Starting Free Fire Ban Checker Bot...")
    print(f"👨‍💻 Developer: Digamber Raj")
    print(f"🔧 Bot Token Present: {'Yes' if BOT_TOKEN and BOT_TOKEN != 'PLACEHOLDER_TOKEN_NO_CONNECTION' else 'No (using placeholder)'}")
    
    if BOT_TOKEN == "PLACEHOLDER_TOKEN_NO_CONNECTION":
        print("⚠️ WARNING: Using placeholder token. Bot will NOT connect to Discord.")
        print("⚠️ Please set DISCORD_BOT_TOKEN environment variable.")
    
    # Start Flask server in background for keep-alive
    import threading
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask keep-alive server started")
    
    try:
        # Start Discord bot
        await bot.start(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("❌ FAILED TO LOGIN: Invalid Discord bot token!")
        print("💡 Please check your DISCORD_BOT_TOKEN environment variable.")
        print("💡 Get token from: https://discord.com/developers/applications")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\n👋 Bot shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
