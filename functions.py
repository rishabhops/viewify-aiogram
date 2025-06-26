
import aiosqlite
import logging

# Configure logging
logger = logging.getLogger(__name__)

async def isExists(user_id: int) -> bool:
    """Check if the user exists in the database."""
    async with aiosqlite.connect("bot_data.db") as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (int(user_id),))
        return await cursor.fetchone() is not None

async def insertUser(user_id: int, data: dict) -> bool:
    """Insert user data if user does not exist."""
    if not await isExists(user_id):
        try:
            async with aiosqlite.connect("bot_data.db") as db:
                await db.execute('''INSERT INTO users 
                                    (user_id, username, balance, ref_by, referred, welcome_bonus, total_refs)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                 (int(data["user_id"]), 
                                  data.get("username", "Unknown"),
                                  float(data["balance"]),
                                  data["ref_by"],
                                  int(data["referred"]),
                                  int(data["welcome_bonus"]),
                                  int(data["total_refs"])))
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting user {user_id}: {e}")
            return False
    return False

async def getData(user_id: int) -> dict:
    """Retrieve all user data from the database."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (int(user_id),))
            row = await cursor.fetchone()
            if row:
                return {
                    "user_id": str(row[0]),  # Convert to string to match original JSON
                    "username": row[1],
                    "balance": row[2],
                    "ref_by": row[3],
                    "referred": row[4],
                    "welcome_bonus": row[5],
                    "total_refs": row[6]
                }
            return None
    except Exception as e:
        logger.error(f"Error retrieving data for user {user_id}: {e}")
        return None

async def addBalance(user_id: int, amount: float) -> bool:
    """Add balance to the user account."""
    if await isExists(user_id):
        try:
            async with aiosqlite.connect("bot_data.db") as db:
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                                (float(amount), int(user_id)))
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding balance for user {user_id}: {e}")
            return False
    return False

async def cutBalance(user_id: int, amount: float) -> bool:
    """Deduct balance from the user account."""
    if await isExists(user_id):
        try:
            async with aiosqlite.connect("bot_data.db") as db:
                cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (int(user_id),))
                current_balance = (await cursor.fetchone())[0]
                if current_balance >= float(amount):
                    await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", 
                                    (float(amount), int(user_id)))
                    await db.commit()
                    return True
        except Exception as e:
            logger.error(f"Error cutting balance for user {user_id}: {e}")
            return False
    return False

async def track_exists(user_id: int) -> bool:
    """Check if the referral user exists."""
    return await isExists(user_id)

async def setWelcomeStaus(user_id: int) -> bool:
    """Set the welcome bonus status for the user."""
    if await isExists(user_id):
        try:
            async with aiosqlite.connect("bot_data.db") as db:
                await db.execute("UPDATE users SET welcome_bonus = 1 WHERE user_id = ?", (int(user_id),))
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting welcome status for user {user_id}: {e}")
            return False
    return False

async def setReferredStatus(user_id: int) -> bool:
    """Set the referred status for the user."""
    if await isExists(user_id):
        try:
            async with aiosqlite.connect("bot_data.db") as db:
                await db.execute("UPDATE users SET referred = 1 WHERE user_id = ?", (int(user_id),))
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting referred status for user {user_id}: {e}")
            return False
    return False

async def addRefCount(user_id: int) -> bool:
    """Increment the referral count for the user."""
    if await isExists(user_id):
        try:
            async with aiosqlite.connect("bot_data.db") as db:
                await db.execute("UPDATE users SET total_refs = total_refs + 1 WHERE user_id = ?", 
                                (int(user_id),))
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error incrementing ref count for user {user_id}: {e}")
            return False
    return False