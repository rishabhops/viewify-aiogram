import os
from dotenv import load_dotenv

# Load environment variables from .env file (optional, for security)
load_dotenv()

# Bot configuration
bot_token = os.getenv("BOT_TOKEN", "5955204118:AAE54SY5sIJUXgDTsu2iNZvKWu8ibTI-x5c")

# SMM Panel API keys
SmmPanelApi = os.getenv("SMM_PANEL_API", "91040099d2b343c94cf07007ac881c1f")
SmmPanelApi2 = os.getenv("SMM_PANEL_API2", "fb8c1e3702d9bbb4d10644254925fea9")
viewsapi = os.getenv("VIEWS_API", "2339a49b7fe9f1964bcec955887894ee")
viewsapiurl = os.getenv("VIEWS_API_URL", "https://trustysmm.com/api/v2")
viewsserviceid = 1533  # SMM panel service ID for views

# Admin and channel configuration
admin_user_id = 5470956337
required_channels = ['@xviewify', '@THANOS_PRO']  # Channels users must join
payment_channel = "@tpviehuhs"  # Channel for order notifications

# Bot assets
logo_url = "https://graph.org/file/c96ff326d198ba2142efb.jpg"

# Bonus and view limits
welcome_bonus = 200  # Coins given to new users
ref_bonus = 150  # Coins given for referrals
min_view = 100  # Minimum views per order
max_view = 50000  # Maximum views per order