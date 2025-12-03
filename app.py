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
import random
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
    load_bot_config,
    mock_player_status  # Fallback function
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
    print("\n💡 Get bot token from: https://discord.com/developers/applications")
    sys.exit(1)

# Bot prefix
COMMAND_PREFIX = "!"

# API endpoints for ban checking (multiple fallbacks)
API_ENDPOINTS = [
    "http://raw.thug4ff.com/check_ban/check_ban/",  # Original API
    "https://raw.thug4ff.com/check_ban/check_ban/", # HTTPS version
]

# Default language
DEFAULT_LANG = "en"

# Config file path
CONFIG_FILE = "bot_config.json"

# Use mock data if API fails (for testing)
USE_MOCK_IF_API_FAILS = True

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
        "api_status": "operational"
    })

@web_app.route('/health')
def health_check():
    """Simple health endpoint for uptime monitoring"""
    return "OK", 200

@web_app.route('/api-test')
def api_test():
    """Test API connectivity"""
    return jsonify({
        "message": "API Test Endpoint",
        "endpoints": API_ENDPOINTS,
        "status": "testing_required"
    })

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
allowed_channels: Dict[int, int] = {}

# Store API status
api_status = {
    "working": False,
    "last_checked": None,
    "active_endpoint": None
}

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
# API Health Check
# ============================================================================

async def check_api_health():
    """Check if API endpoints are working"""
    global api_status
    
    test_id = "1234567890"  # Test ID
    
    for endpoint in API_ENDPOINTS:
        try:
            print(f"🔍 Testing API endpoint: {endpoint}")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{endpoint}{test_id}", timeout=5) as response:
                    if response.status == 200:
                        api_status = {
                            "working": True,
                            "last_checked": datetime.utcnow().isoformat(),
                            "active_endpoint": endpoint
                        }
                        print(f"✅ API is working: {endpoint}")
                        return True
        except Exception as e:
            print(f"❌ API endpoint failed {endpoint}: {e}")
            continue
    
    # All endpoints failed
    api_status = {
        "working": False,
        "last_checked": datetime.utcnow().isoformat(),
        "active_endpoint": None
    }
    print("❌ All API endpoints failed, will use mock data")
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
    
    # Check API health
    await check_api_health()
    
    # Set bot status based on API status
    if api_status["working"]:
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="!ID <player_id>"
        )
    else:
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="API Down - Demo Mode"
        )
    
    try:
        await bot.change_presence(activity=activity)
    except:
        pass

@bot.event
async def on_guild_join(guild):
    """When bot joins a new server"""
    print(f"➕ Joined new server: {guild.name} (ID: {guild.id})")
    
    # Send welcome message
    try:
        channel = guild.system_channel
        if not channel or not channel.permissions_for(guild.me).send_messages:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
        
        if channel and channel.permissions_for(guild.me).send_messages:
            welcome_embed = discord.Embed(
                title="🤖 Free Fire Ban Checker",
                description=(
                    "Thanks for adding me! I check if Free Fire IDs are banned.\n\n"
                    "**Main Commands:**\n"
                    "`!ID <player_id>` - Check ban status\n"
                    "`!lang en/fr` - Set your language\n"
                    "`!guilds` - Show server count\n"
                    "`!botinfo` - Show all commands\n"
                    "`!apistatus` - Check API status\n\n"
                    f"**Current Status:** {'✅ API Working' if api_status['working'] else '⚠️ Demo Mode'}"
                ),
                color=0x5865F2 if api_status["working"] else 0xFFA500,
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
        if "predicate" in str(error):
            return
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
            status_data = None
            
            # Try to get real data from API
            if api_status["working"] and api_status["active_endpoint"]:
                for endpoint in API_ENDPOINTS:
                    status_data = await get_player_status(player_id, endpoint)
                    if status_data:
                        break
            
            # If API failed and mock is enabled, use mock data
            if not status_data and USE_MOCK_IF_API_FAILS:
                print(f"⚠️ Using mock data for ID: {player_id}")
                status_data = mock_player_status(player_id)
                
                # Add note about demo mode
                if 'name' in status_data:
                    status_data['name'] = f"{status_data['name']} [DEMO]"
            
            if not status_data:
                error_msg = translations[lang]['errors']['api_error']
                await ctx.send(f"🔧 {error_msg}")
                return
            
            # Create embed response
            embed = build_embed_response(status_data, lang, translations)
            
            # Add API status note if in demo mode
            if not api_status["working"] and USE_MOCK_IF_API_FAILS:
                embed.add_field(
                    name="⚠️ Note",
                    value="Currently in **Demo Mode** (API offline). Real ban status may vary.",
                    inline=False
                )
            
            # Determine which GIF to send
            is_banned = status_data.get('banned', False)
            gif_filename = "banned.gif" if is_banned else "notbanned.gif"
            gif_path = f"assets/{gif_filename}"
            
            # Check if GIF file exists
            if os.path.exists(gif_path):
                gif_file = discord.File(gif_path, filename=gif_filename)
                await ctx.send(file=gif_file, embed=embed)
            else:
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
    
    embed.add_field(
        name="API Status",
        value="✅ Working" if api_status["working"] else "⚠️ Demo Mode",
        inline=True
    )
    
    embed.set_footer(text=f"Developer: Digamber Raj")
    
    await ctx.send(embed=embed)

@bot.command(name='apistatus')
async def api_status_command(ctx):
    """
    Check the status of the ban check API
    Usage: !apistatus
    """
    # Run API health check
    is_working = await check_api_health()
    
    if is_working:
        embed = discord.Embed(
            title="✅ API Status: WORKING",
            description="The ban check API is currently operational.",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Active Endpoint",
            value=api_status["active_endpoint"] or "None",
            inline=False
        )
        
        embed.add_field(
            name="Last Checked",
            value=api_status["last_checked"] or "Never",
            inline=True
        )
        
        embed.add_field(
            name="Fallback Mode",
            value="Disabled" if api_status["working"] else "Enabled",
            inline=True
        )
    else:
        embed = discord.Embed(
            title="⚠️ API Status: OFFLINE",
            description="The ban check API is currently unavailable.",
            color=0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Fallback Mode",
            value="✅ Enabled (Using mock data)",
            inline=False
        )
        
        embed.add_field(
            name="Note",
            value="Bot will use demo data to continue functioning.",
            inline=False
        )
    
    embed.set_footer(text="Developer: Digamber Raj")
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
            "• `!apistatus` - Check API status\n"
            "• `!botinfo` - Show this info\n"
            "• `!ping` - Check bot latency\n\n"
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
        name="API Status",
        value="✅ Working" if api_status["working"] else "⚠️ Demo Mode",
        inline=True
    )
    
    embed.set_footer(text="Free Fire Ban Checker Bot")
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping_command(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)  # Convert to ms
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: **{latency}ms**",
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="API Status",
        value="✅ Working" if api_status["working"] else "⚠️ Demo Mode",
        inline=True
    )
    
    await ctx.send(embed=embed)

# ============================================================================
# Startup Logic
# ============================================================================

async def start_bot():
    """Start the Discord bot"""
    print("🚀 Starting Free Fire Ban Checker Bot...")
    print(f"👨‍💻 Developer: Digamber Raj")
    print(f"🔧 Bot Token Present: Yes")
    
    # Check API status before starting
    print("🔍 Checking API connectivity...")
    await check_api_health()
    
    if api_status["working"]:
        print("✅ API is working properly")
    else:
        print("⚠️ API is down, using fallback mode")
        if USE_MOCK_IF_API_FAILS:
            print("✅ Fallback mode enabled (mock data)")
        else:
            print("❌ Fallback mode disabled")
    
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
