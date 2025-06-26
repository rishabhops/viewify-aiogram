import logging
import os
import shutil
import zipfile
import aiofiles
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import admin_user_id

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FSM for file manager
class FileManagerStates(StatesGroup):
    waiting_for_extract_path = State()

async def extract_zip(file_path: str, target_dir: str, loop):
    """Extract zip file asynchronously and remove old data in the target directory."""
    try:
        # Run blocking operations in executor
        def sync_extract():
            if os.path.exists(target_dir):
                # Remove old data
                for filename in os.listdir(target_dir):
                    file_path = os.path.join(target_dir, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f'Failed to delete {file_path}. Reason: {e}')
            else:
                os.makedirs(target_dir)
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
        
        await loop.run_in_executor(None, sync_extract)
    except Exception as e:
        logger.error(f"Error extracting zip file {file_path}: {e}")
        raise

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register file manager handlers with the aiogram Dispatcher."""
    
    @dp.message(Command("upl"))
    async def handle_upl(message: types.Message, state: FSMContext):
        if message.from_user.id != admin_user_id:
            await message.reply("You are not authorized to use this bot.")
            return
        
        if not (message.reply_to_message and message.reply_to_message.document):
            await message.reply("Please reply to a document to upload.")
            return
        
        try:
            file_info = await bot.get_file(message.reply_to_message.document.file_id)
            file_name = message.reply_to_message.document.file_name
            file_path = os.path.join(os.getcwd(), file_name)
            
            # Download file
            downloaded_file = await bot.download_file(file_info.file_path)
            
            # Remove existing file if present
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Save file asynchronously
            async with aiofiles.open(file_path, 'wb') as new_file:
                await new_file.write(downloaded_file.read())
            
            if file_name.endswith('.zip'):
                await state.update_data(zip_file_path=file_path)
                await message.reply("Where do you want to extract this data?")
                await state.set_state(FileManagerStates.waiting_for_extract_path)
            else:
                await message.reply(f"Uploaded {file_name}")
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            await message.reply(f"Failed to upload file: {e}")

    @dp.message(Command("ls"))
    async def handle_ls(message: types.Message):
        if message.from_user.id != admin_user_id:
            await message.reply("You are not authorized to use this bot.")
            return
        
        try:
            current_directory = os.getcwd()
            files = os.listdir(current_directory)
            files_list = '\n'.join(files) if files else "No files in current directory."
            await message.reply(f"Current directory files:\n{files_list}")
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            await message.reply(f"Failed to list directory: {e}")

    @dp.message(Command("cd"))
    async def handle_cd(message: types.Message, state: FSMContext):
        if message.from_user.id != admin_user_id:
            await message.reply("You are not authorized to use this bot.")
            return
        
        try:
            dir_name = message.text[4:].strip()
            if not dir_name:
                await message.reply("Please specify a directory name.")
                return
            
            current_directory = os.getcwd()
            new_directory = os.path.join(current_directory, dir_name)
            if os.path.isdir(new_directory):
                os.chdir(new_directory)
                await message.reply(f"Changed directory to {new_directory}")
            else:
                await message.reply(f"Directory {dir_name} does not exist.")
        except Exception as e:
            logger.error(f"Error changing directory: {e}")
            await message.reply(f"Failed to change directory: {e}")

    @dp.message(FileManagerStates.waiting_for_extract_path)
    async def handle_extract(message: types.Message, state: FSMContext):
        if message.from_user.id != admin_user_id:
            await message.reply("You are not authorized to use this bot.")
            return
        
        try:
            data = await state.get_data()
            zip_file_path = data.get('zip_file_path')
            if not zip_file_path:
                await message.reply("No zip file is pending extraction.")
                await state.clear()
                return
            
            target_dir = os.path.join(os.getcwd(), message.text.strip())
            loop = asyncio.get_event_loop()
            
            # Create target directory if it doesn't exist
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            await extract_zip(zip_file_path, target_dir, loop)
            os.remove(zip_file_path)
            await message.reply(f"Extracted data to {target_dir}")
        except Exception as e:
            logger.error(f"Failed to extract zip file: {e}")
            await message.reply(f"Failed to extract zip file: {e}")
        finally:
            await state.clear()