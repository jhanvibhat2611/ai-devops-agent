from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

es = Elasticsearch("http://localhost:9200")

if es.ping():
    print("✅ Connected to Elasticsearch")
else:
    print("❌ Connection Failed")


# Store a merge request in Elasticsearch
def index_merge_request(document: dict):

    response = es.index(
        index="gitlab_merge_requests",
        id=document["mr_id"],
        document=document
    )

    return response

# Search merge requests in Elasticsearch
def search_merge_requests(query: str):

    response = es.search(
        index="gitlab_merge_requests",
        query={
            "multi_match": {
                "query": query,
                "fields": [
                    "title",
                    "description",
                    "author"
                ]
            }
        }
    )

    results = []

    for hit in response["hits"]["hits"]:
        results.append(hit["_source"])

    return results

# Check if a merge request already exists
def merge_request_exists(mr_id: int):

    return es.exists(
        index="gitlab_merge_requests",
        id=str(mr_id)
    )

# Get a merge request from Elasticsearch
def get_merge_request_from_es(mr_id: int):

    response = es.get(
        index="gitlab_merge_requests",
        id=str(mr_id)
    )

    return response["_source"]

# Update an existing merge request
def update_merge_request(document: dict):

    response = es.index(
        index="gitlab_merge_requests",
        id=str(document["mr_id"]),
        document=document
    )

    return response

def bulk_index_merge_requests(documents):

    def document_generator():

        for document in documents:

            yield {
                "_index": "gitlab_merge_requests",
                "_id": document["mr_id"],
                "_source": document
            }

    success, errors = bulk(
        client=es,
        actions=document_generator()
    )

    print(f"Successfully indexed {success} merge requests.")

    if errors:
        print(errors)

def get_mr_context_for_suggestions(
    mr_iid: int,
    mr_title: str = "",
    mr_description: str = ""
):

    query_parts = []

    if mr_title:
        query_parts.append(mr_title)

    if mr_description:
        query_parts.append(mr_description)

    query = " ".join(query_parts).strip()

    if not query:
        return []

    try:

        results = search_merge_requests(query)

        results = [
            mr
            for mr in results
            if str(mr.get("mr_id")) != str(mr_iid)
        ]

        return results[:3]

    except Exception as e:

        print(
            "⚠️ Elasticsearch context search failed:",
            e
        )

        return []
# sample_document = {
#     "mr_id": 2,
#     "title": "Implement Elasticsearch",
#     "author": "Jhanvi",
#     "status": "open"
# }
#
# response = index_merge_request(sample_document)

# print(response)