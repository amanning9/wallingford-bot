from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from typing import Dict, Any


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("rooms")
        helper.copy("users") 
        helper.copy("homeassistant")
        helper.copy("activities")
        helper.copy("confirmation_emojis")
        helper.copy("timing")
        helper.copy("messages")

    @property
    def alex_private_room(self) -> str:
        return self["rooms"]["alex_private"]
    
    @property
    def group_chat_room(self) -> str:
        return self["rooms"]["group_chat"]
    
    @property
    def alex_user_id(self) -> str:
        return self["users"]["alex_user_id"]
    
    @property
    def webhook_secret(self) -> str:
        return self["homeassistant"]["webhook_secret"]
    
    @property
    def activities(self) -> Dict[str, Any]:
        return self["activities"]
    
    @property
    def confirmation_emojis(self) -> list:
        return self["confirmation_emojis"]
    
    @property
    def timing(self) -> Dict[str, Any]:
        return self["timing"]
    
    @property
    def messages(self) -> Dict[str, str]:
        return self["messages"]