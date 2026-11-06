"""Worker-local shutdown; never starts or stops resources in the master."""
def worker_exit(server, worker):
    from runtime import stop_web_listener
    stop_web_listener(getattr(worker, 'wsgi', None))
