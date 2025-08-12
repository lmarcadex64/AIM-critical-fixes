"""
Services AIM - Modules de correction des systèmes critiques

🗣️ ConversationManager - Gestion des conversations multiples
🤖 AIPromptSystem - Système de prompts IA amélioré  
✅ TaskExtractor - Extraction intelligente de tâches
🧠 MemorySystem - Mémoire conversationnelle avancée
"""

from .conversation_manager import ConversationManager
from .ai_prompt_system import AIPromptSystem
from .task_extractor import TaskExtractor
from .memory_system import MemorySystem

__all__ = [
    'ConversationManager',
    'AIPromptSystem', 
    'TaskExtractor',
    'MemorySystem'
]