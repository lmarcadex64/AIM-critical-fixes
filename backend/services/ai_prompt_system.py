"""
🤖 Système de prompts IA amélioré - CORRECTION CRITIQUE #2
Corrige la génération et la gestion des prompts pour une meilleure cohérence IA
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import json
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

class AIPromptSystem:
    """Système de prompts IA avec gestion des contextes et personnalisation"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.base_prompts = self._load_base_prompts()
        
    def _load_base_prompts(self) -> Dict[str, str]:
        """Charge les prompts de base du système"""
        return {
            'coaching_base': """Tu es AIM, un coach IA personnel spécialisé dans l'accompagnement vers l'atteinte d'objectifs.

Tes caractéristiques :
- Bienveillant mais ferme quand nécessaire
- Axé sur l'action concrète et les résultats
- Capable d'adapter ton style selon la personnalité de l'utilisateur
- Expert en planification progressive et motivation

Contexte utilisateur disponible :
{user_context}

Historique conversationnel récent :
{conversation_history}

Objectifs actuels de l'utilisateur :
{current_goals}

Réponds toujours de manière :
1. Personnalisée selon le profil utilisateur
2. Orientée action avec des étapes concrètes
3. Motivante mais réaliste
4. Intégrant le contexte de la conversation""",

            'task_extraction': """Analyse le message utilisateur suivant et identifie toutes les tâches, actions ou objectifs mentionnés.

Message utilisateur : "{user_message}"

Contexte de la conversation : {conversation_context}

Instructions :
1. Identifie chaque tâche/action concrète mentionnée
2. Estime une date d'échéance si possible
3. Catégorise par priorité (haute/moyenne/basse)
4. Associe à un objectif existant si pertinent

Retourne ta réponse au format JSON :
{
    "tasks_found": [
        {
            "title": "titre de la tâche",
            "description": "description détaillée",
            "priority": "haute/moyenne/basse",
            "estimated_date": "YYYY-MM-DD ou null",
            "category": "catégorie",
            "related_goal_id": "id_objectif ou null"
        }
    ],
    "confidence": 0.85,
    "needs_clarification": false
}""",

            'memory_synthesis': """Synthétise les éléments importants de cette conversation pour enrichir la mémoire utilisateur.

Conversation récente :
{recent_messages}

Profil utilisateur actuel :
{user_profile}

Instructions :
1. Identifie les nouvelles préférences, habitudes ou informations personnelles
2. Note les progrès ou difficultés mentionnées
3. Détecte les changements d'objectifs ou de priorités
4. Résume les insights comportementaux

Retourne au format JSON :
{
    "new_preferences": ["préférence1", "préférence2"],
    "progress_notes": ["progrès1", "progrès2"],
    "behavioral_insights": ["insight1", "insight2"],
    "goal_changes": ["changement1", "changement2"],
    "memory_update_confidence": 0.90
}""",

            'proactive_coaching': """Génère un message de coaching proactif personnalisé.

Profil utilisateur :
{user_profile}

Analyse comportementale récente :
{behavior_analysis}

Objectifs actuels :
{current_goals}

Type de message demandé : {message_type}

Généré un message de coaching qui :
1. S'adapte au style de communication préféré de l'utilisateur
2. Prend en compte son état émotionnel récent
3. Propose des actions concrètes et réalisables
4. Maintient la motivation sans être intrusif

Le message doit être naturel, empathique et actionnable."""
        }
    
    async def get_enhanced_prompt(self, prompt_type: str, user_id: str, **context) -> str:
        """Génère un prompt enrichi avec le contexte utilisateur"""
        try:
            base_prompt = self.base_prompts.get(prompt_type)
            if not base_prompt:
                logger.error(f"Type de prompt inconnu: {prompt_type}")
                return ""
            
            # Enrichir avec le contexte utilisateur
            user_context = await self._get_user_context(user_id)
            conversation_history = context.get('conversation_history', '')
            current_goals = await self._get_user_goals(user_id)
            
            enhanced_prompt = base_prompt.format(
                user_context=user_context,
                conversation_history=conversation_history,
                current_goals=current_goals,
                **context
            )
            
            # Sauvegarder pour analytics
            await self._log_prompt_usage(prompt_type, user_id)
            
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Erreur génération prompt {prompt_type}: {e}")
            return self.base_prompts.get(prompt_type, "")
    
    async def _get_user_context(self, user_id: str) -> str:
        """Récupère le contexte utilisateur complet"""
        try:
            # Récupérer le profil comportemental
            behavior_profile = await self.db.user_behavior_profiles.find_one({'user_id': user_id})
            
            # Récupérer les préférences
            user_profile = await self.db.users.find_one({'id': user_id})
            
            # Récupérer l'historique d'onboarding
            onboarding = await self.db.onboarding_profiles.find_one({'user_id': user_id})
            
            context_parts = []
            
            if onboarding:
                context_parts.append(f"Objectif principal: {onboarding.get('objective', 'Non défini')}")
                context_parts.append(f"Domaine: {onboarding.get('domain', 'Non défini')}")
                context_parts.append(f"Niveau: {onboarding.get('current_level', 'Non défini')}")
            
            if behavior_profile:
                context_parts.append(f"Style de motivation: {behavior_profile.get('motivation_type', 'equilibré')}")
                context_parts.append(f"Tendance procrastination: {behavior_profile.get('procrastination_tendency', 'inconnue')}")
            
            return " | ".join(context_parts) if context_parts else "Contexte utilisateur en cours de construction"
            
        except Exception as e:
            logger.error(f"Erreur récupération contexte utilisateur: {e}")
            return "Contexte non disponible"
    
    async def _get_user_goals(self, user_id: str) -> str:
        """Récupère les objectifs actuels de l'utilisateur"""
        try:
            goals = await self.db.goals.find(
                {'user_id': user_id, 'status': 'active'}
            ).limit(5).to_list(length=5)
            
            if not goals:
                return "Aucun objectif actif défini"
            
            goals_text = []
            for goal in goals:
                goals_text.append(f"- {goal.get('title', 'Sans titre')}: {goal.get('description', '')}")
            
            return "\n".join(goals_text)
            
        except Exception as e:
            logger.error(f"Erreur récupération objectifs: {e}")
            return "Objectifs non disponibles"
    
    async def _log_prompt_usage(self, prompt_type: str, user_id: str):
        """Log l'utilisation des prompts pour analytics"""
        try:
            usage_log = {
                'prompt_type': prompt_type,
                'user_id': user_id,
                'timestamp': datetime.utcnow(),
                'usage_count': 1
            }
            
            await self.db.prompt_usage_logs.insert_one(usage_log)
            
        except Exception as e:
            logger.warning(f"Erreur log prompt usage: {e}")
    
    async def update_base_prompt(self, prompt_type: str, new_prompt: str, admin_id: str) -> bool:
        """Met à jour un prompt de base (admin seulement)"""
        try:
            # Sauvegarder l'ancien prompt
            backup = {
                'prompt_type': prompt_type,
                'old_prompt': self.base_prompts.get(prompt_type, ''),
                'new_prompt': new_prompt,
                'updated_by': admin_id,
                'updated_at': datetime.utcnow()
            }
            
            await self.db.prompt_backups.insert_one(backup)
            
            # Mettre à jour le prompt
            self.base_prompts[prompt_type] = new_prompt
            
            # Sauvegarder en base
            await self.db.system_prompts.replace_one(
                {'prompt_type': prompt_type},
                {
                    'prompt_type': prompt_type,
                    'prompt_content': new_prompt,
                    'updated_by': admin_id,
                    'updated_at': datetime.utcnow()
                },
                upsert=True
            )
            
            logger.info(f"Prompt {prompt_type} mis à jour par {admin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour prompt: {e}")
            return False
    
    async def get_prompt_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Récupère les analytics d'utilisation des prompts"""
        try:
            cutoff_date = datetime.utcnow().replace(
                day=datetime.utcnow().day - days
            )
            
            pipeline = [
                {'$match': {'timestamp': {'$gte': cutoff_date}}},
                {'$group': {
                    '_id': '$prompt_type',
                    'usage_count': {'$sum': '$usage_count'},
                    'unique_users': {'$addToSet': '$user_id'}
                }},
                {'$project': {
                    'prompt_type': '$_id',
                    'usage_count': 1,
                    'unique_users_count': {'$size': '$unique_users'}
                }}
            ]
            
            analytics = await self.db.prompt_usage_logs.aggregate(pipeline).to_list(length=None)
            
            return {
                'period_days': days,
                'prompt_analytics': analytics,
                'total_usage': sum(item['usage_count'] for item in analytics)
            }
            
        except Exception as e:
            logger.error(f"Erreur analytics prompts: {e}")
            return {}