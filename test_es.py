from elasticsearch_client import es

response = es.search(
    index="gitlab_merge_requests",
    query={"match_all": {}},
    size=10
)

print(f"Found {response['hits']['total']['value']} documents\n")

for hit in response["hits"]["hits"]:
    print(hit["_source"])
    print("-" * 50)