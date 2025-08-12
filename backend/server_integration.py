"""
🔧 Intégration des corrections critiques dans server.py
Ce fichier montre comment intégrer les 4 corrections dans l'application AIM existante
"""

# IMPORTS SUPPLÉMENTAIRES À AJOUTER AU server.py ORIGINAL
from services.conversation_manager import ConversationManager  
from services.ai_prompt_system import AIPromptSystem
from services.task_extractor import TaskExtractor
from services.memory_system import MemorySystem

# INITIALISATION DES SERVICES (à ajouter après la connexion DB)
"""
# Ajouter après la ligne : db = client[os.environ['DB_NAME']]

# 🔧 INITIALISATION DES SERVICES DE CORRECTION CRITIQUES
conversation_manager = ConversationManager(db)
ai_prompt_system = AIPromptSystem(db) 
task_extractor = TaskExtractor(db, openai_client)
memory_system = MemorySystem(db, openai_client, embedding_model)

print("✅ Services de correction critiques initialisés")
"""

# ENDPOINTS MODIFIÉS/NOUVEAUX (remplacent ou complètent les existants)

@api_router.post("/chat/send")
async def send_chat_message_improved(
    message: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id)
):
    """
    🗣️ CORRECTION #1 : Endpoint de chat amélioré avec gestion des conversations
    """
    try:
        # 1. GESTION DES CONVERSATIONS AMÉLIORÉE
        if not conversation_id:
            # Créer une nouvelle conversation
            conversation = await conversation_manager.create_conversation(
                user_id=user_id,
                title=message[:50] + "..." if len(message) > 50 else message
            )
            conversation_id = conversation['id']
        else:
            # Vérifier que la conversation existe et appartient à l'utilisateur
            conversation = await conversation_manager.get_conversation_by_id(
                conversation_id, user_id
            )
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

        # 2. SYSTÈME DE MÉMOIRE CONVERSATIONNELLE AMÉLIORÉ
        # Récupérer le contexte conversationnel récent
        conversation_context = await memory_system.retrieve_relevant_memories(
            user_id=user_id,
            query=message,
            limit=5
        )

        # 3. SYSTÈME DE PROMPTS IA AMÉLIORÉ
        # Générer un prompt enrichi avec contexte
        enhanced_prompt = await ai_prompt_system.get_enhanced_prompt(
            prompt_type='coaching_base',
            user_id=user_id,
            conversation_history=str(conversation_context),
            user_message=message
        )

        # 4. GÉNÉRATION RÉPONSE IA avec prompt amélioré
        try:
            ai_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=500
            )
            response_text = ai_response.choices[0].message.content
        except Exception as ai_error:
            logger.error(f"Erreur OpenAI: {ai_error}")
            response_text = "Je rencontre actuellement des difficultés techniques. Pouvez-vous reformuler votre question ?"

        # 5. EXTRACTION DE TÂCHES AUTOMATIQUE
        task_extraction = await task_extractor.extract_tasks_from_message(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id,
            conversation_context=[{'content': msg.get('user_message', ''), 'is_user': True} for msg in conversation_context]
        )

        # Créer les tâches extraites automatiquement
        created_tasks = []
        if task_extraction['tasks_found'] and task_extraction['confidence_score'] > 0.6:
            for task_data in task_extraction['tasks_found']:
                # Trouver un goal associé ou créer un goal par défaut
                related_goal_id = task_data.get('related_goal_id')
                if not related_goal_id:
                    # Créer un goal par défaut si aucun n'existe
                    default_goals = await db.goals.find({'user_id': user_id, 'status': 'active'}).limit(1).to_list(1)
                    if default_goals:
                        related_goal_id = default_goals[0]['id']
                    else:
                        # Créer un goal par défaut
                        default_goal = Goal(
                            user_id=user_id,
                            title="Objectifs généraux",
                            description="Objectifs et tâches extraits automatiquement des conversations"
                        )
                        await db.goals.insert_one(default_goal.dict())
                        related_goal_id = default_goal.id

                # Créer la tâche
                new_task = TodoItem(
                    user_id=user_id,
                    goal_id=related_goal_id,
                    title=task_data['title'],
                    description=task_data['description'],
                    priority=task_data.get('priority', 'medium'),
                    source='ai_chat',
                    conversation_id=conversation_id,
                    deadline=datetime.strptime(task_data['estimated_date'], '%Y-%m-%d') if task_data.get('estimated_date') else None
                )
                
                await db.todos.insert_one(new_task.dict())
                created_tasks.append({
                    'id': new_task.id,
                    'title': new_task.title,
                    'priority': new_task.priority
                })

        # 6. STOCKAGE EN MÉMOIRE CONVERSATIONNELLE
        await memory_system.store_conversation_memory(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            response=response_text,
            message_type='user'
        )

        # 7. MISE À JOUR DES COMPTEURS DE CONVERSATION
        await conversation_manager.increment_message_count(conversation_id, user_id)

        # 8. SAUVEGARDER LE MESSAGE EN BASE
        chat_message = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message,
            response=response_text,
            web_search_used=False  # Pour compatibilité
        )
        await db.messages.insert_one(chat_message.dict())

        return {
            "success": True,
            "message": message,
            "response": response_text,
            "conversation_id": conversation_id,
            "tasks_extracted": created_tasks,
            "extraction_confidence": task_extraction.get('confidence_score', 0),
            "timestamp": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur chat amélioré: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@api_router.get("/conversations")
async def get_user_conversations_improved(
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_current_user_id)
):
    """
    🗣️ CORRECTION #1 : Récupération des conversations avec pagination et métadonnées
    """
    try:
        conversations = await conversation_manager.get_user_conversations(
            user_id=user_id,
            limit=limit
        )

        # Enrichir avec des métadonnées
        enriched_conversations = []
        for conv in conversations:
            # Récupérer le dernier message
            last_message = await db.messages.find_one(
                {'conversation_id': conv['id']},
                sort=[('timestamp', -1)]
            )

            conv_data = {
                **conv,
                'last_message_preview': last_message['message'][:100] + "..." if last_message and len(last_message['message']) > 100 else last_message['message'] if last_message else None,
                'last_message_timestamp': last_message['timestamp'] if last_message else None
            }
            enriched_conversations.append(conv_data)

        return {
            "conversations": enriched_conversations,
            "total": len(enriched_conversations),
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Erreur récupération conversations: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération conversations")


@api_router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages_improved(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id)
):
    """
    🗣️ CORRECTION #1 : Récupération des messages avec vérification de propriété
    """
    try:
        messages = await conversation_manager.get_conversation_messages(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=limit
        )

        return {
            "messages": messages,
            "conversation_id": conversation_id,
            "count": len(messages)
        }

    except Exception as e:
        logger.error(f"Erreur récupération messages: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération messages")


@api_router.get("/conversations/{conversation_id}/summary")
async def get_conversation_summary_improved(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    🧠 CORRECTION #4 : Génération de résumé intelligent de conversation
    """
    try:
        summary = await memory_system.get_conversation_summary(
            user_id=user_id,
            conversation_id=conversation_id,
            max_messages=20
        )

        return {
            "conversation_id": conversation_id,
            "summary": summary,
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Erreur génération résumé: {e}")
        raise HTTPException(status_code=500, detail="Erreur génération résumé")


@api_router.post("/admin/prompts/{prompt_type}")
async def update_system_prompt_improved(
    prompt_type: str,
    new_prompt: str = Form(...),
    admin_id: str = Depends(get_admin_user_id)  # Fonction à implémenter
):
    """
    🤖 CORRECTION #2 : Mise à jour des prompts système (admin)
    """
    try:
        success = await ai_prompt_system.update_base_prompt(
            prompt_type=prompt_type,
            new_prompt=new_prompt,
            admin_id=admin_id
        )

        if not success:
            raise HTTPException(status_code=400, detail="Échec mise à jour prompt")

        return {
            "success": True,
            "prompt_type": prompt_type,
            "updated_by": admin_id,
            "updated_at": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur mise à jour prompt: {e}")
        raise HTTPException(status_code=500, detail="Erreur mise à jour prompt")


# FONCTIONS UTILITAIRES SUPPLÉMENTAIRES
async def get_current_user_id(authorization: str = Header(None)) -> str:
    """Récupère l'ID utilisateur depuis le token d'autorisation"""
    user = require_authentication(authorization)
    return user['id']


async def get_admin_user_id(authorization: str = Header(None)) -> str:
    """Récupère l'ID admin depuis le token d'autorisation"""
    user = require_authentication(authorization)
    if not user.get('is_admin', False):
        raise HTTPException(status_code=403, detail="Accès admin requis")
    return user['id']


# INITIALISATION PÉRIODIQUE (à ajouter au startup)
async def initialize_corrections_startup():
    """Initialisation des corrections au démarrage"""
    try:
        # Vérifier que les collections existent
        collections_needed = [
            'conversations', 'conversation_memory', 'task_extractions_log',
            'prompt_usage_logs', 'system_prompts', 'user_behavior_profiles'
        ]
        
        existing_collections = await db.list_collection_names()
        
        for collection in collections_needed:
            if collection not in existing_collections:
                await db.create_collection(collection)
                logger.info(f"✅ Collection créée: {collection}")
        
        # Créer des index pour les performances
        await db.conversation_memory.create_index([("user_id", 1), ("timestamp", -1)])
        await db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
        await db.task_extractions_log.create_index([("user_id", 1), ("timestamp", -1)])
        
        logger.info("🚀 Corrections critiques initialisées avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur initialisation corrections: {e}")