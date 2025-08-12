"""
✅ Extracteur de tâches intelligent - CORRECTION CRITIQUE #3
Corrige l'extraction automatique des tâches depuis les conversations
"""
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from datetime import datetime, timedelta
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
import openai
from openai import OpenAI

logger = logging.getLogger(__name__)

class TaskExtractor:
    """Extracteur intelligent de tâches depuis les conversations"""
    
    def __init__(self, db: AsyncIOMotorDatabase, openai_client: OpenAI):
        self.db = db
        self.openai_client = openai_client
        self.task_patterns = self._init_task_patterns()
        
    def _init_task_patterns(self) -> Dict[str, Any]:
        """Initialise les patterns de détection de tâches"""
        return {
            'action_verbs': [
                'faire', 'créer', 'développer', 'apprendre', 'étudier', 'lire', 'écrire',
                'planifier', 'organiser', 'préparer', 'rechercher', 'analyser', 'contacter',
                'appeler', 'envoyer', 'acheter', 'vendre', 'terminer', 'finir', 'commencer',
                'démarrer', 'installer', 'configurer', 'tester', 'vérifier', 'réviser'
            ],
            'time_indicators': [
                'aujourd\'hui', 'demain', 'cette semaine', 'la semaine prochaine',
                'ce mois', 'le mois prochain', 'avant', 'après', 'dans', 'd\'ici',
                'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'
            ],
            'priority_indicators': {
                'haute': ['urgent', 'important', 'priorité', 'critique', 'immédiat', 'crucial'],
                'moyenne': ['normal', 'standard', 'moyen', 'régulier'],
                'basse': ['quand possible', 'si temps', 'optionnel', 'bonus', 'plus tard']
            }
        }
    
    async def extract_tasks_from_message(self, 
                                       message: str, 
                                       user_id: str,
                                       conversation_id: str,
                                       conversation_context: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extrait les tâches d'un message utilisateur"""
        try:
            # Méthode hybride : règles + IA
            rule_based_tasks = self._extract_by_rules(message)
            ai_based_tasks = await self._extract_by_ai(message, conversation_context or [])
            
            # Fusionner et déduplicater
            merged_tasks = self._merge_task_extractions(rule_based_tasks, ai_based_tasks)
            
            # Enrichir avec le contexte utilisateur
            enriched_tasks = await self._enrich_tasks_with_context(merged_tasks, user_id)
            
            # Sauvegarder l'extraction pour analytics
            await self._log_extraction(user_id, conversation_id, message, enriched_tasks)
            
            return {
                'tasks_found': enriched_tasks,
                'extraction_method': 'hybrid',
                'confidence_score': self._calculate_confidence(enriched_tasks),
                'processed_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Erreur extraction tâches: {e}")
            return {
                'tasks_found': [],
                'extraction_method': 'error',
                'confidence_score': 0.0,
                'error': str(e)
            }
    
    def _extract_by_rules(self, message: str) -> List[Dict[str, Any]]:
        """Extraction basée sur des règles linguistiques"""
        tasks = []
        
        try:
            # Nettoyer le message
            message_clean = message.lower().strip()
            sentences = re.split(r'[.!?]', message_clean)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 5:  # Ignorer les phrases trop courtes
                    continue
                
                # Détecter les verbes d'action
                action_found = None
                for verb in self.task_patterns['action_verbs']:
                    if verb in sentence:
                        action_found = verb
                        break
                
                if not action_found:
                    continue
                
                # Extraire la tâche potentielle
                task = self._parse_task_from_sentence(sentence, action_found)
                if task:
                    tasks.append(task)
            
            return tasks
            
        except Exception as e:
            logger.error(f"Erreur extraction par règles: {e}")
            return []
    
    def _parse_task_from_sentence(self, sentence: str, action_verb: str) -> Optional[Dict[str, Any]]:
        """Parse une tâche depuis une phrase"""
        try:
            # Titre de la tâche (simplifiée)
            title = sentence.replace(action_verb, '').strip()
            title = re.sub(r'^(je vais|je dois|il faut|je veux)', '', title).strip()
            
            if len(title) < 3:
                return None
            
            # Détecter la priorité
            priority = 'moyenne'
            for prio, indicators in self.task_patterns['priority_indicators'].items():
                if any(indicator in sentence for indicator in indicators):
                    priority = prio
                    break
            
            # Détecter les indicateurs temporels
            estimated_date = self._extract_date_from_sentence(sentence)
            
            return {
                'title': title.capitalize(),
                'description': sentence,
                'priority': priority,
                'estimated_date': estimated_date,
                'extraction_method': 'rules',
                'confidence': 0.7
            }
            
        except Exception as e:
            logger.error(f"Erreur parsing tâche: {e}")
            return None
    
    def _extract_date_from_sentence(self, sentence: str) -> Optional[str]:
        """Extrait une date approximative depuis une phrase"""
        try:
            today = datetime.now()
            
            # Patterns temporels simples
            if 'aujourd\'hui' in sentence:
                return today.strftime('%Y-%m-%d')
            elif 'demain' in sentence:
                return (today + timedelta(days=1)).strftime('%Y-%m-%d')
            elif 'cette semaine' in sentence:
                return (today + timedelta(days=3)).strftime('%Y-%m-%d')
            elif 'la semaine prochaine' in sentence:
                return (today + timedelta(days=7)).strftime('%Y-%m-%d')
            elif 'ce mois' in sentence:
                return (today + timedelta(days=15)).strftime('%Y-%m-%d')
            
            # Patterns de jours de la semaine
            days_map = {
                'lundi': 0, 'mardi': 1, 'mercredi': 2, 'jeudi': 3,
                'vendredi': 4, 'samedi': 5, 'dimanche': 6
            }
            
            for day_name, day_num in days_map.items():
                if day_name in sentence:
                    days_ahead = day_num - today.weekday()
                    if days_ahead <= 0:  # Le jour est déjà passé cette semaine
                        days_ahead += 7
                    return (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur extraction date: {e}")
            return None
    
    async def _extract_by_ai(self, message: str, conversation_context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extraction via IA (GPT)"""
        try:
            # Construire le contexte de conversation
            context_text = ""
            if conversation_context:
                recent_messages = conversation_context[-5:]  # Derniers 5 messages
                context_text = "\n".join([
                    f"{'Utilisateur' if msg.get('is_user') else 'Assistant'}: {msg.get('content', '')}"
                    for msg in recent_messages
                ])
            
            # Prompt pour l'extraction de tâches
            prompt = f"""Analyse le message suivant et identifie toutes les tâches, actions ou objectifs mentionnés.

Message à analyser : "{message}"

Contexte de conversation récent :
{context_text}

Instructions :
1. Identifie chaque tâche/action concrète
2. Ignore les questions ou commentaires généraux
3. Estime une priorité (haute/moyenne/basse)
4. Propose une date d'échéance si des indices temporels existent

Réponds uniquement en JSON valide :
{{
    "tasks": [
        {{
            "title": "titre court de la tâche",
            "description": "description plus détaillée",
            "priority": "haute|moyenne|basse",
            "estimated_date": "YYYY-MM-DD ou null",
            "confidence": 0.85
        }}
    ]
}}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parser la réponse JSON
            try:
                parsed = json.loads(result)
                tasks = parsed.get('tasks', [])
                
                # Ajouter metadata
                for task in tasks:
                    task['extraction_method'] = 'ai'
                
                return tasks
                
            except json.JSONDecodeError:
                logger.warning(f"Réponse IA non-JSON: {result}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur extraction IA: {e}")
            return []
    
    def _merge_task_extractions(self, rule_tasks: List[Dict[str, Any]], ai_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fusionne les résultats d'extraction par règles et IA"""
        try:
            merged = []
            
            # Ajouter les tâches IA (généralement de meilleure qualité)
            for task in ai_tasks:
                merged.append(task)
            
            # Ajouter les tâches par règles si elles ne sont pas déjà présentes
            for rule_task in rule_tasks:
                is_duplicate = False
                for merged_task in merged:
                    # Détection de doublons basique par similarité de titre
                    if self._are_tasks_similar(rule_task['title'], merged_task['title']):
                        is_duplicate = True
                        # Enrichir avec les données des règles si nécessaire
                        if not merged_task.get('estimated_date') and rule_task.get('estimated_date'):
                            merged_task['estimated_date'] = rule_task['estimated_date']
                        break
                
                if not is_duplicate:
                    merged.append(rule_task)
            
            return merged
            
        except Exception as e:
            logger.error(f"Erreur fusion extractions: {e}")
            return rule_tasks + ai_tasks  # Fallback simple
    
    def _are_tasks_similar(self, title1: str, title2: str) -> bool:
        """Détecte si deux titres de tâches sont similaires"""
        try:
            # Normalisation simple
            t1 = set(title1.lower().split())
            t2 = set(title2.lower().split())
            
            # Intersection > 50% des mots
            if len(t1) == 0 or len(t2) == 0:
                return False
            
            intersection = len(t1.intersection(t2))
            union = len(t1.union(t2))
            
            return (intersection / union) > 0.5
            
        except Exception as e:
            logger.error(f"Erreur comparaison tâches: {e}")
            return False
    
    async def _enrich_tasks_with_context(self, tasks: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """Enrichit les tâches avec le contexte utilisateur"""
        try:
            # Récupérer les objectifs utilisateur
            user_goals = await self.db.goals.find(
                {'user_id': user_id, 'status': 'active'}
            ).to_list(length=10)
            
            # Récupérer le profil utilisateur
            user_profile = await self.db.onboarding_profiles.find_one({'user_id': user_id})
            
            enriched_tasks = []
            
            for task in tasks:
                # Associer à un objectif si pertinent
                related_goal = self._find_related_goal(task, user_goals)
                if related_goal:
                    task['related_goal_id'] = related_goal['id']
                    task['related_goal_title'] = related_goal['title']
                
                # Catégoriser selon le domaine utilisateur
                if user_profile:
                    task['category'] = user_profile.get('domain', 'général')
                
                # Ajuster la priorité selon le profil comportemental
                task = await self._adjust_priority_by_profile(task, user_id)
                
                enriched_tasks.append(task)
            
            return enriched_tasks
            
        except Exception as e:
            logger.error(f"Erreur enrichissement tâches: {e}")
            return tasks
    
    def _find_related_goal(self, task: Dict[str, Any], user_goals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Trouve l'objectif le plus pertinent pour une tâche"""
        try:
            task_words = set(task['title'].lower().split())
            task_desc_words = set(task.get('description', '').lower().split())
            all_task_words = task_words.union(task_desc_words)
            
            best_match = None
            best_score = 0
            
            for goal in user_goals:
                goal_words = set(goal['title'].lower().split())
                goal_desc_words = set(goal.get('description', '').lower().split())
                all_goal_words = goal_words.union(goal_desc_words)
                
                # Calculer la similarité
                intersection = len(all_task_words.intersection(all_goal_words))
                union = len(all_task_words.union(all_goal_words))
                
                if union > 0:
                    score = intersection / union
                    if score > best_score and score > 0.3:  # Seuil minimum
                        best_score = score
                        best_match = goal
            
            return best_match
            
        except Exception as e:
            logger.error(f"Erreur association objectif: {e}")
            return None
    
    async def _adjust_priority_by_profile(self, task: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Ajuste la priorité selon le profil comportemental"""
        try:
            behavior_profile = await self.db.user_behavior_profiles.find_one({'user_id': user_id})
            
            if not behavior_profile:
                return task
            
            # Ajustement selon la tendance procrastination
            procrastination = behavior_profile.get('procrastination_tendency', 'medium')
            
            if procrastination == 'high':
                # Augmenter la priorité pour les procrastinateurs
                if task['priority'] == 'basse':
                    task['priority'] = 'moyenne'
                elif task['priority'] == 'moyenne':
                    task['priority'] = 'haute'
            
            return task
            
        except Exception as e:
            logger.error(f"Erreur ajustement priorité: {e}")
            return task
    
    def _calculate_confidence(self, tasks: List[Dict[str, Any]]) -> float:
        """Calcule un score de confiance global pour l'extraction"""
        try:
            if not tasks:
                return 0.0
            
            total_confidence = sum(task.get('confidence', 0.5) for task in tasks)
            return min(total_confidence / len(tasks), 1.0)
            
        except Exception as e:
            logger.error(f"Erreur calcul confiance: {e}")
            return 0.5
    
    async def _log_extraction(self, user_id: str, conversation_id: str, message: str, tasks: List[Dict[str, Any]]):
        """Log l'extraction pour analytics et amélioration"""
        try:
            log_entry = {
                'user_id': user_id,
                'conversation_id': conversation_id,
                'original_message': message,
                'tasks_extracted': len(tasks),
                'extraction_confidence': self._calculate_confidence(tasks),
                'timestamp': datetime.utcnow(),
                'tasks_details': tasks
            }
            
            await self.db.task_extractions_log.insert_one(log_entry)
            
        except Exception as e:
            logger.warning(f"Erreur log extraction: {e}")
    
    async def get_extraction_analytics(self, user_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Récupère les analytics d'extraction de tâches"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            match_filter = {'timestamp': {'$gte': cutoff_date}}
            if user_id:
                match_filter['user_id'] = user_id
            
            pipeline = [
                {'$match': match_filter},
                {'$group': {
                    '_id': None,
                    'total_extractions': {'$sum': 1},
                    'total_tasks_found': {'$sum': '$tasks_extracted'},
                    'avg_confidence': {'$avg': '$extraction_confidence'},
                    'unique_users': {'$addToSet': '$user_id'}
                }}
            ]
            
            result = await self.db.task_extractions_log.aggregate(pipeline).to_list(length=1)
            
            if result:
                stats = result[0]
                stats['unique_users_count'] = len(stats['unique_users'])
                del stats['unique_users']
                return stats
            
            return {
                'total_extractions': 0,
                'total_tasks_found': 0,
                'avg_confidence': 0.0,
                'unique_users_count': 0
            }
            
        except Exception as e:
            logger.error(f"Erreur analytics extraction: {e}")
            return {}