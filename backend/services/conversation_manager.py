"""
🗣️ Service de gestion des conversations - CORRECTION CRITIQUE #1
Corrige les problèmes de gestion des conversations multiples et leur persistance
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

class ConversationManager:
    """Gestionnaire principal des conversations avec corrections critiques"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
    async def create_conversation(self, user_id: str, title: str = "Nouvelle conversation") -> Dict[str, Any]:
        """Crée une nouvelle conversation avec validation appropriée"""
        try:
            conversation = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'title': title,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'is_active': True,
                'message_count': 0,
                'last_message_at': None,
                'metadata': {}
            }
            
            await self.db.conversations.insert_one(conversation)
            logger.info(f"Conversation créée: {conversation['id']} pour utilisateur {user_id}")
            return conversation
            
        except Exception as e:
            logger.error(f"Erreur création conversation: {e}")
            raise
    
    async def get_user_conversations(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Récupère toutes les conversations d'un utilisateur avec pagination"""
        try:
            conversations = await self.db.conversations.find(
                {'user_id': user_id, 'is_active': True}
            ).sort('updated_at', -1).limit(limit).to_list(length=limit)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Erreur récupération conversations: {e}")
            return []
    
    async def get_conversation_by_id(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une conversation spécifique avec vérification de propriété"""
        try:
            conversation = await self.db.conversations.find_one({
                'id': conversation_id,
                'user_id': user_id,
                'is_active': True
            })
            return conversation
            
        except Exception as e:
            logger.error(f"Erreur récupération conversation {conversation_id}: {e}")
            return None
    
    async def update_conversation(self, conversation_id: str, user_id: str, **updates) -> bool:
        """Met à jour une conversation avec validation"""
        try:
            updates['updated_at'] = datetime.utcnow()
            
            result = await self.db.conversations.update_one(
                {'id': conversation_id, 'user_id': user_id},
                {'$set': updates}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Erreur mise à jour conversation {conversation_id}: {e}")
            return False
    
    async def increment_message_count(self, conversation_id: str, user_id: str) -> bool:
        """Incrémente le compteur de messages"""
        try:
            result = await self.db.conversations.update_one(
                {'id': conversation_id, 'user_id': user_id},
                {
                    '$inc': {'message_count': 1},
                    '$set': {
                        'last_message_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Erreur incrémentation message count: {e}")
            return False
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Supprime une conversation (soft delete)"""
        try:
            result = await self.db.conversations.update_one(
                {'id': conversation_id, 'user_id': user_id},
                {
                    '$set': {
                        'is_active': False,
                        'deleted_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Erreur suppression conversation {conversation_id}: {e}")
            return False
    
    async def get_conversation_messages(self, conversation_id: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupère les messages d'une conversation avec pagination"""
        try:
            # Vérifier d'abord que la conversation appartient à l'utilisateur
            conversation = await self.get_conversation_by_id(conversation_id, user_id)
            if not conversation:
                return []
            
            messages = await self.db.messages.find(
                {'conversation_id': conversation_id}
            ).sort('timestamp', 1).limit(limit).to_list(length=limit)
            
            return messages
            
        except Exception as e:
            logger.error(f"Erreur récupération messages: {e}")
            return []
    
    async def cleanup_inactive_conversations(self, days_threshold: int = 30) -> int:
        """Nettoie les conversations inactives anciennes"""
        try:
            cutoff_date = datetime.utcnow().replace(
                day=datetime.utcnow().day - days_threshold
            )
            
            result = await self.db.conversations.update_many(
                {
                    'last_message_at': {'$lt': cutoff_date},
                    'is_active': True,
                    'message_count': 0
                },
                {
                    '$set': {
                        'is_active': False,
                        'cleanup_reason': 'inactive_threshold',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Erreur nettoyage conversations: {e}")
            return 0