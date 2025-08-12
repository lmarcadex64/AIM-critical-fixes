"""
🧠 Système de mémoire conversationnelle intelligent - CORRECTION CRITIQUE #4
Corrige la persistance et l'utilisation de la mémoire conversationnelle
"""
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime, timedelta
import logging
import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import openai
from openai import OpenAI

logger = logging.getLogger(__name__)

class MemorySystem:
    """Système de mémoire conversationnelle avancé avec embeddings et synthèse"""
    
    def __init__(self, db: AsyncIOMotorDatabase, openai_client: OpenAI, embedding_model: SentenceTransformer):
        self.db = db
        self.openai_client = openai_client
        self.embedding_model = embedding_model
        
    async def store_conversation_memory(self, 
                                     user_id: str, 
                                     conversation_id: str,
                                     message: str,
                                     response: str,
                                     message_type: str = 'user') -> bool:
        """Stocke un échange conversationnel en mémoire avec embeddings"""
        try:
            # Créer l'embedding du message et de la réponse
            combined_text = f"{message} {response}"
            embedding = self.embedding_model.encode(combined_text).tolist()
            
            # Créer l'entrée mémoire
            memory_entry = {
                'id': f"{conversation_id}_{datetime.utcnow().timestamp()}",
                'user_id': user_id,
                'conversation_id': conversation_id,
                'user_message': message,
                'ai_response': response,
                'message_type': message_type,
                'embedding': embedding,
                'timestamp': datetime.utcnow(),
                'importance_score': self._calculate_importance_score(message, response),
                'topics_mentioned': await self._extract_topics(combined_text),
                'emotions_detected': self._detect_emotions(message),
                'metadata': {}
            }
            
            # Stocker en base
            await self.db.conversation_memory.insert_one(memory_entry)
            
            # Déclencher la synthèse périodique si nécessaire
            await self._trigger_memory_synthesis(user_id)
            
            logger.info(f"Mémoire conversationnelle stockée pour {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur stockage mémoire: {e}")
            return False
    
    async def retrieve_relevant_memories(self, 
                                       user_id: str, 
                                       query: str, 
                                       limit: int = 5,
                                       min_similarity: float = 0.3) -> List[Dict[str, Any]]:
        """Récupère les souvenirs les plus pertinents pour une requête"""
        try:
            # Créer l'embedding de la requête
            query_embedding = self.embedding_model.encode(query)
            
            # Récupérer toutes les mémoires de l'utilisateur (avec pagination future)
            memories = await self.db.conversation_memory.find(
                {'user_id': user_id}
            ).sort('timestamp', -1).limit(50).to_list(length=50)
            
            if not memories:
                return []
            
            # Calculer les similarités
            relevant_memories = []
            
            for memory in memories:
                if 'embedding' not in memory:
                    continue
                
                memory_embedding = np.array(memory['embedding'])
                similarity = cosine_similarity(
                    [query_embedding], 
                    [memory_embedding]
                )[0][0]
                
                if similarity >= min_similarity:
                    memory['similarity_score'] = float(similarity)
                    relevant_memories.append(memory)
            
            # Trier par pertinence et importance
            relevant_memories.sort(
                key=lambda x: (x['similarity_score'] * 0.7 + x.get('importance_score', 0.5) * 0.3),
                reverse=True
            )
            
            return relevant_memories[:limit]
            
        except Exception as e:
            logger.error(f"Erreur récupération mémoires: {e}")
            return []
    
    async def get_conversation_summary(self, 
                                    user_id: str, 
                                    conversation_id: str, 
                                    max_messages: int = 20) -> Dict[str, Any]:
        """Génère un résumé intelligent d'une conversation"""
        try:
            # Récupérer les messages de la conversation
            memories = await self.db.conversation_memory.find(
                {
                    'user_id': user_id,
                    'conversation_id': conversation_id
                }
            ).sort('timestamp', 1).limit(max_messages).to_list(length=max_messages)
            
            if not memories:
                return {'summary': 'Aucun historique disponible', 'key_points': []}
            
            # Construire le contexte pour l'IA
            conversation_text = []
            for memory in memories:
                conversation_text.append(f"Utilisateur: {memory['user_message']}")
                conversation_text.append(f"Assistant: {memory['ai_response']}")
            
            context = "\n".join(conversation_text[-20:])  # Derniers 20 échanges
            
            # Générer le résumé via IA
            summary_prompt = f"""Analyse cette conversation et génère un résumé structuré :

{context}

Instructions :
1. Résume les points clés de la conversation
2. Identifie les objectifs ou intentions de l'utilisateur
3. Note les progrès ou difficultés mentionnés
4. Liste les décisions ou engagements pris

Réponds en JSON :
{{
    "summary": "résumé en 2-3 phrases",
    "key_points": ["point1", "point2", "point3"],
    "user_objectives": ["objectif1", "objectif2"],
    "commitments": ["engagement1", "engagement2"],
    "next_actions": ["action1", "action2"]
}}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.3,
                max_tokens=400
            )
            
            try:
                summary_data = json.loads(response.choices[0].message.content.strip())
                
                # Enrichir avec metadata
                summary_data['message_count'] = len(memories)
                summary_data['time_span'] = self._calculate_time_span(memories)
                summary_data['generated_at'] = datetime.utcnow()
                
                return summary_data
                
            except json.JSONDecodeError:
                # Fallback si JSON invalide
                return {
                    'summary': response.choices[0].message.content.strip(),
                    'key_points': [],
                    'message_count': len(memories)
                }
            
        except Exception as e:
            logger.error(f"Erreur génération résumé: {e}")
            return {'summary': 'Erreur génération résumé', 'key_points': []}
    
    async def update_user_profile_from_memory(self, user_id: str) -> Dict[str, Any]:
        """Met à jour le profil utilisateur basé sur l'analyse de la mémoire"""
        try:
            # Récupérer les mémoires récentes (30 derniers jours)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            recent_memories = await self.db.conversation_memory.find(
                {
                    'user_id': user_id,
                    'timestamp': {'$gte': cutoff_date}
                }
            ).sort('timestamp', -1).limit(100).to_list(length=100)
            
            if not recent_memories:
                return {'updated': False, 'reason': 'no_recent_memories'}
            
            # Analyser les patterns
            analysis = await self._analyze_memory_patterns(recent_memories)
            
            # Mettre à jour le profil comportemental
            behavior_update = {
                'communication_patterns': analysis['communication_style'],
                'recurring_topics': analysis['frequent_topics'],
                'goal_evolution': analysis['goal_changes'],
                'response_preferences': analysis['preferred_responses'],
                'activity_patterns': analysis['activity_timing'],
                'last_memory_analysis': datetime.utcnow()
            }
            
            # Sauvegarder les updates
            await self.db.user_behavior_profiles.update_one(
                {'user_id': user_id},
                {
                    '$set': behavior_update,
                    '$inc': {'memory_analysis_count': 1}
                },
                upsert=True
            )
            
            return {
                'updated': True,
                'analysis_summary': analysis,
                'memories_analyzed': len(recent_memories)
            }
            
        except Exception as e:
            logger.error(f"Erreur mise à jour profil mémoire: {e}")
            return {'updated': False, 'error': str(e)}
    
    async def _analyze_memory_patterns(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse les patterns dans les mémoires conversationnelles"""
        try:
            # Extraire les topics fréquents
            all_topics = []
            all_emotions = []
            response_lengths = []
            time_patterns = []
            
            for memory in memories:
                all_topics.extend(memory.get('topics_mentioned', []))
                all_emotions.extend(memory.get('emotions_detected', []))
                response_lengths.append(len(memory.get('ai_response', '')))
                time_patterns.append(memory['timestamp'].hour)
            
            # Analyser les patterns
            frequent_topics = self._get_frequent_items(all_topics, min_count=3)
            dominant_emotions = self._get_frequent_items(all_emotions, min_count=2)
            avg_response_length = np.mean(response_lengths) if response_lengths else 0
            most_active_hours = self._get_frequent_items(time_patterns, min_count=2)
            
            return {
                'frequent_topics': frequent_topics,
                'dominant_emotions': dominant_emotions,
                'communication_style': {
                    'prefers_detailed_responses': avg_response_length > 200,
                    'most_active_hours': most_active_hours
                },
                'goal_changes': await self._detect_goal_evolution(memories),
                'preferred_responses': self._analyze_response_preferences(memories),
                'activity_timing': {
                    'most_active_hours': most_active_hours,
                    'total_interactions': len(memories)
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur analyse patterns: {e}")
            return {}
    
    def _get_frequent_items(self, items: List[Any], min_count: int = 2) -> List[Tuple[Any, int]]:
        """Récupère les éléments les plus fréquents"""
        try:
            from collections import Counter
            counter = Counter(items)
            return [(item, count) for item, count in counter.most_common(10) if count >= min_count]
        except Exception:
            return []
    
    async def _detect_goal_evolution(self, memories: List[Dict[str, Any]]) -> List[str]:
        """Détecte l'évolution des objectifs dans les mémoires"""
        try:
            # Simple détection par mots-clés pour maintenant
            goal_keywords = ['objectif', 'goal', 'veux', 'souhaite', 'planifie', 'projet']
            goal_mentions = []
            
            for memory in memories:
                text = f"{memory.get('user_message', '')} {memory.get('ai_response', '')}"
                if any(keyword in text.lower() for keyword in goal_keywords):
                    goal_mentions.append(text[:100])  # Premier 100 caractères
            
            return goal_mentions[-5:]  # Dernières 5 mentions
            
        except Exception as e:
            logger.error(f"Erreur détection évolution objectifs: {e}")
            return []
    
    def _analyze_response_preferences(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse les préférences de réponse de l'utilisateur"""
        try:
            # Analyser la longueur des réponses appréciées
            positive_indicators = ['merci', 'parfait', 'excellent', 'super', 'génial']
            negative_indicators = ['trop long', 'compliqué', 'pas clair']
            
            positive_response_lengths = []
            negative_response_lengths = []
            
            for memory in memories:
                user_message = memory.get('user_message', '').lower()
                response_length = len(memory.get('ai_response', ''))
                
                if any(indicator in user_message for indicator in positive_indicators):
                    positive_response_lengths.append(response_length)
                elif any(indicator in user_message for indicator in negative_indicators):
                    negative_response_lengths.append(response_length)
            
            preferences = {}
            if positive_response_lengths:
                preferences['preferred_response_length'] = np.mean(positive_response_lengths)
            if negative_response_lengths:
                preferences['disliked_response_length'] = np.mean(negative_response_lengths)
            
            return preferences
            
        except Exception as e:
            logger.error(f"Erreur analyse préférences: {e}")
            return {}
    
    def _calculate_importance_score(self, message: str, response: str) -> float:
        """Calcule un score d'importance pour une interaction"""
        try:
            importance_keywords = [
                'important', 'urgent', 'objectif', 'goal', 'décision', 'problème',
                'solution', 'projet', 'plan', 'échéance', 'deadline'
            ]
            
            combined_text = f"{message} {response}".lower()
            keyword_matches = sum(1 for keyword in importance_keywords if keyword in combined_text)
            
            # Score basé sur les mots-clés et la longueur
            base_score = min(keyword_matches * 0.2, 0.8)
            length_bonus = min(len(combined_text) / 1000, 0.2)  # Bonus pour les interactions longues
            
            return min(base_score + length_bonus, 1.0)
            
        except Exception:
            return 0.5  # Score par défaut
    
    async def _extract_topics(self, text: str) -> List[str]:
        """Extrait les topics/sujets principaux d'un texte"""
        try:
            # Topics basiques par mots-clés (peut être enrichi avec NLP avancé)
            topic_keywords = {
                'business': ['business', 'entreprise', 'startup', 'marketing', 'vente'],
                'développement_personnel': ['développement', 'croissance', 'habitude', 'mindset'],
                'santé': ['santé', 'sport', 'nutrition', 'fitness', 'bien-être'],
                'éducation': ['apprendre', 'étudier', 'formation', 'compétence', 'cours'],
                'technologie': ['tech', 'programmation', 'code', 'développement', 'app'],
                'créativité': ['créatif', 'art', 'design', 'écriture', 'musique'],
                'finances': ['argent', 'budget', 'investissement', 'épargne', 'finance']
            }
            
            detected_topics = []
            text_lower = text.lower()
            
            for topic, keywords in topic_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    detected_topics.append(topic)
            
            return detected_topics
            
        except Exception:
            return []
    
    def _detect_emotions(self, text: str) -> List[str]:
        """Détecte les émotions dans un message (basique)"""
        try:
            emotion_keywords = {
                'positif': ['heureux', 'content', 'motivé', 'enthousiaste', 'super', 'génial'],
                'négatif': ['triste', 'déçu', 'frustré', 'difficile', 'problème', 'inquiet'],
                'neutre': ['normal', 'ok', 'bien', 'standard'],
                'déterminé': ['déterminé', 'motivé', 'prêt', 'go', 'action', 'objectif']
            }
            
            detected_emotions = []
            text_lower = text.lower()
            
            for emotion, keywords in emotion_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    detected_emotions.append(emotion)
            
            return detected_emotions if detected_emotions else ['neutre']
            
        except Exception:
            return ['neutre']
    
    def _calculate_time_span(self, memories: List[Dict[str, Any]]) -> str:
        """Calcule la durée d'une conversation"""
        try:
            if len(memories) < 2:
                return "conversation unique"
            
            start_time = min(memory['timestamp'] for memory in memories)
            end_time = max(memory['timestamp'] for memory in memories)
            
            duration = end_time - start_time
            
            if duration.days > 0:
                return f"{duration.days} jour(s)"
            elif duration.seconds > 3600:
                return f"{duration.seconds // 3600} heure(s)"
            else:
                return f"{duration.seconds // 60} minute(s)"
                
        except Exception:
            return "durée inconnue"
    
    async def _trigger_memory_synthesis(self, user_id: str):
        """Déclenche la synthèse mémoire si nécessaire"""
        try:
            # Vérifier si une synthèse est nécessaire (tous les 50 messages par exemple)
            message_count = await self.db.conversation_memory.count_documents(
                {'user_id': user_id}
            )
            
            if message_count > 0 and message_count % 50 == 0:
                # Déclencher la mise à jour du profil
                await self.update_user_profile_from_memory(user_id)
                logger.info(f"Synthèse mémoire déclenchée pour {user_id} à {message_count} messages")
                
        except Exception as e:
            logger.error(f"Erreur déclenchement synthèse: {e}")
    
    async def get_memory_analytics(self, user_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Récupère les analytics du système de mémoire"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            match_filter = {'timestamp': {'$gte': cutoff_date}}
            if user_id:
                match_filter['user_id'] = user_id
            
            pipeline = [
                {'$match': match_filter},
                {'$group': {
                    '_id': None,
                    'total_memories': {'$sum': 1},
                    'avg_importance': {'$avg': '$importance_score'},
                    'unique_users': {'$addToSet': '$user_id'},
                    'unique_conversations': {'$addToSet': '$conversation_id'}
                }}
            ]
            
            result = await self.db.conversation_memory.aggregate(pipeline).to_list(length=1)
            
            if result:
                stats = result[0]
                stats['unique_users_count'] = len(stats['unique_users'])
                stats['unique_conversations_count'] = len(stats['unique_conversations'])
                del stats['unique_users']
                del stats['unique_conversations']
                return stats
            
            return {
                'total_memories': 0,
                'avg_importance': 0.0,
                'unique_users_count': 0,
                'unique_conversations_count': 0
            }
            
        except Exception as e:
            logger.error(f"Erreur analytics mémoire: {e}")
            return {}
    
    async def cleanup_old_memories(self, days_to_keep: int = 90) -> int:
        """Nettoie les anciennes mémoires peu importantes"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Garder les mémoires importantes même anciennes
            result = await self.db.conversation_memory.delete_many(
                {
                    'timestamp': {'$lt': cutoff_date},
                    'importance_score': {'$lt': 0.7}  # Garder les mémoires importantes
                }
            )
            
            logger.info(f"Nettoyage mémoire: {result.deleted_count} entrées supprimées")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Erreur nettoyage mémoire: {e}")
            return 0