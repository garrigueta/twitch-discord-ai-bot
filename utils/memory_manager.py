"""
Memory manager for the AI bot using vector database for semantic search.
"""
import os
import json
import logging
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple

# Import conditionally to handle potential missing dependencies
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    VECTOR_DB_AVAILABLE = True
except ImportError:
    VECTOR_DB_AVAILABLE = False

from config.config import (
    ENABLE_VECTOR_MEMORY,
    MEMORY_DATABASE_PATH,
    MEMORY_COLLECTION_CONVERSATIONS,
    MEMORY_COLLECTION_KNOWLEDGE,
    MEMORY_EMBEDDING_MODEL,
    MEMORY_SIMILARITY_THRESHOLD,
    MEMORY_MAX_RESULTS
)

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manager for AI memory using vector databases for semantic search."""
    
    def __init__(self):
        """Initialize the memory manager."""
        self.enabled = ENABLE_VECTOR_MEMORY and VECTOR_DB_AVAILABLE
        self.db_path = MEMORY_DATABASE_PATH
        self.embedding_model_name = MEMORY_EMBEDDING_MODEL
        self.similarity_threshold = MEMORY_SIMILARITY_THRESHOLD
        self.max_results = MEMORY_MAX_RESULTS
        
        if not self.enabled:
            if not VECTOR_DB_AVAILABLE:
                logger.warning("Vector database dependencies not available. Memory features disabled.")
                logger.warning("Install with: pip install chromadb sentence-transformers")
            else:
                logger.warning("Vector memory disabled in configuration.")
            return
            
        # Create data directory if it doesn't exist
        os.makedirs(self.db_path, exist_ok=True)
        
        try:
            # Initialize embedding model for vectorization
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            
            # Initialize Chroma client
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Initialize collections
            self._init_collections()
            
            logger.info(f"Memory manager initialized with model: {self.embedding_model_name}")
            logger.info(f"Using database path: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize memory manager: {e}")
            self.enabled = False
    
    def _init_collections(self):
        """Initialize the collections in the database."""
        try:
            # Collection for conversation history
            self.conversations = self.client.get_or_create_collection(
                name=MEMORY_COLLECTION_CONVERSATIONS,
                metadata={"description": "Conversation history from all platforms"}
            )
            
            # Collection for knowledge base
            self.knowledge = self.client.get_or_create_collection(
                name=MEMORY_COLLECTION_KNOWLEDGE,
                metadata={"description": "Knowledge base from files and curated content"}
            )
            
            logger.info(f"Collections initialized: {MEMORY_COLLECTION_CONVERSATIONS}, {MEMORY_COLLECTION_KNOWLEDGE}")
        except Exception as e:
            logger.error(f"Failed to initialize collections: {e}")
            self.enabled = False
    
    def _generate_id(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Generate a unique ID for a piece of content."""
        # Create a string combining content and metadata
        metadata_str = json.dumps(metadata, sort_keys=True) if metadata else ""
        combined = f"{content}|{metadata_str}"
        
        # Generate a hash
        return hashlib.md5(combined.encode()).hexdigest()
    
    def store_conversation(self, content: str, username: str, platform: str, 
                          channel_id: str, role: str = "user") -> bool:
        """
        Store a conversation message in the vector database.
        
        Args:
            content: The message content
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            role: 'user' or 'assistant'
            
        Returns:
            bool: Success or failure
        """
        if not self.enabled:
            return False
            
        try:
            # Create metadata
            metadata = {
                "username": username,
                "platform": platform,
                "channel_id": channel_id,
                "role": role,
                "timestamp": time.time()
            }
            
            # Generate a unique ID
            doc_id = self._generate_id(content, metadata)
            
            # Check if similar content already exists to avoid duplicates
            if not self._is_duplicate(content, MEMORY_COLLECTION_CONVERSATIONS):
                # Add to the database
                self.conversations.add(
                    documents=[content],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                logger.debug(f"Stored conversation: {doc_id[:8]}... from {username} on {platform}")
                return True
            else:
                logger.debug(f"Skipped duplicate conversation from {username}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
            return False
    
    def add_knowledge(self, content: str, source: str, 
                     category: str = "general", metadata: Dict[str, Any] = None) -> bool:
        """
        Add knowledge to the database.
        
        Args:
            content: The knowledge content
            source: The source of the knowledge (filename, user, etc.)
            category: Category for organizing knowledge
            metadata: Additional metadata
            
        Returns:
            bool: Success or failure
        """
        if not self.enabled:
            return False
            
        try:
            # Create metadata
            meta = {
                "source": source,
                "category": category,
                "timestamp": time.time()
            }
            
            # Add custom metadata if provided
            if metadata:
                meta.update(metadata)
                
            # Generate a unique ID
            doc_id = self._generate_id(content, meta)
            
            # Check if similar content already exists
            if not self._is_duplicate(content, MEMORY_COLLECTION_KNOWLEDGE):
                # Add to the database
                self.knowledge.add(
                    documents=[content],
                    metadatas=[meta],
                    ids=[doc_id]
                )
                logger.info(f"Added knowledge: {doc_id[:8]}... from {source}")
                return True
            else:
                logger.debug(f"Skipped duplicate knowledge from {source}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False
    
    def search_memory(self, query: str, collection_name: str = None, 
                    filter_metadata: Dict[str, Any] = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        Search the memory for relevant information.
        
        Args:
            query: The search query
            collection_name: Which collection to search (conversations, knowledge, or both)
            filter_metadata: Filter results by metadata
            limit: Maximum number of results
            
        Returns:
            List of relevant documents with their metadata
        """
        if not self.enabled:
            return []
            
        results = []
        max_results = limit or self.max_results
        
        try:
            # Determine which collections to search
            collections = []
            if collection_name == MEMORY_COLLECTION_CONVERSATIONS:
                collections = [self.conversations]
            elif collection_name == MEMORY_COLLECTION_KNOWLEDGE:
                collections = [self.knowledge]
            else:
                # Search both collections if none specified
                collections = [self.conversations, self.knowledge]
                
            # Search each collection
            for collection in collections:
                search_results = collection.query(
                    query_texts=[query],
                    n_results=max_results,
                    where=filter_metadata
                )
                
                # Process results
                if search_results and 'documents' in search_results and len(search_results['documents']) > 0:
                    docs = search_results['documents'][0]  # First query results
                    metadatas = search_results['metadatas'][0]
                    distances = search_results['distances'][0] if 'distances' in search_results else [1.0] * len(docs)
                    
                    # Filter by similarity threshold and format results
                    for doc, meta, dist in zip(docs, metadatas, distances):
                        # Convert distance to similarity (1.0 - distance)
                        similarity = 1.0 - dist if dist <= 1.0 else 0.0
                        
                        if similarity >= self.similarity_threshold:
                            results.append({
                                "content": doc,
                                "metadata": meta,
                                "similarity": similarity,
                                "collection": collection.name
                            })
            
            # Sort by similarity (highest first)
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limit results if needed
            if max_results and len(results) > max_results:
                results = results[:max_results]
                
            logger.debug(f"Found {len(results)} relevant results for query: {query[:30]}...")
            return results
            
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []
    
    def get_relevant_context(self, query: str, username: str = None, 
                           channel_id: str = None, platform: str = None) -> str:
        """
        Get relevant context from memory for a specific query.
        
        Args:
            query: The user's query
            username: The username (optional filter)
            channel_id: The channel ID (optional filter)
            platform: The platform (optional filter)
            
        Returns:
            Formatted context string with relevant information
        """
        if not self.enabled:
            return ""
            
        # Format filters correctly for ChromaDB
        # ChromaDB expects filters in the format {"$and": [{"field": value}, {"field": value}]}
        # or {"$or": [{"field": value}, {"field": value}]}
        filters = {"$and": []}
        
        if username:
            filters["$and"].append({"username": username})
        if channel_id:
            filters["$and"].append({"channel_id": channel_id})
        if platform:
            filters["$and"].append({"platform": platform})
            
        # If no filters, set to None
        if not filters["$and"]:
            filters = None
            
        # Get relevant conversations
        conv_results = self.search_memory(
            query=query, 
            collection_name=MEMORY_COLLECTION_CONVERSATIONS,
            filter_metadata=filters,
            limit=3  # Limit conversation history
        )
        
        # Get relevant knowledge
        knowledge_results = self.search_memory(
            query=query,
            collection_name=MEMORY_COLLECTION_KNOWLEDGE,
            limit=3  # Limit knowledge items
        )
        
        # Format results
        context_parts = []
        
        # Add knowledge context
        if knowledge_results:
            context_parts.append("### Información relevante:")
            for idx, item in enumerate(knowledge_results):
                source = item['metadata'].get('source', 'desconocido')
                context_parts.append(f"{idx+1}. {item['content']} (Fuente: {source})")
                
        # Add conversation context
        if conv_results:
            context_parts.append("\n### Conversación anterior relevante:")
            for idx, item in enumerate(conv_results):
                role = "Usuario" if item['metadata'].get('role') == 'user' else "Asistente"
                context_parts.append(f"{role}: {item['content']}")
                
        # Combine all context
        if context_parts:
            return "\n\n".join(context_parts)
        else:
            return ""
    
    def _is_duplicate(self, content: str, collection_name: str) -> bool:
        """
        Check if content is similar to existing content in the database.
        
        Args:
            content: The content to check
            collection_name: The collection to check against
            
        Returns:
            bool: True if a similar document exists
        """
        if not self.enabled:
            return False
            
        try:
            # Search for similar content
            collection = getattr(self, collection_name.lower(), None)
            if not collection:
                return False
                
            results = collection.query(
                query_texts=[content],
                n_results=1
            )
            
            # Check if any results have similarity above threshold
            if 'distances' in results and results['distances'] and results['distances'][0]:
                # Convert distance to similarity (1.0 - distance)
                similarity = 1.0 - results['distances'][0][0]
                return similarity >= self.similarity_threshold
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            return False
    
    def import_knowledge_from_file(self, file_path: str, category: str = "general",
                                 chunk_size: int = 500, overlap: int = 50) -> Tuple[int, int]:
        """
        Import knowledge from a file into the vector database.
        
        Args:
            file_path: Path to the file
            category: Category for the knowledge
            chunk_size: Size of text chunks to split content
            overlap: Overlap between chunks
            
        Returns:
            Tuple of (success_count, total_chunks)
        """
        if not self.enabled or not os.path.exists(file_path):
            return (0, 0)
            
        try:
            # Get file name as source
            file_name = os.path.basename(file_path)
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Split into chunks with overlap for context preservation
            chunks = self._split_text(content, chunk_size, overlap)
            
            # Add each chunk to the knowledge base
            success_count = 0
            for i, chunk in enumerate(chunks):
                metadata = {
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_name": file_name
                }
                
                if self.add_knowledge(chunk, source=file_name, category=category, metadata=metadata):
                    success_count += 1
                    
            logger.info(f"Imported {success_count}/{len(chunks)} chunks from {file_name}")
            return (success_count, len(chunks))
            
        except Exception as e:
            logger.error(f"Failed to import knowledge from file {file_path}: {e}")
            return (0, 0)
    
    def _split_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks for better context preservation.
        
        Args:
            text: The text to split
            chunk_size: Maximum size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        # If text is smaller than chunk size, return as is
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        
        while start < len(text):
            # Get the chunk
            end = min(start + chunk_size, len(text))
            
            # Adjust for sentence boundaries if possible
            if end < len(text):
                # Try to end at a sentence boundary
                for boundary in ['. ', '! ', '? ', '\n']:
                    pos = text[start:end].rfind(boundary)
                    if pos > chunk_size // 2:  # Only adjust if we're far enough in
                        end = start + pos + len(boundary)
                        break
            
            # Add the chunk
            chunks.append(text[start:end])
            
            # Move start position, accounting for overlap
            start = end - overlap if end - overlap > start else end
            
        return chunks
    
    def import_discord_history(self, messages: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Import Discord message history.
        
        Args:
            messages: List of Discord messages with author, content, etc.
            
        Returns:
            Tuple of (success_count, total_messages)
        """
        if not self.enabled:
            return (0, 0)
            
        success_count = 0
        total_messages = len(messages)
        
        for msg in messages:
            if not msg.get('content'):
                continue
                
            username = msg.get('author', {}).get('name', 'unknown')
            channel_id = str(msg.get('channel_id', '0'))
            
            # Store as conversation
            if self.store_conversation(
                content=msg['content'],
                username=username,
                platform='discord',
                channel_id=channel_id,
                role='user'
            ):
                success_count += 1
                
        logger.info(f"Imported {success_count}/{total_messages} Discord messages")
        return (success_count, total_messages)