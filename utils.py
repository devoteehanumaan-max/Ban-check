"""
Utility functions for Free Fire Ban Checker
Helper module for API calls, embed building, and translations
"""

import json
import aiohttp
import os
from typing import Dict, Any, Optional
from datetime import datetime

import discord

# ============================================================================
# Constants
# ============================================================================

# Custom Discord emojis (must exist in the server where bot is used)
BANNED_EMOJI = "<a:emoji_48:1430083636425920673>"
NOT_BANNED_EMOJI = "<a:emoji_18:1430082305032192000>"

# Config file path
CONFIG_FILE = "bot_config.json"

# ============================================================================
# Configuration Functions
# ============================================================================

def save_bot_config(data: Dict[str, Any]):
    """
    Save configuration to file
    
    Args:
        data: Configuration data to save
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def load_bot_config() -> Dict[str, Any]:
    """
    Load configuration from file
    
    Returns:
        Configuration dictionary
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Return empty config if file doesn't exist
            return {
                'allowed_channels': {},
                'developer': 'Digamber Raj'
            }
    except json.JSONDecodeError:
        # If file is corrupted, return empty config
        return {
            'allowed_channels': {},
            'developer': 'Digamber Raj'
        }
    except Exception as e:
        print(f"Error loading config: {e}")
        return {
            'allowed_channels': {},
            'developer': 'Digamber Raj'
        }

def is_allowed_channel(guild_id: int, channel_id: int, allowed_channels: Dict[int, int]) -> bool:
    """
    Check if a channel is allowed for bot commands
    
    Args:
        guild_id: Discord guild ID
        channel_id: Discord channel ID
        allowed_channels: Dictionary of allowed channels
    
    Returns:
        True if channel is allowed, False otherwise
    """
    # If no restriction for this guild, all channels are allowed
    if guild_id not in allowed_channels:
        return True
    
    # Check if current channel is the allowed one
    return channel_id == allowed_channels[guild_id]

# ============================================================================
# API Functions
# ============================================================================

async def get_player_status(player_id: str, api_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch ban status for a player ID from the API
    
    Args:
        player_id: Free Fire player ID
        api_url: Base API URL
    
    Returns:
        Dictionary with player status or None if error
    """
    full_url = f"{api_url}{player_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"API returned status {response.status} for ID {player_id}")
                    return None
    except aiohttp.ClientError as e:
        print(f"Network error for ID {player_id}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON parse error for ID {player_id}: {e}")
        return None
    except asyncio.TimeoutError:
        print(f"Timeout error for ID {player_id}")
        return None
    except Exception as e:
        print(f"Unexpected error for ID {player_id}: {e}")
        return None

# ============================================================================
# Embed Building
# ============================================================================

def build_embed_response(status_data: Dict[str, Any], lang: str, translations: Dict) -> discord.Embed:
    """
    Create a Discord embed from player status data
    
    Args:
        status_data: Player status dictionary from API
        lang: Language code ('en' or 'fr')
        translations: Loaded translations dictionary
    
    Returns:
        Discord Embed object
    """
    # Extract data
    player_id = status_data.get('id', 'N/A')
    is_banned = status_data.get('banned', False)
    player_name = status_data.get('name', 'Unknown')
    
    # Get translation strings
    t = translations[lang]
    
    # Determine title, color, and emoji
    if is_banned:
        title = f"{BANNED_EMOJI} {t['banned']['title']}"
        color = 0xFF0000  # Red
        status_text = t['banned']['description']
        footer_text = t['banned']['footer']
    else:
        title = f"{NOT_BANNED_EMOJI} {t['not_banned']['title']}"
        color = 0x00FF00  # Green
        status_text = t['not_banned']['description']
        footer_text = t['not_banned']['footer']
    
    # Create embed
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    # Add player information fields
    embed.add_field(
        name=t['fields']['player_id'],
        value=f"`{player_id}`",
        inline=True
    )
    
    embed.add_field(
        name=t['fields']['player_name'],
        value=player_name,
        inline=True
    )
    
    embed.add_field(
        name=t['fields']['status'],
        value=status_text,
        inline=False
    )
    
    # Add footer with developer credit
    embed.set_footer(text=f"{footer_text} • Developer: Digamber Raj")
    
    return embed

# ============================================================================
# Translation System
# ============================================================================

def load_translations() -> Dict[str, Dict]:
    """
    Load all translation strings
    
    Returns:
        Dictionary with language codes as keys
    """
    return {
        'en': {
            'banned': {
                'title': 'Account Banned',
                'description': 'This player account has been **permanently banned** from Free Fire.',
                'footer': 'Violation detected'
            },
            'not_banned': {
                'title': 'Account Clean',
                'description': 'This player account is **not banned** and can play normally.',
                'footer': 'No violations found'
            },
            'fields': {
                'player_id': 'Player ID',
                'player_name': 'Player Name',
                'status': 'Ban Status'
            },
            'errors': {
                'missing_id': 'Please provide a player ID. Usage: `!ID <player_id>`',
                'invalid_id': 'Player ID must contain only numbers.',
                'api_error': 'Unable to check ban status at this time. Please try again later.',
                'unexpected': 'An unexpected error occurred. Please try again.'
            },
            'language_set': 'Your language has been set to English.',
            'guilds': {
                'title': 'Server Count',
                'description': 'This bot is currently serving **{count}** Discord servers.'
            }
        },
        'fr': {
            'banned': {
                'title': 'Compte Banni',
                'description': 'Ce compte joueur a été **définitivement banni** de Free Fire.',
                'footer': 'Violation détectée'
            },
            'not_banned': {
                'title': 'Compte Propre',
                'description': 'Ce compte joueur **n\'est pas banni** et peut jouer normalement.',
                'footer': 'Aucune violation trouvée'
            },
            'fields': {
                'player_id': 'ID du Joueur',
                'player_name': 'Nom du Joueur',
                'status': 'Statut du Bannissement'
            },
            'errors': {
                'missing_id': 'Veuillez fournir un ID joueur. Utilisation : `!ID <player_id>`',
                'invalid_id': 'L\'ID joueur doit contenir uniquement des chiffres.',
                'api_error': 'Impossible de vérifier le statut de bannissement pour le moment. Réessayez plus tard.',
                'unexpected': 'Une erreur inattendue est survenue. Veuillez réessayer.'
            },
            'language_set': 'Votre langue a été définie sur Français.',
            'guilds': {
                'title': 'Nombre de Serveurs',
                'description': 'Ce bot est actuellement utilisé sur **{count}** serveurs Discord.'
            }
        }
    }

# ============================================================================
# Helper Functions
# ============================================================================

def get_guild_count(bot) -> int:
    """
    Get the number of guilds the bot is in
    
    Args:
        bot: Discord bot instance
    
    Returns:
        Number of guilds
    """
    return len(bot.guilds)

def validate_player_id(player_id: str) -> bool:
    """
    Validate that a player ID contains only digits
    
    Args:
        player_id: Player ID string
    
    Returns:
        True if valid, False otherwise
    """
    return player_id.isdigit() and len(player_id) <= 20
