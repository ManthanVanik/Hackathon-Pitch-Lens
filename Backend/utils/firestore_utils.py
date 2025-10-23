from google.cloud import firestore
from typing import Dict, List, Any, Optional
import logging
from config.settings import settings
from utils.cache_utils import extract_cached_memo

logger = logging.getLogger(__name__)

class FirestoreManager:
    def __init__(self):
        self.db = firestore.Client()
        self.collection_name = "deals"
        self.cache_collection_name = "deck_cache"

    async def create_deal(self, deal_id: str, data: Dict[str, Any]) -> bool:
        """Create new deal document"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(deal_id)
            doc_ref.set({"metadata": data})
            logger.info(f"Created deal document: {deal_id}")
            return True

        except Exception as e:
            logger.error(f"Firestore create error: {str(e)}")
            return False

    async def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get deal document by ID"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(deal_id)
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            else:
                logger.warning(f"Deal not found: {deal_id}")
                return None

        except Exception as e:
            logger.error(f"Firestore get error: {str(e)}")
            return None

    async def update_deal(self, deal_id: str, updates: Dict[str, Any]) -> bool:
        """Update deal document"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(deal_id)

            # Handle nested updates (e.g., "metadata.status")
            formatted_updates = {}
            for key, value in updates.items():
                if '.' in key:
                    # Nested field update
                    formatted_updates[key] = value
                else:
                    formatted_updates[key] = value

            doc_ref.update(formatted_updates)
            logger.info(f"Updated deal document: {deal_id}")
            return True

        except Exception as e:
            logger.error(f"Firestore update error: {str(e)}")
            return False

    async def delete_deal(self, deal_id: str) -> bool:
        """Delete deal document"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(deal_id)
            doc_ref.delete()
            logger.info(f"Deleted deal document: {deal_id}")
            return True

        except Exception as e:
            logger.error(f"Firestore delete error: {str(e)}")
            return False

    async def list_deals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all deals with pagination"""
        try:
            docs = self.db.collection(self.collection_name).limit(limit).stream()

            deals = []
            for doc in docs:
                deal_data = doc.to_dict()
                deal_data['deal_id'] = doc.id
                deals.append(deal_data)

            return deals

        except Exception as e:
            logger.error(f"Firestore list error: {str(e)}")
            return []

    async def get_cached_deck(self, deck_hash: Optional[str]) -> Optional[Dict[str, Any]]:
        if not deck_hash:
            return None

        try:
            doc_ref = self.db.collection(self.cache_collection_name).document(deck_hash)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logger.error(f"Firestore cache fetch error: {str(e)}")
        return None

    async def set_cached_deck(self, deck_hash: Optional[str], payload: Dict[str, Any]) -> None:
        if not deck_hash:
            return

        try:
            doc_ref = self.db.collection(self.cache_collection_name).document(deck_hash)
            doc_ref.set(
                {
                    **payload,
                    "deck_hash": deck_hash,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            logger.info("Cached deck summary for hash %s", deck_hash)
        except Exception as e:
            logger.error(f"Firestore cache set error: {str(e)}")

    async def get_cached_memo(self, deck_hash: Optional[str], weight_signature: str) -> Optional[Dict[str, Any]]:
        if not deck_hash or not weight_signature:
            return None

        cache_doc = await self.get_cached_deck(deck_hash)
        if not cache_doc:
            return None

        return extract_cached_memo(cache_doc, weight_signature)

    async def cache_memo(
        self,
        deck_hash: Optional[str],
        weight_signature: str,
        memo_payload: Dict[str, Any],
        weightage: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not deck_hash or not weight_signature:
            return

        try:
            doc_ref = self.db.collection(self.cache_collection_name).document(deck_hash)
            doc_ref.set(
                {
                    "deck_hash": deck_hash,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                    "memos": {
                        weight_signature: {
                            "memo_json": memo_payload,
                            "weight_signature": weight_signature,
                            "weightage": weightage or {},
                        }
                    },
                },
                merge=True,
            )
            logger.info(
                "Cached memo for hash %s with signature %s",
                deck_hash,
                weight_signature,
            )
        except Exception as e:
            logger.error(f"Firestore memo cache set error: {str(e)}")

    # async def get_all_deals(self):
    #     deals_ref = self.db.collection(self.collection_name)
    #     snapshot = deals_ref.stream()
    #     all_deals = []
    #     async for doc in snapshot:
    #         all_deals.append(doc.to_dict())
    #     return all_deals