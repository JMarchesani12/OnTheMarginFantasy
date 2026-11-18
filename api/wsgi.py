"""Gunicorn callable; runtime construction belongs to the patched serving worker."""

class WorkerApplication:
    def __init__(self):
        self.application = None

    def initialize(self):
        if self.application is None:
            from runtime import create_web_app
            self.application = create_web_app(start_listener=False)
        return self.application

    def __call__(self, environ, start_response):
        if self.application is None:
            raise RuntimeError('Gunicorn worker runtime has not been initialized')
        return self.application(environ, start_response)


app = WorkerApplication()
