import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import aiosqlite
from config import admin_user_id

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('broadcast.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global broadcast stats
broadcast_stats = {
    'successful': 0,
    'failed': 0,
    'blocked': 0,
    'inactive': 0,
    'total': 0,
    'in_progress': False,
    'start_time': None,
    'current_user': 0,
    'cancelled': False
}

async def send_error_to_owner(bot: Bot, error_message: str, context: str = ""):
    """Send error message to owner."""
    try:
        if admin_user_id:
            error_text = f"🚨 Broadcast Bot Error\n\n"
            if context:
                error_text += f"📍 Context: {context}\n\n"
            error_text += f"❌ Error: {error_message}\n\n"
            error_text += f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            await bot.send_message(admin_user_id, error_text[:4096])  # Telegram message limit
    except Exception as e:
        logger.error(f"Failed to send error to owner: {e}")

async def load_user_ids() -> set:
    """Load user IDs from SQLite."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            user_ids = set(row[0] for row in rows)
            logger.info(f"Loaded {len(user_ids)} user IDs")
            return user_ids
    except Exception as e:
        logger.error(f"Unexpected error loading user IDs: {e}")
        await send_error_to_owner(None, f"Unexpected error loading user IDs: {str(e)}", "load_user_ids")
        return set()

async def clean_inactive_users(bot: Bot, inactive_users: list):
    """Remove inactive users from the users table."""
    try:
        if inactive_users:
            logger.info(f"Removing {len(inactive_users)} inactive users")
            async with aiosqlite.connect("bot_data.db") as db:
                await db.executemany("DELETE FROM users WHERE user_id = ?", [(uid,) for uid in inactive_users])
                await db.commit()
            logger.info(f"Cleaned {len(inactive_users)} inactive users from database")
    except Exception as e:
        error_msg = f"Failed to clean inactive users: {str(e)}"
        logger.error(error_msg)
        await send_error_to_owner(bot, error_msg, "clean_inactive_users")

async def send_broadcast_message(bot: Bot, user_id: int, message_data: dict, is_forward: bool = False) -> dict:
    """Send message to a single user with comprehensive error handling."""
    try:
        if is_forward:
            await bot.forward_message(
                user_id,
                message_data['chat_id'],
                message_data['message_id']
            )
        else:
            if message_data.get('content_type') == 'text':
                await bot.send_message(
                    user_id,
                    message_data['text'],
                    parse_mode=message_data.get('parse_mode'),
                    disable_web_page_preview=message_data.get('disable_web_page_preview', True)
                )
            elif message_data.get('content_type') == 'photo':
                await bot.send_photo(
                    user_id,
                    message_data['photo'],
                    caption=message_data.get('caption'),
                    parse_mode=message_data.get('parse_mode')
                )
            elif message_data.get('content_type') == 'video':
                await bot.send_video(
                    user_id,
                    message_data['video'],
                    caption=message_data.get('caption'),
                    parse_mode=message_data.get('parse_mode')
                )
            elif message_data.get('content_type') == 'document':
                await bot.send_document(
                    user_id,
                    message_data['document'],
                    caption=message_data.get('caption'),
                    parse_mode=message_data.get('parse_mode')
                )
            elif message_data.get('content_type') == 'audio':
                await bot.send_audio(
                    user_id,
                    message_data['audio'],
                    caption=message_data.get('caption'),
                    parse_mode=message_data.get('parse_mode')
                )
            else:
                return {'status': 'error', 'error': f"Unsupported content type: {message_data.get('content_type')}"}
        
        return {'status': 'success'}
    
    except Exception as e:
        if hasattr(e, 'error_code'):
            error_code = e.error_code
            error_description = str(e)
            
            if error_code == 403:
                if "bot was blocked" in error_description.lower():
                    return {'status': 'blocked'}
                elif "user is deactivated" in error_description.lower():
                    return {'status': 'inactive'}
                else:
                    return {'status': 'forbidden', 'error': error_description}
            elif error_code == 400:
                if "chat not found" in error_description.lower():
                    return {'status': 'inactive'}
                else:
                    return {'status': 'bad_request', 'error': error_description}
            elif error_code == 429:
                retry_after = getattr(e, 'retry_after', 1)
                logger.warning(f"Rate limit hit for user {user_id}, retry after {retry_after} seconds")
                await asyncio.sleep(retry_after)
                return {'status': 'retry'}
            else:
                return {'status': 'error', 'error': f"Code {error_code}: {error_description}"}
        else:
            error_msg = f"Unexpected error sending to user {user_id}: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': str(e)}

async def chunk_list(lst: list, chunk_size: int):
    """Divide the list into chunks of the specified size."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

async def broadcast_worker(bot: Bot, admin_chat_id: int, message_data: dict, is_forward: bool = False):
    """Background worker for broadcasting messages."""
    global broadcast_stats
    
    try:
        broadcast_stats['in_progress'] = True
        broadcast_stats['start_time'] = datetime.now()
        broadcast_stats['cancelled'] = False
        
        user_ids = await load_user_ids()
        user_list = list(user_ids)
        broadcast_stats['total'] = len(user_list)
        
        logger.info(f"Starting broadcast to {broadcast_stats['total']} users")
        
        # Send initial status
        status_msg = None
        try:
            status_msg = await bot.send_message(
                admin_chat_id,
                f"🚀 Broadcast started!\n"
                f"📊 Total users: {broadcast_stats['total']}\n"
                f"⏰ Started at: {broadcast_stats['start_time'].strftime('%H:%M:%S')}\n\n"
                f"Progress will be updated every 100 messages..."
            )
        except Exception as e:
            await send_error_to_owner(bot, f"Failed to send initial status: {str(e)}", "broadcast_worker")
        
        # Process users in chunks with adaptive rate limiting
        chunk_size = 30
        delay_between_messages = 0.05  # 50ms delay
        delay_between_chunks = 2  # 2 seconds between chunks
        
        user_chunks = list(chunk_list(user_list, chunk_size))
        
        for chunk_index, chunk in enumerate(user_chunks):
            if broadcast_stats.get('cancelled', False):
                logger.info("Broadcast cancelled by admin")
                break
                
            consecutive_rate_limits = 0
            inactive_users = []
            
            for user_id in chunk:
                if broadcast_stats.get('cancelled', False):
                    break
                    
                broadcast_stats['current_user'] += 1
                
                max_retries = 3
                for attempt in range(max_retries):
                    result = await send_broadcast_message(bot, user_id, message_data, is_forward)
                    
                    if result['status'] == 'success':
                        broadcast_stats['successful'] += 1
                        break
                    elif result['status'] == 'blocked':
                        broadcast_stats['blocked'] += 1
                        inactive_users.append(user_id)
                        break
                    elif result['status'] == 'inactive':
                        broadcast_stats['inactive'] += 1
                        inactive_users.append(user_id)
                        break
                    elif result['status'] == 'retry':
                        consecutive_rate_limits += 1
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        else:
                            broadcast_stats['failed'] += 1
                            break
                    else:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            broadcast_stats['failed'] += 1
                            logger.error(f"Failed to send to user {user_id}: {result.get('error', 'Unknown error')}")
                            break
                
                await asyncio.sleep(delay_between_messages)
            
            # Update progress every 100 users or every 5 chunks
            if (broadcast_stats['current_user'] % 100 == 0 or chunk_index % 5 == 0) and status_msg:
                try:
                    progress_percent = (broadcast_stats['current_user'] / broadcast_stats['total']) * 100
                    elapsed_time = datetime.now() - broadcast_stats['start_time']
                    
                    await bot.edit_message_text(
                        f"📡 Broadcast in progress...\n\n"
                        f"📊 Progress: {broadcast_stats['current_user']}/{broadcast_stats['total']} ({progress_percent:.1f}%)\n"
                        f"✅ Successful: {broadcast_stats['successful']}\n"
                        f"❌ Failed: {broadcast_stats['failed']}\n"
                        f"🚫 Blocked: {broadcast_stats['blocked']}\n"
                        f"💤 Inactive: {broadcast_stats['inactive']}\n"
                        f"⏱️ Elapsed: {str(elapsed_time).split('.')[0]}\n\n"
                        f"🔄 Processing chunk {chunk_index + 1}/{len(user_chunks)}...",
                        admin_chat_id,
                        status_msg.message_id
                    )
                except Exception as e:
                    logger.error(f"Failed to update progress: {e}")
            
            # Adaptive rate limiting
            if consecutive_rate_limits > 3:
                delay_between_chunks = min(delay_between_chunks * 1.5, 30)
                delay_between_messages = min(delay_between_messages * 1.2, 1)
                logger.warning(f"Increased delays due to rate limits: chunk={delay_between_chunks}s, message={delay_between_messages}s")
            
            if chunk_index < len(user_chunks) - 1:
                await asyncio.sleep(delay_between_chunks)
        
        # Clean up inactive users
        if inactive_users:
            await clean_inactive_users(bot, inactive_users)
        
        # Final report
        end_time = datetime.now()
        total_time = end_time - broadcast_stats['start_time']
        
        status_emoji = "✅" if not broadcast_stats.get('cancelled', False) else "🛑"
        status_text = "completed" if not broadcast_stats.get('cancelled', False) else "cancelled"
        
        final_report = (
            f"{status_emoji} Broadcast {status_text}!\n\n"
            f"📊 Final Statistics:\n"
            f"👥 Total users processed: {broadcast_stats['current_user']}/{broadcast_stats['total']}\n"
            f"✅ Successful: {broadcast_stats['successful']}\n"
            f"❌ Failed: {broadcast_stats['failed']}\n"
            f"🚫 Blocked by users: {broadcast_stats['blocked']}\n"
            f"💤 Inactive accounts: {broadcast_stats['inactive']}\n\n"
            f"⏱️ Total time: {str(total_time).split('.')[0]}\n"
        )
        
        if broadcast_stats['total'] > 0:
            final_report += f"📈 Success rate: {(broadcast_stats['successful']/broadcast_stats['total']*100):.1f}%\n"
        
        final_report += f"🧹 Cleaned {len(inactive_users)} inactive users from database"
        
        try:
            if status_msg:
                await bot.edit_message_text(final_report, admin_chat_id, status_msg.message_id)
            else:
                await bot.send_message(admin_chat_id, final_report)
        except Exception as e:
            await send_error_to_owner(bot, f"Failed to send final report: {str(e)}", "broadcast_worker")
        
        logger.info(f"Broadcast completed: {broadcast_stats}")
    
    except Exception as e:
        error_msg = f"Critical error in broadcast_worker: {str(e)}"
        logger.error(error_msg)
        await send_error_to_owner(bot, error_msg, "broadcast_worker")
        try:
            await bot.send_message(admin_chat_id, f"🚨 Broadcast failed due to critical error:\n{str(e)}")
        except:
            pass
    
    finally:
        # Reset stats
        broadcast_stats.update({
            'successful': 0,
            'failed': 0,
            'blocked': 0,
            'inactive': 0,
            'total': 0,
            'in_progress': False,
            'start_time': None,
            'current_user': 0,
            'cancelled': False
        })

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register broadcast handlers with the aiogram Dispatcher."""
    @dp.message(Command("broadcast"))
    async def handle_broadcast(message: types.Message, state: FSMContext):
        try:
            if message.chat.id != admin_user_id or message.chat.type != 'private':
                await message.reply("❌ This command is restricted to the bot owner and should be sent in a private chat.")
                return
            
            if broadcast_stats['in_progress']:
                progress_percent = (broadcast_stats['current_user'] / broadcast_stats['total']) * 100 if broadcast_stats['total'] > 0 else 0
                await message.reply(
                    f"⚠️ A broadcast is already in progress!\n\n"
                    f"📊 Progress: {broadcast_stats['current_user']}/{broadcast_stats['total']} ({progress_percent:.1f}%)\n"
                    f"⏱️ Started: {broadcast_stats['start_time'].strftime('%H:%M:%S') if broadcast_stats['start_time'] else 'Unknown'}\n\n"
                    f"Use /bcancel to cancel the current broadcast."
                )
                return
            
            user_ids = await load_user_ids()
            if not user_ids:
                await message.reply("❌ No users found in database!")
                return
            
            message_data = {}
            is_forward = False
            
            if message.reply_to_message:
                is_forward = True
                message_data = {
                    'chat_id': message.reply_to_message.chat.id,
                    'message_id': message.reply_to_message.message_id
                }
            else:
                broadcast_text = ' '.join(message.text.split()[1:])
                if not broadcast_text:
                    await message.reply(
                        "❌ Please specify the message you want to broadcast or reply to a message to forward.\n\n"
                        "📝 Usage:\n"
                        "• `/broadcast Your message here` - Send text message\n"
                        "• Reply to any message with `/broadcast` - Forward that message\n"
                        "• `/bstatus` - Check broadcast status\n"
                        "• `/bcancel` - Cancel ongoing broadcast\n"
                        "• `/users` - Check user count"
                    )
                    return
                
                message_data = {
                    'content_type': 'text',
                    'text': broadcast_text,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                }
            
            # Confirmation
            confirmation_markup = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton("✅ Confirm Broadcast", callback_data="broadcast_confirm"),
                 types.InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
            ])
            
            preview_text = "📝 Text message" if not is_forward else "🔄 Forwarded message"
            
            await message.reply(
                f"🔍 Broadcast Preview:\n\n"
                f"📊 Recipients: {len(user_ids)} users\n"
                f"📝 Content: {preview_text}\n\n"
                f"⚠️ Are you sure you want to proceed?",
                reply_markup=confirmation_markup
            )
            
            # Store broadcast data in FSM context
            await state.update_data(
                message_data=message_data,
                is_forward=is_forward,
                admin_chat_id=message.chat.id
            )
            
        except Exception as e:
            error_msg = f"Error in handle_broadcast: {str(e)}"
            logger.error(error_msg)
            await send_error_to_owner(bot, error_msg, "handle_broadcast")
            await message.reply(f"🚨 Error occurred while setting up broadcast:\n{str(e)}")

    @dp.callback_query(Command(commands=["broadcast_confirm", "broadcast_cancel"]))
    async def handle_broadcast_confirmation(callback: types.CallbackQuery, state: FSMContext):
        try:
            if callback.from_user.id != admin_user_id:
                await callback.answer("❌ Unauthorized")
                return
            
            if callback.data == 'broadcast_cancel':
                await callback.message.edit_text("❌ Broadcast cancelled.")
                await callback.answer("Broadcast cancelled")
                await state.clear()
                return
            
            if callback.data == 'broadcast_confirm':
                await callback.message.edit_text("🚀 Starting broadcast...")
                await callback.answer("Broadcast started!")
                
                broadcast_data = await state.get_data()
                if broadcast_data:
                    asyncio.create_task(
                        broadcast_worker(
                            bot,
                            broadcast_data['admin_chat_id'],
                            broadcast_data['message_data'],
                            broadcast_data['is_forward']
                        )
                    )
                    await state.clear()
                else:
                    await callback.message.reply("❌ Error: Broadcast data not found")
                    
        except Exception as e:
            error_msg = f"Error in handle_broadcast_confirmation: {str(e)}"
            logger.error(error_msg)
            await send_error_to_owner(bot, error_msg, "handle_broadcast_confirmation")
            await callback.answer("❌ Error occurred")
            await callback.message.reply(f"🚨 Error occurred:\n{str(e)}")

    @dp.message(Command("bstatus"))
    async def broadcast_status(message: types.Message):
        try:
            if message.chat.id != admin_user_id or message.chat.type != 'private':
                return
            
            if not broadcast_stats['in_progress']:
                current_users = await load_user_ids()
                await message.reply(
                    f"📊 Broadcast Status: Idle\n\n"
                    f"👥 Total users in database: {len(current_users)}"
                )
            else:
                progress_percent = (broadcast_stats['current_user'] / broadcast_stats['total']) * 100 if broadcast_stats['total'] > 0 else 0
                elapsed_time = datetime.now() - broadcast_stats['start_time'] if broadcast_stats['start_time'] else None
                
                status_text = (
                    f"📡 Broadcast Status: In Progress\n\n"
                    f"📊 Progress: {broadcast_stats['current_user']}/{broadcast_stats['total']} ({progress_percent:.1f}%)\n"
                    f"✅ Successful: {broadcast_stats['successful']}\n"
                    f"❌ Failed: {broadcast_stats['failed']}\n"
                    f"🚫 Blocked: {broadcast_stats['blocked']}\n"
                    f"💤 Inactive: {broadcast_stats['inactive']}\n"
                )
                
                if elapsed_time:
                    status_text += f"⏱️ Elapsed: {str(elapsed_time).split('.')[0]}\n\n"
                    
                status_text += "Use /bcancel to cancel the broadcast."
                
                await message.reply(status_text)
                
        except Exception as e:
            error_msg = f"Error in broadcast_status: {str(e)}"
            logger.error(error_msg)
            await send_error_to_owner(bot, error_msg, "broadcast_status")
            await message.reply(f"🚨 Error getting status: {str(e)}")

    @dp.message(Command("bcancel"))
    async def cancel_broadcast(message: types.Message):
        try:
            if message.chat.id != admin_user_id or message.chat.type != 'private':
                return
            
            if not broadcast_stats['in_progress']:
                await message.reply("❌ No broadcast is currently running.")
                return
            
            broadcast_stats['cancelled'] = True
            await message.reply("🛑 Broadcast cancellation requested. It will stop after the current chunk is processed.")
            
        except Exception as e:
            error_msg = f"Error in cancel_broadcast: {str(e)}"
            logger.error(error_msg)
            await send_error_to_owner(bot, error_msg, "cancel_broadcast")
            await message.reply(f"🚨 Error cancelling broadcast: {str(e)}")

    @dp.message(Command("users"))
    async def user_count(message: types.Message):
        try:
            if message.chat.id != admin_user_id or message.chat.type != 'private':
                return
            
            current_users = await load_user_ids()
            await message.reply(
                f"👥 Total users: {len(current_users)}\n"
                f"📊 Broadcast status: {'In Progress' if broadcast_stats['in_progress'] else 'Idle'}"
            )
                
        except Exception as e:
            error_msg = f"Error in user_count: {str(e)}"
            logger.error(error_msg)
            await send_error_to_owner(bot, error_msg, "user_count")
            await message.reply(f"🚨 Error getting user count: {str(e)}")

    @dp.message(Command("bhelp"))
    async def broadcast_help(message: types.Message):
        try:
            if message.chat.id != admin_user_id or message.chat.type != 'private':
                return
            
            help_text = (
                "📡 Broadcast Bot Commands:\n\n"
                "🔹 `/broadcast <message>` - Send text message to all users\n"
                "🔹 Reply to any message with `/broadcast` - Forward that message\n"
                "🔹 `/bstatus` - Check current broadcast status\n"
                "🔹 `/bcancel` - Cancel ongoing broadcast\n"
                "🔹 `/users` - Get total user count\n"
                "🔹 `/bhelp` - Show this help message\n\n"
                "📝 Features:\n"
                "• Automatic retry on failures\n"
                "• Rate limiting protection\n"
                "• Inactive user cleanup\n"
                "• Real-time progress updates\n"
                "• Error reporting to owner\n"
                "• Support for text, photos, videos, documents"
            )
            
            await message.reply(help_text)
            
        except Exception as e:
            error_msg = f"Error in broadcast_help: {str(e)}"
            logger.error(error_msg)
            await send_error_to_owner(bot, error_msg, "broadcast_help")
            await message.reply(f"🚨 Error in help command: {str(e)}")