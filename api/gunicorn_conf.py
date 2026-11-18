"""Worker-local shutdown; never starts or stops resources in the master."""
def post_worker_init(worker):
    from runtime import start_web_listener_for_app
    start_web_listener_for_app(worker.wsgi.initialize())


def worker_exit(server, worker):
    from runtime import stop_web_listener
    app = getattr(worker, 'wsgi', None)
    stop_web_listener(getattr(app, 'application', app))
