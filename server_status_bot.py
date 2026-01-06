import pandas as pd
from mcstatus import JavaServer
from datetime import datetime
import time
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import threading
import signal
import sys

# Configuration
SERVER_ADDRESS = "your_minecraft_server_ip"  # Your Minecraft server IP
TOKEN = 'your_telegram_bot_token'  # Your Telegram bot token
EXCEL_FILE = "players_online.xlsx"  # File name for saving data

# Admin IDs (REPLACE WITH REAL IDs)
ADMIN_IDS = {admin_id1, admin_id2, admin_id3,...}  # ← Insert real Telegram IDs here

# Server initialization for the bot
server = JavaServer.lookup(SERVER_ADDRESS)

# Global flag for stopping the monitoring
monitoring_active = True

def is_admin(user_id: int) -> bool:
    """Check if user is an administrator"""
    return user_id in ADMIN_IDS

def save_players_to_excel():
    """Save current player information to Excel file"""
    
    try:
        # Get data from server
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        
        # Current time
        current_time = datetime.now()
        
        # Prepare data
        data = {
            'Date': current_time.strftime('%Y-%m-%d'),
            'Time': current_time.strftime('%H:%M:%S'),
            'Day of week': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][current_time.weekday()],
            'Total online': status.players.online
        }
        
        # Add player names
        if status.players.sample:
            players = [player.name for player in status.players.sample]
            for i, player in enumerate(players, 1):
                data[f'Player {i}'] = player
            
            # Add empty cells if less than 50 players
            for i in range(len(players) + 1, 51):
                data[f'Player {i}'] = ''
        else:
            for i in range(1, 51):
                data[f'Player {i}'] = ''
        
        # Create DataFrame
        df_new = pd.DataFrame([data])
        
        # If file exists - append new data
        if os.path.exists(EXCEL_FILE):
            df_existing = pd.read_excel(EXCEL_FILE)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_combined = df_new
        
        # Save to Excel
        df_combined.to_excel(EXCEL_FILE, index=False)
        
        print(f"✅ Data saved: {current_time.strftime('%H:%M:%S')} - {status.players.online} players")
        
        if status.players.sample:
            print("Players:")
            for player in status.players.sample:
                print(f"  - {player.name}")
        
    except Exception as e:
        print(f"❌ Error saving to Excel: {e}")

def run_every_15_minutes():
    """Run data collection every 15 minutes in background"""
    
    print("Starting Minecraft server data collection")
    print(f"Server: {SERVER_ADDRESS}")
    print(f"Data saved to file: {EXCEL_FILE}")
    print("="*50)
    
    global monitoring_active
    
    # Initial save
    save_players_to_excel()
    
    while monitoring_active:
        try:
            # Wait 15 minutes (900 seconds) but check every second for stop signal
            for _ in range(900):
                if not monitoring_active:
                    break
                time.sleep(1)
            
            if monitoring_active:
                save_players_to_excel()
                print(f"\nNext check in 15 minutes...\n")
                
        except Exception as e:
            print(f"❌ Error in monitoring thread: {e}")
            if monitoring_active:
                time.sleep(60)  # Wait a minute before retrying

# ==================== TELEGRAM BOT ====================

async def get_server_stats():
    """Async server status retrieval for Telegram bot"""
    try:
        status = await server.async_status()
        
        # Prepare message
        message = f"😛 Currently {status.players.online} player(s) online\n"
        message += f"😢 Latency: {status.latency:.1f} ms\n"
        message += f"😍 Version: {status.version.name}\n"
        message += f"❤️ Description: {status.description}\n"
        
        # Show player names if available
        if status.players.sample:
            players_list = ", ".join([player.name for player in status.players.sample])
            message += f"😘 Online players: {players_list}"
        else:
            message += "😭 Player list unavailable"
            
        return message
    except Exception as e:
        return f"Error getting server status: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command"""
    await update.message.reply_text('Hello! I am a Minecraft server status monitoring bot.\n'
                                   'Available commands:\n'
                                   '/stats - current server status\n'
                                   '/info - bot information\n'
                                   '/admin_check - check admin status\n'
                                   '/activity_get - get online history file (admins only)')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /stats command"""
    # Send loading message
    await update.message.reply_text("🧐 Getting server status...")
    
    # Get statistics
    stats_message = await get_server_stats()
    
    # Send result
    await update.message.reply_text(stats_message)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /info command"""
    await update.message.reply_text(
        "🤖 Minecraft server monitoring bot\n\n"
        "Features:\n"
        "• Check current online players\n"
        "• Real-time player monitoring\n"
        "• Automatic statistics saving to Excel\n"
        "• Report sending to administrators\n\n"
        "Commands:\n"
        "/start - start working\n"
        "/stats - server status\n"
        "/info - bot information"
    )

async def activity_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to send online history file (admins only)"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    # Check if file exists
    if not os.path.exists(EXCEL_FILE):
        await update.message.reply_text(f"❌ File '{EXCEL_FILE}' not found.")
        return
    
    try:
        # Send file
        with open(EXCEL_FILE, 'rb') as file:
            await update.message.reply_document(
                document=file,
                caption="📊 Online players history file"
            )
        await update.message.reply_text("✅ File sent successfully.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending file: {str(e)}")

async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check admin status"""
    user_id = update.effective_user.id
    if is_admin(user_id):
        await update.message.reply_text("✅ You are an administrator.\n"
                                       "Available commands:\n"
                                       "/activity_get - get statistics file")
    else:
        await update.message.reply_text("❌ You are not an administrator.")

async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual save of current online status (admins only)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    await update.message.reply_text("💾 Saving current online status...")
    save_players_to_excel()
    await update.message.reply_text("✅ Current online status saved to file!")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Received shutdown signal...")
    global monitoring_active
    monitoring_active = False
    sys.exit(0)

def start_background_monitoring():
    """Start background server monitoring"""
    # Create separate thread for monitoring
    monitoring_thread = threading.Thread(target=run_every_15_minutes, daemon=True)
    monitoring_thread.start()
    print("📊 Background server monitoring started (every 15 minutes)")
    return monitoring_thread

def main():
    """Main program startup function"""
    print("="*50)
    print("🚀 Starting Minecraft server monitoring system")
    print("="*50)
    
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check required settings
    if SERVER_ADDRESS == "your_minecraft_server_ip":
        print("❌ ERROR: Set real Minecraft server address in SERVER_ADDRESS variable!")
        exit(1)
    
    if TOKEN == 'your_telegram_bot_token':
        print("❌ ERROR: Set real Telegram bot token in TOKEN variable!")
        exit(1)
    
    if not ADMIN_IDS:
        print("⚠️  WARNING: Admin IDs not specified!")
        print("Add real Telegram IDs to ADMIN_IDS variable")
    
    # Start background monitoring
    monitoring_thread = start_background_monitoring()
    
    # Start Telegram bot
    print("\n🤖 Starting Telegram bot...")
    
    try:
        # Create and configure the bot application
        application = Application.builder().token(TOKEN).build()
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("info", info))
        application.add_handler(CommandHandler("save", save_command))
        application.add_handler(CommandHandler("activity_get", activity_get))
        application.add_handler(CommandHandler("admin_check", admin_check))
        
        print("✅ Telegram bot started and ready!")
        print("\n📝 Bot is now running. Press Ctrl+C to stop.")
        
        # Run the bot with polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except KeyboardInterrupt:
        print("\n🛑 Program stopped by user")
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop monitoring thread
        global monitoring_active
        monitoring_active = False
        monitoring_thread.join(timeout=2)
        print("\n👋 Program terminated cleanly")
# SUS

if __name__ == "__main__":
    main()