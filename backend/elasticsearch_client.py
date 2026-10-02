"""Project-scoped MR metadata retrieval, not repository-code RAG."""
import logging
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

es = Elasticsearch("http://localhost:9200", request_timeout=3, max_retries=0)
INDEX = "gitlab_merge_requests"


def identity(project_id, mr_iid):
    if not project_id:
        raise ValueError("Explicit project identity is required.")
    return f"{int(project_id)}:{int(mr_iid)}"


def index_merge_request(document):
    try:
        return es.index(index=INDEX, id=identity(document["project_id"], document["mr_id"]), document=document)
    except Exception:
        logging.warning("Elasticsearch indexing unavailable")
        return None


update_merge_request = index_merge_request


def search_merge_requests(query, project_id):
    if not project_id:
        raise ValueError("Explicit project identity is required.")
    try:
        response = es.search(index=INDEX, size=10, query={"bool": {
            "filter": [{"term": {"project_id": int(project_id)}}],
            "must": [{"multi_match": {"query": query, "fields": ["title", "description", "author"]}}]}})
        return [hit["_source"] for hit in response["hits"]["hits"]]
    except Exception:
        logging.warning("Elasticsearch unavailable; continuing without MR context")
        return []


def merge_request_exists(mr_id, project_id):
    try:
        return bool(es.exists(index=INDEX, id=identity(project_id, mr_id)))
    except Exception:
        return False


def get_merge_request_from_es(mr_id, project_id):
    try:
        return es.get(index=INDEX, id=identity(project_id, mr_id))["_source"]
    except Exception:
        return None


def bulk_index_merge_requests(documents):
    try:
        return bulk(es, [{"_index": INDEX, "_id": identity(d["project_id"], d["mr_id"]), "_source": d} for d in documents])
    except Exception:
        logging.warning("Elasticsearch synchronization unavailable")
        return None


def get_mr_context_for_suggestions(mr_iid, title, description="", *, project_id):
    return [mr for mr in search_merge_requests(f"{title} {description or ''}", project_id)
            if str(mr.get("mr_id")) != str(mr_iid)][:3]
