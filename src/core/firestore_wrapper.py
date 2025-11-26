from typing import Any, Optional, List, Union, Tuple
import logging
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.query import Query
from google.cloud.firestore_v1.base_query import BaseQuery
from google.cloud.firestore_v1.batch import WriteBatch
from google.cloud.firestore_v1.transaction import Transaction

from src.core.security import current_tenant, SecurityBreachError

logger = logging.getLogger(__name__)

def _validate_path(path: str) -> None:
    """
    Validates that the path starts with 'tenants/{tenant_id}/'.
    Raises SecurityBreachError if not.
    """
    tenant_id = current_tenant.get()
    if not tenant_id:
        raise SecurityBreachError("Access denied: No active tenant context.")
    
    expected_prefix = f"tenants/{tenant_id}/"
    clean_path = path.strip("/")
    
    if clean_path == f"tenants/{tenant_id}":
        return 
               
    if not clean_path.startswith(expected_prefix):
        msg = f"Security Alert: Attempted access to {clean_path} from tenant {tenant_id}"
        logger.error(msg)
        raise SecurityBreachError(msg)


class TenantQuery:
    def __init__(self, original_query: Query):
        self._query = original_query

    def stream(self, transaction=None):
        return self._query.stream(transaction=transaction)

    def get(self, transaction=None):
        return self._query.get(transaction=transaction)

    def where(self, field_path, op_string, value):
        return TenantQuery(self._query.where(field_path, op_string, value))
        
    def limit(self, count):
        return TenantQuery(self._query.limit(count))
        
    def order_by(self, field_path, direction=Query.ASCENDING):
        return TenantQuery(self._query.order_by(field_path, direction=direction))
    
    def offset(self, offset):
        return TenantQuery(self._query.offset(offset))

    def start_at(self, document_fields_or_snapshot):
        return TenantQuery(self._query.start_at(document_fields_or_snapshot))

    def start_after(self, document_fields_or_snapshot):
        return TenantQuery(self._query.start_after(document_fields_or_snapshot))

    def end_at(self, document_fields_or_snapshot):
        return TenantQuery(self._query.end_at(document_fields_or_snapshot))

    def end_before(self, document_fields_or_snapshot):
        return TenantQuery(self._query.end_before(document_fields_or_snapshot))


class TenantWriteBatch:
    def __init__(self, batch: WriteBatch):
        self._batch = batch

    def set(self, reference, document_data, merge=False):
        if hasattr(reference, '_ref'):
            reference = reference._ref
        
        if hasattr(reference, 'path'):
            _validate_path(reference.path)
        
        self._batch.set(reference, document_data, merge=merge)
        return self

    def create(self, reference, document_data):
        if hasattr(reference, '_ref'):
            reference = reference._ref
        
        if hasattr(reference, 'path'):
            _validate_path(reference.path)

        self._batch.create(reference, document_data)
        return self

    def update(self, reference, field_updates, option=None):
        if hasattr(reference, '_ref'):
            reference = reference._ref
        
        if hasattr(reference, 'path'):
            _validate_path(reference.path)

        self._batch.update(reference, field_updates, option=option)
        return self

    def delete(self, reference, option=None):
        if hasattr(reference, '_ref'):
            reference = reference._ref
        
        if hasattr(reference, 'path'):
            _validate_path(reference.path)

        self._batch.delete(reference, option=option)
        return self

    def commit(self):
        return self._batch.commit()


class TenantTransaction(TenantWriteBatch):
    def __init__(self, transaction: Transaction):
        self._transaction = transaction
        self._batch = transaction 

    def get(self, reference):
        if hasattr(reference, '_ref'):
            reference = reference._ref
        else:
             if hasattr(reference, 'path'):
                 _validate_path(reference.path)
        return self._transaction.get(reference)


class TenantDocumentReference:
    def __init__(self, original_ref: DocumentReference):
        self._ref = original_ref

    @property
    def id(self):
        return self._ref.id
        
    @property
    def path(self):
        return self._ref.path

    @property
    def parent(self):
        parent_ref = self._ref.parent
        try:
            _validate_path(parent_ref.path)
        except SecurityBreachError:
             msg = f"Traversal attempt denied: Parent {parent_ref.path} is outside tenant scope."
             logger.error(msg)
             raise SecurityBreachError(msg)
             
        return TenantCollectionReference(parent_ref)

    def collection(self, collection_id: str):
        full_path = f"{self._ref.path}/{collection_id}"
        _validate_path(full_path)
        return TenantCollectionReference(self._ref.collection(collection_id))

    def get(self, field_paths=None, transaction=None, retry=None, timeout=None):
        return self._ref.get(field_paths=field_paths, transaction=transaction, retry=retry, timeout=timeout)
        
    def set(self, document_data, merge=False, transaction=None):
        return self._ref.set(document_data, merge=merge, transaction=transaction)
        
    def update(self, field_updates, option=None, transaction=None):
        return self._ref.update(field_updates, option=option, transaction=transaction)
        
    def delete(self, option=None, transaction=None):
        return self._ref.delete(option=option, transaction=transaction)


class TenantCollectionReference:
    def __init__(self, original_ref: CollectionReference):
        self._ref = original_ref

    @property
    def id(self):
        return self._ref.id
        
    @property
    def path(self):
        return self._ref.path

    @property
    def parent(self):
        parent_ref = self._ref.parent
        if parent_ref is None: 
             msg = "Traversal attempt denied: Cannot go above root."
             logger.error(msg)
             raise SecurityBreachError(msg)
             
        try:
            _validate_path(parent_ref.path)
        except SecurityBreachError:
             msg = f"Traversal attempt denied: Parent {parent_ref.path} is outside tenant scope."
             logger.error(msg)
             raise SecurityBreachError(msg)
             
        return TenantDocumentReference(parent_ref)

    def document(self, document_id: Optional[str] = None):
        if document_id:
            full_path = f"{self._ref.path}/{document_id}"
            _validate_path(full_path)
            return TenantDocumentReference(self._ref.document(document_id))
        else:
            doc_ref = self._ref.document()
            _validate_path(doc_ref.path)
            return TenantDocumentReference(doc_ref)

    # Query methods delegated to TenantQuery
    def where(self, field_path, op_string, value):
        return TenantQuery(self._ref.where(field_path, op_string, value))

    def limit(self, count):
        return TenantQuery(self._ref.limit(count))
        
    def order_by(self, field_path, direction=Query.ASCENDING):
        return TenantQuery(self._ref.order_by(field_path, direction=direction))

    def offset(self, offset):
        return TenantQuery(self._ref.offset(offset))

    def start_at(self, document_fields_or_snapshot):
        return TenantQuery(self._ref.start_at(document_fields_or_snapshot))

    def start_after(self, document_fields_or_snapshot):
        return TenantQuery(self._ref.start_after(document_fields_or_snapshot))

    def end_at(self, document_fields_or_snapshot):
        return TenantQuery(self._ref.end_at(document_fields_or_snapshot))

    def end_before(self, document_fields_or_snapshot):
        return TenantQuery(self._ref.end_before(document_fields_or_snapshot))

    def stream(self, transaction=None, retry=None, timeout=None):
        return self._ref.stream(transaction=transaction, retry=retry, timeout=timeout)
        
    def get(self, transaction=None, retry=None, timeout=None):
        return self._ref.get(transaction=transaction, retry=retry, timeout=timeout)
        
    def add(self, document_data, document_id=None, retry=None, timeout=None):
        if document_id is None:
            doc_ref = self._ref.document() 
        else:
            doc_ref = self._ref.document(document_id)
            
        _validate_path(doc_ref.path)
        ts = doc_ref.create(document_data, retry=retry, timeout=timeout) 
        return ts, TenantDocumentReference(doc_ref)


class TenantTransactionContextManager:
    def __init__(self, real_transaction):
        self._real_transaction = real_transaction
        
    def __enter__(self):
        real_tx = self._real_transaction.__enter__()
        return TenantTransaction(real_tx)
        
    def __exit__(self, exc_type, exc_value, traceback):
        return self._real_transaction.__exit__(exc_type, exc_value, traceback)


class TenantFirestore:
    def __init__(self, project=None, credentials=None, database=None, client=None):
        if client:
            self._client = client
        else:
            self._client = Client(project=project, credentials=credentials, database=database)

    def collection(self, path: str) -> TenantCollectionReference:
        _validate_path(path)
        return TenantCollectionReference(self._client.collection(path))

    def document(self, path: str) -> TenantDocumentReference:
        _validate_path(path)
        return TenantDocumentReference(self._client.document(path))

    def collection_group(self, collection_id: str):
        msg = "Security Alert: collection_group queries are disabled for strict tenant isolation."
        logger.error(msg)
        raise SecurityBreachError(msg)

    def get_all(self, references: List[Any], field_paths=None, transaction=None, retry=None, timeout=None):
        unwrapped_refs = []
        for ref in references:
            path = getattr(ref, 'path', None)
            if not path and hasattr(ref, '_ref'): 
                 path = ref._ref.path
            
            if path:
                _validate_path(path)
            else:
                 raise SecurityBreachError("Cannot validate reference in get_all")
            
            if hasattr(ref, '_ref'):
                unwrapped_refs.append(ref._ref)
            else:
                unwrapped_refs.append(ref)
                
        return self._client.get_all(unwrapped_refs, field_paths=field_paths, transaction=transaction, retry=retry, timeout=timeout)

    def batch(self):
        return TenantWriteBatch(self._client.batch())

    def transaction(self, **kwargs):
        return TenantTransactionContextManager(self._client.transaction(**kwargs))
