def remove_subscription_delete(endpoints):
    # your modifications to the list of operations that are exposed in the schema
    to_remove = []
    for (path, path_regex, method, callback) in endpoints:
        if (path == r"/api/subscriptions/" and method == "POST") or (
            path == r"/api/subscriptions/{subscription_id}/"
        ):
            to_remove.append((path, path_regex, method, callback))
    for item in to_remove:
        endpoints.remove(item)
    return endpoints
