```markdown
# Free Fire Ban Checker Bot

A Discord bot that checks if a Free Fire player ID is banned by querying the official ban check API.

## Features

- **Real-time Ban Checking**: Instantly check any Free Fire player ID
- **Channel Restriction**: Restrict bot to specific channels (Admin only)
- **Multi-language Support**: English and French interfaces
- **Visual Feedback**: Custom GIFs for banned/clean accounts
- **Custom Emojis**: Special animated emojis for status indicators
- **Server Statistics**: Track how many servers are using the bot
- **Keep-alive System**: Built-in Flask server for 24/7 uptime

## Commands

### User Commands
| Command | Description | Example |
|---------|-------------|---------|
| `!ID <player_id>` | Check ban status for a player ID | `!ID 1234567890` |
| `!lang <en/fr>` | Set your preferred language | `!lang fr` |
| `!guilds` | Show how many servers use this bot | `!guilds` |
| `!helpchannel` | Show current channel restriction | `!helpchannel` |
| `!botinfo` | Show bot information | `!botinfo` |

### Admin Commands
| Command | Description | Permission |
|---------|-------------|------------|
| `!setchannel` | Restrict bot to current channel | Administrator |
| `!removechannel` | Remove channel restriction | Administrator |

## Channel Restriction System

The bot includes a channel restriction feature that allows server administrators to limit where the bot can be used:

1. **Set a restricted channel**: 
   - Admin uses `!setchannel` in any channel
   - Bot will only respond to commands in that channel
   - Useful for keeping chat organized

2. **Remove restriction**:
   - Admin uses `!removechannel`
   - Bot will work in all channels again

3. **Check current restriction**:
   - Anyone can use `!helpchannel`
   - Shows which channel is set (if any)

## Setup & Deployment

### Prerequisites

1. Python 3.8 or higher
2. Discord Bot Token
3. Discord Developer Portal access
4. Administrator permissions in your Discord server

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd check-ban-freefire-bot
```

1. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
2. Set up environment variables
   ```bash
   export DISCORD_BOT_TOKEN="your_bot_token_here"
   ```
3. Add GIF files
   · Place banned.gif in assets/ folder
   · Place notbanned.gif in assets/ folder
4. Run the bot
   ```bash
   python app.py
   ```

Vercel Deployment (Recommended)

1. Push code to GitHub
2. Import project in Vercel
3. Add environment variable: DISCORD_BOT_TOKEN
4. Deploy

Environment Variables

Variable Description Required
DISCORD_BOT_TOKEN Your Discord bot token Yes

File Structure

```
check-ban-freefire-bot/
├── app.py              # Main bot application
├── utils.py            # Utility functions
├── bot_config.json     # Channel restriction config (auto-generated)
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel deployment config
├── README.md           # This file
└── assets/             # Image assets
    ├── banned.gif      # Banned account GIF
    └── notbanned.gif   # Clean account GIF
```

API Reference

The bot uses the official Free Fire ban check API:

```
GET http://raw.thug4ff.com/check_ban/check_ban/{player_id}
```

Response Format

```json
{
  "id": "1234567890",
  "name": "PlayerName",
  "banned": true
}
```

Emoji Requirements

For full functionality, add these custom emojis to your Discord server:

1. Banned Emoji: <a:emoji_48:1430083636425920673>
2. Not Banned Emoji: <a:emoji_18:1430082305032192000>

If these emojis aren't available in your server, the bot will display text-only status.

Admin Guide

Setting up Channel Restriction

1. Invite bot to your server
2. Go to the channel where you want bot to work
3. Type !setchannel (requires Admin permissions)
4. Bot will now only respond in that channel

Removing Restriction

1. Go to any channel where you have Admin access
2. Type !removechannel
3. Bot will work in all channels again

Troubleshooting

Bot not responding to commands:

· Check if channel restriction is set
· Use !helpchannel to see current restriction
· Make sure you're in the correct channel

Admin commands not working:

· Verify you have Administrator permissions
· Check role hierarchy in server settings
· Try using server owner account

Support

For issues, questions, or feature requests:

· Check the GitHub repository issues
· Ensure you're using the latest version

Credits

Developer: Digamber Raj

This bot is not affiliated with Garena or Free Fire. It simply queries publicly available ban status information.

License

This project is for educational and personal use only. Commercial use is prohibited.

```