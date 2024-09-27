import logging
import os

from config import BASE_URL

from fastapi import FastAPI
from vocode.streaming.models.telephony import TelnyxConfig  # Replace Twilio with Telnyx

# Import both if using ngrok
# from pyngrok import ngrok
# import sys
from memory_config import config_manager
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    TelnyxInboundCallConfig,  # Replace Twilio with Telnyx
    TelephonyServer,
)
from vocode.streaming.models.synthesizer import StreamElementsSynthesizerConfig  # ,ElevenLabsSynthesizerConfig

# Imports our custom actions
from speller_agent import SpellerAgentFactory

# Imports additional events like transcripts
from events_manager import EventsManager

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(docs_url=None)

# Initialize logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# We store the state of the call in memory
# You can customize the config within the memory_config.py
CONFIG_MANAGER = config_manager  # RedisConfigManager()

# Activate this if you want to support NGROK
# if not BASE_URL:
#     ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
#     if ngrok_auth is not None:
#         ngrok.set_auth_token(ngrok_auth)
#     port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000
#
#     # Open a ngrok tunnel to the dev server
#     BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
#     logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))
#

# Only continue if the base URL was set within the environment variable.
if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")


# Now we need a Telnyx account and number from which to make our call.
# You can make an account here: https://telnyx.com
# Ensure your account has a number for use
TELNYX_CONFIG = TelnyxConfig(
  api_key=os.environ.get("TELNYX_API_KEY"),
)

# Get the instructions for the assistant
def get_assistant_instructions():

  # Open the file and read its contents
  with open('instructions.txt', 'r') as file:
    return file.read()

# Now, we'll configure our agent and its objective.
# We'll use ChatGPT here, but you can import other models like
# GPT4AllAgent and ChatAnthropicAgent.
# Don't forget to set OPENAI_API_KEY!
AGENT_CONFIG = ChatGPTAgentConfig(
  initial_message=BaseMessage(text="Hello, who am I talking to?"),
  prompt_preamble=get_assistant_instructions(),
  generate_responses=True,
)

# Now we'll give our agent a voice and ears.
# Our default speech-to-text engine is DeepGram, so you'll need to set
# the env variable DEEPGRAM_API_KEY to your Deepgram API key.
# https://deepgram.com/

# We use StreamElements for speech synthesis here because it's fast and
# free, but there are plenty of other options that are slower but
# higher quality (like Eleven Labs below, needs key) available in
# vocode.streaming.models.synthesizer.
SYNTH_CONFIG = StreamElementsSynthesizerConfig.from_telephone_output_device()
# SYNTH_CONFIG = ElevenLabsSynthesizerConfig.from_telephone_output_device(
#   api_key=os.getenv("ELEVEN_LABS_API_KEY") or "<your EL token>")

# This is where we spin up the Telephony server to get the calls running
telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TelnyxInboundCallConfig(  # Replacing TwilioInboundCallConfig with Telnyx
            url="/inbound_call",
            agent_config=AGENT_CONFIG,
            telnyx_config=TELNYX_CONFIG,  # Use Telnyx config instead of Twilio
            synthesizer_config=SYNTH_CONFIG,
        )
    ],
    events_manager=EventsManager(),
    agent_factory=SpellerAgentFactory(),
    logger=logger,
)

app.include_router(telephony_server.get_router())
